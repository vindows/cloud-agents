from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher

from app.classifier.base import ClassifierBackend
from app.config import Settings, get_settings
from app.models.jev import ChoiceQuestion, NoulQuestion, ScoreQuestion
from app.models.tickets import Ticket, TicketIn
from app.models.triage import (
    ArchiveLeverConfig,
    PipelineResult,
    StepResult,
    TriageRequest,
)
from app.triage.archive_policy import evaluate_archive

CATEGORY_GROUPS = {
    "access": "IT Access & Identity",
    "hardware": "Endpoint Hardware",
    "network": "Network Operations",
    "applications": "Enterprise Applications",
}

# Demo agent roster snippets — full roster lives in data/agents.json when present
DEMO_AGENTS = {
    "access": ["a.chen", "m.patel", "j.okonkwo"],
    "hardware": ["r.nguyen", "s.alvarez", "k.brown"],
    "network": ["t.singh", "l.martin", "p.garcia"],
    "applications": ["e.wilson", "c.lee", "d.moore"],
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ticket_text(ticket: TicketIn | Ticket) -> str:
    return f"{ticket.short_description}\n{ticket.description}".strip()


def _ensure_ticket(ticket_in: TicketIn) -> Ticket:
    now = _utcnow()
    data = ticket_in.model_dump()
    data["number"] = data.get("number") or f"INC{uuid.uuid4().hex[:7].upper()}"
    data["sys_id"] = data.get("sys_id") or str(uuid.uuid4())
    data["opened_at"] = data.get("opened_at") or now
    return Ticket.model_validate(data)


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


class TriageEngine:
    def __init__(
        self,
        classifier: ClassifierBackend,
        settings: Settings | None = None,
    ) -> None:
        self.classifier = classifier
        self.settings = settings or get_settings()

    async def run(self, request: TriageRequest) -> PipelineResult:
        ticket = _ensure_ticket(request.ticket)
        levers = request.archive or ArchiveLeverConfig(
            mode=self.settings.archive_mode,
            age_years=self.settings.archive_age_years,
            inactive_days=self.settings.archive_inactive_days,
        )
        open_tickets = request.existing_open or []
        steps: list[StepResult] = []

        # 1) Intake
        steps.append(
            await self._step_intake(ticket)
        )

        # 2) Classify
        classify_step, category, cat_conf = await self._step_classify(ticket)
        steps.append(classify_step)
        ticket.category = category  # type: ignore[assignment]

        # 3) Dedupe
        dedupe_step, is_dup, dup_of, dup_conf = await self._step_dedupe(
            ticket, open_tickets
        )
        steps.append(dedupe_step)
        if is_dup:
            ticket.triage_status = "duplicate"
            ticket.duplicate_of = dup_of
            ticket.parent = dup_of
            return PipelineResult(
                ticket=ticket,
                steps=steps,
                outcome="duplicate",
                archive=None,
                classifier_backend=self.classifier.name,
            )

        # 4) Priority
        priority_step, priority, urg_conf = await self._step_priority(ticket)
        steps.append(priority_step)
        ticket.priority = priority  # type: ignore[assignment]

        # 5) Archive candidate check (before route — stale backlog may skip routing)
        archive = evaluate_archive(ticket, levers)
        archive_step = StepResult(
            step="archive",
            action=(
                "archived"
                if archive.auto_applied
                else ("candidate" if archive.candidate else "skip")
            ),
            reason=archive.reason,
            confidence=archive.confidence,
            needs_human=archive.needs_human,
            detail=archive.model_dump(),
            finished_at=_utcnow(),
        )
        steps.append(archive_step)

        if archive.auto_applied:
            ticket.triage_status = "archived"
            ticket.state = "archived"
            return PipelineResult(
                ticket=ticket,
                steps=steps,
                outcome="archived",
                archive=archive,
                classifier_backend=self.classifier.name,
            )

        if archive.candidate and archive.needs_human:
            ticket.triage_status = "archive_candidate"
            return PipelineResult(
                ticket=ticket,
                steps=steps,
                outcome="archive_candidate",
                archive=archive,
                classifier_backend=self.classifier.name,
            )

        # 6) Route
        route_step = await self._step_route(ticket, category, cat_conf, urg_conf)
        steps.append(route_step)
        ticket.assignment_group = route_step.detail.get("assignment_group")
        ticket.assigned_to = route_step.detail.get("assigned_to")
        ticket.route_group = ticket.assignment_group
        ticket.route_agent = ticket.assigned_to

        low_conf = min(cat_conf, urg_conf) < self.settings.confidence_threshold
        if low_conf or route_step.needs_human:
            ticket.triage_status = "needs_human"
            outcome = "needs_human"
        else:
            ticket.triage_status = "routed"
            ticket.state = "open"
            outcome = "routed"

        return PipelineResult(
            ticket=ticket,
            steps=steps,
            outcome=outcome,  # type: ignore[arg-type]
            archive=archive if archive.candidate else None,
            classifier_backend=self.classifier.name,
        )

    async def _step_intake(self, ticket: Ticket) -> StepResult:
        return StepResult(
            step="intake",
            action="accepted",
            reason=(
                f"Accepted ServiceNow-shaped ticket {ticket.number} "
                f"(sys_id={ticket.sys_id[:8]}…)."
            ),
            confidence=1.0,
            detail={
                "number": ticket.number,
                "sys_id": ticket.sys_id,
                "opened_at": ticket.opened_at.isoformat(),
            },
            finished_at=_utcnow(),
        )

    async def _step_classify(
        self, ticket: Ticket
    ) -> tuple[StepResult, str, float]:
        started = _utcnow()
        text = _ticket_text(ticket)
        resp = await self.classifier.answer_questions(
            state=text,
            questions={
                "category": ChoiceQuestion(
                    type="choice",
                    instructions="Which IT category does this ticket belong to?",
                    criteria={
                        "access": "Identity, passwords, MFA, permissions, badge access",
                        "hardware": "Laptops, monitors, peripherals, docking, printers",
                        "network": "WiFi, VPN, DNS, firewall, connectivity, outages",
                        "applications": "Business apps, Outlook, Teams, SaaS, installs",
                    },
                )
            },
        )
        ans = resp.answers["category"]
        choice = ans["choice"]
        conf = float(ans["confidence"])
        probs = ans["probabilities"]
        reason = (
            f"Classified as '{choice}' via System One choice "
            f"(backend={self.classifier.name}, confidence={conf:.2f}). "
            f"Top probs: "
            + ", ".join(
                f"{k}={v:.2f}"
                for k, v in sorted(probs.items(), key=lambda x: -x[1])[:3]
            )
            + "."
        )
        needs_human = conf < self.settings.confidence_threshold
        finished = _utcnow()
        step = StepResult(
            step="classify",
            action=choice,
            reason=reason,
            confidence=conf,
            needs_human=needs_human,
            detail={"probabilities": probs, "model": resp.model},
            started_at=started,
            finished_at=finished,
            duration_ms=(finished - started).total_seconds() * 1000,
        )
        return step, choice, conf

    async def _step_dedupe(
        self, ticket: Ticket, open_tickets: list[Ticket]
    ) -> tuple[StepResult, bool, str | None, float]:
        started = _utcnow()
        text = _ticket_text(ticket)

        best: tuple[float, Ticket] | None = None
        for other in open_tickets:
            if other.sys_id == ticket.sys_id or other.number == ticket.number:
                continue
            if other.state in ("closed", "resolved", "archived"):
                continue
            score = _similarity(text, _ticket_text(other))
            # Boost if same caller and similar short description
            if (
                ticket.caller_id
                and other.caller_id
                and ticket.caller_id == other.caller_id
            ):
                score = min(1.0, score + 0.08)
            if best is None or score > best[0]:
                best = (score, other)

        # Also ask System One noul for duplicate signal on the text itself
        noul_resp = await self.classifier.answer_questions(
            state=text,
            questions={
                "is_duplicate_language": NoulQuestion(
                    type="noul",
                    instructions="Does this ticket describe a duplicate of an already-reported issue?",
                )
            },
        )
        lang_p = float(noul_resp.answers["is_duplicate_language"]["noul"])

        sim = best[0] if best else 0.0
        # Combined: high text similarity OR strong duplicate language + moderate sim
        is_dup = sim >= 0.72 or (sim >= 0.55 and lang_p >= 0.7)
        conf = max(sim, lang_p * sim) if best else 1.0 - lang_p
        dup_of = best[1].number if is_dup and best else None

        if is_dup and best:
            reason = (
                f"Likely duplicate of {best[1].number} "
                f"(text similarity={sim:.2f}, duplicate-language noul={lang_p:.2f}). "
                f"Linking as child; skip re-route."
            )
            action = "duplicate"
        elif best:
            reason = (
                f"No duplicate above threshold. Nearest open ticket "
                f"{best[1].number} similarity={sim:.2f} "
                f"(noul={lang_p:.2f}). Proceeding."
            )
            action = "unique"
            conf = max(0.55, 1.0 - sim)
        else:
            reason = "No open tickets to compare — treating as unique."
            action = "unique"
            conf = 0.9

        finished = _utcnow()
        step = StepResult(
            step="dedupe",
            action=action,
            reason=reason,
            confidence=float(conf),
            detail={
                "similarity": sim,
                "duplicate_language_noul": lang_p,
                "nearest": best[1].number if best else None,
                "duplicate_of": dup_of,
            },
            started_at=started,
            finished_at=finished,
            duration_ms=(finished - started).total_seconds() * 1000,
        )
        return step, is_dup, dup_of, float(conf)

    async def _step_priority(
        self, ticket: Ticket
    ) -> tuple[StepResult, str, float]:
        started = _utcnow()
        text = _ticket_text(ticket)
        resp = await self.classifier.answer_questions(
            state=text,
            questions={
                "urgency": ScoreQuestion(
                    type="score",
                    instructions="How urgent is this IT ticket?",
                    criteria=[
                        "Can wait / low impact",
                        "Needs attention this week",
                        "Needs attention today / outage or blocked work",
                    ],
                )
            },
        )
        ans = resp.answers["urgency"]
        score = float(ans["score"])
        conf = float(ans["confidence"])
        # Map expected score 0..2 → ServiceNow priority 5..1 (lower number = higher urgency)
        if score >= 1.6:
            priority = "1"
        elif score >= 1.1:
            priority = "2"
        elif score >= 0.7:
            priority = "3"
        elif score >= 0.35:
            priority = "4"
        else:
            priority = "5"

        legend = ans.get("legend", {})
        reason = (
            f"Urgency score={score:.2f} (legend={legend}) → priority P{priority}. "
            f"Confidence={conf:.2f}."
        )
        finished = _utcnow()
        step = StepResult(
            step="priority",
            action=f"P{priority}",
            reason=reason,
            confidence=conf,
            needs_human=conf < self.settings.confidence_threshold,
            detail={
                "urgency_score": score,
                "probabilities": ans.get("probabilities"),
                "priority": priority,
            },
            started_at=started,
            finished_at=finished,
            duration_ms=(finished - started).total_seconds() * 1000,
        )
        return step, priority, conf

    async def _step_route(
        self,
        ticket: Ticket,
        category: str,
        cat_conf: float,
        urg_conf: float,
    ) -> StepResult:
        started = _utcnow()
        group = CATEGORY_GROUPS.get(category, "IT Service Desk")
        agents = DEMO_AGENTS.get(category, ["queue.unassigned"])
        # Stable pick from ticket number hash for demo reproducibility
        digits = int(re.sub(r"\D", "", ticket.number) or "0")
        agent = agents[digits % len(agents)]
        conf = min(cat_conf, urg_conf)
        reason = (
            f"Routed to assignment group '{group}' → agent '{agent}' "
            f"because category={category} (classify conf={cat_conf:.2f}) "
            f"and priority=P{ticket.priority}."
        )
        finished = _utcnow()
        return StepResult(
            step="route",
            action="assigned",
            reason=reason,
            confidence=conf,
            needs_human=conf < self.settings.confidence_threshold,
            detail={
                "assignment_group": group,
                "assigned_to": agent,
                "category": category,
                "priority": ticket.priority,
            },
            started_at=started,
            finished_at=finished,
            duration_ms=(finished - started).total_seconds() * 1000,
        )

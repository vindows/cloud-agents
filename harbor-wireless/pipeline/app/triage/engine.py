from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher

from app.classifier.base import ClassifierBackend
from app.config import Settings, get_settings
from app.models.jev import ChoiceQuestion, NoulQuestion, ScoreQuestion
from app.models.tickets import (
    Agent,
    PersonRef,
    Ticket,
    TicketIn,
    caller_key,
    is_open_state,
    priority_label,
)
from app.models.triage import (
    ArchiveLeverConfig,
    PipelineResult,
    StepResult,
    TriageRequest,
)
from app.triage.archive_policy import evaluate_archive

# Match harbor-wireless/data assignment groups
CATEGORY_GROUPS = {
    "access": "HW-Access-Identity",
    "hardware": "HW-Endpoint-Hardware",
    "network": "HW-Network-Ops",
    "applications": "HW-Enterprise-Apps",
}

# Fallback when agents.json not loaded
DEMO_AGENTS = {
    "access": ["dperez001", "mchen002", "jokonkwo003"],
    "hardware": ["rnguyen004", "salvarez005", "kbrown006"],
    "network": ["tsingh007", "lmartin008", "pgarcia009"],
    "applications": ["ewilson010", "clee011", "dmoore012"],
}

URGENCY_FROM_SCORE = (
    (1.6, "critical"),
    (1.1, "high"),
    (0.55, "medium"),
    (0.0, "low"),
)

PRIORITY_FROM_URGENCY = {
    "critical": "1",
    "high": "2",
    "medium": "3",
    "low": "4",
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
    if isinstance(data.get("caller_id"), dict):
        data["caller_id"] = PersonRef.model_validate(data["caller_id"])
    if isinstance(data.get("assigned_to"), dict):
        data["assigned_to"] = PersonRef.model_validate(data["assigned_to"])
    return Ticket.model_validate(data)


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _urgency_from_score(score: float) -> str:
    for threshold, label in URGENCY_FROM_SCORE:
        if score >= threshold:
            return label
    return "low"


class TriageEngine:
    def __init__(
        self,
        classifier: ClassifierBackend,
        settings: Settings | None = None,
        agents_by_category: dict[str, list[Agent]] | None = None,
    ) -> None:
        self.classifier = classifier
        self.settings = settings or get_settings()
        self.agents_by_category = agents_by_category or {}

    async def run(self, request: TriageRequest) -> PipelineResult:
        ticket = _ensure_ticket(request.ticket)
        levers = request.archive or ArchiveLeverConfig(
            mode=self.settings.archive_mode,
            age_years=self.settings.archive_age_years,
            inactive_days=self.settings.archive_inactive_days,
        )
        open_tickets = [
            t
            for t in (request.existing_open or [])
            if is_open_state(t.state)
        ]
        steps: list[StepResult] = []

        steps.append(await self._step_intake(ticket))

        classify_step, category, cat_conf = await self._step_classify(ticket)
        steps.append(classify_step)
        ticket.category = category  # type: ignore[assignment]

        dedupe_step, is_dup, dup_of, _dup_conf = await self._step_dedupe(
            ticket, open_tickets
        )
        steps.append(dedupe_step)
        if is_dup:
            ticket.triage_status = "duplicate"
            ticket.is_duplicate = True
            # parent = original ticket number (data contract)
            ticket.parent = dup_of
            ticket.duplicate_of = dup_of
            return PipelineResult(
                ticket=ticket,
                steps=steps,
                outcome="duplicate",
                archive=None,
                classifier_backend=self.classifier.name,
            )

        priority_step, priority, urgency, urg_conf = await self._step_priority(ticket)
        steps.append(priority_step)
        ticket.priority = priority
        ticket.urgency = urgency

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
            ticket.state = "Closed"
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

        route_step = await self._step_route(ticket, category, cat_conf, urg_conf)
        steps.append(route_step)
        ticket.assignment_group = route_step.detail.get("assignment_group")
        assigned = route_step.detail.get("assigned_to")
        if isinstance(assigned, dict):
            ticket.assigned_to = PersonRef.model_validate(assigned)
            ticket.route_agent = assigned.get("user_name")
        else:
            ticket.assigned_to = assigned
            ticket.route_agent = assigned if isinstance(assigned, str) else None
        ticket.route_group = ticket.assignment_group

        low_conf = min(cat_conf, urg_conf) < self.settings.confidence_threshold
        if low_conf or route_step.needs_human:
            ticket.triage_status = "needs_human"
            outcome = "needs_human"
        else:
            ticket.triage_status = "routed"
            ticket.state = "In Progress"
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
                "parent": ticket.parent,
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
        ticket_caller = caller_key(ticket.caller_id)

        best: tuple[float, Ticket] | None = None
        for other in open_tickets:
            if other.sys_id == ticket.sys_id or other.number == ticket.number:
                continue
            if not is_open_state(other.state):
                continue
            # Prefer matching against non-duplicate originals
            if other.is_duplicate and other.parent:
                continue
            score = _similarity(text, _ticket_text(other))
            other_caller = caller_key(other.caller_id)
            if ticket_caller and other_caller and ticket_caller == other_caller:
                score = min(1.0, score + 0.08)
            if best is None or score > best[0]:
                best = (score, other)

        noul_resp = await self.classifier.answer_questions(
            state=text,
            questions={
                "is_duplicate_language": NoulQuestion(
                    type="noul",
                    instructions=(
                        "Does this ticket describe a duplicate of an "
                        "already-reported issue?"
                    ),
                )
            },
        )
        lang_p = float(noul_resp.answers["is_duplicate_language"]["noul"])

        sim = best[0] if best else 0.0
        is_dup = sim >= 0.72 or (sim >= 0.55 and lang_p >= 0.7)
        conf = max(sim, lang_p * sim) if best else 1.0 - lang_p
        # parent / duplicate_of = original ticket *number*
        dup_of = best[1].number if is_dup and best else None

        if is_dup and best:
            reason = (
                f"Likely duplicate of {best[1].number} "
                f"(text similarity={sim:.2f}, duplicate-language noul={lang_p:.2f}). "
                f"Setting parent={best[1].number}; skip re-route."
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
                "parent": dup_of,
            },
            started_at=started,
            finished_at=finished,
            duration_ms=(finished - started).total_seconds() * 1000,
        )
        return step, is_dup, dup_of, float(conf)

    async def _step_priority(
        self, ticket: Ticket
    ) -> tuple[StepResult, str, str, float]:
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
        urgency = _urgency_from_score(score)
        code = PRIORITY_FROM_URGENCY[urgency]
        priority = priority_label(code)

        legend = ans.get("legend", {})
        reason = (
            f"Urgency score={score:.2f} → urgency={urgency}, priority={priority} "
            f"(legend={legend}). Confidence={conf:.2f}."
        )
        finished = _utcnow()
        step = StepResult(
            step="priority",
            action=priority,
            reason=reason,
            confidence=conf,
            needs_human=conf < self.settings.confidence_threshold,
            detail={
                "urgency_score": score,
                "urgency": urgency,
                "probabilities": ans.get("probabilities"),
                "priority": priority,
            },
            started_at=started,
            finished_at=finished,
            duration_ms=(finished - started).total_seconds() * 1000,
        )
        return step, priority, urgency, conf

    async def _step_route(
        self,
        ticket: Ticket,
        category: str,
        cat_conf: float,
        urg_conf: float,
    ) -> StepResult:
        started = _utcnow()
        group = CATEGORY_GROUPS.get(category, "HW-Access-Identity")
        roster = [a for a in self.agents_by_category.get(category, []) if a.active]
        digits = int(re.sub(r"\D", "", ticket.number) or "0")
        if roster:
            agent = roster[digits % len(roster)]
            assigned_payload = {
                "sys_id": agent.sys_id,
                "name": agent.name,
                "user_name": agent.user_name,
            }
            agent_label = agent.user_name
        else:
            fallback = DEMO_AGENTS.get(category, ["queue.unassigned"])
            agent_label = fallback[digits % len(fallback)]
            assigned_payload = agent_label

        conf = min(cat_conf, urg_conf)
        reason = (
            f"Routed to assignment group '{group}' → agent '{agent_label}' "
            f"because category={category} (classify conf={cat_conf:.2f}) "
            f"and priority={ticket.priority}."
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
                "assigned_to": assigned_payload,
                "category": category,
                "priority": ticket.priority,
                "roster_size": len(roster),
            },
            started_at=started,
            finished_at=finished,
            duration_ms=(finished - started).total_seconds() * 1000,
        )

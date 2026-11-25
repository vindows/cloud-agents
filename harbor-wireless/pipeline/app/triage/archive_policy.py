from __future__ import annotations

from datetime import datetime, timezone

from app.models.tickets import Ticket
from app.models.triage import ArchiveDecision, ArchiveLeverConfig


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def evaluate_archive(
    ticket: Ticket,
    levers: ArchiveLeverConfig,
    now: datetime | None = None,
) -> ArchiveDecision:
    """Apply archive levers: auto | human | hybrid.

    auto   — archive when age >= age_years
    human  — never auto-apply; always surface as candidate for approval
    hybrid — auto only when age >= age_years AND requester inactive
    """
    now = _aware(now or _utcnow())
    opened = _aware(ticket.opened_at)
    age_years = (now - opened).total_seconds() / (365.25 * 24 * 3600)
    age_ok = age_years >= levers.age_years

    last_active = ticket.requester_last_active_at
    if last_active is None:
        # Unknown activity: treat as inactive for hybrid when ticket itself is stale
        inactive = age_ok
        inactive_note = "requester activity unknown; treating as inactive because ticket is stale"
    else:
        last_active = _aware(last_active)
        inactive_days = (now - last_active).total_seconds() / 86400.0
        inactive = inactive_days >= levers.inactive_days
        inactive_note = (
            f"requester last active {inactive_days:.0f}d ago "
            f"(threshold {levers.inactive_days}d)"
        )

    candidate = age_ok
    conf = min(0.95, 0.55 + 0.1 * max(0.0, age_years - levers.age_years))

    if not candidate:
        return ArchiveDecision(
            candidate=False,
            auto_applied=False,
            mode=levers.mode,
            reason=(
                f"Ticket age {age_years:.1f}y is below archive threshold "
                f"of {levers.age_years}y — keep in backlog."
            ),
            confidence=0.7,
            needs_human=False,
        )

    if levers.mode == "human":
        return ArchiveDecision(
            candidate=True,
            auto_applied=False,
            mode=levers.mode,
            reason=(
                f"Archive candidate (age {age_years:.1f}y ≥ {levers.age_years}y) "
                f"but mode=human — requires explicit approval. {inactive_note}."
            ),
            confidence=conf,
            needs_human=True,
        )

    if levers.mode == "auto":
        return ArchiveDecision(
            candidate=True,
            auto_applied=True,
            mode=levers.mode,
            reason=(
                f"Auto-archived: age {age_years:.1f}y ≥ {levers.age_years}y "
                f"(mode=auto). {inactive_note}."
            ),
            confidence=conf,
            needs_human=False,
        )

    # hybrid
    if inactive:
        return ArchiveDecision(
            candidate=True,
            auto_applied=True,
            mode=levers.mode,
            reason=(
                f"Hybrid auto-archive: age {age_years:.1f}y ≥ {levers.age_years}y "
                f"AND {inactive_note}."
            ),
            confidence=conf,
            needs_human=False,
        )

    return ArchiveDecision(
        candidate=True,
        auto_applied=False,
        mode=levers.mode,
        reason=(
            f"Hybrid hold: age {age_years:.1f}y meets threshold but requester "
            f"still active ({inactive_note}) — send to human review."
        ),
        confidence=conf,
        needs_human=True,
    )

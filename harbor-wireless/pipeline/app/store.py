"""In-memory ticket + metrics store for the demo pipeline."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from app.config import get_settings
from app.models.tickets import Ticket
from app.models.triage import ArchiveLeverConfig, PipelineResult


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DemoStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self.tickets: dict[str, Ticket] = {}
        self.results: list[PipelineResult] = []
        self.archive_levers = ArchiveLeverConfig(
            mode=get_settings().archive_mode,
            age_years=get_settings().archive_age_years,
            inactive_days=get_settings().archive_inactive_days,
        )
        self._outcome_counts: Counter[str] = Counter()
        self._category_counts: Counter[str] = Counter()
        self._step_ms: dict[str, list[float]] = defaultdict(list)

    def load_tickets_file(self, path: Path) -> int:
        if not path.exists():
            return 0
        data = json.loads(path.read_text())
        items = data if isinstance(data, list) else data.get("tickets", [])
        loaded = 0
        with self._lock:
            for raw in items:
                try:
                    t = Ticket.model_validate(raw)
                except Exception:
                    continue
                self.tickets[t.number] = t
                loaded += 1
        return loaded

    def open_tickets(self) -> list[Ticket]:
        with self._lock:
            return [
                t
                for t in self.tickets.values()
                if t.state not in ("closed", "resolved", "archived")
                and t.triage_status not in ("archived", "duplicate")
            ]

    def upsert_ticket(self, ticket: Ticket) -> None:
        with self._lock:
            self.tickets[ticket.number] = ticket

    def record_result(self, result: PipelineResult) -> None:
        with self._lock:
            self.results.append(result)
            self.tickets[result.ticket.number] = result.ticket
            self._outcome_counts[result.outcome] += 1
            if result.ticket.category:
                self._category_counts[result.ticket.category] += 1
            for step in result.steps:
                if step.duration_ms is not None:
                    self._step_ms[step.step].append(step.duration_ms)

    def set_archive_levers(self, levers: ArchiveLeverConfig) -> ArchiveLeverConfig:
        with self._lock:
            self.archive_levers = levers
            return self.archive_levers

    def get_archive_levers(self) -> ArchiveLeverConfig:
        with self._lock:
            return self.archive_levers.model_copy()

    def metrics(self) -> dict[str, Any]:
        with self._lock:
            handled = len(self.results)
            outcomes = dict(self._outcome_counts)
            deduped = outcomes.get("duplicate", 0)
            archived = outcomes.get("archived", 0) + outcomes.get(
                "archive_candidate", 0
            )
            routed = outcomes.get("routed", 0)
            needs_human = outcomes.get("needs_human", 0)
            avg_step = {
                step: (sum(vals) / len(vals) if vals else 0.0)
                for step, vals in self._step_ms.items()
            }
            return {
                "handled": handled,
                "open_tickets": len(
                    [
                        t
                        for t in self.tickets.values()
                        if t.state not in ("closed", "resolved", "archived")
                    ]
                ),
                "outcomes": outcomes,
                "by_category": dict(self._category_counts),
                "dedupe_rate": (deduped / handled) if handled else 0.0,
                "archive_rate": (archived / handled) if handled else 0.0,
                "route_rate": (routed / handled) if handled else 0.0,
                "human_fallback_rate": (needs_human / handled) if handled else 0.0,
                "avg_step_ms": avg_step,
                "archive_levers": self.archive_levers.model_dump(),
                "classifier_backend": get_settings().classifier_backend,
                "as_of": _utcnow().isoformat(),
            }


store = DemoStore()

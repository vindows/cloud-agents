"""In-memory ticket + agent + metrics store for the demo pipeline."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from app.config import get_settings
from app.models.tickets import (
    Agent,
    GoldenLabel,
    Ticket,
    is_open_state,
)
from app.models.triage import ArchiveLeverConfig, PipelineResult
from app.normalize import coerce_ticket_dict


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def resolve_data_dir(configured: str | None = None) -> Path:
    settings_dir = configured or get_settings().data_dir
    path = Path(settings_dir)
    if path.is_absolute() and path.exists():
        return path
    # harbor-wireless/pipeline/app/store.py → harbor-wireless/data
    sibling = Path(__file__).resolve().parents[2] / "data"
    if sibling.exists():
        return sibling
    return path


class DemoStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self.tickets: dict[str, Ticket] = {}
        self.agents: list[Agent] = []
        self.agents_by_category: dict[str, list[Agent]] = defaultdict(list)
        self.golden: list[GoldenLabel] = []
        self.results: list[PipelineResult] = []
        self.archive_levers = ArchiveLeverConfig(
            mode=get_settings().archive_mode,
            age_years=get_settings().archive_age_years,
            inactive_days=get_settings().archive_inactive_days,
        )
        self._outcome_counts: Counter[str] = Counter()
        self._category_counts: Counter[str] = Counter()
        self._step_ms: dict[str, list[float]] = defaultdict(list)
        self.tickets_loaded = 0
        self.agents_loaded = 0
        self.golden_loaded = 0

    def load_data_dir(self, data_dir: Path) -> dict[str, int]:
        return {
            "tickets": self.load_tickets_file(data_dir / "tickets.json"),
            "agents": self.load_agents_file(data_dir / "agents.json"),
            "golden": self.load_golden_file(data_dir / "golden-set.json"),
        }

    def load_tickets_file(self, path: Path) -> int:
        if not path.exists():
            return 0
        data = json.loads(path.read_text())
        items = data if isinstance(data, list) else data.get("tickets", [])
        loaded = 0
        skipped = 0
        with self._lock:
            for raw in items:
                try:
                    t = Ticket.model_validate(coerce_ticket_dict(raw))
                except Exception:
                    skipped += 1
                    continue
                # Preserve dataset duplicate link: parent is ticket number
                if t.parent and t.is_duplicate:
                    t.duplicate_of = t.parent
                self.tickets[t.number] = t
                loaded += 1
            self.tickets_loaded = loaded
        if skipped:
            # Keep quiet in API; surfaced via /health detail if needed
            pass
        return loaded

    def load_agents_file(self, path: Path) -> int:
        if not path.exists():
            return 0
        data = json.loads(path.read_text())
        items = data if isinstance(data, list) else data.get("agents", [])
        loaded = 0
        with self._lock:
            self.agents.clear()
            self.agents_by_category.clear()
            for raw in items:
                try:
                    agent = Agent.model_validate(raw)
                except Exception:
                    continue
                self.agents.append(agent)
                if agent.active:
                    self.agents_by_category[agent.category].append(agent)
                loaded += 1
            self.agents_loaded = loaded
        return loaded

    def load_golden_file(self, path: Path) -> int:
        if not path.exists():
            return 0
        data = json.loads(path.read_text())
        items = data if isinstance(data, list) else data.get("golden", [])
        loaded = 0
        with self._lock:
            self.golden.clear()
            for raw in items:
                try:
                    self.golden.append(GoldenLabel.model_validate(raw))
                except Exception:
                    continue
                loaded += 1
            self.golden_loaded = loaded
        return loaded

    def open_tickets(self) -> list[Ticket]:
        with self._lock:
            return [
                t
                for t in self.tickets.values()
                if is_open_state(t.state)
                and t.triage_status not in ("archived", "duplicate")
                and not t.is_duplicate
            ]

    def agents_for(self, category: str) -> list[Agent]:
        with self._lock:
            return list(self.agents_by_category.get(category, []))

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
            open_n = sum(1 for t in self.tickets.values() if is_open_state(t.state))
            return {
                "handled": handled,
                "tickets_loaded": self.tickets_loaded,
                "agents_loaded": self.agents_loaded,
                "golden_loaded": self.golden_loaded,
                "open_tickets": open_n,
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

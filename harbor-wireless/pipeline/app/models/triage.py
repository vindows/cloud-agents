from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.config import ArchiveMode
from app.models.tickets import Ticket, TicketIn
from app.normalize import coerce_ticket_dict


class StepResult(BaseModel):
    step: str
    action: str
    reason: str
    confidence: float
    detail: dict[str, Any] = Field(default_factory=dict)
    needs_human: bool = False
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: float | None = None


class ArchiveDecision(BaseModel):
    candidate: bool
    auto_applied: bool
    mode: ArchiveMode
    reason: str
    confidence: float
    needs_human: bool


class ArchiveLeverConfig(BaseModel):
    mode: ArchiveMode = "hybrid"
    age_years: float = 3.0
    inactive_days: int = 365


class TriageRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ticket: TicketIn
    archive: ArchiveLeverConfig | None = None
    existing_open: list[Ticket] | None = None
    dry_run: bool = False

    @model_validator(mode="before")
    @classmethod
    def _coerce_nested_tickets(cls, data: Any) -> Any:
        """Coerce raw tickets.json shapes on ticket + existing_open."""
        if not isinstance(data, dict):
            return data
        out = dict(data)
        if isinstance(out.get("ticket"), dict):
            out["ticket"] = coerce_ticket_dict(out["ticket"])
        open_list = out.get("existing_open")
        if isinstance(open_list, list):
            out["existing_open"] = [
                coerce_ticket_dict(item) if isinstance(item, dict) else item
                for item in open_list
            ]
        return out


class PipelineResult(BaseModel):
    ticket: Ticket
    steps: list[StepResult]
    outcome: Literal[
        "routed",
        "duplicate",
        "archived",
        "archive_candidate",
        "needs_human",
    ]
    archive: ArchiveDecision | None = None
    classifier_backend: str

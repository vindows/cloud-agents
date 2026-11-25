from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.config import ArchiveMode
from app.models.tickets import Ticket, TicketIn


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
    ticket: TicketIn
    archive: ArchiveLeverConfig | None = None
    existing_open: list[Ticket] | None = None
    dry_run: bool = False


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

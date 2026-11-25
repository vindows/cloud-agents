from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Category = Literal["access", "hardware", "network", "applications"]
Priority = Literal["1", "2", "3", "4", "5"]
State = Literal[
    "new",
    "open",
    "in_progress",
    "pending",
    "resolved",
    "closed",
    "archived",
]


class TicketIn(BaseModel):
    number: str | None = None
    short_description: str
    description: str = ""
    category: Category | None = None
    priority: Priority | None = None
    state: State = "new"
    assignment_group: str | None = None
    assigned_to: str | None = None
    opened_at: datetime | None = None
    caller_id: str | None = None
    sys_id: str | None = None
    parent: str | None = None
    requester_last_active_at: datetime | None = None


class Ticket(TicketIn):
    number: str
    sys_id: str
    opened_at: datetime
    category: Category | None = None
    priority: Priority | None = None
    triage_status: Literal[
        "untriaged",
        "triaged",
        "routed",
        "duplicate",
        "archive_candidate",
        "archived",
        "needs_human",
    ] = "untriaged"
    duplicate_of: str | None = None
    route_group: str | None = None
    route_agent: str | None = None
    tags: list[str] = Field(default_factory=list)

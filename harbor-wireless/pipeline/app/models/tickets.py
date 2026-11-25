from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.normalize import coerce_person, coerce_ticket_dict, normalize_priority

Category = Literal["access", "hardware", "network", "applications"]
Urgency = Literal["low", "medium", "high", "critical"]
RecencyTier = Literal["recent", "middle", "stale"]

PRIORITY_BY_CODE = {
    "1": "1 - Critical",
    "2": "2 - High",
    "3": "3 - Moderate",
    "4": "4 - Low",
    "5": "5 - Planning",
}


class PersonRef(BaseModel):
    """Caller or assignee as emitted by the synthetic dataset."""

    model_config = ConfigDict(extra="ignore")

    sys_id: str | None = None
    name: str | None = None
    user_name: str | None = None
    active: bool | None = True
    email: str | None = None


class Agent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sys_id: str
    employee_number: str | None = None
    name: str
    email: str | None = None
    user_name: str
    assignment_group: str
    category: Category
    role: str | None = None
    region: str | None = None
    active: bool = True
    skills: list[str] = Field(default_factory=list)


class TicketIn(BaseModel):
    """Ingress ticket — accepts raw harbor-wireless/data/tickets.json rows."""

    model_config = ConfigDict(extra="ignore")

    number: str | None = None
    short_description: str
    description: str = ""
    category: Category | None = None
    priority: str | None = None
    urgency: str | None = None
    state: str = "New"
    assignment_group: str | None = None
    assigned_to: PersonRef | str | None = None
    opened_at: datetime | None = None
    caller_id: PersonRef | str | None = None
    sys_id: str | None = None
    # Duplicate link: parent ticket *number* (e.g. INC1000527), not sys_id
    parent: str | None = None
    is_duplicate: bool | None = None
    recency_tier: RecencyTier | None = None
    channel: str | None = None
    requester_last_active_at: datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_servicenow_shape(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        return coerce_ticket_dict(data)

    @field_validator("caller_id", "assigned_to", mode="before")
    @classmethod
    def _coerce_person_field(cls, v: Any) -> Any:
        return coerce_person(v)

    @field_validator("priority", mode="before")
    @classmethod
    def _coerce_priority(cls, v: Any) -> Any:
        return normalize_priority(v)


class Ticket(TicketIn):
    number: str
    sys_id: str
    opened_at: datetime
    category: Category | None = None
    priority: str | None = None
    triage_status: Literal[
        "untriaged",
        "triaged",
        "routed",
        "duplicate",
        "archive_candidate",
        "archived",
        "needs_human",
    ] = "untriaged"
    # duplicate_of mirrors parent (ticket number) after triage
    duplicate_of: str | None = None
    route_group: str | None = None
    route_agent: str | None = None
    tags: list[str] = Field(default_factory=list)


class GoldenLabel(BaseModel):
    """Eval row from data/golden-set.json (labels use label_* prefix)."""

    model_config = ConfigDict(extra="ignore")

    sys_id: str
    number: str
    short_description: str
    description: str = ""
    label_category: Category
    label_is_duplicate: bool
    label_urgency: Urgency
    label_parent: str | None = None
    opened_at: datetime | None = None
    priority: str | None = None


CLOSED_STATES = {
    "closed",
    "resolved",
    "canceled",
    "cancelled",
    "archived",
}


def normalize_state(state: str | None) -> str:
    return (state or "").strip().lower()


def is_open_state(state: str | None) -> bool:
    return normalize_state(state) not in CLOSED_STATES


def caller_key(caller: PersonRef | str | None) -> str | None:
    if caller is None:
        return None
    if isinstance(caller, str):
        return caller
    return caller.user_name or caller.sys_id or caller.name


def caller_is_active(ticket: Ticket) -> bool | None:
    """True/False from caller_id.active; None if unknown."""
    c = ticket.caller_id
    if isinstance(c, PersonRef):
        return c.active
    return None


def priority_label(code: str) -> str:
    return PRIORITY_BY_CODE.get(code, code)

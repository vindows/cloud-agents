"""Coerce ServiceNow / harbor-wireless/data ticket shapes into pipeline models.

Dataset (PR #2) emits display fields the strict first-cut schema rejected:
  - priority: \"3 - Moderate\" (not bare \"1\"..\"5\")
  - state: \"New\" / \"In Progress\" (not lowercase enum)
  - caller_id / assigned_to: objects (not bare strings)
  - parent: original ticket *number* (kept as-is)

This layer runs on every TicketIn ingress (API body + JSON load) so UI/e2e
can POST raw tickets.json rows without reshaping.
"""

from __future__ import annotations

import re
from typing import Any

# Display priority → code (first digit), and code → canonical display
_PRIORITY_DISPLAY = {
    "1": "1 - Critical",
    "2": "2 - High",
    "3": "3 - Moderate",
    "4": "4 - Low",
    "5": "5 - Planning",
}

_STATE_ALIASES = {
    "new": "New",
    "open": "New",
    "in progress": "In Progress",
    "in_progress": "In Progress",
    "pending": "On Hold",
    "on hold": "On Hold",
    "on_hold": "On Hold",
    "resolved": "Resolved",
    "closed": "Closed",
    "canceled": "Canceled",
    "cancelled": "Canceled",
    "archived": "Closed",
}


def priority_code(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    if s in _PRIORITY_DISPLAY:
        return s
    m = re.match(r"^([1-5])\b", s)
    return m.group(1) if m else None


def normalize_priority(value: Any) -> str | None:
    """Keep ServiceNow display form when possible; accept bare codes too."""
    if value is None:
        return None
    code = priority_code(value)
    if code:
        return _PRIORITY_DISPLAY[code]
    s = str(value).strip()
    return s or None


def normalize_state(value: Any) -> str:
    if value is None or value == "":
        return "New"
    s = str(value).strip()
    key = s.lower()
    if key in _STATE_ALIASES:
        return _STATE_ALIASES[key]
    # Already a dataset display value
    for display in (
        "New",
        "In Progress",
        "On Hold",
        "Resolved",
        "Closed",
        "Canceled",
    ):
        if s.lower() == display.lower():
            return display
    return s


def coerce_person(value: Any) -> dict[str, Any] | str | None:
    """Accept string id or ServiceNow person object."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return {
            "sys_id": value.get("sys_id"),
            "name": value.get("name"),
            "user_name": value.get("user_name"),
            "active": value.get("active", True),
            "email": value.get("email"),
        }
    # pydantic model
    if hasattr(value, "model_dump"):
        return coerce_person(value.model_dump())
    return str(value)


def coerce_ticket_dict(raw: Any) -> dict[str, Any]:
    """Normalize one ticket dict (or model) for TicketIn / Ticket validation."""
    if raw is None:
        return {}
    if hasattr(raw, "model_dump"):
        data = raw.model_dump()
    elif isinstance(raw, dict):
        data = dict(raw)
    else:
        raise TypeError(f"Cannot coerce ticket of type {type(raw)!r}")

    # Drop generator-only noise if present; keep known extras that models allow
    if "priority" in data:
        data["priority"] = normalize_priority(data.get("priority"))
    if "state" in data or data.get("state") is None:
        data["state"] = normalize_state(data.get("state"))
    if "caller_id" in data:
        data["caller_id"] = coerce_person(data.get("caller_id"))
    if "assigned_to" in data:
        data["assigned_to"] = coerce_person(data.get("assigned_to"))

    # parent stays ticket number (string) or null — never rewrite to sys_id
    parent = data.get("parent")
    if parent is not None:
        data["parent"] = str(parent).strip() or None

    return data

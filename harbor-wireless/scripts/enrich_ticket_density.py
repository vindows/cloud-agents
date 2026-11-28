#!/usr/bin/env python3
"""Enrich Harbor Wireless tickets for Signal Deck ops-density demo.

Adds (synthetic only, no real PII):
  - activity stream (comments / work notes / triage log)
  - assignment_history
  - cmdb_ci (affected service) on a large share
  - impact (alongside existing urgency)
  - hard_block flags (vip / security / privileged_access) on a small share

Hero set (~80): deep activity + assignment history.
Everyone else: 1–2 stub activity rows when useful; CI on ~65%.

Idempotent: re-running overwrites enrichment keys only.
"""

from __future__ import annotations

import hashlib
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

SEED = 20261128
N_HEROES = 80
NOW = datetime(2026, 11, 24, 18, 0, 0, tzinfo=timezone.utc)

CI_BY_CATEGORY = {
    "access": [
        ("Okta", "Application"),
        ("Active Directory", "Application"),
        ("VPN Gateway", "Network Gear"),
        ("Privileged Access Mgmt", "Application"),
        ("Badge Access Control", "Application"),
    ],
    "hardware": [
        ("Dell Latitude 5440", "Computer"),
        ("MacBook Pro 14", "Computer"),
        ("Cisco Headset 562", "Hardware"),
        ("Intune MDM", "Application"),
        ("MiFi Hotspot Fleet", "Hardware"),
        ("Floor Printer HQ-3", "Printer"),
    ],
    "network": [
        ("eNodeB-LAS-14", "Network Gear"),
        ("SD-WAN Edge Dallas", "Network Gear"),
        ("Corp Wi-Fi Controller", "Network Gear"),
        ("MPLS Core Phoenix", "Network Gear"),
        ("DNS Internal Zones", "Application"),
        ("Firewall Partner Edge", "Network Gear"),
    ],
    "applications": [
        ("Salesforce", "Application"),
        ("Workday", "Application"),
        ("Teams", "Application"),
        ("SAP-ECC", "Application"),
        ("ServiceNow", "Application"),
        ("HarborCRM", "Application"),
        ("Confluence", "Application"),
        ("Jira", "Application"),
    ],
}

IMPACT_BY_URGENCY = {
    "critical": "1 - High",
    "high": "1 - High",
    "medium": "2 - Medium",
    "low": "3 - Low",
}

HARD_BLOCK_REASONS = {
    "vip": "Caller marked VIP — auto-archive locked; human review required.",
    "security": "Security-sensitive keywords — route to human review only.",
    "privileged_access": "Privileged-access request — no auto-archive; specialist must decide.",
}

SYSTEM_ACTORS = [
    ("System One", "AI"),
    ("Triage shim", "System"),
    ("Archive policy", "System"),
]


def rng_for(sys_id: str, salt: str = "") -> random.Random:
    digest = hashlib.sha256(f"{SEED}:{sys_id}:{salt}".encode()).hexdigest()
    return random.Random(int(digest[:16], 16))


def parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def pick_ci(ticket: dict, rng: random.Random) -> dict | None:
    # ~65% of tickets get a CI; heroes always do.
    pool = CI_BY_CATEGORY.get(ticket["category"], CI_BY_CATEGORY["applications"])
    name, klass = rng.choice(pool)
    return {
        "sys_id": f"ci-{hashlib.md5(name.encode()).hexdigest()[:12]}",
        "name": name,
        "class": klass,
    }


def hard_block_for(ticket: dict, rng: random.Random, is_hero: bool) -> dict | None:
    text = f"{ticket['short_description']} {ticket['description']}".lower()
    flags: list[str] = []
    if "privileged" in text or "elevated" in text or "privilege" in text:
        flags.append("privileged_access")
    if "security" in text or "compromise" in text or "dlp" in text:
        flags.append("security")
    # VIP: rare, biased to heroes / high urgency
    if is_hero and rng.random() < 0.18:
        flags.append("vip")
    elif ticket.get("urgency") == "critical" and rng.random() < 0.08:
        flags.append("vip")
    elif rng.random() < 0.015:
        flags.append("vip")

    # Dedupe preserve order
    seen: set[str] = set()
    ordered = []
    for f in flags:
        if f not in seen:
            seen.add(f)
            ordered.append(f)
    if not ordered:
        return None
    primary = ordered[0]
    return {
        "flags": ordered,
        "reason": HARD_BLOCK_REASONS[primary],
        "forces_human_review": True,
        "locks_auto_archive": True,
    }


def stub_activity(ticket: dict, rng: random.Random) -> list[dict]:
    opened = parse_dt(ticket["opened_at"])
    caller = ticket["caller_id"]
    entries = [
        {
            "at": iso(opened + timedelta(minutes=rng.randint(1, 40))),
            "actor": caller.get("name") or "Caller",
            "role": "Caller",
            "kind": "comment",
            "action": "Opened request",
            "body": ticket["short_description"],
            "reason": None,
        }
    ]
    if ticket.get("is_duplicate") and ticket.get("parent"):
        entries.append(
            {
                "at": iso(opened + timedelta(hours=rng.randint(1, 48))),
                "actor": "System One",
                "role": "AI",
                "kind": "triage",
                "action": "Marked duplicate candidate",
                "body": f"Near-match to parent {ticket['parent']} by short_description overlap.",
                "reason": "dedupe",
            }
        )
    elif not caller.get("active", True) and ticket.get("recency_tier") == "stale":
        entries.append(
            {
                "at": iso(NOW - timedelta(days=rng.randint(1, 30))),
                "actor": "Archive policy",
                "role": "System",
                "kind": "work_note",
                "action": "Archive candidate flagged",
                "body": "Requester inactive and ticket age exceeds hybrid lever.",
                "reason": "archive_policy",
            }
        )
    return entries


def deep_activity(ticket: dict, rng: random.Random, agents_by_group: dict) -> list[dict]:
    opened = parse_dt(ticket["opened_at"])
    caller = ticket["caller_id"]
    group = ticket["assignment_group"]
    pool = agents_by_group.get(group) or []
    agent = rng.choice(pool) if pool else None
    agent_name = agent["name"] if agent else "Queue lead"

    cat_conf = round(0.62 + rng.random() * 0.32, 2)
    entries: list[dict] = [
        {
            "at": iso(opened + timedelta(minutes=rng.randint(2, 25))),
            "actor": caller.get("name") or "Caller",
            "role": "Caller",
            "kind": "comment",
            "action": "Additional detail",
            "body": (
                f"Channel {ticket.get('channel', 'portal')}. "
                f"Need this routed — blocking work at {caller.get('name', 'site')}."
            ),
            "reason": None,
        },
        {
            "at": iso(opened + timedelta(hours=rng.randint(1, 18))),
            "actor": "System One",
            "role": "AI",
            "kind": "triage",
            "action": "Classified",
            "body": f"Classified {ticket['category']} · confidence {cat_conf}.",
            "reason": "classify",
        },
        {
            "at": iso(opened + timedelta(hours=rng.randint(20, 60))),
            "actor": "Triage shim",
            "role": "System",
            "kind": "work_note",
            "action": "Priority scored",
            "body": (
                f"Urgency {ticket.get('urgency', 'medium')} · impact "
                f"{IMPACT_BY_URGENCY.get(ticket.get('urgency', 'medium'), '2 - Medium')} → "
                f"{ticket.get('priority')}."
            ),
            "reason": "priority",
        },
    ]

    if ticket.get("is_duplicate") and ticket.get("parent"):
        entries.append(
            {
                "at": iso(opened + timedelta(hours=rng.randint(4, 72))),
                "actor": "System One",
                "role": "AI",
                "kind": "triage",
                "action": "Dedupe match",
                "body": f"Linked to parent {ticket['parent']} — short_description overlap.",
                "reason": "dedupe",
            }
        )
    else:
        entries.append(
            {
                "at": iso(opened + timedelta(hours=rng.randint(24, 96))),
                "actor": "System One",
                "role": "AI",
                "kind": "triage",
                "action": "Route suggestion",
                "body": (
                    f"Recommend {group}"
                    + (f" → {agent_name}" if agent else "")
                    + f" · load-aware assign."
                ),
                "reason": "route",
            }
        )

    if ticket.get("hard_block"):
        entries.append(
            {
                "at": iso(opened + timedelta(hours=rng.randint(2, 12))),
                "actor": "System One",
                "role": "AI",
                "kind": "triage",
                "action": "Hard block — human review",
                "body": ticket["hard_block"]["reason"],
                "reason": "hard_block",
            }
        )

    # Aging wait theater — assignment still pending for many New tickets
    if ticket["state"] == "New" and ticket.get("assigned_to") is None:
        wait_days = max(1, (NOW - opened).days)
        entries.append(
            {
                "at": iso(NOW - timedelta(hours=rng.randint(2, 48))),
                "actor": "Queue monitor",
                "role": "System",
                "kind": "work_note",
                "action": "Still untriaged",
                "body": f"Waiting {wait_days}d in {group} — classic 13-day routing wait story.",
                "reason": "aging",
            }
        )
    elif agent and ticket.get("assigned_to"):
        entries.append(
            {
                "at": iso(opened + timedelta(days=min(12, max(1, (NOW - opened).days // 3)))),
                "actor": agent_name,
                "role": "Agent",
                "kind": "work_note",
                "action": "Acknowledged",
                "body": f"Picked up from {group}. Synthetic ack for demo paper trail.",
                "reason": None,
            }
        )

    if not caller.get("active", True):
        entries.append(
            {
                "at": iso(NOW - timedelta(days=rng.randint(5, 40))),
                "actor": "Archive policy",
                "role": "System",
                "kind": "work_note",
                "action": "Requester inactive",
                "body": "Caller active=false — hybrid archive lever may apply.",
                "reason": "archive_policy",
            }
        )

    entries.sort(key=lambda e: e["at"])
    return entries


def assignment_history(ticket: dict, rng: random.Random, agents_by_group: dict) -> list[dict]:
    opened = parse_dt(ticket["opened_at"])
    group = ticket["assignment_group"]
    pool = agents_by_group.get(group) or []
    agent = ticket.get("assigned_to")
    suggested = rng.choice(pool) if pool else None

    rows = [
        {
            "at": iso(opened),
            "group": None,
            "assignee": None,
            "action": "Opened — unassigned",
        },
        {
            "at": iso(opened + timedelta(hours=rng.randint(6, 72))),
            "group": group,
            "assignee": None,
            "action": f"Suggested group {group}",
        },
    ]
    if suggested and (agent or ticket["state"] == "New"):
        rows.append(
            {
                "at": iso(opened + timedelta(days=rng.randint(1, 10))),
                "group": group,
                "assignee": (agent or {}).get("name") if isinstance(agent, dict) else suggested["name"],
                "action": (
                    f"Assigned to {(agent or {}).get('name') if isinstance(agent, dict) else suggested['name']}"
                    if agent
                    else f"Suggested agent {suggested['name']} (pending)"
                ),
            }
        )
    if ticket.get("hard_block"):
        rows.append(
            {
                "at": iso(opened + timedelta(hours=rng.randint(2, 20))),
                "group": group,
                "assignee": None,
                "action": "Held for human review (hard block)",
            }
        )
    return rows


def select_heroes(tickets: list[dict], rng: random.Random) -> set[str]:
    """Prefer New/unassigned, duplicates, stale inactive, high urgency — demo walkthrough set."""
    scored: list[tuple[float, str]] = []
    for t in tickets:
        score = 0.0
        if t["state"] == "New" and t.get("assigned_to") is None:
            score += 5
        if t.get("is_duplicate"):
            score += 2
        if t.get("recency_tier") == "stale" and not t["caller_id"].get("active", True):
            score += 3
        if t.get("urgency") in ("critical", "high"):
            score += 2
        if t.get("recency_tier") == "recent":
            score += 1.5
        score += rng.random() * 0.5
        scored.append((score, t["sys_id"]))
    scored.sort(reverse=True)
    return {sys_id for _, sys_id in scored[:N_HEROES]}


def enrich(tickets: list[dict], agents: list[dict]) -> dict:
    agents_by_group: dict[str, list[dict]] = {}
    for a in agents:
        agents_by_group.setdefault(a["assignment_group"], []).append(a)

    master = random.Random(SEED)
    heroes = select_heroes(tickets, master)

    ci_count = 0
    deep_count = 0
    hard_count = 0

    for t in tickets:
        rng = rng_for(t["sys_id"])
        is_hero = t["sys_id"] in heroes
        t["impact"] = IMPACT_BY_URGENCY.get(t.get("urgency", "medium"), "2 - Medium")
        t["hard_block"] = hard_block_for(t, rng, is_hero)
        if t["hard_block"]:
            hard_count += 1

        if is_hero or rng.random() < 0.65:
            t["cmdb_ci"] = pick_ci(t, rng)
            ci_count += 1
        else:
            t["cmdb_ci"] = None

        if is_hero:
            t["activity"] = deep_activity(t, rng, agents_by_group)
            t["assignment_history"] = assignment_history(t, rng, agents_by_group)
            t["demo_hero"] = True
            deep_count += 1
        else:
            t["activity"] = stub_activity(t, rng)
            t["assignment_history"] = [
                {
                    "at": t["opened_at"],
                    "group": t["assignment_group"],
                    "assignee": (t["assigned_to"] or {}).get("name")
                    if isinstance(t.get("assigned_to"), dict)
                    else None,
                    "action": "Opened",
                }
            ]
            t["demo_hero"] = False

    return {
        "heroes": deep_count,
        "with_ci": ci_count,
        "hard_blocks": hard_count,
        "tickets": len(tickets),
    }


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    data_dir = root / "data"
    tickets_path = data_dir / "tickets.json"
    agents_path = data_dir / "agents.json"
    meta_path = data_dir / "dataset-meta.json"

    tickets = json.loads(tickets_path.read_text(encoding="utf-8"))
    agents = json.loads(agents_path.read_text(encoding="utf-8"))
    summary = enrich(tickets, agents)

    tickets_path.write_text(json.dumps(tickets, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    meta = {}
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["ops_density"] = {
        **summary,
        "enriched_at": iso(NOW),
        "notes": "Synthetic activity/CI/hard_block for Signal Deck P0/P1; no real PII.",
    }
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(meta["ops_density"], indent=2))


if __name__ == "__main__":
    main()

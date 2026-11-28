#!/usr/bin/env python3
"""Generate Harbor Wireless synthetic ServiceNow-shaped ticket dataset.

Emits:
  data/agents.json   (~180 agents, 4 assignment groups)
  data/tickets.json  (~6000 tickets over ~6 years, ~30% duplicates)
  data/golden-set.json (~200 labeled: category, is_duplicate, urgency)
"""

from __future__ import annotations

import json
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

SEED = 20261124
N_TICKETS = 6000
N_AGENTS = 180
N_GOLDEN = 200
TARGET_DUPE_RATE = 0.30
YEARS = 6

# Demo "now" — fixed so regenerations stay stable relative to recency tiers.
NOW = datetime(2026, 11, 24, 18, 0, 0, tzinfo=timezone.utc)
START = NOW - timedelta(days=365 * YEARS)

CATEGORIES = ("access", "hardware", "network", "applications")

ASSIGNMENT_GROUPS = {
    "access": "HW-Access-Identity",
    "hardware": "HW-Endpoint-Hardware",
    "network": "HW-Network-Ops",
    "applications": "HW-Enterprise-Apps",
}

PRIORITIES = ("1 - Critical", "2 - High", "3 - Moderate", "4 - Low")
PRIORITY_WEIGHTS = (0.05, 0.18, 0.47, 0.30)

STATES = (
    "New",
    "In Progress",
    "On Hold",
    "Resolved",
    "Closed",
    "Canceled",
)
STATE_WEIGHTS = (0.22, 0.18, 0.08, 0.20, 0.28, 0.04)

FIRST_NAMES = [
    "Aisha", "Alex", "Amir", "Ana", "Andre", "Ava", "Ben", "Camila", "Carlos",
    "Chloe", "Chris", "Dana", "Diego", "Elena", "Emma", "Ethan", "Fatima",
    "Grace", "Hassan", "Priya", "Ian", "Isabel", "Jake", "Jasmine", "Jordan",
    "Kai", "Kate", "Kenji", "Lila", "Luis", "Maya", "Mei", "Miguel", "Nina",
    "Noah", "Omar", "Owen", "Paula", "Quinn", "Ravi", "Riley", "Sam", "Sara",
    "Sofia", "Tanya", "Theo", "Uma", "Victor", "Wei", "Yara", "Zoe",
]

LAST_NAMES = [
    "Adams", "Baker", "Chen", "Cruz", "Davis", "Diaz", "Evans", "Foster",
    "Garcia", "Gupta", "Harris", "Huang", "Ibrahim", "Jackson", "Kim", "Lee",
    "Lopez", "Martin", "Nguyen", "Ortiz", "Patel", "Perez", "Quinn", "Reed",
    "Santos", "Singh", "Torres", "Walker", "Wright", "Young", "Zhang",
]

REGIONS = [
    "Northeast", "Southeast", "Midwest", "Southwest", "Pacific", "Mountain",
    "Central", "Great Lakes",
]

SITES = [
    "HQ-Dallas", "NOC-Atlanta", "Retail-Support-Chicago", "Call-Center-Phoenix",
    "Warehouse-Memphis", "Field-Ops-Denver", "Corp-Seattle", "Corp-NYC",
    "Lab-Austin", "Retail-Support-LA",
]

# Templates: (short_description, description_body). {placeholders} filled at gen time.
TEMPLATES: dict[str, list[tuple[str, str]]] = {
    "access": [
        (
            "VPN MFA not working after password reset",
            "User {name} at {site} cannot complete MFA challenge for corporate VPN. "
            "Password was reset yesterday. Error: 'Authenticator registration required'. "
            "Blocks remote access to {system}.",
        ),
        (
            "Badge access denied for {site} server room",
            "Physical badge FOB-{badge} fails at door {door}. Security desk confirmed "
            "badge is active in physical security system but AD group "
            "srv-room-{site} may be missing.",
        ),
        (
            "AD account locked after failed logins",
            "{name} reports account locked out after multiple failed Outlook "
            "logins from laptop. Need unlock and verify no compromise. "
            "User ID: {userid}",
        ),
        (
            "Request access to SharePoint site for store ops",
            "New hire {name} needs Contribute access to the Store Ops SharePoint "
            "for {region} region. Manager approved via email.",
        ),
        (
            "Okta SSO failing for Salesforce",
            "SSO redirect loops when launching Salesforce from Okta tile. "
            "Affects {name} only so far. Browser cache cleared; issue persists.",
        ),
        (
            "Privileged access request — change window",
            "Temporary elevated rights needed for {name} to apply patch on "
            "{system} during tonight's change window. Duration: 4 hours.",
        ),
        (
            "Contractor account expiry blocking project",
            "Contractor account for {name} expired; cannot access Jira and "
            "Confluence. Extension approved by sponsor for 90 days.",
        ),
        (
            "Wi-Fi captive portal credentials rejected",
            "Guest/corp Wi-Fi login rejects credentials for {name} at {site}. "
            "Other users on same AP are fine.",
        ),
        (
            "DLP policy blocking email attachment send",
            "{name} cannot send spreadsheet with store inventory to vendor. "
            "DLP quarantine ID logged. Need review / exception.",
        ),
        (
            "Service account password rotation broke job",
            "Nightly ETL job failed after scheduled svc account password rotate. "
            "Account: svc-{system}. Need coordinated reset.",
        ),
    ],
    "hardware": [
        (
            "Laptop won't power on after overnight charge",
            "{name}'s Dell Latitude at {site} shows no LED activity after "
            "charging overnight. Tried alternate charger. Possible battery/MB fail.",
        ),
        (
            "Docking station USB-C port intermittent",
            "Dock at desk {door} loses monitors when cable bumped. Laptop works "
            "standalone. Request dock swap.",
        ),
        (
            "Broken laptop screen — travel damage",
            "Screen cracked during travel. Device still boots. Need loaner and "
            "repair RMA for asset TAG-{badge}.",
        ),
        (
            "Headset audio cutouts on softphone",
            "Cisco headset for {name} drops audio mid-call in Contact Center. "
            "Reproduced on two softphone clients.",
        ),
        (
            "Mobile device enrollment failing Intune",
            "Company iPhone for {name} fails Intune enrollment at 'Installing "
            "management profile'. Blocks MDM apps for field work.",
        ),
        (
            "Printer offline in {site} copy room",
            "Floor printer shows Offline; queue backs up. Power cycled; still "
            "unreachable on print VLAN.",
        ),
        (
            "Request replacement keyboard — sticky keys",
            "Several keys stick on keyboard for {name}. Standard USB keyboard "
            "request for {site}.",
        ),
        (
            "Barcode scanner not pairing to POS tablet",
            "Bluetooth scanner for retail POS at {site} will not stay paired. "
            "Impacts inventory count tonight.",
        ),
        (
            "Hotspot device SIM not activating",
            "MiFi unit for field tech {name} shows No Service after SIM swap. "
            "ICCID verified against provisioning.",
        ),
        (
            "Monitor flicker on DisplayPort",
            "External monitor flickers every few minutes for {name} at {site}. "
            "Tried new cable; issue continues.",
        ),
    ],
    "network": [
        (
            "Store Wi-Fi down — customers and POS affected",
            "Retail site {site} reports Wi-Fi SSID down. Wired POS partially up. "
            "AP controller shows APs offline. Region: {region}.",
        ),
        (
            "High latency to datacenter from {site}",
            "Users at {site} report 400ms+ RTT to HQ apps. Traceroute stalls at "
            "WAN edge. Started ~{hour} local.",
        ),
        (
            "VPN tunnel flaps every few minutes",
            "Site-to-site VPN for {site} renegotiates repeatedly. Packet loss "
            "correlates with flaps. Affects {system} replication.",
        ),
        (
            "DNS resolution failing for internal zones",
            "{name} cannot resolve *.corp.harborwireless.internal from laptop "
            "on VPN. Public DNS works.",
        ),
        (
            "Firewall change request — vendor IP allow",
            "Need outbound allow to vendor IP range for {system} integration. "
            "Change ticket for next maintenance window.",
        ),
        (
            "Cell site backhaul alarm — packet loss",
            "NOC alarm: elevated packet loss on backhaul for sector near "
            "{region}. Correlated with customer speed complaints.",
        ),
        (
            "Switch port error counters climbing",
            "Access switch at {site} port Gi1/0/{door} CRC errors rising. "
            "User {name} drops every few minutes.",
        ),
        (
            "Guest network captive portal timeout",
            "Guest Wi-Fi portal times out before auth completes at {site} lobby. "
            "Staff Wi-Fi unaffected.",
        ),
        (
            "SD-WAN path preference incorrect after cutover",
            "After circuit cutover, {site} SD-WAN still prefers degraded path. "
            "Need policy check.",
        ),
        (
            "VoIP call quality poor — jitter alerts",
            "Contact center agents at {site} report choppy calls. MOS scores "
            "below threshold since morning.",
        ),
    ],
    "applications": [
        (
            "Salesforce opportunity records not saving",
            "{name} gets timeout saving Opportunities in Salesforce. Intermittent "
            "since last weekend release. Region: {region}.",
        ),
        (
            "Workday timesheet submission error",
            "Cannot submit timesheet for prior week. Error code WW-4821. "
            "Blocks payroll for {name}.",
        ),
        (
            "Jira project permissions incorrect after migration",
            "Team cannot transition tickets in project HW-{system}. Appear "
            "read-only after space migration.",
        ),
        (
            "Outlook search returns no results",
            "Desktop Outlook for {name} returns empty search; OWA works. "
            "Cached mode rebuild attempted.",
        ),
        (
            "SAP transaction dump on Z_INV_POST",
            "Running Z_INV_POST dumps with RAISE_EXCEPTION for plant {site}. "
            "Finance closing blocked.",
        ),
        (
            "Teams meeting lobby admits not working",
            "{name} cannot admit guests from lobby in scheduled meeting. "
            "Affects vendor workshop today.",
        ),
        (
            "CRM mobile app crash on launch",
            "Harbor CRM iOS app crashes immediately for {name}. Reinstall "
            "attempted. Device on latest iOS.",
        ),
        (
            "Confluence page edit conflict / version lost",
            "Edit to runbook page was overwritten. Need restore from history "
            "for {system} on-call doc.",
        ),
        (
            "Payroll export job stuck in queued state",
            "Nightly payroll export to bank file stuck Queued in {system}. "
            "Ops needs unblock before ACH cutoff.",
        ),
        (
            "Service catalog request form validation bug",
            "Catalog item 'New laptop' rejects valid cost center codes. "
            "Blocks onboarding for {name} at {site}.",
        ),
    ],
}

SYSTEMS = [
    "Salesforce", "Workday", "SAP-ECC", "ServiceNow", "Okta", "ActiveDirectory",
    "ExchangeOnline", "Teams", "Jira", "Confluence", "HarborCRM", "BillingCore",
    "InventoryMgmt", "NetworkOrchestrator", "PCI-Vault",
]

URGENCY_BY_PRIORITY = {
    "1 - Critical": "critical",
    "2 - High": "high",
    "3 - Moderate": "medium",
    "4 - Low": "low",
}


def uid() -> str:
    return str(uuid.UUID(int=random.getrandbits(128), version=4))


def pick_name() -> tuple[str, str]:
    return random.choice(FIRST_NAMES), random.choice(LAST_NAMES)


def make_userid(first: str, last: str, n: int) -> str:
    return f"{first[0].lower()}{last.lower()}{n % 1000:03d}"


def fill_template(tmpl: str, ctx: dict) -> str:
    try:
        return tmpl.format(**ctx)
    except KeyError:
        return tmpl


def recency_tier(opened_at: datetime) -> str:
    age_days = (NOW - opened_at).days
    if age_days <= 15:
        return "recent"
    if age_days <= 180:
        return "middle"
    return "stale"


def sample_opened_at() -> datetime:
    """Skew: most tickets older; thin recent and middle bands for demo story."""
    # Weights across years roughly flat with a mild recent bump for open work.
    r = random.random()
    if r < 0.04:
        # last 15 days
        delta = timedelta(seconds=random.randint(0, 15 * 86400))
        return NOW - delta
    if r < 0.18:
        # middle band ~16–180 days
        delta = timedelta(seconds=random.randint(16 * 86400, 180 * 86400))
        return NOW - delta
    # multi-year stale / historical (180 days → 6 years)
    span = (NOW - START).total_seconds() - 180 * 86400
    delta = timedelta(seconds=random.randint(180 * 86400, int(180 * 86400 + span)))
    return NOW - delta


def generate_agents(n: int = N_AGENTS) -> list[dict]:
    agents: list[dict] = []
    # ~equal split across 4 groups
    per = n // 4
    extras = n - per * 4
    idx = 0
    for cat in CATEGORIES:
        count = per + (1 if extras > 0 else 0)
        if extras > 0:
            extras -= 1
        group = ASSIGNMENT_GROUPS[cat]
        for i in range(count):
            first, last = pick_name()
            idx += 1
            email = f"{first.lower()}.{last.lower()}{idx}@harborwireless.example"
            agents.append(
                {
                    "sys_id": uid(),
                    "employee_number": f"E{10000 + idx}",
                    "name": f"{first} {last}",
                    "email": email,
                    "user_name": make_userid(first, last, idx),
                    "assignment_group": group,
                    "category": cat,
                    "role": random.choice(
                        ["L1 Agent", "L2 Specialist", "Queue Lead", "Senior Engineer"]
                    ),
                    "region": random.choice(REGIONS),
                    "active": True,
                    "skills": [cat, random.choice(["triage", "escalation", "vip"])],
                }
            )
    return agents


def generate_callers(n: int = 900) -> list[dict]:
    callers = []
    for i in range(n):
        first, last = pick_name()
        callers.append(
            {
                "sys_id": uid(),
                "name": f"{first} {last}",
                "user_name": make_userid(first, last, i + 1),
                "email": f"{first.lower()}.{last.lower()}{i + 1}@harborwireless.example",
                "site": random.choice(SITES),
                "region": random.choice(REGIONS),
                # ~12% inactive — used by archive hybrid lever story
                "active": random.random() > 0.12,
            }
        )
    return callers


def build_ticket_text(category: str, caller: dict) -> tuple[str, str]:
    short_t, body_t = random.choice(TEMPLATES[category])
    ctx = {
        "name": caller["name"],
        "site": caller["site"],
        "region": caller["region"],
        "userid": caller["user_name"],
        "system": random.choice(SYSTEMS),
        "badge": f"{random.randint(10000, 99999)}",
        "door": f"{random.randint(1, 48)}",
        "hour": f"{random.randint(6, 18):02d}:00",
    }
    short = fill_template(short_t, ctx)
    body = fill_template(body_t, ctx)
    # Light paraphrase noise so duplicates aren't byte-identical.
    if random.random() < 0.35:
        body += f" Ticket opened from {random.choice(['portal', 'phone', 'walk-up', 'email'])}."
    return short, body


def mutate_for_duplicate(short: str, description: str) -> tuple[str, str]:
    """Create a near-duplicate with wording drift."""
    prefixes = ["Re: ", "Follow-up: ", "Same issue — ", "Still seeing: ", ""]
    suffixes = [" (again)", " - continued", " please help", ""]
    short2 = random.choice(prefixes) + short + random.choice(suffixes)
    extras = [
        " Same symptoms as before.",
        " Still broken after waiting overnight.",
        " Manager asked me to re-open.",
        " Duplicate of earlier report.",
        " User called back about this.",
    ]
    desc2 = description + random.choice(extras)
    return short2.strip(), desc2


def assign_agent(agents_by_group: dict[str, list[dict]], category: str, state: str):
    group = ASSIGNMENT_GROUPS[category]
    pool = agents_by_group[group]
    if state in ("New", "Canceled") and random.random() < 0.55:
        return group, None
    agent = random.choice(pool)
    return group, agent


def generate_tickets(
    agents: list[dict],
    callers: list[dict],
    n: int = N_TICKETS,
) -> list[dict]:
    agents_by_group: dict[str, list[dict]] = {g: [] for g in ASSIGNMENT_GROUPS.values()}
    for a in agents:
        agents_by_group[a["assignment_group"]].append(a)

    tickets: list[dict] = []
    # First pass: originals. Then attach duplicates targeting ~30% of corpus.
    n_dupes = int(round(n * TARGET_DUPE_RATE))
    n_originals = n - n_dupes

    # Category mix roughly even with slight network/app skew for carrier IT.
    cat_weights = (0.22, 0.23, 0.28, 0.27)

    for i in range(n_originals):
        category = random.choices(CATEGORIES, weights=cat_weights, k=1)[0]
        caller = random.choice(callers)
        short, description = build_ticket_text(category, caller)
        priority = random.choices(PRIORITIES, weights=PRIORITY_WEIGHTS, k=1)[0]
        state = random.choices(STATES, weights=STATE_WEIGHTS, k=1)[0]
        opened_at = sample_opened_at()
        group, agent = assign_agent(agents_by_group, category, state)
        number = f"INC{1000000 + i + 1:07d}"
        tickets.append(
            {
                "sys_id": uid(),
                "number": number,
                "short_description": short,
                "description": description,
                "category": category,
                "priority": priority,
                "urgency": URGENCY_BY_PRIORITY[priority],
                "state": state,
                "assignment_group": group,
                "assigned_to": None
                if agent is None
                else {
                    "sys_id": agent["sys_id"],
                    "name": agent["name"],
                    "user_name": agent["user_name"],
                },
                "opened_at": opened_at.isoformat().replace("+00:00", "Z"),
                "caller_id": {
                    "sys_id": caller["sys_id"],
                    "name": caller["name"],
                    "user_name": caller["user_name"],
                    "active": caller["active"],
                },
                "parent": None,
                "is_duplicate": False,
                "recency_tier": recency_tier(opened_at),
                "channel": random.choice(
                    ["portal", "phone", "email", "walk-up", "chat"]
                ),
            }
        )

    # Duplicate tickets pointing at original parents (prefer open-ish originals).
    parent_pool = [
        t
        for t in tickets
        if t["state"] in ("New", "In Progress", "On Hold", "Resolved")
    ]
    if not parent_pool:
        parent_pool = list(tickets)

    for j in range(n_dupes):
        parent = random.choice(parent_pool)
        caller = random.choice(callers)
        # Same category as parent; near-duplicate text.
        short, description = mutate_for_duplicate(
            parent["short_description"], parent["description"]
        )
        # Dupes tend to open after parent.
        parent_dt = datetime.fromisoformat(parent["opened_at"].replace("Z", "+00:00"))
        max_after = max(1, int((NOW - parent_dt).total_seconds()))
        opened_at = parent_dt + timedelta(seconds=random.randint(1, max_after))
        if opened_at > NOW:
            opened_at = NOW - timedelta(minutes=random.randint(1, 120))
        priority = parent["priority"]
        if random.random() < 0.15:
            priority = random.choices(PRIORITIES, weights=PRIORITY_WEIGHTS, k=1)[0]
        state = random.choices(STATES, weights=STATE_WEIGHTS, k=1)[0]
        group, agent = assign_agent(agents_by_group, parent["category"], state)
        number = f"INC{1000000 + n_originals + j + 1:07d}"
        tickets.append(
            {
                "sys_id": uid(),
                "number": number,
                "short_description": short,
                "description": description,
                "category": parent["category"],
                "priority": priority,
                "urgency": URGENCY_BY_PRIORITY[priority],
                "state": state,
                "assignment_group": group,
                "assigned_to": None
                if agent is None
                else {
                    "sys_id": agent["sys_id"],
                    "name": agent["name"],
                    "user_name": agent["user_name"],
                },
                "opened_at": opened_at.isoformat().replace("+00:00", "Z"),
                "caller_id": {
                    "sys_id": caller["sys_id"],
                    "name": caller["name"],
                    "user_name": caller["user_name"],
                    "active": caller["active"],
                },
                "parent": parent["number"],
                "is_duplicate": True,
                "recency_tier": recency_tier(opened_at),
                "channel": random.choice(
                    ["portal", "phone", "email", "walk-up", "chat"]
                ),
            }
        )

    # Stable sort by opened_at then number for deterministic files.
    tickets.sort(key=lambda t: (t["opened_at"], t["number"]))
    return tickets


def generate_golden_set(tickets: list[dict], n: int = N_GOLDEN) -> list[dict]:
    """Labeled subset for eval: category, is_duplicate, urgency."""
    # Stratify: include duplicates and all categories.
    by_cat: dict[str, list[dict]] = {c: [] for c in CATEGORIES}
    dupes = [t for t in tickets if t["is_duplicate"]]
    originals = [t for t in tickets if not t["is_duplicate"]]
    for t in tickets:
        by_cat[t["category"]].append(t)

    selected: list[dict] = []
    seen: set[str] = set()

    def take(pool: list[dict], k: int) -> None:
        random.shuffle(pool)
        taken = 0
        for t in pool:
            if len(selected) >= n or taken >= k:
                return
            if t["sys_id"] in seen:
                continue
            seen.add(t["sys_id"])
            selected.append(t)
            taken += 1

    # Aim ~30% duplicates in golden set to mirror corpus; rest stratified by category.
    take(list(dupes), int(round(n * 0.30)))
    remaining = n - len(selected)
    per_cat = max(1, remaining // 4)
    for cat in CATEGORIES:
        pool = [
            t
            for t in by_cat[cat]
            if t["sys_id"] not in seen and not t["is_duplicate"]
        ]
        take(pool, per_cat)
    # Fill remainder preferring originals, then any leftover tickets.
    take([t for t in originals if t["sys_id"] not in seen], n - len(selected))
    take([t for t in tickets if t["sys_id"] not in seen], n - len(selected))

    golden = []
    for t in selected[:n]:
        golden.append(
            {
                "sys_id": t["sys_id"],
                "number": t["number"],
                "short_description": t["short_description"],
                "description": t["description"],
                "label_category": t["category"],
                "label_is_duplicate": t["is_duplicate"],
                "label_urgency": t["urgency"],
                "label_parent": t["parent"],
                "opened_at": t["opened_at"],
                "priority": t["priority"],
            }
        )
    golden.sort(key=lambda g: g["number"])
    return golden


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")


def summarize(agents: list[dict], tickets: list[dict], golden: list[dict]) -> dict:
    from collections import Counter

    cats = Counter(t["category"] for t in tickets)
    tiers = Counter(t["recency_tier"] for t in tickets)
    dupes = sum(1 for t in tickets if t["is_duplicate"])
    groups = Counter(a["assignment_group"] for a in agents)
    opened = [datetime.fromisoformat(t["opened_at"].replace("Z", "+00:00")) for t in tickets]
    return {
        "agents": len(agents),
        "agents_by_group": dict(groups),
        "tickets": len(tickets),
        "duplicate_count": dupes,
        "duplicate_rate": round(dupes / len(tickets), 4),
        "categories": dict(cats),
        "recency_tiers": dict(tiers),
        "opened_at_min": min(opened).isoformat().replace("+00:00", "Z"),
        "opened_at_max": max(opened).isoformat().replace("+00:00", "Z"),
        "golden_set": len(golden),
        "golden_dupes": sum(1 for g in golden if g["label_is_duplicate"]),
        "golden_categories": dict(Counter(g["label_category"] for g in golden)),
    }


def main() -> None:
    random.seed(SEED)
    root = Path(__file__).resolve().parents[1]
    data_dir = root / "data"

    agents = generate_agents()
    callers = generate_callers()
    tickets = generate_tickets(agents, callers)
    golden = generate_golden_set(tickets)

    write_json(data_dir / "agents.json", agents)
    write_json(data_dir / "tickets.json", tickets)
    write_json(data_dir / "golden-set.json", golden)

    meta = summarize(agents, tickets, golden)
    write_json(data_dir / "dataset-meta.json", meta)
    print(json.dumps(meta, indent=2))

    # Ops-density fields (activity, CI, hard_block) — separate RNG so base corpus stays stable.
    enrich_path = Path(__file__).resolve().parent / "enrich_ticket_density.py"
    if enrich_path.exists():
        import importlib.util

        spec = importlib.util.spec_from_file_location("enrich_ticket_density", enrich_path)
        mod = importlib.util.module_from_spec(spec) if spec else None
        if mod and spec and spec.loader:
            spec.loader.exec_module(mod)
            density = mod.enrich(tickets, agents)
            write_json(data_dir / "tickets.json", tickets)
            meta["ops_density"] = density
            write_json(data_dir / "dataset-meta.json", meta)
            print(json.dumps({"ops_density": density}, indent=2))
    else:
        print("enrich_ticket_density.py missing; skip density pass")


if __name__ == "__main__":
    main()

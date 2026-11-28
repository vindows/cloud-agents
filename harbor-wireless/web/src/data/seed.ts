import type {
  Agent,
  ArchivePolicy,
  OpsMetrics,
  QueueItem,
  QueueRecommendKind,
  Ticket,
  TicketCategory,
  TicketPriority,
  TicketState,
  TriageRun,
  TriageStep,
} from "../api/types";

/** Demo "now" — aligned with synthetic corpus. */
export const DEMO_NOW_MS = Date.UTC(2026, 10, 24);

export function ageDays(openedAt: string, nowMs = DEMO_NOW_MS): number {
  return Math.max(0, Math.floor((nowMs - new Date(openedAt).getTime()) / (24 * 3600 * 1000)));
}

export function waitLabel(days: number): string {
  if (days <= 0) return "<1d";
  if (days < 7) return `${days}d`;
  if (days < 30) return `${Math.floor(days / 7)}w ${days % 7}d`;
  if (days < 365) return `${Math.floor(days / 30)}mo`;
  return `${(days / 365).toFixed(1)}y`;
}

function buildWhyRecommend(
  ticket: Ticket,
  suggested: Agent | null,
  tickets: Ticket[],
): { why_here: string; recommend: string; recommend_kind: QueueRecommendKind } {
  if (ticket.hard_block) {
    return {
      why_here: `Hard block: ${ticket.hard_block.flags.join(", ")} — ${ticket.hard_block.reason}`,
      recommend: "Hold for human review (auto-archive locked)",
      recommend_kind: "human_review",
    };
  }
  if (ticket.is_duplicate || ticket.parent) {
    const parent = tickets.find((t) => t.sys_id === ticket.parent || t.number === ticket.parent);
    const parentLabel = parent?.number ?? ticket.parent ?? "parent";
    return {
      why_here: `Duplicate of ${parentLabel} — short_description overlap in ${ticket.category}`,
      recommend: `Mark duplicate of ${parentLabel}`,
      recommend_kind: "duplicate",
    };
  }
  if (ticket.triage_status === "archive_candidate" || (ticket.requester_inactive && ageDays(ticket.opened_at) > 365 * 3)) {
    return {
      why_here: `Archive candidate — age ${waitLabel(ageDays(ticket.opened_at))}${
        ticket.requester_inactive ? ", caller inactive" : ""
      }`,
      recommend: "Reject / archive under hybrid levers",
      recommend_kind: "archive",
    };
  }
  if ((ticket.confidence ?? 1) < 0.65) {
    return {
      why_here: `Low confidence (${Math.round((ticket.confidence ?? 0) * 100)}%) — classifier below HITL threshold`,
      recommend: suggested
        ? `Hold, then route to ${suggested.name} on confirm`
        : `Hold for human · ${ticket.assignment_group}`,
      recommend_kind: "human_review",
    };
  }
  const load = suggested ? `${suggested.active_load}/${suggested.capacity}` : "n/a";
  return {
    why_here: `Untriaged ${ticket.category} · P${ticket.priority} · wait ${waitLabel(ageDays(ticket.opened_at))}`,
    recommend: suggested
      ? `Route to ${suggested.name} (${suggested.assignment_group}, load ${load})`
      : `Route to ${ticket.assignment_group}`,
    recommend_kind: "route",
  };
}

const CATEGORIES: TicketCategory[] = ["access", "hardware", "network", "applications"];
const GROUPS: Record<TicketCategory, string> = {
  access: "HW-Access-Identity",
  hardware: "HW-Endpoint-Hardware",
  network: "HW-Network-Ops",
  applications: "HW-Enterprise-Apps",
};

const SHORTS: Record<TicketCategory, string[]> = {
  access: [
    "VPN MFA reset for field tech",
    "Okta group membership request",
    "Shared mailbox access — Finance",
    "Service account password rotation",
    "Contractor AD expire extension",
    "Privilege elevation for change window",
  ],
  hardware: [
    "Laptop battery swelling — replace",
    "Docking station no display signal",
    "Broken webcam on MacBook Pro",
    "Request dual monitors for new hire",
    "Badge printer offline — HQ floor 3",
    "Mobile hotspot device failure",
  ],
  network: [
    "Site-to-site VPN flap — Dallas POP",
    "Wi-Fi dead zone warehouse B",
    "Circuit utilization >90% Chicago",
    "DNS resolution failures for CDN",
    "Firewall rule for partner API",
    "Latency spike on MPLS to Phoenix",
  ],
  applications: [
    "Salesforce sync job stuck",
    "Workday leave request error",
    "Confluence space permission drift",
    "ServiceNow catalog item broken",
    "Teams meeting recording missing",
    "ERP report timeout after upgrade",
  ],
};

const FIRST = ["Avery", "Jordan", "Sam", "Riley", "Casey", "Quinn", "Morgan", "Taylor", "Alex", "Jamie"];
const LAST = ["Chen", "Patel", "Nguyen", "Garcia", "Kim", "Brooks", "Walsh", "Singh", "Ortiz", "Reed"];

function mulberry32(seed: number) {
  return () => {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function pick<T>(rand: () => number, arr: T[]): T {
  return arr[Math.floor(rand() * arr.length)]!;
}

function isoDaysAgo(rand: () => number, minDays: number, maxDays: number): string {
  const days = minDays + rand() * (maxDays - minDays);
  const d = new Date(Date.UTC(2026, 10, 24));
  d.setUTCDate(d.getUTCDate() - Math.floor(days));
  d.setUTCHours(Math.floor(rand() * 24), Math.floor(rand() * 60), 0, 0);
  return d.toISOString();
}

/** Demo subset (~180 tickets). Full ~6k sheet lands via data worker at harbor-wireless/data/. */
export function buildDemoTickets(count = 180): Ticket[] {
  const rand = mulberry32(42);
  const tickets: Ticket[] = [];
  const openParents: Ticket[] = [];

  for (let i = 0; i < count; i++) {
    const category = pick(rand, CATEGORIES);
    const short = pick(rand, SHORTS[category]);
    const tier = rand();
    let opened_at: string;
    if (tier < 0.25) opened_at = isoDaysAgo(rand, 0, 15);
    else if (tier < 0.55) opened_at = isoDaysAgo(rand, 16, 180);
    else opened_at = isoDaysAgo(rand, 181, 365 * 6);

    const ageYears =
      (Date.UTC(2026, 10, 24) - new Date(opened_at).getTime()) / (365.25 * 24 * 3600 * 1000);
    const isDup = rand() < 0.3 && openParents.length > 0 && category === openParents[0]?.category;
    const parent = isDup ? pick(rand, openParents.filter((t) => t.category === category)) : null;

    const priorityRoll = rand();
    const priority: TicketPriority =
      priorityRoll < 0.08 ? "1" : priorityRoll < 0.22 ? "2" : priorityRoll < 0.55 ? "3" : priorityRoll < 0.8 ? "4" : "5";

    let state: TicketState = "new";
    let triage_status: Ticket["triage_status"] = "untriaged";
    let assigned_to: string | null = null;
    let routed_at: string | null = null;

    if (parent) {
      state = "duplicate";
      triage_status = "routed";
    } else if (ageYears > 3 && rand() < 0.4) {
      state = rand() < 0.5 ? "archived" : "open";
      triage_status = state === "archived" ? "archived" : "archive_candidate";
    } else if (rand() < 0.45) {
      state = pick(rand, ["open", "in_progress", "pending"] as TicketState[]);
      triage_status = "routed";
      assigned_to = `agent-${Math.floor(rand() * 180) + 1}`;
      routed_at = new Date(new Date(opened_at).getTime() + rand() * 48 * 3600 * 1000).toISOString();
    } else if (rand() < 0.15) {
      state = "resolved";
      triage_status = "routed";
      assigned_to = `agent-${Math.floor(rand() * 180) + 1}`;
    }

    const inactive = ageYears > 2 && rand() < 0.55;
    const isHero = i < 12;
    const hard =
      short.toLowerCase().includes("privilege") || rand() < 0.04
        ? {
            flags: ["privileged_access" as const],
            reason: "Privileged-access request — no auto-archive; specialist must decide.",
            forces_human_review: true,
            locks_auto_archive: true,
          }
        : null;
    const ticket: Ticket = {
      sys_id: `sys${String(i + 1).padStart(6, "0")}`,
      number: `INC${String(1000000 + i)}`,
      short_description: short,
      description: `${short}. Opened by store/ops user. Synthetic Harbor Wireless IT ticket for CIO demo. Category hint: ${category}.`,
      category,
      priority,
      state,
      assignment_group: GROUPS[category],
      assigned_to,
      opened_at,
      caller_id: `caller-${Math.floor(rand() * 900) + 100}`,
      caller_name: `${pick(rand, FIRST)} ${pick(rand, LAST)}`,
      caller_user_name: `user${i}`,
      parent: parent?.sys_id ?? null,
      requester_inactive: inactive,
      urgency: Number(priority) <= 2 ? "high" : Number(priority) <= 3 ? "medium" : "low",
      impact: Number(priority) <= 2 ? "1 - High" : "2 - Medium",
      channel: pick(rand, ["portal", "email", "chat", "phone", "walk-up"]),
      urgency_score: Math.round((6 - Number(priority)) * 18 + rand() * 12),
      confidence: hard ? 0.52 : 0.55 + rand() * 0.4,
      routed_at,
      triage_status: hard && triage_status === "archive_candidate" ? "untriaged" : triage_status,
      cmdb_ci: {
        sys_id: `ci-seed-${i}`,
        name: pick(rand, ["Okta", "Salesforce", "eNodeB-LAS-14", "Dell Latitude 5440", "Teams"]),
        class: "Application",
      },
      hard_block: hard,
      demo_hero: isHero,
      activity: isHero
        ? [
            {
              at: opened_at,
              actor: "Caller",
              role: "Caller",
              kind: "comment",
              action: "Opened request",
              body: short,
            },
            {
              at: opened_at,
              actor: "System One",
              role: "AI",
              kind: "triage",
              action: "Classified",
              body: `Classified ${category}`,
              reason: "classify",
            },
          ]
        : [
            {
              at: opened_at,
              actor: "Caller",
              role: "Caller",
              kind: "comment",
              action: "Opened request",
              body: short,
            },
          ],
      assignment_history: [
        { at: opened_at, group: null, assignee: null, action: "Opened — unassigned" },
        {
          at: opened_at,
          group: GROUPS[category],
          assignee: assigned_to,
          action: assigned_to ? `Assigned to ${assigned_to}` : `Suggested ${GROUPS[category]}`,
        },
      ],
    };

    tickets.push(ticket);
    if (!parent && ["new", "open", "in_progress"].includes(state)) {
      openParents.push(ticket);
      if (openParents.length > 40) openParents.shift();
    }
  }

  return tickets;
}

export function buildDemoAgents(): Agent[] {
  const rand = mulberry32(99);
  const agents: Agent[] = [];
  let n = 0;
  for (const category of CATEGORIES) {
    const perGroup = 45;
    for (let i = 0; i < perGroup; i++) {
      n += 1;
      agents.push({
        id: `agent-${n}`,
        name: `${pick(rand, FIRST)} ${pick(rand, LAST)}`,
        email: `agent${n}@harborwireless.example`,
        assignment_group: GROUPS[category],
        category,
        active_load: Math.floor(rand() * 12),
        capacity: 12,
      });
    }
  }
  return agents;
}

export function buildOpsMetrics(tickets: Ticket[]): OpsMetrics {
  const handled = tickets.filter((t) => t.triage_status !== "untriaged");
  const byCat = CATEGORIES.map((category) => ({
    category,
    count: handled.filter((t) => t.category === category).length,
  }));
  const archived = tickets.filter((t) => t.state === "archived").length;
  const human = tickets.filter((t) => t.triage_status === "archive_candidate").length;
  const routed = tickets.filter((t) => t.triage_status === "routed" && t.state !== "duplicate").length;
  const dups = tickets.filter((t) => t.state === "duplicate").length;

  const daily: OpsMetrics["daily_volume"] = [];
  for (let i = 13; i >= 0; i--) {
    const d = new Date(Date.UTC(2026, 10, 24));
    d.setUTCDate(d.getUTCDate() - i);
    daily.push({
      date: d.toISOString().slice(0, 10),
      routed: 18 + ((i * 7) % 11),
      archived: 4 + ((i * 3) % 6),
      duplicates: 6 + ((i * 5) % 8),
    });
  }

  return {
    total_handled: handled.length,
    volume_by_category: byCat,
    avg_time_to_route_hours: 1.8,
    dedupe_rate: handled.length ? dups / handled.length : 0,
    archive_vs_human: { archived, human_review: human, routed },
    confidence_fallbacks: Math.round(handled.length * 0.08),
    daily_volume: daily,
    golden_set: {
      category_accuracy: 0.91,
      dedupe_precision: 0.88,
      dedupe_recall: 0.84,
      urgency_accuracy: 0.86,
    },
  };
}

export function buildQueue(tickets: Ticket[], agents: Agent[]): QueueItem[] {
  const open = tickets.filter(
    (t) =>
      (t.state === "new" ||
        t.state === "open" ||
        t.triage_status === "untriaged" ||
        t.triage_status === "archive_candidate" ||
        Boolean(t.hard_block)) &&
      t.state !== "duplicate" &&
      t.state !== "archived" &&
      t.state !== "resolved" &&
      t.state !== "closed",
  );
  const ranked = [...open].sort((a, b) => {
    const hb = Number(Boolean(b.hard_block)) - Number(Boolean(a.hard_block));
    if (hb) return hb;
    return (b.urgency_score ?? 0) - (a.urgency_score ?? 0);
  });
  return ranked.slice(0, 60).map((ticket, idx) => {
    const pool = agents
      .filter((a) => a.category === ticket.category)
      .sort((a, b) => a.active_load - b.active_load);
    const suggested = pool[0] ?? null;
    const days = ageDays(ticket.opened_at);
    const { why_here, recommend, recommend_kind } = buildWhyRecommend(ticket, suggested, tickets);
    const assignment_reason = suggested
      ? `${suggested.assignment_group} · lowest load (${suggested.active_load}/${suggested.capacity}) · category match ${ticket.category} · P${ticket.priority}`
      : `Route to ${ticket.assignment_group} — no idle agent; queue for next available.`;
    return {
      ticket,
      rank: idx + 1,
      urgency_score: ticket.urgency_score ?? 50,
      why_here,
      recommend,
      recommend_kind,
      suggested_agent: suggested,
      suggested_group: ticket.assignment_group,
      confidence: ticket.confidence ?? 0.8,
      assignment_reason,
      age_days: days,
      wait_label: waitLabel(days),
    };
  });
}

export function simulateTriage(ticket: Ticket, tickets: Ticket[], agents: Agent[]): TriageRun {
  const steps: TriageStep[] = [];
  const now = Date.now();
  const mk = (
    name: TriageStep["name"],
    reason: string,
    confidence: number,
    meta?: Record<string, unknown>,
    status: TriageStep["status"] = "done",
  ): TriageStep => ({
    id: `${ticket.sys_id}-${name}`,
    name,
    status,
    reason,
    confidence,
    started_at: new Date(now).toISOString(),
    finished_at: new Date(now + 400).toISOString(),
    meta,
  });

  const callerLabel = ticket.caller_name ?? ticket.caller_id;
  steps.push(
    mk(
      "intake",
      `Accepted ${ticket.number} via ${ticket.channel ?? "portal"}. Caller ${callerLabel}${
        ticket.requester_inactive ? " (inactive)" : ""
      }. Group ${ticket.assignment_group}.`,
      0.99,
      { source: "synthetic-snow", channel: ticket.channel },
    ),
  );
  steps.push(
    mk(
      "classify",
      `Classified as ${ticket.category} (BERT/Jev-shim). Top tokens aligned with ${ticket.assignment_group}${
        ticket.cmdb_ci ? ` · CI ${ticket.cmdb_ci.name}` : ""
      }.`,
      ticket.confidence ?? 0.87,
      { category: ticket.category, backend: "bert", provenance: "matched phrase set · golden-set baseline" },
    ),
  );

  const dup = tickets.find(
    (t) =>
      t.sys_id !== ticket.sys_id &&
      t.category === ticket.category &&
      t.short_description === ticket.short_description &&
      ["open", "in_progress", "new"].includes(t.state),
  );
  const parentHit =
    dup ?? tickets.find((t) => t.sys_id === ticket.parent || t.number === ticket.parent);
  if (parentHit || ticket.parent) {
    steps.push(
      mk(
        "dedupe",
        `Likely duplicate of ${parentHit?.number ?? ticket.parent} — same short description and open ${ticket.category} parent.`,
        0.9,
        { duplicate_of: parentHit?.sys_id ?? ticket.parent, provenance: "parent INC by short_description overlap" },
      ),
    );
  } else {
    steps.push(mk("dedupe", "No open near-duplicate found in active backlog (cosine + field match).", 0.82));
  }

  steps.push(
    mk(
      "priority",
      `Urgency ${ticket.urgency ?? "n/a"} · impact ${ticket.impact ?? "n/a"} → P${ticket.priority} (score ${ticket.urgency_score}/100).`,
      0.84,
      { priority: ticket.priority, urgency_score: ticket.urgency_score },
    ),
  );

  if (ticket.hard_block) {
    steps.push(
      mk(
        "route",
        `Hard block (${ticket.hard_block.flags.join(", ")}): ${ticket.hard_block.reason}`,
        0.95,
        { hard_block: ticket.hard_block },
      ),
    );
    steps.push({
      id: `${ticket.sys_id}-archive`,
      name: "archive",
      status: "skipped",
      reason: "Skipped — auto-archive locked by hard block.",
      confidence: 0,
    });
    return {
      ticket_sys_id: ticket.sys_id,
      steps,
      final_action: "human-review",
      assignment_group: ticket.assignment_group,
    };
  }

  const ageYears =
    (DEMO_NOW_MS - new Date(ticket.opened_at).getTime()) / (365.25 * 24 * 3600 * 1000);
  const archiveCandidate = ageYears >= 3 && (ticket.requester_inactive ?? false);

  if (archiveCandidate) {
    steps.push(
      mk(
        "archive",
        `Age ${ageYears.toFixed(1)}y and requester inactive — hybrid archive candidate; awaiting policy lever.`,
        0.78,
        { age_years: ageYears },
      ),
    );
    steps.push({
      id: `${ticket.sys_id}-route`,
      name: "route",
      status: "skipped",
      reason: "Skipped — archive path selected.",
      confidence: 0,
    });
    return {
      ticket_sys_id: ticket.sys_id,
      steps,
      final_action: "archive-candidate",
    };
  }

  const agent =
    agents
      .filter((a) => a.category === ticket.category)
      .sort((a, b) => a.active_load - b.active_load)[0] ?? null;

  steps.push(
    mk(
      "route",
      agent
        ? `Auto-assign to ${agent.name} (${agent.assignment_group}) — load ${agent.active_load}/${agent.capacity}.`
        : `Park on ${ticket.assignment_group} queue.`,
      agent ? 0.88 : 0.7,
      { assigned_to: agent?.id, assignment_group: ticket.assignment_group },
    ),
  );
  steps.push({
    id: `${ticket.sys_id}-archive`,
    name: "archive",
    status: "skipped",
    reason: "Skipped — ticket routed; not an archive candidate under current levers.",
    confidence: 0,
  });

  return {
    ticket_sys_id: ticket.sys_id,
    steps,
    final_action: (ticket.confidence ?? 1) < 0.65 ? "human-review" : "route",
    assigned_to: agent?.name ?? agent?.id,
    assignment_group: ticket.assignment_group,
    duplicate_of: parentHit?.sys_id,
  };
}

export const defaultArchivePolicy: ArchivePolicy = {
  mode: "hybrid",
  age_years: 3,
  inactive_days: 365,
};

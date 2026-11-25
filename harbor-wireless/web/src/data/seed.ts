import type {
  Agent,
  ArchivePolicy,
  OpsMetrics,
  QueueItem,
  Ticket,
  TicketCategory,
  TicketPriority,
  TicketState,
  TriageRun,
  TriageStep,
} from "../api/types";

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
      parent: parent?.sys_id ?? null,
      requester_inactive: ageYears > 2 && rand() < 0.55,
      urgency_score: Math.round((6 - Number(priority)) * 18 + rand() * 12),
      confidence: 0.55 + rand() * 0.4,
      routed_at,
      triage_status,
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
      (t.state === "new" || t.state === "open" || t.triage_status === "untriaged") &&
      t.state !== "duplicate" &&
      t.state !== "archived",
  );
  const ranked = [...open].sort((a, b) => (b.urgency_score ?? 0) - (a.urgency_score ?? 0));
  return ranked.slice(0, 40).map((ticket, idx) => {
    const pool = agents
      .filter((a) => a.category === ticket.category)
      .sort((a, b) => a.active_load - b.active_load);
    const suggested = pool[0] ?? null;
    return {
      ticket,
      rank: idx + 1,
      urgency_score: ticket.urgency_score ?? 50,
      suggested_agent: suggested,
      suggested_group: ticket.assignment_group,
      confidence: ticket.confidence ?? 0.8,
      assignment_reason: suggested
        ? `${suggested.assignment_group} · lowest load (${suggested.active_load}/${suggested.capacity}) · category match ${ticket.category} · P${ticket.priority} urgency ${ticket.urgency_score}`
        : `Route to ${ticket.assignment_group} — no idle agent; queue for next available.`,
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

  steps.push(
    mk("intake", `Accepted ${ticket.number} from ServiceNow-shaped intake. Caller ${ticket.caller_id}.`, 0.99, {
      source: "synthetic-snow",
    }),
  );
  steps.push(
    mk(
      "classify",
      `Classified as ${ticket.category} (BERT/Jev-shim). Top tokens aligned with ${ticket.assignment_group}.`,
      ticket.confidence ?? 0.87,
      { category: ticket.category, backend: "bert" },
    ),
  );

  const dup = tickets.find(
    (t) =>
      t.sys_id !== ticket.sys_id &&
      t.category === ticket.category &&
      t.short_description === ticket.short_description &&
      ["open", "in_progress", "new"].includes(t.state),
  );
  if (dup || ticket.parent) {
    const target = dup ?? tickets.find((t) => t.sys_id === ticket.parent);
    steps.push(
      mk(
        "dedupe",
        `Likely duplicate of ${target?.number ?? ticket.parent} — same short description and open ${ticket.category} parent.`,
        0.9,
        { duplicate_of: target?.sys_id ?? ticket.parent },
      ),
    );
  } else {
    steps.push(mk("dedupe", "No open near-duplicate found in active backlog (cosine + field match).", 0.82));
  }

  steps.push(
    mk(
      "priority",
      `Urgency score ${ticket.urgency_score}/100 → priority P${ticket.priority}. Factors: age band, keyword severity, requester impact.`,
      0.84,
      { priority: ticket.priority, urgency_score: ticket.urgency_score },
    ),
  );

  const ageYears =
    (Date.UTC(2026, 10, 24) - new Date(ticket.opened_at).getTime()) / (365.25 * 24 * 3600 * 1000);
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
    assigned_to: agent?.id,
    assignment_group: ticket.assignment_group,
    duplicate_of: (dup ?? tickets.find((t) => t.sys_id === ticket.parent))?.sys_id,
  };
}

export const defaultArchivePolicy: ArchivePolicy = {
  mode: "hybrid",
  age_years: 3,
  inactive_days: 365,
};

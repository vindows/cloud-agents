import type {
  ActivityEntry,
  Agent,
  AssignmentHistoryEntry,
  CmdbCi,
  HardBlock,
  HardBlockFlag,
  Ticket,
  TicketCategory,
  TicketPriority,
  TicketState,
} from "./types";

/** Raw shapes from harbor-wireless/data/*.json (data worker). */
type RawPerson = string | { sys_id?: string; name?: string; user_name?: string; active?: boolean } | null;

export interface RawTicket {
  sys_id: string;
  number: string;
  short_description: string;
  description: string;
  category: string;
  priority: string | number;
  urgency?: string;
  impact?: string;
  state: string;
  assignment_group: string;
  assigned_to: RawPerson;
  opened_at: string;
  caller_id: RawPerson;
  parent?: string | null;
  is_duplicate?: boolean;
  recency_tier?: string;
  channel?: string;
  cmdb_ci?: CmdbCi | null;
  hard_block?: HardBlock | null;
  activity?: ActivityEntry[];
  assignment_history?: AssignmentHistoryEntry[];
  demo_hero?: boolean;
}

export interface RawAgent {
  sys_id: string;
  name: string;
  email: string;
  assignment_group: string;
  category: string;
  active?: boolean;
  role?: string;
}

const CATEGORIES: TicketCategory[] = ["access", "hardware", "network", "applications"];
const HARD_FLAGS: HardBlockFlag[] = ["vip", "security", "privileged_access"];

function personRef(raw: RawPerson): { id: string | null; name?: string; user_name?: string; active: boolean } {
  if (raw == null) return { id: null, active: true };
  if (typeof raw === "string") return { id: raw, active: true };
  return {
    id: raw.sys_id ?? raw.user_name ?? raw.name ?? null,
    name: raw.name,
    user_name: raw.user_name,
    active: raw.active ?? true,
  };
}

function normalizeHardBlock(raw: HardBlock | null | undefined): HardBlock | null {
  if (!raw || !Array.isArray(raw.flags) || !raw.flags.length) return null;
  const flags = raw.flags.filter((f): f is HardBlockFlag => HARD_FLAGS.includes(f as HardBlockFlag));
  if (!flags.length) return null;
  return {
    flags,
    reason: raw.reason || "Requires human review.",
    forces_human_review: raw.forces_human_review ?? true,
    locks_auto_archive: raw.locks_auto_archive ?? true,
  };
}

export function normalizeTicket(raw: RawTicket): Ticket {
  const caller = personRef(raw.caller_id);
  const assignee = personRef(raw.assigned_to);
  const hard_block = normalizeHardBlock(raw.hard_block);

  const priority = parsePriority(raw.priority, raw.urgency);
  const state = parseState(raw.state, Boolean(raw.is_duplicate || raw.parent));
  const category = (CATEGORIES.includes(raw.category as TicketCategory)
    ? raw.category
    : "applications") as TicketCategory;

  const urgency_score =
    raw.urgency === "critical"
      ? 95
      : raw.urgency === "high"
        ? 80
        : raw.urgency === "medium"
          ? 55
          : raw.urgency === "low"
            ? 30
            : Math.round((6 - Number(priority)) * 18);

  let triage_status: Ticket["triage_status"] = "untriaged";
  if (state === "archived") triage_status = "archived";
  else if (state === "duplicate") triage_status = "routed";
  else if (state === "resolved" || state === "closed") triage_status = "routed";
  else if (hard_block?.forces_human_review && !assignee.id && state === "new") {
    triage_status = "untriaged";
  } else if (assignee.id || state === "in_progress" || state === "open" || state === "pending") {
    triage_status = "routed";
  } else if (raw.recency_tier === "stale" && !caller.active) {
    triage_status = "archive_candidate";
  }

  // Hard blocks never sit as silent archive candidates — force the HITL path.
  if (hard_block?.locks_auto_archive && triage_status === "archive_candidate") {
    triage_status = "untriaged";
  }

  let confidence = 0.72 + (Number(priority) <= 2 ? 0.1 : 0.05);
  if (hard_block) confidence = Math.min(confidence, 0.55);
  if (raw.demo_hero && Number(priority) >= 4) confidence = Math.min(confidence, 0.68);

  return {
    sys_id: raw.sys_id,
    number: raw.number,
    short_description: raw.short_description,
    description: raw.description,
    category,
    priority,
    priority_label: String(raw.priority),
    state,
    assignment_group: raw.assignment_group,
    assigned_to: assignee.name ?? assignee.id,
    opened_at: raw.opened_at,
    caller_id: caller.id ?? "unknown",
    caller_name: caller.name,
    caller_user_name: caller.user_name,
    parent: raw.parent ?? null,
    requester_inactive: !caller.active,
    urgency_score,
    urgency: raw.urgency,
    impact: raw.impact,
    channel: raw.channel,
    confidence,
    triage_status,
    recency_tier: raw.recency_tier,
    is_duplicate: Boolean(raw.is_duplicate || raw.parent),
    cmdb_ci: raw.cmdb_ci ?? null,
    hard_block,
    activity: raw.activity ?? [],
    assignment_history: raw.assignment_history ?? [],
    demo_hero: Boolean(raw.demo_hero),
  };
}

export function normalizeAgent(raw: RawAgent, index: number): Agent {
  const category = (CATEGORIES.includes(raw.category as TicketCategory)
    ? raw.category
    : "applications") as TicketCategory;
  return {
    id: raw.sys_id,
    name: raw.name,
    email: raw.email,
    assignment_group: raw.assignment_group,
    category,
    active_load: index % 12,
    capacity: 12,
  };
}

function parsePriority(priority: string | number, urgency?: string): TicketPriority {
  if (typeof priority === "number") {
    const n = Math.min(5, Math.max(1, Math.round(priority)));
    return String(n) as TicketPriority;
  }
  const m = String(priority).match(/(\d)/);
  if (m) return m[1] as TicketPriority;
  if (urgency === "critical") return "1";
  if (urgency === "high") return "2";
  if (urgency === "medium") return "3";
  if (urgency === "low") return "4";
  return "3";
}

function parseState(state: string, isDup: boolean): TicketState {
  if (isDup) return "duplicate";
  const s = state.toLowerCase().replace(/\s+/g, "_");
  const map: Record<string, TicketState> = {
    new: "new",
    open: "open",
    in_progress: "in_progress",
    "in-progress": "in_progress",
    on_hold: "pending",
    pending: "pending",
    resolved: "resolved",
    closed: "closed",
    canceled: "closed",
    cancelled: "closed",
    archived: "archived",
    duplicate: "duplicate",
  };
  return map[s] ?? "open";
}

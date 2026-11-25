import type { Agent, Ticket, TicketCategory, TicketPriority, TicketState } from "./types";

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
  state: string;
  assignment_group: string;
  assigned_to: RawPerson;
  opened_at: string;
  caller_id: RawPerson;
  parent?: string | null;
  is_duplicate?: boolean;
  recency_tier?: string;
  channel?: string;
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

function personRef(raw: RawPerson): { id: string | null; name?: string; active: boolean } {
  if (raw == null) return { id: null, active: true };
  if (typeof raw === "string") return { id: raw, active: true };
  return {
    id: raw.sys_id ?? raw.user_name ?? raw.name ?? null,
    name: raw.name,
    active: raw.active ?? true,
  };
}

export function normalizeTicket(raw: RawTicket): Ticket {
  const caller = personRef(raw.caller_id);
  const assignee = personRef(raw.assigned_to);

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
  else if (assignee.id || state === "in_progress" || state === "open" || state === "pending") {
    triage_status = "routed";
  } else if (raw.recency_tier === "stale" && !caller.active) {
    triage_status = "archive_candidate";
  }

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
    parent: raw.parent ?? null,
    requester_inactive: !caller.active,
    urgency_score,
    confidence: 0.72 + (Number(priority) <= 2 ? 0.1 : 0.05),
    triage_status,
    recency_tier: raw.recency_tier,
    is_duplicate: Boolean(raw.is_duplicate || raw.parent),
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
    pending: "pending",
    resolved: "resolved",
    closed: "closed",
    archived: "archived",
    duplicate: "duplicate",
  };
  return map[s] ?? "open";
}

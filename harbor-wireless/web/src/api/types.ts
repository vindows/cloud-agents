/** ServiceNow-shaped ticket + pipeline contracts shared with data/pipeline workers. */

export type TicketCategory = "access" | "hardware" | "network" | "applications";
export type TicketState =
  | "new"
  | "open"
  | "in_progress"
  | "pending"
  | "resolved"
  | "closed"
  | "archived"
  | "duplicate";
export type TicketPriority = "1" | "2" | "3" | "4" | "5";
export type ArchiveMode = "auto" | "human" | "hybrid";

export type TriageStepName =
  | "intake"
  | "classify"
  | "dedupe"
  | "priority"
  | "route"
  | "archive"
  | "archive-candidate";

export interface Ticket {
  sys_id: string;
  number: string;
  short_description: string;
  description: string;
  category: TicketCategory;
  priority: TicketPriority;
  priority_label?: string;
  state: TicketState;
  assignment_group: string;
  assigned_to: string | null;
  opened_at: string;
  caller_id: string;
  caller_name?: string;
  parent?: string | null;
  requester_inactive?: boolean;
  urgency_score?: number;
  confidence?: number;
  routed_at?: string | null;
  triage_status?: "untriaged" | "triaging" | "routed" | "archive_candidate" | "archived";
  recency_tier?: string;
  is_duplicate?: boolean;
}

export interface Agent {
  id: string;
  name: string;
  email: string;
  assignment_group: string;
  category: TicketCategory;
  active_load: number;
  capacity: number;
}

export interface TriageStep {
  id: string;
  name: TriageStepName;
  status: "pending" | "running" | "done" | "skipped";
  reason: string;
  confidence: number;
  started_at?: string;
  finished_at?: string;
  meta?: Record<string, unknown>;
}

export interface TriageRun {
  ticket_sys_id: string;
  steps: TriageStep[];
  final_action: "route" | "archive-candidate" | "human-review" | "archived" | "duplicate";
  assigned_to?: string | null;
  assignment_group?: string | null;
  duplicate_of?: string | null;
}

export interface QueueItem {
  ticket: Ticket;
  rank: number;
  urgency_score: number;
  assignment_reason: string;
  suggested_agent: Agent | null;
  suggested_group: string;
  confidence: number;
}

export interface OpsMetrics {
  total_handled: number;
  volume_by_category: { category: TicketCategory; count: number }[];
  avg_time_to_route_hours: number;
  dedupe_rate: number;
  archive_vs_human: { archived: number; human_review: number; routed: number };
  confidence_fallbacks: number;
  daily_volume: { date: string; routed: number; archived: number; duplicates: number }[];
  golden_set?: {
    category_accuracy: number;
    dedupe_precision: number;
    dedupe_recall: number;
    urgency_accuracy: number;
  };
  source?: "pipeline" | "seed";
}

/** Matches pipeline ArchiveLeverConfig */
export interface ArchivePolicy {
  mode: ArchiveMode;
  age_years: number;
  inactive_days: number;
}

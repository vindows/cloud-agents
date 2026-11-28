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

export type ActivityKind = "comment" | "work_note" | "triage";

export interface ActivityEntry {
  at: string;
  actor: string;
  role: string;
  kind: ActivityKind;
  action: string;
  body: string;
  reason?: string | null;
}

export interface AssignmentHistoryEntry {
  at: string;
  group: string | null;
  assignee: string | null;
  action: string;
}

export interface CmdbCi {
  sys_id: string;
  name: string;
  class: string;
}

export type HardBlockFlag = "vip" | "security" | "privileged_access";

export interface HardBlock {
  flags: HardBlockFlag[];
  reason: string;
  forces_human_review: boolean;
  locks_auto_archive: boolean;
}

export type HitlDecision = "approve_route" | "hold_human" | "reject_archive";

export type HitlOverrideReason =
  | "wrong_category"
  | "not_duplicate"
  | "vip_high_risk"
  | "policy"
  | "other";

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
  caller_user_name?: string;
  parent?: string | null;
  requester_inactive?: boolean;
  urgency_score?: number;
  urgency?: string;
  impact?: string;
  channel?: string;
  confidence?: number;
  routed_at?: string | null;
  triage_status?: "untriaged" | "triaging" | "routed" | "archive_candidate" | "archived";
  recency_tier?: string;
  is_duplicate?: boolean;
  cmdb_ci?: CmdbCi | null;
  hard_block?: HardBlock | null;
  activity?: ActivityEntry[];
  assignment_history?: AssignmentHistoryEntry[];
  demo_hero?: boolean;
  hitl_decision?: HitlDecision | null;
  hitl_override_reason?: HitlOverrideReason | null;
  hitl_note?: string | null;
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

export type QueueRecommendKind = "route" | "duplicate" | "archive" | "human_review";

export interface QueueItem {
  ticket: Ticket;
  rank: number;
  urgency_score: number;
  /** Why this ticket is in the queue / escalated. */
  why_here: string;
  /** Suggested next action (route / dup / archive / human). */
  recommend: string;
  recommend_kind: QueueRecommendKind;
  assignment_reason: string;
  suggested_agent: Agent | null;
  suggested_group: string;
  confidence: number;
  age_days: number;
  wait_label: string;
}

export type QueueLane =
  | "all"
  | "untriaged"
  | "low_confidence"
  | "archive_candidates"
  | "duplicates"
  | "routed_today";

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

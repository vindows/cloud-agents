/**
 * Data + pipeline adapters.
 * Prefer harbor-wireless/data (/demo-data) + pipeline on :8080; seed fallback.
 *
 * Env:
 *   VITE_DATA_BASE     — default /demo-data
 *   VITE_PIPELINE_URL  — default http://127.0.0.1:8080
 */

import type {
  Agent,
  ArchivePolicy,
  OpsMetrics,
  QueueItem,
  Ticket,
  TicketCategory,
  TriageRun,
  TriageStep,
  TriageStepName,
} from "./types";
import { normalizeAgent, normalizeTicket, type RawAgent, type RawTicket } from "./normalize";
import {
  buildDemoAgents,
  buildDemoTickets,
  buildOpsMetrics,
  buildQueue,
  defaultArchivePolicy,
  simulateTriage,
} from "../data/seed";

const DATA_BASE = import.meta.env.VITE_DATA_BASE ?? "/demo-data";
const PIPELINE_URL = import.meta.env.VITE_PIPELINE_URL ?? "http://127.0.0.1:8080";

async function tryJson<T>(url: string, init?: RequestInit): Promise<T | null> {
  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(8000), ...init });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

let ticketCache: Ticket[] | null = null;
let agentCache: Agent[] | null = null;
let ticketSource: "remote" | "seed" = "seed";
let policyCache: ArchivePolicy = { ...defaultArchivePolicy };

export async function loadTickets(): Promise<{ tickets: Ticket[]; source: "remote" | "seed" }> {
  if (ticketCache) return { tickets: ticketCache, source: ticketSource };

  const remote = await tryJson<RawTicket[]>(`${DATA_BASE}/tickets.json`);
  if (remote && Array.isArray(remote) && remote.length) {
    ticketCache = remote.map(normalizeTicket);
    ticketSource = "remote";
    return { tickets: ticketCache, source: "remote" };
  }

  ticketCache = buildDemoTickets(180);
  ticketSource = "seed";
  return { tickets: ticketCache, source: "seed" };
}

export async function loadAgents(): Promise<{ agents: Agent[]; source: "remote" | "seed" }> {
  if (agentCache) return { agents: agentCache, source: "remote" };
  const remote = await tryJson<RawAgent[]>(`${DATA_BASE}/agents.json`);
  if (remote && Array.isArray(remote) && remote.length) {
    agentCache = remote.map(normalizeAgent);
    return { agents: agentCache, source: "remote" };
  }
  agentCache = buildDemoAgents();
  return { agents: agentCache, source: "seed" };
}

interface PipelineMetrics {
  handled?: number;
  dedupe_rate?: number;
  human_fallback_rate?: number;
  by_category?: Record<string, number>;
  outcomes?: Record<string, number>;
  avg_step_ms?: Record<string, number>;
}

export async function loadMetrics(tickets: Ticket[]): Promise<OpsMetrics> {
  const remote = await tryJson<PipelineMetrics>(`${PIPELINE_URL}/metrics`);
  if (remote && typeof remote.handled === "number") {
    const outcomes = remote.outcomes ?? {};
    const cats = (["access", "hardware", "network", "applications"] as TicketCategory[]).map(
      (category) => ({
        category,
        count: remote.by_category?.[category] ?? 0,
      }),
    );
    const routeMs = remote.avg_step_ms?.route ?? 0;
    return {
      total_handled: remote.handled,
      volume_by_category: cats.some((c) => c.count > 0) ? cats : buildOpsMetrics(tickets).volume_by_category,
      avg_time_to_route_hours: routeMs > 0 ? routeMs / 3_600_000 : buildOpsMetrics(tickets).avg_time_to_route_hours,
      dedupe_rate: remote.dedupe_rate ?? 0,
      archive_vs_human: {
        archived: outcomes.archived ?? 0,
        human_review: (outcomes.archive_candidate ?? 0) + (outcomes.needs_human ?? 0),
        routed: outcomes.routed ?? 0,
      },
      confidence_fallbacks: outcomes.needs_human ?? Math.round(remote.handled * (remote.human_fallback_rate ?? 0)),
      daily_volume: buildOpsMetrics(tickets).daily_volume,
      golden_set: buildOpsMetrics(tickets).golden_set,
      source: "pipeline",
    };
  }
  return { ...buildOpsMetrics(tickets), source: "seed" };
}

export async function loadQueue(tickets: Ticket[], agents: Agent[]): Promise<QueueItem[]> {
  return buildQueue(tickets, agents);
}

interface PipelineStep {
  step: string;
  action?: string;
  reason: string;
  confidence: number;
  detail?: Record<string, unknown>;
  needs_human?: boolean;
  started_at?: string;
  finished_at?: string;
}

interface PipelineResult {
  ticket?: {
    sys_id?: string;
    assigned_to?: string | { name?: string; user_name?: string; sys_id?: string } | null;
    assignment_group?: string;
    parent?: string | null;
  };
  steps: PipelineStep[];
  outcome: string;
  archive?: { candidate?: boolean; auto_applied?: boolean } | null;
}

export async function runTriage(ticket: Ticket, tickets: Ticket[], agents: Agent[]): Promise<TriageRun> {
  try {
    const res = await fetch(`${PIPELINE_URL}/triage/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ticket: {
          sys_id: ticket.sys_id,
          number: ticket.number,
          short_description: ticket.short_description,
          description: ticket.description,
          category: ticket.category,
          priority: ticket.priority_label ?? ticket.priority,
          state: ticket.state,
          assignment_group: ticket.assignment_group,
          assigned_to: ticket.assigned_to,
          opened_at: ticket.opened_at,
          caller_id: ticket.caller_id,
          parent: ticket.parent,
        },
        archive: policyCache,
        dry_run: false,
      }),
      signal: AbortSignal.timeout(12000),
    });
    if (res.ok) {
      const body = (await res.json()) as PipelineResult;
      if (body.steps?.length) return mapPipelineResult(body, ticket);
    }
  } catch {
    /* seed simulation */
  }
  return simulateTriage(ticket, tickets, agents);
}

function mapPipelineResult(body: PipelineResult, fallback: Ticket): TriageRun {
  const steps: TriageStep[] = body.steps.map((s, i) => {
    const name = normalizeStepName(s.step);
    const skipped = s.action === "skip" || s.action === "skipped";
    return {
      id: `${fallback.sys_id}-${name}-${i}`,
      name,
      status: skipped ? "skipped" : "done",
      reason: s.reason,
      confidence: s.confidence,
      started_at: s.started_at,
      finished_at: s.finished_at,
      meta: s.detail,
    };
  });

  const assigned = body.ticket?.assigned_to;
  const assignedStr =
    typeof assigned === "string"
      ? assigned
      : assigned?.name ?? assigned?.user_name ?? assigned?.sys_id ?? null;

  const outcome = body.outcome;
  let final_action: TriageRun["final_action"] = "route";
  if (outcome === "archived") final_action = "archived";
  else if (outcome === "archive_candidate") final_action = "archive-candidate";
  else if (outcome === "needs_human") final_action = "human-review";
  else if (outcome === "duplicate") final_action = "duplicate";

  return {
    ticket_sys_id: body.ticket?.sys_id ?? fallback.sys_id,
    steps,
    final_action,
    assigned_to: assignedStr,
    assignment_group: body.ticket?.assignment_group ?? fallback.assignment_group,
    duplicate_of: body.ticket?.parent ?? null,
  };
}

function normalizeStepName(step: string): TriageStepName {
  if (step === "archive-candidate" || step === "archive") return "archive";
  if (
    step === "intake" ||
    step === "classify" ||
    step === "dedupe" ||
    step === "priority" ||
    step === "route"
  ) {
    return step;
  }
  return "classify";
}

export function getArchivePolicy(): ArchivePolicy {
  return { ...policyCache };
}

export async function fetchArchivePolicy(): Promise<ArchivePolicy> {
  const remote = await tryJson<ArchivePolicy>(`${PIPELINE_URL}/archive/levers`);
  if (remote && remote.mode) {
    policyCache = {
      mode: remote.mode,
      age_years: remote.age_years ?? 3,
      inactive_days: remote.inactive_days ?? 365,
    };
  }
  return { ...policyCache };
}

export function setArchivePolicy(next: ArchivePolicy): ArchivePolicy {
  policyCache = {
    mode: next.mode,
    age_years: next.age_years,
    inactive_days: next.inactive_days ?? 365,
  };
  void fetch(`${PIPELINE_URL}/archive/levers`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(policyCache),
  }).catch(() => undefined);
  return { ...policyCache };
}

export function applyArchivePolicy(tickets: Ticket[], policy: ArchivePolicy): Ticket[] {
  const now = Date.UTC(2026, 10, 24);
  return tickets.map((t) => {
    if (t.state === "duplicate" || t.state === "archived" || t.state === "resolved" || t.state === "closed") {
      return t;
    }
    const ageYears = (now - new Date(t.opened_at).getTime()) / (365.25 * 24 * 3600 * 1000);
    const ageOk = ageYears >= policy.age_years;
    if (!ageOk) return t;

    const inactiveOk = Boolean(t.requester_inactive);

    if (policy.mode === "auto") {
      return { ...t, state: "archived", triage_status: "archived" };
    }
    if (policy.mode === "human") {
      return { ...t, triage_status: "archive_candidate" };
    }
    // hybrid: auto only when age + inactive
    if (inactiveOk) {
      return { ...t, state: "archived", triage_status: "archived" };
    }
    return { ...t, triage_status: "archive_candidate" };
  });
}

export function invalidateCaches() {
  ticketCache = null;
  agentCache = null;
}

export { PIPELINE_URL };

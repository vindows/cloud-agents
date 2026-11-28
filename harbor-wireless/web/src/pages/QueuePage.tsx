import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { QueueLane } from "../api/types";
import { DEMO_NOW_MS } from "../data/seed";
import { useDemo } from "../state/DemoStore";

const LANES: { id: QueueLane; label: string }[] = [
  { id: "all", label: "All in queue" },
  { id: "untriaged", label: "Untriaged" },
  { id: "low_confidence", label: "Low confidence" },
  { id: "archive_candidates", label: "Archive candidates" },
  { id: "duplicates", label: "Duplicates" },
  { id: "routed_today", label: "Routed today" },
];

export function QueuePage() {
  const { queue, tickets, startTriage, triagingId } = useDemo();
  const [lane, setLane] = useState<QueueLane>("all");

  const laneCounts = useMemo(() => {
    const today = new Date(DEMO_NOW_MS).toISOString().slice(0, 10);
    return {
      all: queue.length,
      untriaged: tickets.filter((t) => t.triage_status === "untriaged").length,
      low_confidence: tickets.filter((t) => (t.confidence ?? 1) < 0.65).length,
      archive_candidates: tickets.filter((t) => t.triage_status === "archive_candidate").length,
      duplicates: tickets.filter((t) => t.is_duplicate || t.state === "duplicate").length,
      routed_today: tickets.filter((t) => t.routed_at?.slice(0, 10) === today).length,
    } satisfies Record<QueueLane, number>;
  }, [queue, tickets]);

  const filtered = useMemo(() => {
    if (lane === "all") return queue;
    return queue.filter((item) => {
      const t = item.ticket;
      if (lane === "untriaged") return t.triage_status === "untriaged";
      if (lane === "low_confidence") return item.confidence < 0.65;
      if (lane === "archive_candidates") return t.triage_status === "archive_candidate" || item.recommend_kind === "archive";
      if (lane === "duplicates") return t.is_duplicate || item.recommend_kind === "duplicate";
      if (lane === "routed_today") {
        const today = new Date(DEMO_NOW_MS).toISOString().slice(0, 10);
        return t.routed_at?.slice(0, 10) === today;
      }
      return true;
    });
  }, [queue, lane]);

  return (
    <div>
      <div className="page-head">
        <h1>Priority & auto-assign</h1>
        <p>Ranked work for category agents. Age, why here, and System One recommend — one column of work.</p>
      </div>

      <div className="lane-tiles" role="tablist" aria-label="Queue lanes">
        {LANES.map((l) => (
          <button
            key={l.id}
            type="button"
            role="tab"
            aria-selected={lane === l.id}
            className="lane-tile"
            data-active={lane === l.id}
            onClick={() => setLane(l.id)}
          >
            <span className="lane-count mono">{laneCounts[l.id]}</span>
            <span className="lane-label">{l.label}</span>
          </button>
        ))}
      </div>

      <div className="queue-list">
        <div className="queue-header">
          <span>Age</span>
          <span>Ticket</span>
          <span>Why here</span>
          <span>Recommend</span>
          <span>Conf</span>
        </div>
        {filtered.map((item) => (
          <div className="queue-item dense" key={item.ticket.sys_id}>
            <div className={`age-chip ${item.age_days >= 13 ? "stale" : item.age_days >= 3 ? "warm" : ""}`}>
              <span className="mono">{item.wait_label}</span>
            </div>
            <div>
              <div className="queue-meta">
                <span className="rank mono">{item.rank}</span>
                <Link to={`/tickets/${item.ticket.sys_id}`} className="mono" style={{ color: "var(--hw-signal)" }}>
                  {item.ticket.number}
                </Link>
                <span>P{item.ticket.priority}</span>
                <span style={{ color: "var(--hw-slate)" }}>{item.ticket.category}</span>
                {item.ticket.channel && (
                  <span style={{ color: "var(--hw-slate)" }}>{item.ticket.channel}</span>
                )}
                {item.ticket.hard_block && <span className="status flare">hard block</span>}
              </div>
              <div style={{ fontWeight: 650, marginTop: 2 }}>{item.ticket.short_description}</div>
              <p className="why muted">
                {item.ticket.assignment_group}
                {item.suggested_agent ? ` · ${item.suggested_agent.name}` : ""}
              </p>
            </div>
            <p className="why">{item.why_here}</p>
            <p className="recommend">{item.recommend}</p>
            <div style={{ textAlign: "right" }}>
              <div className={`conf ${item.confidence < 0.65 ? "low" : ""}`}>
                {Math.round(item.confidence * 100)}%
              </div>
              <button
                className="btn ghost"
                style={{ marginTop: 8 }}
                disabled={Boolean(triagingId)}
                onClick={() => void startTriage(item.ticket)}
              >
                Triage
              </button>
            </div>
          </div>
        ))}
        {!filtered.length && (
          <div style={{ padding: 24, color: "var(--hw-slate)" }}>
            No tickets in this lane — try All or Untriaged.
          </div>
        )}
      </div>
    </div>
  );
}

import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import type { TicketCategory, TicketState } from "../api/types";
import { useDemo } from "../state/DemoStore";

const CATEGORIES: Array<TicketCategory | "all"> = ["all", "access", "hardware", "network", "applications"];
const STATES: Array<TicketState | "all" | "untriaged"> = [
  "all",
  "untriaged",
  "new",
  "open",
  "in_progress",
  "duplicate",
  "archived",
];

export function TicketsPage() {
  const { tickets, startTriage, triagingId } = useDemo();
  const { sysId } = useParams();
  const navigate = useNavigate();
  const [category, setCategory] = useState<(typeof CATEGORIES)[number]>("all");
  const [state, setState] = useState<(typeof STATES)[number]>("all");
  const [q, setQ] = useState("");

  const filtered = useMemo(() => {
    return tickets.filter((t) => {
      if (category !== "all" && t.category !== category) return false;
      if (state === "untriaged" && t.triage_status !== "untriaged") return false;
      else if (state !== "all" && state !== "untriaged" && t.state !== state) return false;
      if (q) {
        const hay = `${t.number} ${t.short_description} ${t.caller_id}`.toLowerCase();
        if (!hay.includes(q.toLowerCase())) return false;
      }
      return true;
    });
  }, [tickets, category, state, q]);

  const selected = tickets.find((t) => t.sys_id === sysId) ?? null;
  const detailRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (selected) detailRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [selected?.sys_id]);

  return (
    <div>
      <div className="page-head">
        <h1>Ticket system</h1>
        <p>ServiceNow-shaped backlog. Select a row for detail, duplicates, and live triage.</p>
      </div>

      <div className="tickets-layout">
        <aside className="filter-rail">
          <div>
            <div className="group-label">Category</div>
            {CATEGORIES.map((c) => (
              <button key={c} type="button" data-active={category === c} onClick={() => setCategory(c)}>
                {c}
              </button>
            ))}
          </div>
          <div>
            <div className="group-label">State</div>
            {STATES.map((s) => (
              <button key={s} type="button" data-active={state === s} onClick={() => setState(s)}>
                {s.replace("_", " ")}
              </button>
            ))}
          </div>
          <div>
            <div className="group-label">Search</div>
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="INC / text"
              style={{
                width: "100%",
                border: "1px solid var(--hw-line)",
                borderRadius: "var(--hw-radius)",
                padding: "0.45rem 0.55rem",
                background: "var(--hw-panel)",
              }}
            />
          </div>
        </aside>

        <div>
          {selected && (
            <div className="detail-split" ref={detailRef} style={{ marginBottom: 20 }}>
              <div>
                <h2 style={{ fontSize: "1.25rem", marginBottom: 12 }}>{selected.short_description}</h2>
                <dl>
                  <div className="kv">
                    <dt>Number</dt>
                    <dd className="mono">{selected.number}</dd>
                  </div>
                  <div className="kv">
                    <dt>Caller</dt>
                    <dd>
                      {selected.caller_name ?? selected.caller_id}
                      {selected.caller_name ? (
                        <span className="mono" style={{ color: "var(--hw-slate)", marginLeft: 8 }}>
                          {selected.caller_id}
                        </span>
                      ) : null}
                    </dd>
                  </div>
                  <div className="kv">
                    <dt>Group</dt>
                    <dd>{selected.assignment_group}</dd>
                  </div>
                  <div className="kv">
                    <dt>Assignee</dt>
                    <dd>{selected.assigned_to ?? "—"}</dd>
                  </div>
                  <div className="kv">
                    <dt>Parent</dt>
                    <dd>
                      {selected.parent ? (
                        <Link to={`/tickets/${selected.parent}`} className="mono" style={{ color: "var(--hw-dup)" }}>
                          {selected.parent}
                        </Link>
                      ) : (
                        "—"
                      )}
                    </dd>
                  </div>
                  <div className="kv">
                    <dt>Triage</dt>
                    <dd>{selected.triage_status ?? "—"}</dd>
                  </div>
                </dl>
                <p style={{ color: "var(--hw-slate)", maxWidth: "62ch" }}>{selected.description}</p>
                <div className="hero-actions" style={{ marginTop: 16 }}>
                  <button
                    className="btn signal"
                    disabled={Boolean(triagingId)}
                    onClick={() => {
                      void startTriage(selected);
                      navigate("/");
                    }}
                  >
                    Run live triage
                  </button>
                </div>
              </div>
              <div className="panel">
                <div className="group-label" style={{ marginBottom: 8 }}>
                  Linked / context
                </div>
                <p style={{ margin: 0, color: "var(--hw-slate)", fontSize: "0.92rem" }}>
                  {selected.parent
                    ? `Marked duplicate of ${selected.parent}. Dedupe step will cite the open parent.`
                    : `Opened ${selected.opened_at.slice(0, 10)}. Requester ${
                        selected.requester_inactive ? "inactive" : "active"
                      } — archive hybrid lever uses age + inactivity.`}
                </p>
              </div>
            </div>
          )}

          <p style={{ color: "var(--hw-slate)", fontSize: "0.85rem", margin: "0 0 8px" }}>
            Showing {Math.min(filtered.length, 120)} of {filtered.length} · {tickets.length} total
          </p>
          <div className="ticket-table-wrap">
            <table className="ticket-table">
              <thead>
                <tr>
                  <th>Number</th>
                  <th>Short description</th>
                  <th>Category</th>
                  <th>Priority</th>
                  <th>State</th>
                  <th>Opened</th>
                </tr>
              </thead>
              <tbody>
                {filtered.slice(0, 120).map((t) => (
                  <tr
                    key={t.sys_id}
                    className={selected?.sys_id === t.sys_id ? "selected" : ""}
                    onClick={() => navigate(`/tickets/${t.sys_id}`)}
                  >
                    <td className="mono">{t.number}</td>
                    <td>{t.short_description}</td>
                    <td>{t.category}</td>
                    <td className={Number(t.priority) <= 2 ? "status flare" : ""}>P{t.priority}</td>
                    <td>
                      <span className={stateClass(t.state)}>{t.state}</span>
                      {t.parent ? <span className="status dup"> · dup</span> : null}
                    </td>
                    <td className="mono">{t.opened_at.slice(0, 10)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!filtered.length && <div className="empty" style={{ padding: 24, color: "var(--hw-slate)" }}>No tickets match.</div>}
          </div>
        </div>
      </div>
    </div>
  );
}

function stateClass(state: string) {
  if (state === "archived") return "status route";
  if (state === "duplicate") return "status dup";
  if (state === "new") return "status warn";
  return "status";
}

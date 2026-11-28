import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import type { TicketCategory, TicketState } from "../api/types";
import { HitlDecidePane } from "../components/HitlDecidePane";
import { ageDays, waitLabel } from "../data/seed";
import { needsHitlPane } from "../lib/hitl";
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

const PAGE_SIZE = 100;

type DetailTab = "overview" | "activity" | "related";

export function TicketsPage() {
  const { tickets, startTriage, triagingId, applyHitlDecision, findRelated, queue } = useDemo();
  const { sysId } = useParams();
  const navigate = useNavigate();
  const [category, setCategory] = useState<(typeof CATEGORIES)[number]>("all");
  const [state, setState] = useState<(typeof STATES)[number]>("all");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(0);
  const [tab, setTab] = useState<DetailTab>("overview");
  const [sortAge, setSortAge] = useState<"none" | "asc" | "desc">("none");

  const filtered = useMemo(() => {
    let rows = tickets.filter((t) => {
      if (category !== "all" && t.category !== category) return false;
      if (state === "untriaged" && t.triage_status !== "untriaged") return false;
      else if (state !== "all" && state !== "untriaged" && t.state !== state) return false;
      if (q) {
        const hay = `${t.number} ${t.short_description} ${t.caller_id} ${t.caller_name ?? ""} ${t.channel ?? ""} ${t.cmdb_ci?.name ?? ""}`.toLowerCase();
        if (!hay.includes(q.toLowerCase())) return false;
      }
      return true;
    });
    if (sortAge !== "none") {
      rows = [...rows].sort((a, b) => {
        const da = ageDays(a.opened_at);
        const db = ageDays(b.opened_at);
        return sortAge === "asc" ? da - db : db - da;
      });
    }
    return rows;
  }, [tickets, category, state, q, sortAge]);

  const filterKey = `${category}|${state}|${q}|${sortAge}`;
  const [filterKeySeen, setFilterKeySeen] = useState(filterKey);
  const effectivePage = filterKeySeen === filterKey ? page : 0;
  if (filterKeySeen !== filterKey) {
    setFilterKeySeen(filterKey);
    if (page !== 0) setPage(0);
  }

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pageRows = filtered.slice(effectivePage * PAGE_SIZE, effectivePage * PAGE_SIZE + PAGE_SIZE);

  const selected = tickets.find((t) => t.sys_id === sysId) ?? null;
  const detailRef = useRef<HTMLDivElement>(null);
  const related = selected ? findRelated(selected) : { parent: null, duplicates: [] };
  const queueHint = selected ? queue.find((qi) => qi.ticket.sys_id === selected.sys_id) : null;
  const showHitl = selected ? needsHitlPane(selected) : false;
  const [tabTicketId, setTabTicketId] = useState<string | null>(null);
  const activeTab = selected && tabTicketId === selected.sys_id ? tab : "overview";
  if (selected && tabTicketId !== selected.sys_id) {
    setTabTicketId(selected.sys_id);
    if (tab !== "overview") setTab("overview");
  }

  useEffect(() => {
    if (selected) detailRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [selected?.sys_id]);

  return (
    <div>
      <div className="page-head">
        <h1>Ticket system</h1>
        <p>ServiceNow-shaped backlog. Select a row for detail, activity, related CI, and HITL decide.</p>
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
              placeholder="INC / text / CI"
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
            <div className={`detail-shell ${showHitl ? "with-hitl" : ""}`} ref={detailRef}>
              <div className="detail-main">
                <div className="detail-tabs" role="tablist">
                  {(["overview", "activity", "related"] as DetailTab[]).map((t) => (
                    <button
                      key={t}
                      type="button"
                      role="tab"
                      data-active={activeTab === t}
                      onClick={() => setTab(t)}
                    >
                      {t === "related" ? "Related / CI" : t}
                    </button>
                  ))}
                </div>

                {activeTab === "overview" && (
                  <div className="detail-split">
                    <div>
                      <h2 style={{ fontSize: "1.25rem", marginBottom: 12 }}>{selected.short_description}</h2>
                      <dl>
                        <div className="kv">
                          <dt>Number</dt>
                          <dd className="mono">{selected.number}</dd>
                        </div>
                        <div className="kv">
                          <dt>Channel</dt>
                          <dd>{selected.channel ?? "—"}</dd>
                        </div>
                        <div className="kv">
                          <dt>Caller</dt>
                          <dd>
                            {selected.caller_name ?? selected.caller_id}
                            {selected.caller_user_name ? (
                              <span className="mono" style={{ color: "var(--hw-slate)", marginLeft: 8 }}>
                                {selected.caller_user_name}
                              </span>
                            ) : null}
                            <span
                              className={`status ${selected.requester_inactive ? "flare" : "route"}`}
                              style={{ marginLeft: 8 }}
                            >
                              {selected.requester_inactive ? "inactive" : "active"}
                            </span>
                          </dd>
                        </div>
                        <div className="kv">
                          <dt>Urgency</dt>
                          <dd>
                            {selected.urgency ?? "—"}
                            {selected.impact ? ` · impact ${selected.impact}` : ""}
                            {` · P${selected.priority}`}
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
                          <dt>Age / wait</dt>
                          <dd className="mono">
                            {waitLabel(ageDays(selected.opened_at))} · opened {selected.opened_at.slice(0, 10)}
                          </dd>
                        </div>
                        <div className="kv">
                          <dt>Parent</dt>
                          <dd>
                            {related.parent ? (
                              <Link
                                to={`/tickets/${related.parent.sys_id}`}
                                className="mono"
                                style={{ color: "var(--hw-dup)" }}
                              >
                                {related.parent.number}
                              </Link>
                            ) : selected.parent ? (
                              <span className="mono">{selected.parent}</span>
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
                        {related.parent
                          ? `Marked duplicate of ${related.parent.number}. Dedupe step will cite the open parent.`
                          : `Opened ${selected.opened_at.slice(0, 10)}. Requester ${
                              selected.requester_inactive ? "inactive" : "active"
                            } — archive hybrid lever uses age + inactivity.`}
                      </p>
                      {selected.cmdb_ci && (
                        <p style={{ margin: "12px 0 0", fontSize: "0.92rem" }}>
                          <span className="group-label">Affected CI</span>
                          <br />
                          <strong>{selected.cmdb_ci.name}</strong>
                          <span className="mono" style={{ color: "var(--hw-slate)", marginLeft: 8 }}>
                            {selected.cmdb_ci.class}
                          </span>
                        </p>
                      )}
                      {selected.hard_block && (
                        <p className="status flare" style={{ marginTop: 12 }}>
                          Hard block · {selected.hard_block.flags.join(", ")}
                        </p>
                      )}
                    </div>
                  </div>
                )}

                {activeTab === "activity" && (
                  <div className="activity-panel">
                    <div className="group-label">Activity · comments, work notes, triage log</div>
                    <table className="activity-table">
                      <thead>
                        <tr>
                          <th>Time</th>
                          <th>Actor</th>
                          <th>Role</th>
                          <th>Action</th>
                          <th>Reason</th>
                        </tr>
                      </thead>
                      <tbody>
                        {[...(selected.activity ?? [])]
                          .sort((a, b) => a.at.localeCompare(b.at))
                          .map((e, i) => (
                            <tr key={`${e.at}-${i}`}>
                              <td className="mono">{e.at.replace("T", " ").slice(0, 16)}</td>
                              <td>{e.actor}</td>
                              <td>
                                <span className={`status ${e.role === "AI" ? "dup" : e.kind === "comment" ? "warn" : ""}`}>
                                  {e.role}
                                </span>
                              </td>
                              <td>
                                <div>{e.action}</div>
                                <div className="activity-body">{e.body}</div>
                                <span className="activity-kind">{e.kind.replace("_", " ")}</span>
                              </td>
                              <td className="mono">{e.reason ?? "—"}</td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                    {!selected.activity?.length && (
                      <p style={{ color: "var(--hw-slate)" }}>No activity seeded for this ticket.</p>
                    )}

                    {!!selected.assignment_history?.length && (
                      <>
                        <div className="group-label" style={{ marginTop: 24 }}>
                          Assignment history
                        </div>
                        <ul className="assign-hist">
                          {selected.assignment_history.map((h, i) => (
                            <li key={`${h.at}-${i}`}>
                              <span className="mono">{h.at.slice(0, 10)}</span>
                              <span>{h.action}</span>
                              {h.group && <span className="muted">{h.group}</span>}
                            </li>
                          ))}
                        </ul>
                      </>
                    )}
                  </div>
                )}

                {activeTab === "related" && (
                  <div className="related-panel">
                    <div className="panel" style={{ marginBottom: 16 }}>
                      <div className="group-label">Configuration item</div>
                      {selected.cmdb_ci ? (
                        <p style={{ margin: "8px 0 0" }}>
                          <strong>{selected.cmdb_ci.name}</strong>
                          <span className="mono" style={{ marginLeft: 8, color: "var(--hw-slate)" }}>
                            {selected.cmdb_ci.class} · {selected.cmdb_ci.sys_id}
                          </span>
                        </p>
                      ) : (
                        <p style={{ color: "var(--hw-slate)" }}>No CI linked on this record.</p>
                      )}
                    </div>
                    <div className="panel">
                      <div className="group-label">Parent / duplicates</div>
                      {related.parent ? (
                        <p>
                          Parent:{" "}
                          <Link to={`/tickets/${related.parent.sys_id}`} className="mono" style={{ color: "var(--hw-dup)" }}>
                            {related.parent.number}
                          </Link>{" "}
                          — {related.parent.short_description}
                        </p>
                      ) : (
                        <p style={{ color: "var(--hw-slate)" }}>No parent link.</p>
                      )}
                      {related.duplicates.length > 0 ? (
                        <ul className="dup-list">
                          {related.duplicates.slice(0, 12).map((d) => (
                            <li key={d.sys_id}>
                              <Link to={`/tickets/${d.sys_id}`} className="mono" style={{ color: "var(--hw-dup)" }}>
                                {d.number}
                              </Link>{" "}
                              {d.short_description}
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p style={{ color: "var(--hw-slate)" }}>No child duplicates pointing here.</p>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {showHitl && (
                <HitlDecidePane
                  ticket={selected}
                  recommend={
                    queueHint?.recommend ??
                    (selected.hard_block
                      ? "Hold for human review (auto-archive locked)"
                      : selected.triage_status === "archive_candidate"
                        ? "Reject / archive under hybrid levers"
                        : `Route to ${selected.assignment_group}`)
                  }
                  recommendKind={
                    queueHint?.recommend_kind ??
                    (selected.hard_block
                      ? "human_review"
                      : selected.triage_status === "archive_candidate"
                        ? "archive"
                        : "route")
                  }
                  onDecide={(decision, overrideReason, note) =>
                    applyHitlDecision(selected.sys_id, decision, overrideReason, note)
                  }
                />
              )}
            </div>
          )}

          <div className="table-toolbar">
            <p style={{ color: "var(--hw-slate)", fontSize: "0.85rem", margin: 0 }}>
              Showing {pageRows.length ? effectivePage * PAGE_SIZE + 1 : 0}–
              {Math.min((effectivePage + 1) * PAGE_SIZE, filtered.length)} of {filtered.length} · {tickets.length}{" "}
              total
            </p>
            <div className="pager">
              <button
                type="button"
                className="btn ghost"
                disabled={effectivePage <= 0}
                onClick={() => setPage((p) => p - 1)}
              >
                Prev
              </button>
              <span className="mono">
                {effectivePage + 1}/{pageCount}
              </span>
              <button
                type="button"
                className="btn ghost"
                disabled={effectivePage >= pageCount - 1}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </button>
            </div>
          </div>
          <div className="ticket-table-wrap">
            <table className="ticket-table">
              <thead>
                <tr>
                  <th>Number</th>
                  <th>Short description</th>
                  <th>Channel</th>
                  <th>
                    <button
                      type="button"
                      className="th-sort"
                      onClick={() => setSortAge((s) => (s === "desc" ? "asc" : s === "asc" ? "none" : "desc"))}
                    >
                      Age{sortAge === "desc" ? " ↓" : sortAge === "asc" ? " ↑" : ""}
                    </button>
                  </th>
                  <th>Category</th>
                  <th>Priority</th>
                  <th>State</th>
                  <th>Opened</th>
                </tr>
              </thead>
              <tbody>
                {pageRows.map((t) => {
                  const days = ageDays(t.opened_at);
                  return (
                    <tr
                      key={t.sys_id}
                      className={selected?.sys_id === t.sys_id ? "selected" : ""}
                      onClick={() => navigate(`/tickets/${t.sys_id}`)}
                    >
                      <td className="mono">{t.number}</td>
                      <td>
                        {t.short_description}
                        {t.hard_block ? <span className="status flare"> · block</span> : null}
                      </td>
                      <td>{t.channel ?? "—"}</td>
                      <td className={`mono ${days >= 13 ? "status flare" : ""}`}>{waitLabel(days)}</td>
                      <td>{t.category}</td>
                      <td className={Number(t.priority) <= 2 ? "status flare" : ""}>P{t.priority}</td>
                      <td>
                        <span className={stateClass(t.state)}>{t.state}</span>
                        {t.parent ? <span className="status dup"> · dup</span> : null}
                      </td>
                      <td className="mono">{t.opened_at.slice(0, 10)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {!filtered.length && (
              <div className="empty" style={{ padding: 24, color: "var(--hw-slate)" }}>
                No tickets match.
              </div>
            )}
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

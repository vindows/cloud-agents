import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { Ticket } from "../api/types";
import { PipelineSpine } from "../components/PipelineSpine";
import { ageDays, waitLabel } from "../data/seed";
import { useDemo } from "../state/DemoStore";

export function LiveTriagePage() {
  const { tickets, liveSteps, triagingId, startTriage, activeTriage } = useDemo();
  const [pinned, setPinned] = useState<Ticket | null>(null);

  const candidate = useMemo(() => {
    if (pinned) {
      return tickets.find((t) => t.sys_id === pinned.sys_id) ?? pinned;
    }
    if (triagingId) {
      return tickets.find((t) => t.sys_id === triagingId) ?? null;
    }
    return (
      tickets.find((t) => t.demo_hero && t.triage_status === "untriaged") ??
      tickets.find((t) => t.triage_status === "untriaged" && t.state === "new") ??
      tickets.find((t) => t.triage_status === "untriaged") ??
      tickets[0] ??
      null
    );
  }, [tickets, triagingId, pinned]);

  const activeStep = [...liveSteps].reverse().find((s) => s.status === "running" || s.status === "done");
  const reasonStep =
    liveSteps.find((s) => s.status === "running") ??
    [...liveSteps].reverse().find((s) => s.status === "done" || s.status === "skipped");

  const spineSteps = liveSteps.filter((s) => s.name !== "intake"); // CIO spine: classify→archive

  return (
    <section className="triage-hero">
      <div>
        <div className="hero-brand">Harbor Wireless</div>
        <p className="hero-purpose">Routing first — resolution later. Watch every System One decision with confidence.</p>
      </div>

      <PipelineSpine steps={spineSteps} idle={!liveSteps.length} />

      <div className="reason-block">
        {candidate ? (
          <>
            <div className="ticket-ref">{candidate.number}</div>
            <h2>{candidate.short_description}</h2>
            <div className="live-meta">
              <span>{candidate.assignment_group}</span>
              <span>·</span>
              <span>{candidate.channel ?? "portal"}</span>
              <span>·</span>
              <span>
                urgency {candidate.urgency ?? "—"}
                {candidate.impact ? ` / ${candidate.impact}` : ""}
              </span>
              <span>·</span>
              <span className={candidate.requester_inactive ? "status flare" : ""}>
                caller {candidate.caller_name ?? candidate.caller_id}
                {candidate.requester_inactive ? " (inactive)" : ""}
              </span>
              <span>·</span>
              <span className="mono">wait {waitLabel(ageDays(candidate.opened_at))}</span>
              {candidate.hard_block && (
                <>
                  <span>·</span>
                  <span className="status flare">hard block</span>
                </>
              )}
              {candidate.cmdb_ci && (
                <>
                  <span>·</span>
                  <span>CI {candidate.cmdb_ci.name}</span>
                </>
              )}
            </div>
            <p className={`reason-text ${reasonStep ? "reveal" : ""}`} key={reasonStep?.id ?? "idle"}>
              {reasonStep?.reason ??
                "Select Run triage to classify, dedupe, score priority, and route — or surface an archive candidate."}
            </p>
            {reasonStep && (
              <div className="reason-confidence">
                confidence {Math.round(reasonStep.confidence * 100)}%
                {activeStep ? ` · ${activeStep.name}` : ""}
                {typeof reasonStep.meta?.provenance === "string"
                  ? ` · ${reasonStep.meta.provenance}`
                  : ""}
              </div>
            )}
            {activeTriage && !triagingId && (
              <div className="step-log" style={{ marginTop: 16 }}>
                <div className="status route">
                  Final: {activeTriage.final_action.replace("-", " ")}
                  {activeTriage.assigned_to ? ` → ${activeTriage.assigned_to}` : ""}
                  {activeTriage.assignment_group ? ` · ${activeTriage.assignment_group}` : ""}
                </div>
              </div>
            )}
          </>
        ) : (
          <p className="reason-text">No tickets loaded.</p>
        )}
      </div>

      <div className="hero-actions">
        <button
          className="btn signal"
          disabled={!candidate || Boolean(triagingId)}
          onClick={() => {
            if (!candidate) return;
            setPinned(candidate);
            void startTriage(candidate);
          }}
        >
          {triagingId ? "Triaging…" : "Run triage"}
        </button>
        <button
          className="btn ghost"
          disabled={Boolean(triagingId)}
          onClick={() => {
            setPinned(null);
            const next =
              tickets.find(
                (t) =>
                  t.triage_status === "untriaged" &&
                  t.state === "new" &&
                  t.sys_id !== candidate?.sys_id,
              ) ?? null;
            if (next) setPinned(next);
          }}
        >
          Next ticket
        </button>
        <Link className="btn ghost" to="/tickets">
          Open ticket system
        </Link>
        <Link className="btn ghost" to="/queue">
          Priority queue
        </Link>
      </div>
    </section>
  );
}

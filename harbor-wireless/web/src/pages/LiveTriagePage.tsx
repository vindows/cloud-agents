import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { Ticket } from "../api/types";
import { PipelineSpine } from "../components/PipelineSpine";
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
            <p className={`reason-text ${reasonStep ? "reveal" : ""}`} key={reasonStep?.id ?? "idle"}>
              {reasonStep?.reason ??
                "Select Run triage to classify, dedupe, score priority, and route — or surface an archive candidate."}
            </p>
            {reasonStep && (
              <div className="reason-confidence">
                confidence {Math.round(reasonStep.confidence * 100)}%
                {activeStep ? ` · ${activeStep.name}` : ""}
              </div>
            )}
            {activeTriage && !triagingId && (
              <div className="step-log" style={{ marginTop: 16 }}>
                <div className="status route">
                  Final: {activeTriage.final_action.replace("-", " ")}
                  {activeTriage.assigned_to ? ` → ${activeTriage.assigned_to}` : ""}
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

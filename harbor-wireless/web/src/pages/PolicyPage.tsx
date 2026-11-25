import type { ArchiveMode } from "../api/types";
import { useDemo } from "../state/DemoStore";

const MODES: { id: ArchiveMode; label: string; blurb: string }[] = [
  {
    id: "auto",
    label: "Auto",
    blurb: "Archive when ticket age meets the threshold — no human confirmation.",
  },
  {
    id: "human",
    label: "Human",
    blurb: "Surface archive candidates for approval — nothing archives alone.",
  },
  {
    id: "hybrid",
    label: "Hybrid",
    blurb: "Auto-archive only when age and inactive-requester rules both pass; else HITL.",
  },
];

export function PolicyPage() {
  const { policy, setPolicy, tickets } = useDemo();

  const archived = tickets.filter((t) => t.triage_status === "archived").length;
  const candidates = tickets.filter((t) => t.triage_status === "archive_candidate").length;

  const outcome =
    policy.mode === "auto"
      ? `Auto mode: tickets older than ${policy.age_years} years archive immediately. Currently ${archived} archived.`
      : policy.mode === "human"
        ? `Human mode: age ≥ ${policy.age_years}y becomes an archive candidate for review. ${candidates} candidates in view.`
        : `Hybrid: auto-archive when age ≥ ${policy.age_years}y AND requester inactive ≥ ${policy.inactive_days}d; otherwise candidate. ${archived} archived · ${candidates} awaiting review.`;

  return (
    <div>
      <div className="page-head">
        <h1>Archive levers</h1>
        <p>Control how the backlog pass treats stale tickets. CIO story: automation with an explicit HITL dial.</p>
      </div>

      <div className="panel" style={{ maxWidth: 640 }}>
        <div className="group-label" style={{ marginBottom: 12 }}>
          Mode
        </div>
        <div className="segmented" role="tablist" aria-label="Archive mode">
          {MODES.map((m) => (
            <button
              key={m.id}
              type="button"
              role="tab"
              data-active={policy.mode === m.id}
              aria-selected={policy.mode === m.id}
              onClick={() => setPolicy({ ...policy, mode: m.id })}
            >
              {m.label}
            </button>
          ))}
        </div>
        <p style={{ color: "var(--hw-slate)", marginTop: 12, maxWidth: "62ch" }}>
          {MODES.find((m) => m.id === policy.mode)?.blurb}
        </p>

        {policy.mode === "hybrid" && (
          <div className="lever-fields">
            <label>
              Minimum age (years)
              <input
                type="number"
                min={1}
                max={10}
                value={policy.age_years}
                onChange={(e) =>
                  setPolicy({ ...policy, age_years: Math.max(1, Number(e.target.value) || 1) })
                }
              />
            </label>
            <label>
              Inactive requester (days)
              <input
                type="number"
                min={30}
                max={2000}
                value={policy.inactive_days}
                onChange={(e) =>
                  setPolicy({
                    ...policy,
                    inactive_days: Math.max(30, Number(e.target.value) || 365),
                  })
                }
              />
            </label>
          </div>
        )}

        <p className="outcome">{outcome}</p>
      </div>
    </div>
  );
}

import type { TriageStep, TriageStepName } from "../api/types";

const STAGES = ["classify", "dedupe", "priority", "route", "archive"] as const;

const LABELS: Record<(typeof STAGES)[number], string> = {
  classify: "Classify",
  dedupe: "Dedupe",
  priority: "Priority",
  route: "Route",
  archive: "Archive",
};

interface Props {
  steps: TriageStep[];
  idle?: boolean;
}

export function PipelineSpine({ steps, idle }: Props) {
  const byName = new Map(steps.map((s) => [canonical(s.name), s]));

  return (
    <div className="pipeline-spine" role="list" aria-label="Triage pipeline">
      {STAGES.map((name) => {
        const step = byName.get(name);
        let status: "idle" | "pending" | "running" | "done" | "skipped" = "idle";
        if (idle || steps.length === 0) status = "idle";
        else if (step) status = step.status === "pending" ? "pending" : step.status;
        else if (steps.length) status = "pending";

        const cls = [
          "stage",
          status === "running" ? "active" : "",
          status === "done" ? "done" : "",
          status === "skipped" ? "skipped" : "",
        ]
          .filter(Boolean)
          .join(" ");

        return (
          <div key={name} className={cls} role="listitem">
            <div className="stage-label">
              <span className="stage-marker" aria-hidden>
                {status === "done" ? "✓" : ""}
              </span>
              {LABELS[name]}
            </div>
            <div className="stage-meta">
              {status === "running"
                ? "In progress"
                : status === "done"
                  ? `${Math.round((step?.confidence ?? 0) * 100)}%`
                  : status === "skipped"
                    ? "Skipped"
                    : "Waiting"}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function canonical(name: TriageStepName): (typeof STAGES)[number] | string {
  if (name === "archive-candidate") return "archive";
  return name;
}

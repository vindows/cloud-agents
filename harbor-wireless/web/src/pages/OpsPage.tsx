import { useDemo } from "../state/DemoStore";

export function OpsPage() {
  const { metrics } = useDemo();

  if (!metrics) {
    return (
      <div className="page-head">
        <h1>What’s already handled</h1>
        <p>Metrics loading…</p>
      </div>
    );
  }

  const maxCat = Math.max(...metrics.volume_by_category.map((c) => c.count), 1);
  const { archived, human_review, routed } = metrics.archive_vs_human;
  const archiveHitl = archived + human_review || 1;

  return (
    <div>
      <div className="page-head">
        <h1>What’s already handled</h1>
        <p>Past tickets through the Phase 1 routing pipeline — volume, speed, and HITL pressure.</p>
      </div>

      <div className="ops-hero-metrics">
        <div className="ops-metric">
          <div className="label">Avg time-to-route</div>
          <div className="value">{metrics.avg_time_to_route_hours.toFixed(1)}h</div>
        </div>
        <div className="ops-metric">
          <div className="label">Dedupe rate</div>
          <div className="value">{Math.round(metrics.dedupe_rate * 100)}%</div>
        </div>
        <div className="ops-metric">
          <div className="label">Archive vs HITL</div>
          <div className="value">
            {Math.round((archived / archiveHitl) * 100)}
            <span style={{ fontSize: "1.1rem", color: "var(--hw-slate)" }}> / {Math.round((human_review / archiveHitl) * 100)}</span>
          </div>
        </div>
      </div>

      <h2 style={{ fontSize: "1.25rem" }}>Volume by category</h2>
      <div className="bar-set">
        {metrics.volume_by_category.map((row) => (
          <div className="bar-row" key={row.category}>
            <span>{row.category}</span>
            <div className="bar-track">
              <div className="bar-fill" style={{ width: `${(row.count / maxCat) * 100}%` }} />
            </div>
            <span className="mono">{row.count}</span>
          </div>
        ))}
      </div>

      <div className="golden-row">
        <span>
          Handled <strong>{metrics.total_handled}</strong>
        </span>
        <span>
          Routed <strong>{routed}</strong>
        </span>
        <span>
          Confidence fallbacks <strong>{metrics.confidence_fallbacks}</strong>
        </span>
        {metrics.golden_set && (
          <>
            <span>
              Golden category <strong>{Math.round(metrics.golden_set.category_accuracy * 100)}%</strong>
            </span>
            <span>
              Dedupe P/R{" "}
              <strong>
                {Math.round(metrics.golden_set.dedupe_precision * 100)}/{Math.round(metrics.golden_set.dedupe_recall * 100)}
              </strong>
            </span>
          </>
        )}
      </div>
    </div>
  );
}

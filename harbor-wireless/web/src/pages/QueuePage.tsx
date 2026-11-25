import { Link } from "react-router-dom";
import { useDemo } from "../state/DemoStore";

export function QueuePage() {
  const { queue, startTriage, triagingId } = useDemo();

  return (
    <div>
      <div className="page-head">
        <h1>Priority & auto-assign</h1>
        <p>Ranked work for category agents. Each row includes why this queue and who gets it.</p>
      </div>

      <div className="queue-list">
        {queue.map((item) => (
          <div className="queue-item" key={item.ticket.sys_id}>
            <div className="rank">{item.rank}</div>
            <div>
              <div>
                <Link to={`/tickets/${item.ticket.sys_id}`} className="mono" style={{ color: "var(--hw-signal)" }}>
                  {item.ticket.number}
                </Link>
                <span style={{ marginLeft: 8 }}>P{item.ticket.priority}</span>
                <span style={{ marginLeft: 8, color: "var(--hw-slate)" }}>{item.ticket.category}</span>
              </div>
              <div style={{ fontWeight: 650, marginTop: 2 }}>{item.ticket.short_description}</div>
              <p className="why">
                Why: {item.assignment_reason}
                {item.suggested_agent ? ` → ${item.suggested_agent.name}` : ""}
              </p>
            </div>
            <div style={{ textAlign: "right" }}>
              <div className="conf">{Math.round(item.confidence * 100)}%</div>
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
        {!queue.length && <div style={{ padding: 24, color: "var(--hw-slate)" }}>Queue empty — backlog already routed.</div>}
      </div>
    </div>
  );
}

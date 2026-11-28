import { useState } from "react";
import type { HitlDecision, HitlOverrideReason, QueueRecommendKind, Ticket } from "../api/types";

const OVERRIDE_REASONS: { value: HitlOverrideReason; label: string }[] = [
  { value: "wrong_category", label: "Wrong category" },
  { value: "not_duplicate", label: "Not a duplicate" },
  { value: "vip_high_risk", label: "VIP / high risk" },
  { value: "policy", label: "Policy" },
  { value: "other", label: "Other" },
];

interface Props {
  ticket: Ticket;
  recommend: string;
  recommendKind: QueueRecommendKind;
  onDecide: (decision: HitlDecision, overrideReason: HitlOverrideReason | null, note: string) => void;
}

function needsOverride(decision: HitlDecision, recommendKind: QueueRecommendKind, ticket: Ticket): boolean {
  if (ticket.hard_block && decision === "reject_archive") return true;
  if (recommendKind === "archive" && decision === "approve_route") return true;
  if (recommendKind === "route" && decision === "reject_archive") return true;
  if (recommendKind === "human_review" && decision === "reject_archive" && ticket.hard_block) return true;
  if (recommendKind === "duplicate" && decision !== "hold_human") return true;
  return false;
}

export function HitlDecidePane({ ticket, recommend, recommendKind, onDecide }: Props) {
  const lockedArchive = Boolean(ticket.hard_block?.locks_auto_archive);
  const defaultDecision: HitlDecision =
    recommendKind === "archive" && !lockedArchive
      ? "reject_archive"
      : recommendKind === "human_review" || lockedArchive
        ? "hold_human"
        : "approve_route";

  const [decision, setDecision] = useState<HitlDecision>(defaultDecision);
  const [reason, setReason] = useState<HitlOverrideReason | "">("");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);

  const overrideRequired = needsOverride(decision, recommendKind, ticket);

  return (
    <aside className="hitl-pane" aria-label="HITL decide">
      <div className="group-label">Your step: decide</div>
      <p className="hitl-recommend">
        System One recommends: <strong>{recommend}</strong>
      </p>
      {ticket.hard_block && (
        <div className="hitl-block">
          <span className="status flare">Hard block</span>
          <p>{ticket.hard_block.reason}</p>
          <p className="hitl-flags mono">{ticket.hard_block.flags.join(" · ")}</p>
        </div>
      )}

      <fieldset className="hitl-options">
        <legend className="sr-only">Decision</legend>
        <label>
          <input
            type="radio"
            name={`hitl-${ticket.sys_id}`}
            checked={decision === "approve_route"}
            onChange={() => setDecision("approve_route")}
          />
          <span>
            Approve route
            <small>Assign to suggested group / agent</small>
          </span>
        </label>
        <label>
          <input
            type="radio"
            name={`hitl-${ticket.sys_id}`}
            checked={decision === "hold_human"}
            onChange={() => setDecision("hold_human")}
          />
          <span>
            Hold for human
            <small>Keep in untriaged · specialist owns next step</small>
          </span>
        </label>
        <label className={lockedArchive ? "hitl-locked" : undefined}>
          <input
            type="radio"
            name={`hitl-${ticket.sys_id}`}
            checked={decision === "reject_archive"}
            disabled={lockedArchive}
            onChange={() => setDecision("reject_archive")}
          />
          <span>
            Reject / archive
            <small>{lockedArchive ? "Locked by hard block" : "Close as archive under policy"}</small>
          </span>
        </label>
      </fieldset>

      {overrideRequired && (
        <div className="hitl-override">
          <label>
            Override reason
            <select value={reason} onChange={(e) => setReason(e.target.value as HitlOverrideReason | "")}>
              <option value="">Select reason…</option>
              {OVERRIDE_REASONS.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Note
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={2}
              placeholder="Why override System One?"
            />
          </label>
        </div>
      )}

      {error && <p className="hitl-error">{error}</p>}

      {ticket.hitl_decision ? (
        <p className="status route" style={{ marginTop: 12 }}>
          Recorded: {ticket.hitl_decision.replace("_", " ")}
          {ticket.hitl_override_reason ? ` · ${ticket.hitl_override_reason}` : ""}
        </p>
      ) : (
        <button
          type="button"
          className="btn signal"
          style={{ marginTop: 12, width: "100%" }}
          onClick={() => {
            if (overrideRequired && !reason) {
              setError("Override requires a reason code.");
              return;
            }
            setError(null);
            onDecide(decision, overrideRequired ? (reason as HitlOverrideReason) : null, note);
          }}
        >
          Confirm decision
        </button>
      )}
    </aside>
  );
}


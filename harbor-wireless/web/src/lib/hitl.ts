import type { Ticket } from "../api/types";

export function needsHitlPane(ticket: Ticket): boolean {
  if (ticket.hard_block) return true;
  if (ticket.triage_status === "archive_candidate") return true;
  if ((ticket.confidence ?? 1) < 0.65) return true;
  if (ticket.triage_status === "untriaged" && ticket.state === "new") return true;
  return false;
}

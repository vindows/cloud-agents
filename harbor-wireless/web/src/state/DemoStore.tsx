import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  applyArchivePolicy,
  fetchArchivePolicy,
  getArchivePolicy,
  loadAgents,
  loadMetrics,
  loadQueue,
  loadTickets,
  runTriage,
  setArchivePolicy as persistPolicy,
} from "../api/adapters";
import type {
  Agent,
  ArchivePolicy,
  OpsMetrics,
  QueueItem,
  Ticket,
  TriageRun,
  TriageStep,
} from "../api/types";

interface DemoState {
  ready: boolean;
  dataSource: "remote" | "seed";
  tickets: Ticket[];
  agents: Agent[];
  queue: QueueItem[];
  metrics: OpsMetrics | null;
  policy: ArchivePolicy;
  activeTriage: TriageRun | null;
  liveSteps: TriageStep[];
  triagingId: string | null;
  setPolicy: (p: ArchivePolicy) => void;
  refreshMetrics: () => Promise<void>;
  startTriage: (ticket: Ticket) => Promise<void>;
  getTicket: (sysId: string) => Ticket | undefined;
}

const Ctx = createContext<DemoState | null>(null);

export function DemoProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [dataSource, setDataSource] = useState<"remote" | "seed">("seed");
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [metrics, setMetrics] = useState<OpsMetrics | null>(null);
  const [policy, setPolicyState] = useState<ArchivePolicy>(getArchivePolicy());
  const [activeTriage, setActiveTriage] = useState<TriageRun | null>(null);
  const [liveSteps, setLiveSteps] = useState<TriageStep[]>([]);
  const [triagingId, setTriagingId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const [{ tickets: t, source }, { agents: a }, levers] = await Promise.all([
        loadTickets(),
        loadAgents(),
        fetchArchivePolicy(),
      ]);
      if (cancelled) return;
      setPolicyState(levers);
      const applied = applyArchivePolicy(t, levers);
      setTickets(applied);
      setAgents(a);
      setDataSource(source);
      setQueue(await loadQueue(applied, a));
      setMetrics(await loadMetrics(applied));
      setReady(true);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const refreshMetrics = useCallback(async () => {
    setMetrics(await loadMetrics(tickets));
  }, [tickets]);

  const setPolicy = useCallback(
    (p: ArchivePolicy) => {
      const saved = persistPolicy(p);
      setPolicyState(saved);
      setTickets((prev) => {
        const next = applyArchivePolicy(prev.map(resetArchiveFlags), saved);
        void loadQueue(next, agents).then(setQueue);
        void loadMetrics(next).then(setMetrics);
        return next;
      });
    },
    [agents],
  );

  const startTriage = useCallback(
    async (ticket: Ticket) => {
      setTriagingId(ticket.sys_id);
      setActiveTriage(null);
      setLiveSteps([]);
      setTickets((prev) =>
        prev.map((t) => (t.sys_id === ticket.sys_id ? { ...t, triage_status: "triaging" } : t)),
      );

      const run = await runTriage(ticket, tickets, agents);
      const animated: TriageStep[] = run.steps.map((s) => ({ ...s, status: "pending" }));
      setLiveSteps(animated);
      setActiveTriage({ ...run, steps: animated });

      for (let i = 0; i < run.steps.length; i++) {
        const step = run.steps[i]!;
        setLiveSteps((prev) =>
          prev.map((s, idx) =>
            idx === i ? { ...s, status: step.status === "skipped" ? "skipped" : "running" } : s,
          ),
        );
        await wait(step.status === "skipped" ? 280 : 650);
        setLiveSteps((prev) =>
          prev.map((s, idx) =>
            idx === i ? { ...step, status: step.status === "skipped" ? "skipped" : "done" } : s,
          ),
        );
      }

      setActiveTriage(run);

      setTickets((prev) => {
        const next = prev.map((t) => {
          if (t.sys_id !== ticket.sys_id) return t;
          if (run.final_action === "archived") {
            return { ...t, state: "archived" as const, triage_status: "archived" as const };
          }
          if (run.final_action === "archive-candidate") {
            return { ...t, triage_status: "archive_candidate" as const };
          }
          if (run.final_action === "duplicate" || run.duplicate_of) {
            return {
              ...t,
              state: "duplicate" as const,
              parent: run.duplicate_of ?? t.parent,
              triage_status: "routed" as const,
            };
          }
          if (run.final_action === "human-review") {
            return { ...t, triage_status: "untriaged" as const, confidence: 0.5 };
          }
          return {
            ...t,
            state: "open" as const,
            triage_status: "routed" as const,
            assigned_to: run.assigned_to ?? t.assigned_to,
            assignment_group: run.assignment_group ?? t.assignment_group,
            routed_at: new Date().toISOString(),
          };
        });
        void loadQueue(next, agents).then(setQueue);
        void loadMetrics(next).then(setMetrics);
        return next;
      });

      setTriagingId(null);
    },
    [tickets, agents],
  );

  const getTicket = useCallback((sysId: string) => tickets.find((t) => t.sys_id === sysId), [tickets]);

  const value = useMemo(
    () => ({
      ready,
      dataSource,
      tickets,
      agents,
      queue,
      metrics,
      policy,
      activeTriage,
      liveSteps,
      triagingId,
      setPolicy,
      refreshMetrics,
      startTriage,
      getTicket,
    }),
    [
      ready,
      dataSource,
      tickets,
      agents,
      queue,
      metrics,
      policy,
      activeTriage,
      liveSteps,
      triagingId,
      setPolicy,
      refreshMetrics,
      startTriage,
      getTicket,
    ],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useDemo() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useDemo must be used within DemoProvider");
  return ctx;
}

function wait(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

function resetArchiveFlags(t: Ticket): Ticket {
  if (t.state === "duplicate" || t.state === "resolved" || t.state === "closed") return t;
  if (t.triage_status === "archived" || t.triage_status === "archive_candidate") {
    return {
      ...t,
      state: t.state === "archived" ? "open" : t.state,
      triage_status: t.assigned_to ? "routed" : "untriaged",
    };
  }
  return t;
}

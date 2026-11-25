import { api, API_BASE } from "./api";
import { useUI } from "@/stores/ui";

export type DomainEvent = {
  seq: number;
  event_id: string;
  event_type: string;
  occurred_at: string;
  organization_id: string | null;
  aggregate_id: string | null;
  schema_version: number;
  correlation_id: string | null;
  payload: any;
};

type Listener = (e: DomainEvent) => void;
const listeners = new Map<string, Set<Listener>>();
const KNOWN_SCHEMA: Record<string, number> = {};

export function onEvent(type: string, fn: Listener) {
  if (!listeners.has(type)) listeners.set(type, new Set());
  listeners.get(type)!.add(fn);
  return () => listeners.get(type)!.delete(fn);
}

function dispatch(e: DomainEvent) {
  const max = KNOWN_SCHEMA[e.event_type] ?? 1;
  if (e.schema_version > max) return; // versión de contrato no soportada: se ignora sin romper
  listeners.get(e.event_type)?.forEach((f) => f(e));
  listeners.get("*")?.forEach((f) => f(e));
}

const TYPES = [
  "learning.progress.updated", "assessment.submitted", "course.completed", "recommendation.created", "model.training.started",
  "model.training.progress", "model.training.completed", "model.training.failed", "model.deployed", "model.inference",
  "notification.created", "activity.created", "dataset.updated", "certificate.issued", "community.posted",
];

/** SSE con ticket de un solo uso, reconexión con backoff exponencial y recuperación por Last-Event-ID. */
export function connectRealtime(): () => void {
  let es: EventSource | null = null;
  let stopped = false;
  let attempt = 0;
  let lastSeq = Number(sessionStorage.getItem("em-last-seq") ?? 0) || 0;
  let timer: number | undefined;
  const { setRt, touch } = useUI.getState();

  const open = async () => {
    if (stopped) return;
    setRt("connecting");
    try {
      const { ticket } = await api<{ ticket: string }>("/realtime/ticket", { method: "POST" });
      const url = `${API_BASE}/realtime/stream?ticket=${encodeURIComponent(ticket)}${lastSeq ? `&last_event_id=${lastSeq}` : ""}`;
      es = new EventSource(url);
      es.addEventListener("hello", () => { attempt = 0; setRt("live"); });
      es.addEventListener("heartbeat", () => setRt("live"));
      TYPES.forEach((t) =>
        es!.addEventListener(t, (m) => {
          const ev = JSON.parse((m as MessageEvent).data) as DomainEvent;
          lastSeq = Math.max(lastSeq, ev.seq);
          sessionStorage.setItem("em-last-seq", String(lastSeq));
          touch();
          dispatch(ev);
        }),
      );
      es.onerror = () => {
        es?.close();
        setRt("offline");
        schedule();
      };
    } catch {
      setRt("offline");
      schedule();
    }
  };
  const schedule = () => {
    if (stopped) return;
    const delay = Math.min(30000, 1000 * 2 ** attempt++) + Math.random() * 500;
    timer = window.setTimeout(open, delay);
  };
  open();
  return () => {
    stopped = true;
    es?.close();
    clearTimeout(timer);
  };
}

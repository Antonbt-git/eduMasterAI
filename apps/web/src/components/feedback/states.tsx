import clsx from "clsx";
import { AlertTriangle, CheckCircle2, Info, Inbox, RotateCw, X } from "lucide-react";
import type { ReactNode } from "react";
import { ApiError } from "@/services/api";
import { useUI } from "@/stores/ui";
import { Button } from "../ui/primitives";

export const Skeleton = ({ className }: { className?: string }) => <div className={clsx("skeleton", className)} aria-hidden />;

export function EmptyState({ title, text, action, icon }: { title: string; text?: string; action?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-10 text-center">
      <span className="grid size-11 place-items-center rounded-full bg-electric/10 text-cyan">{icon ?? <Inbox className="size-5" />}</span>
      <p className="font-medium text-frost">{title}</p>
      {text && <p className="max-w-sm text-[13px] text-mist">{text}</p>}
      {action}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const e = error as ApiError;
  return (
    <div role="alert" className="flex flex-col items-center gap-2 py-8 text-center">
      <AlertTriangle className="size-6 text-danger" />
      <p className="font-medium">{e?.message ?? "No se pudo cargar la información"}</p>
      {e?.correlationId && <p className="text-[12px] text-dim">Referencia: {e.correlationId}</p>}
      {onRetry && <Button size="sm" variant="outline" onClick={onRetry}><RotateCw /> Reintentar</Button>}
    </div>
  );
}

/** Envoltorio estándar de consulta: carga, error, vacío y contenido. */
export function QueryState<T>({ q, empty, skeleton, children }: {
  q: { data?: T; isLoading: boolean; error: unknown; refetch: () => void }; empty?: (d: T) => boolean | ReactNode; skeleton?: ReactNode; children: (d: T) => ReactNode;
}) {
  if (q.isLoading) return <>{skeleton ?? <Skeleton className="h-40 w-full" />}</>;
  if (q.error) return <ErrorState error={q.error} onRetry={q.refetch} />;
  if (q.data === undefined) return null;
  if (empty) {
    const e = empty(q.data);
    if (e === true) return <EmptyState title="Sin datos para los filtros seleccionados" text="Prueba con otro periodo o quita filtros." />;
    if (e) return <>{e}</>;
  }
  return <>{children(q.data)}</>;
}

export function Toaster() {
  const { toasts, dismiss } = useUI();
  return (
    <div className="fixed right-4 bottom-4 z-[60] flex w-[min(380px,calc(100vw-2rem))] flex-col gap-2" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className={clsx("panel panel-glow flex items-start gap-3 px-4 py-3 text-[13px]",
          t.kind === "error" && "!border-danger/50", t.kind === "ok" && "!border-teal/50")}>
          {t.kind === "ok" ? <CheckCircle2 className="mt-0.5 size-4 text-teal" /> : t.kind === "error" ? <AlertTriangle className="mt-0.5 size-4 text-danger" /> : <Info className="mt-0.5 size-4 text-cyan" />}
          <p className="flex-1">{t.text}</p>
          <button onClick={() => dismiss(t.id)} aria-label="Cerrar aviso" className="text-mist hover:text-frost"><X className="size-4" /></button>
        </div>
      ))}
    </div>
  );
}

export function errorText(e: unknown) {
  const err = e as ApiError;
  if (err?.details && Array.isArray(err.details)) return `${err.message}: ${(err.details as any[]).map((d) => `${d.field} ${d.message}`).join("; ")}`;
  return err?.message ?? "Error inesperado";
}

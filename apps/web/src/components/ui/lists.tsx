import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { Award, BookOpen, Check, ChevronRight, CircleCheck, ClipboardCheck, Compass, FileCheck2, PlayCircle, Rocket, Star, Target, Trophy, X } from "lucide-react";
import { useState } from "react";
import { ErrorState, errorText } from "@/components/feedback/states";
import { ago, pct } from "@/lib/format";
import { api } from "@/services/api";
import { useUI } from "@/stores/ui";
import { Badge, Button, StatusBadge } from "./primitives";

const ACTION_STYLE: Record<string, [string, any]> = {
  Repasa: ["bg-violet text-white", Star], Completa: ["bg-electric text-white", PlayCircle], Sigue: ["bg-teal text-ink", Trophy],
  Realiza: ["bg-[#FF8A3D] text-white", ClipboardCheck], Explora: ["bg-[#FF8F3A] text-white", Compass],
};

export function RecommendationList({ items, compact }: { items: any[]; compact?: boolean }) {
  const qc = useQueryClient();
  const toast = useUI((s) => s.toast);
  const [open, setOpen] = useState<string | null>(null);
  const fb = useMutation({
    mutationFn: ({ id, action }: { id: string; action: string }) => api(`/recommendations/${id}/feedback`, { body: { action } }),
    onSuccess: (_d, v) => { qc.invalidateQueries({ queryKey: ["recommendations"] }); toast("ok", { accepted: "Recomendación aceptada", dismissed: "Recomendación descartada", completed: "Marcada como completada", useful: "Gracias, la marcamos como útil", not_useful: "Gracias por tu opinión" }[v.action] ?? "Guardado"); },
    onError: (e) => toast("error", errorText(e)),
  });
  return (
    <ul className="flex flex-col gap-1.5">
      {items.map((r) => {
        const [cls, Icon] = ACTION_STYLE[r.action] ?? ACTION_STYLE.Explora;
        const isOpen = open === r.id;
        const rest = r.title.replace(`${r.action}: `, "");
        return (
          <li key={r.id} className="panel-inner">
            <button className="flex w-full items-center gap-3 px-3 py-2 text-left" onClick={() => setOpen(isOpen ? null : r.id)} aria-expanded={isOpen}>
              <span className={clsx("grid size-7 shrink-0 place-items-center rounded-lg", cls)}><Icon className="size-4" /></span>
              <span className="min-w-0 flex-1 truncate text-[13px]"><span className="text-[#FFC48A]">{r.action}:</span> {rest}</span>
              {!compact && <StatusBadge status={r.status} />}
              <ChevronRight className={clsx("size-4 text-mist transition-transform", isOpen && "rotate-90")} />
            </button>
            {isOpen && (
              <div className="border-t border-line/40 px-3 pt-2 pb-3 text-[12px]">
                <div className="mb-1 flex flex-wrap gap-1.5">
                  <Badge tone="violet">Impacto {r.impact}</Badge>
                  {r.rationale?.competency && <Badge tone="cyan">{r.rationale.competency}</Badge>}
                  {r.rationale?.estimated_difficulty && <Badge>Dificultad {r.rationale.estimated_difficulty}</Badge>}
                  {r.confidence != null && <Badge>Confianza {pct(r.confidence, 0)}</Badge>}
                  {r.student && <Badge tone="blue">{r.student.name}</Badge>}
                </div>
                <ul className="mt-1 list-disc space-y-0.5 pl-4 text-mist">{(r.rationale?.reasons ?? []).map((x: string) => <li key={x}>{x}</li>)}</ul>
                <p className="mt-1 text-dim">{r.rationale?.disclaimer} Modelo: {r.model_version ?? "—"} · {ago(r.created_at)}</p>
                {r.status === "new" && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    <Button size="sm" onClick={() => fb.mutate({ id: r.id, action: "accepted" })}><Check /> Aceptar</Button>
                    <Button size="sm" variant="outline" onClick={() => fb.mutate({ id: r.id, action: "dismissed" })}><X /> Descartar</Button>
                    <Button size="sm" variant="ghost" onClick={() => fb.mutate({ id: r.id, action: "useful" })}>Me fue útil</Button>
                  </div>
                )}
                {r.status === "accepted" && <Button size="sm" variant="outline" className="mt-2" onClick={() => fb.mutate({ id: r.id, action: "completed" })}><CircleCheck /> Marcar completada</Button>}
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}

const ACT_ICON: Record<string, [any, string]> = {
  course_completed: [CircleCheck, "bg-teal/20 text-teal"], certificate_issued: [Award, "bg-cyan/15 text-cyan"], enrollment: [PlayCircle, "bg-violet/20 text-[#FFC48A]"],
  assessment_graded: [FileCheck2, "bg-electric/20 text-[#A996FF]"], goal: [Target, "bg-cyan/15 text-cyan"], session: [BookOpen, "bg-electric/15 text-[#A996FF]"],
  model_deployed: [Rocket, "bg-violet/20 text-[#FFC48A]"], course_published: [BookOpen, "bg-teal/15 text-teal"],
};

export function ActivityFeed({ limit = 6, type }: { limit?: number; type?: string }) {
  const q = useQuery({ queryKey: ["activity", limit, type], queryFn: () => api(`/activity?limit=${limit}${type ? `&type=${type}` : ""}`) });
  if (q.isLoading) return <div className="skeleton h-48" />;
  if (q.error) return <ErrorState error={q.error} onRetry={q.refetch} />;
  if (!q.data?.items.length) return <p className="py-6 text-center text-[13px] text-mist">Aún no hay actividad registrada.</p>;
  return (
    <ul className="flex flex-col gap-1">
      {q.data.items.map((a: any) => {
        const [Icon, cls] = ACT_ICON[a.type] ?? [BookOpen, "bg-electric/15 text-cyan"];
        return (
          <li key={a.id} className="flex items-center gap-3 rounded-lg px-1 py-1.5">
            <span className={clsx("grid size-8 shrink-0 place-items-center rounded-lg", cls)}><Icon className="size-4" /></span>
            <span className="min-w-0 flex-1 truncate text-[13px]">{a.title}</span>
            <time className="shrink-0 text-[11px] text-mist" dateTime={a.created_at}>{ago(a.created_at)}</time>
          </li>
        );
      })}
    </ul>
  );
}

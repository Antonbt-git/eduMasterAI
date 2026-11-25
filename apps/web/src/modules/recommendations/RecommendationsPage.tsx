import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Lightbulb, Sparkles } from "lucide-react";
import { useState } from "react";
import { EmptyState, errorText, QueryState } from "@/components/feedback/states";
import { RecommendationList } from "@/components/ui/lists";
import { Button, PageHeader, Panel, Tabs } from "@/components/ui/primitives";
import { int, pct } from "@/lib/format";
import { api } from "@/services/api";
import { useAuth } from "@/stores/auth";
import { useUI } from "@/stores/ui";

export function RecommendationsPage() {
  const me = useAuth((s) => s.me)!;
  const qc = useQueryClient();
  const toast = useUI((s) => s.toast);
  const [status, setStatus] = useState("new");
  const q = useQuery({ queryKey: ["recommendations", status], queryFn: () => api(`/recommendations?limit=60${status ? `&status=${status}` : ""}`) });
  const students = useQuery({ queryKey: ["students", "pick"], queryFn: () => api("/students?limit=50"), enabled: !me.student_id && me.permissions.includes("recommendations:review") });
  const [sid, setSid] = useState("");
  const gen = useMutation({
    mutationFn: () => api("/recommendations/generate", { body: { student_id: sid || null } }),
    onSuccess: (d: any) => { toast("ok", `${d.items.length} recomendaciones generadas: modelo → reglas de negocio → explicación`); qc.invalidateQueries({ queryKey: ["recommendations"] }); },
    onError: (e) => toast("error", errorText(e)),
  });
  const m = q.data?.metrics;
  return (
    <div>
      <PageHeader title="Recomendaciones de IA" subtitle="Lista priorizada con motivo, impacto y confianza. El docente puede revisarlas; ninguna reemplaza su criterio."
        actions={<>
          {students.data && <select aria-label="Estudiante" value={sid} onChange={(e) => setSid(e.target.value)}><option value="">Elegir estudiante</option>{students.data.items.map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}</select>}
          {(me.student_id || students.data) && <Button variant="violet" onClick={() => gen.mutate()} loading={gen.isPending} disabled={!me.student_id && !sid}><Sparkles /> Generar con IA</Button>}
        </>} />
      {m && (
        <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
          {[["Nuevas", int(m.by_status.new ?? 0)], ["Aceptadas", int((m.by_status.accepted ?? 0) + (m.by_status.completed ?? 0))], ["Tasa de aceptación", pct(m.acceptance_rate, 0)], ["Utilidad reportada", pct(m.usefulness_rate, 0)]].map(([l, v]) => (
            <div key={l} className="panel-inner px-4 py-3"><div className="text-[12px] text-mist">{l}</div><div className="font-display text-2xl font-semibold tabular">{v}</div></div>
          ))}
        </div>
      )}
      <Panel title="Recomendaciones" icon={<Lightbulb />} actions={<Tabs value={status} onChange={setStatus} items={[{ value: "new", label: "Nuevas" }, { value: "accepted", label: "Aceptadas" }, { value: "completed", label: "Completadas" }, { value: "dismissed", label: "Descartadas" }, { value: "expired", label: "Expiradas" }, { value: "", label: "Todas" }]} />}>
        <QueryState q={q} empty={(d: any) => d.items.length === 0 ? <EmptyState title="No hay recomendaciones en este estado" text="Genera nuevas con la red de recomendación." /> : false}>
          {(d: any) => <RecommendationList items={d.items} />}
        </QueryState>
        {m && <p className="mt-3 text-[11px] text-dim">{m.note}</p>}
      </Panel>
    </div>
  );
}

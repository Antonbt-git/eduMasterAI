import { useMutation, useQuery } from "@tanstack/react-query";
import { Brain, ScanSearch } from "lucide-react";
import { useState } from "react";
import { SkillHeatmap } from "@/components/charts/charts";
import { errorText, QueryState } from "@/components/feedback/states";
import { FilterBar, useFilterQs } from "@/components/ui/FilterBar";
import { Avatar, Badge, Button, PageHeader, Panel, PermissionGate, Progress } from "@/components/ui/primitives";
import { pct } from "@/lib/format";
import { api } from "@/services/api";
import { useUI } from "@/stores/ui";

const LEVELS = ["Principiante", "Elemental", "Intermedio", "Avanzado", "Experto"];

export function SkillsPage() {
  const { q } = useFilterQs();
  const v = useQuery({ queryKey: ["analytics", "skill", q, "validated"], queryFn: () => api(`/analytics/skill-mastery${q}${q ? "&" : "?"}source=validated`) });
  const ai = useQuery({ queryKey: ["analytics", "skill", q, "ai"], queryFn: () => api(`/analytics/skill-mastery${q}${q ? "&" : "?"}source=ai`) });
  return (
    <div>
      <PageHeader title="Dominio de habilidades" subtitle="El nivel validado por evaluación o docente se muestra siempre separado del nivel estimado por la red de dominio." />
      <FilterBar exportable={false} />
      <div className="grid gap-4 xl:grid-cols-2">
        <Panel title="Nivel validado" icon={<Brain />} actions={<Badge tone="teal">Evaluación y docente</Badge>}>
          <QueryState q={v}>{(d: any) => <><SkillHeatmap skills={d.skills} levels={d.levels} matrix={d.matrix} height={280} /><p className="text-[11px] text-dim">{d.source}</p></>}</QueryState>
        </Panel>
        <Panel title="Estimación IA" icon={<Brain />} actions={<Badge tone="violet">No certificada</Badge>}>
          <QueryState q={ai} empty={(d: any) => d.matrix.every((m: number[]) => m[2] === 0) ? <p className="py-16 text-center text-[13px] text-mist">Aún no hay estimaciones. Ejecuta la red de dominio sobre estudiantes desde el panel de la derecha o la vista de estudiante.</p> : false}>
            {(d: any) => <><SkillHeatmap skills={d.skills} levels={d.levels} matrix={d.matrix} height={280} /><p className="text-[11px] text-dim">{d.source}</p></>}
          </QueryState>
        </Panel>
        <StudentLookup />
      </div>
    </div>
  );
}

function StudentLookup() {
  const toast = useUI((s) => s.toast);
  const [term, setTerm] = useState("");
  const [sel, setSel] = useState<string | null>(null);
  const list = useQuery({ queryKey: ["students", term], queryFn: () => api(`/students?limit=8&q=${encodeURIComponent(term)}`) });
  const detail = useQuery({ queryKey: ["students", sel, "progress"], queryFn: () => api(`/students/${sel}/progress`), enabled: !!sel });
  const run = useMutation({
    mutationFn: (net: string) => api("/ml/predictions", { body: { network_key: net, student_id: sel } }),
    onSuccess: () => { toast("ok", "Estimación registrada como evidencia IA (no oficial)"); detail.refetch(); },
    onError: (e) => toast("error", errorText(e)),
  });
  return (
    <Panel className="xl:col-span-2" title="Evidencias por estudiante" icon={<ScanSearch />}>
      <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
        <div>
          <input type="search" placeholder="Buscar estudiante" aria-label="Buscar estudiante" value={term} onChange={(e) => setTerm(e.target.value)} className="w-full" />
          <ul className="mt-2 max-h-80 overflow-auto">
            {list.data?.items.map((s: any) => (
              <li key={s.id}><button onClick={() => setSel(s.id)} className={`flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-[13px] ${sel === s.id ? "bg-electric/20" : "hover:bg-white/5"}`}>
                <Avatar src={s.avatar_url} name={s.name} size={26} /><span className="flex-1 truncate">{s.name}</span><span className="text-[11px] text-dim">{pct(s.avg_progress, 0)}</span></button></li>
            ))}
            {list.error && <li className="p-2 text-[13px] text-mist">Sin permiso para listar estudiantes.</li>}
          </ul>
        </div>
        <div>
          {!sel ? <p className="py-10 text-center text-[13px] text-mist">Selecciona un estudiante para ver sus evidencias por competencia.</p> : (
            <QueryState q={detail}>
              {(d: any) => (
                <div>
                  <div className="mb-3 flex flex-wrap items-center gap-2">
                    <span className="font-display text-lg font-semibold">{d.student.name}</span><Badge>{d.student.region}</Badge>
                    {d.risk_probability != null && <Badge tone={d.risk_probability > 0.6 ? "warn" : "teal"}>Riesgo estimado {pct(d.risk_probability, 0)}</Badge>}
                    <PermissionGate perm="ml:predict"><span className="ml-auto flex gap-1.5">
                      <Button size="sm" variant="violet" loading={run.isPending} onClick={() => run.mutate("mastery_ordinal")}>Estimar dominio</Button>
                      <Button size="sm" variant="outline" onClick={() => run.mutate("risk_transformer")}>Estimar riesgo</Button></span></PermissionGate>
                  </div>
                  <ul className="space-y-2">
                    {d.skills.map((s: any) => (
                      <li key={s.skill + s.source} className="flex items-center gap-3 text-[13px]">
                        <span className="w-44 truncate">{s.skill}</span><Progress value={s.score} tone={s.source === "ai_estimate" ? "violet" : "teal"} />
                        <Badge tone={s.source === "ai_estimate" ? "violet" : "teal"}>{s.source === "ai_estimate" ? "IA" : s.source === "instructor" ? "Docente" : "Evaluación"}</Badge>
                        <span className="w-24 text-right text-mist">{LEVELS[s.level]}</span>
                      </li>
                    ))}
                  </ul>
                  <p className="mt-3 text-[11px] text-dim">{d.note} La señal de riesgo es para apoyo humano: nunca sanciona ni excluye.</p>
                </div>
              )}
            </QueryState>
          )}
        </div>
      </div>
    </Panel>
  );
}

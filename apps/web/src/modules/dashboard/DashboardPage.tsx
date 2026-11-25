import { useQuery } from "@tanstack/react-query";
import { BarChart3, Brain, CircleGauge, Clock, Globe2, Lightbulb, PieChart } from "lucide-react";
import { Link } from "react-router-dom";
import { Bars, CompletionDonut, SkillHeatmap, TrendChart } from "@/components/charts/charts";
import { GeoProgressMap } from "@/components/charts/GeoProgressMap";
import { QueryState, Skeleton } from "@/components/feedback/states";
import { FilterBar, useFilterQs } from "@/components/ui/FilterBar";
import { KpiCard } from "@/components/ui/KpiCard";
import { ActivityFeed, RecommendationList } from "@/components/ui/lists";
import { DemoBadge, Panel, Tabs } from "@/components/ui/primitives";
import { STATE_LABEL, useNetworkLive, vizMode } from "@/hooks/useNetworkLive";
import { int, num, pct } from "@/lib/format";
import { api } from "@/services/api";
import { useAuth } from "@/stores/auth";
import { useUI } from "@/stores/ui";
import { type Graph, NeuralNetworkCanvas } from "../neural-visualizer/NeuralNetworkCanvas";
import { useState } from "react";
import { StudentHome } from "./StudentHome";

export function DashboardPage() {
  const me = useAuth((s) => s.me)!;
  if (!me.permissions.includes("analytics:read")) return <StudentHome />;
  return <ExecutiveDashboard />;
}

function ExecutiveDashboard() {
  const { q, f } = useFilterQs();
  const setFilters = useUI((s) => s.setFilters);
  const sum = useQuery({ queryKey: ["dashboard", "summary", q], queryFn: () => api(`/dashboard/summary${q}`) });
  const prog = useQuery({ queryKey: ["analytics", "progress", q], queryFn: () => api(`/analytics/progress${q}`) });
  const geo = useQuery({ queryKey: ["analytics", "geo", q], queryFn: () => api(`/analytics/geo${q}`) });
  const comp = useQuery({ queryKey: ["analytics", "completion", q], queryFn: () => api(`/analytics/completion${q}`) });
  const [src, setSrc] = useState<"validated" | "ai">("validated");
  const skill = useQuery({ queryKey: ["analytics", "skill", q, src], queryFn: () => api(`/analytics/skill-mastery${q}${q ? "&" : "?"}source=${src}`) });
  const recs = useQuery({ queryKey: ["recommendations", "dash"], queryFn: () => api("/recommendations?limit=5&status=new") });
  const k = sum.data?.kpis;

  return (
    <div>
      <FilterBar />
      <div className="grid gap-4 xl:grid-cols-12">
        <ArchitecturePanel kpis={k} className="xl:col-span-7" />
        <Panel className="xl:col-span-5" title="Progreso analítico" icon={<BarChart3 />} actions={<DemoBadge />}>
          <QueryState q={prog} skeleton={<Skeleton className="h-[300px]" />}>
            {(d: any) => (
              <>
                <div className="mb-1 flex items-end gap-6">
                  <div>
                    <div className="font-display text-[30px] leading-none font-semibold tabular">{int(d.series[0].data.reduce((a: number, b: number) => a + b, 0))} h</div>
                    <div className="mt-1 text-[13px] text-mist">Horas de aprendizaje en 12 meses</div>
                  </div>
                  {k?.learning_hours?.delta_pct != null && <div className={k.learning_hours.delta_pct >= 0 ? "text-[13px] text-teal" : "text-[13px] text-danger"}>{k.learning_hours.delta_pct >= 0 ? "↑ +" : "↓ "}{k.learning_hours.delta_pct}% vs. periodo anterior</div>}
                </div>
                <TrendChart labels={d.labels} series={d.series.slice(0, 3)} height={262} />
                <p className="text-[11px] text-dim">Sin facturación en el alcance: se muestran métricas académicas. Fuente: {d.source}.</p>
              </>
            )}
          </QueryState>
        </Panel>

        <Panel className="xl:col-span-4" title="Dominio de habilidades" icon={<Brain />}
          actions={<Tabs value={src} onChange={setSrc} items={[{ value: "validated", label: "Validado" }, { value: "ai", label: "Estimación IA" }]} />}>
          <QueryState q={skill} empty={(d: any) => d.matrix.every((m: number[]) => m[2] === 0) ? (
            <p className="py-10 text-center text-[13px] text-mist">{src === "ai" ? "Aún no hay estimaciones IA. Se generan al ejecutar el modelo de dominio sobre estudiantes." : "Sin evidencias validadas para estos filtros."}</p>) : false}>
            {(d: any) => <><SkillHeatmap skills={d.skills} levels={d.levels} matrix={d.matrix} height={250} /><p className="text-[11px] text-dim">{d.source}</p></>}
          </QueryState>
        </Panel>

        <Panel className="xl:col-span-5" title="Mapa de progreso de aprendizaje" icon={<Globe2 />}
          actions={f.region && <span className="text-[12px] text-violet">Filtrando: {f.region}</span>}>
          <QueryState q={geo} skeleton={<Skeleton className="h-[260px]" />}>
            {(d: any) => <GeoProgressMap regions={d.regions} selected={f.region} onSelect={(r) => setFilters({ region: r })} />}
          </QueryState>
          <p className="mt-1 text-[11px] text-dim">Estudiantes activos en el periodo, agregados por región. Toca una región para filtrar el panel.</p>
        </Panel>

        <Panel className="xl:col-span-3" title="Finalización de cursos" icon={<PieChart />}>
          <QueryState q={comp} empty={(d: any) => d.total === 0}>
            {(d: any) => (
              <>
                <CompletionDonut breakdown={d.breakdown} />
                <ul className="mt-1 space-y-1 text-[13px]">
                  {d.breakdown.map((b: any, i: number) => (
                    <li key={b.status} className="flex items-center gap-2">
                      <span className="size-2.5 rounded-full" style={{ background: ["#FF5FD2", "#FF9F43", "#6E7BFF"][i] }} />{b.label}
                      <span className="ml-auto font-medium tabular">{pct(b.pct, 0)}</span><span className="w-12 text-right text-[11px] text-dim tabular">{int(b.count)}</span>
                    </li>
                  ))}
                </ul>
                <div className="mt-2"><Bars values={d.weekly_completions} height={44} label="Finalizaciones por semana (26 semanas)" /></div>
              </>
            )}
          </QueryState>
        </Panel>

        <Panel className="xl:col-span-6" title="Recomendaciones de IA" icon={<Lightbulb />} actions={<Link to="/recomendaciones" className="text-[13px] text-cyan hover:underline">Ver todas</Link>}>
          <QueryState q={recs} empty={(d: any) => d.items.length === 0}>
            {(d: any) => <RecommendationList items={d.items} compact />}
          </QueryState>
        </Panel>
        <Panel className="xl:col-span-6" title="Actividad reciente" icon={<Clock />} actions={<Link to="/actividad" className="text-[13px] text-cyan hover:underline">Ver todas</Link>}>
          <ActivityFeed limit={6} />
        </Panel>
      </div>
    </div>
  );
}

function ArchitecturePanel({ kpis, className }: { kpis: any; className?: string }) {
  const graph = useQuery({ queryKey: ["ml", "graph", "edumaster_mtl", undefined], queryFn: () => api<Graph & any>("/ml/networks/edumaster_mtl/graph"), retry: 1 });
  const live = useNetworkLive("edumaster_mtl", { runId: graph.data?.last_run?.id, status: graph.data?.last_run?.status, history: graph.data?.last_run?.history });
  const mode = vizMode(live, false, !!live.activations);
  const rt = useUI((s) => s.rt);
  return (
    <Panel glow className={className} title="Arquitectura de aprendizaje inteligente" icon={<CircleGauge />}
      actions={
        <span className="inline-flex items-center gap-2 text-[13px]">
          <span className={`size-2 rounded-full ${rt === "live" ? "live-dot bg-teal" : "bg-danger"}`} />
          <span className={rt === "live" ? "text-teal" : "text-mist"}>{rt === "live" ? "En vivo" : "Sin conexión"}</span>
          <span className="text-dim">· {mode === "idle" && graph.data?.production_version ? "Publicado" : STATE_LABEL[mode]}</span>
        </span>
      }>
      <div className="grid-bg relative h-[330px] overflow-hidden rounded-xl border border-cyan/10">
        {graph.isLoading && <Skeleton className="absolute inset-3" />}
        {graph.error && <p className="p-6 text-[13px] text-mist">El servicio de inferencia no está disponible; la topología se mostrará cuando se reconecte.</p>}
        {graph.data && <NeuralNetworkCanvas graph={graph.data} mode={mode} activations={live.activations} gradNorms={live.gradNorms} pulseKey={live.pulseKey} backKey={live.backKey} showWeights />}
        {graph.data && (
          <Link to="/redes" className="absolute bottom-2 left-2 rounded-md border border-cyan/25 bg-ink/80 px-2 py-1 text-[11px] text-mist hover:text-frost">
            {graph.data.title} {graph.data.production_version ? `v${graph.data.production_version}` : ""} · ver las 5 redes
          </Link>
        )}
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2.5 md:grid-cols-4">
        <KpiCard label="Alumnos activos" kpi={kpis?.active_students} format={(v) => int(v)} />
        <KpiCard label="Cursos publicados" kpi={kpis?.courses} format={(v) => int(v)} />
        <KpiCard label="Horas de aprendizaje" kpi={kpis?.learning_hours} format={(v) => num(v, 0)} />
        <KpiCard label="Certificaciones" kpi={kpis?.certifications} format={(v) => int(v)} note={kpis ? `${int(kpis.certifications.period_value)} en el periodo` : undefined} />
      </div>
    </Panel>
  );
}

import { useQuery } from "@tanstack/react-query";
import { BarChart3, Table2 } from "lucide-react";
import { TrendChart } from "@/components/charts/charts";
import { QueryState } from "@/components/feedback/states";
import { FilterBar, useFilterQs } from "@/components/ui/FilterBar";
import { KpiCard } from "@/components/ui/KpiCard";
import { DemoBadge, PageHeader, Panel, Progress, StatusBadge } from "@/components/ui/primitives";
import { int, num, pct } from "@/lib/format";
import { api } from "@/services/api";

export function AnalyticsPage() {
  const { q } = useFilterQs();
  const sum = useQuery({ queryKey: ["dashboard", "summary", q], queryFn: () => api(`/dashboard/summary${q}`) });
  const prog = useQuery({ queryKey: ["analytics", "progress", q], queryFn: () => api(`/analytics/progress${q}`) });
  const table = useQuery({ queryKey: ["analytics", "courses", q], queryFn: () => api(`/analytics/courses${q}`) });
  const k = sum.data?.kpis;
  return (
    <div>
      <PageHeader title="Analítica educativa" subtitle="Participación, tiempo activo, entregas, progreso y finalización. Cada indicador tiene una definición documentada y se exporta con fecha y filtros." actions={<DemoBadge />} />
      <FilterBar />
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <KpiCard label="Alumnos activos" kpi={k?.active_students} format={int} />
        <KpiCard label="Horas de aprendizaje" kpi={k?.learning_hours} format={(v) => num(v, 0)} />
        <KpiCard label="Tasa de finalización" kpi={k?.completion_rate} format={(v) => pct(v)} accent="teal" />
        <KpiCard label="Certificaciones" kpi={k?.certifications} format={int} />
        <KpiCard label="Puntuación global" kpi={k?.global_score} format={(v) => pct(v)} accent="violet" />
        <KpiCard label="Cursos publicados" kpi={k?.courses} format={int} />
      </div>
      <Panel title="Tendencia mensual" icon={<BarChart3 />} className="mb-4">
        <QueryState q={prog}>{(d: any) => <TrendChart labels={d.labels} series={d.series} height={300} />}</QueryState>
      </Panel>
      <Panel title="Indicadores por curso" icon={<Table2 />}>
        <QueryState q={table} empty={(d: any) => d.items.length === 0}>
          {(d: any) => (
            <>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[900px] text-[13px]">
                  <thead className="text-left text-[12px] text-mist">
                    <tr>{["Curso", "Estado", "Matriculados", "Avance medio", "Finalización", "Participación", "Horas activas", "Entregas", "Nota media", "Tardías"].map((h) => <th key={h} className="pb-2 font-normal">{h}</th>)}</tr>
                  </thead>
                  <tbody>
                    {d.items.map((r: any) => (
                      <tr key={r.course_id} className="border-t border-line/40">
                        <td className="py-2"><span className="text-cyan">{r.code}</span> {r.title}</td>
                        <td><StatusBadge status={r.status} /></td>
                        <td className="tabular">{int(r.enrolled)}</td>
                        <td className="w-36"><div className="flex items-center gap-2"><Progress value={r.avg_progress} /><span className="tabular">{pct(r.avg_progress, 0)}</span></div></td>
                        <td className="tabular">{pct(r.completion_rate, 0)}</td>
                        <td className="tabular">{pct(r.participation, 0)}</td>
                        <td className="tabular">{num(r.active_hours, 1)}</td>
                        <td className="tabular">{int(r.submissions)}</td>
                        <td className="tabular">{r.avg_score === null ? "—" : pct(r.avg_score, 0)}</td>
                        <td className="tabular">{int(r.late_submissions)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <details className="mt-3 text-[12px] text-mist"><summary className="cursor-pointer text-frost">Definición de indicadores</summary>
                <ul className="mt-2 list-disc space-y-1 pl-5">{Object.entries(d.definitions).map(([k2, v]) => <li key={k2}><b className="text-frost">{k2}</b>: {v as string}</li>)}</ul>
              </details>
            </>
          )}
        </QueryState>
      </Panel>
    </div>
  );
}

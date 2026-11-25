import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Award, BookOpenCheck, Brain, Clock, Lightbulb, Map as MapIcon, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import { Bars } from "@/components/charts/charts";
import { errorText, QueryState } from "@/components/feedback/states";
import { ActivityFeed, RecommendationList } from "@/components/ui/lists";
import { Badge, Button, PageHeader, Panel, Progress, StatusBadge } from "@/components/ui/primitives";
import { pct } from "@/lib/format";
import { api } from "@/services/api";
import { useAuth } from "@/stores/auth";
import { useUI } from "@/stores/ui";

const LEVELS = ["Principiante", "Elemental", "Intermedio", "Avanzado", "Experto"];

export function StudentHome() {
  const me = useAuth((s) => s.me)!;
  const qc = useQueryClient();
  const toast = useUI((s) => s.toast);
  const prog = useQuery({ queryKey: ["dashboard", "me"], queryFn: () => api("/me/progress"), enabled: !!me.student_id });
  const recs = useQuery({ queryKey: ["recommendations", "mine"], queryFn: () => api("/recommendations?limit=6") });
  const paths = useQuery({ queryKey: ["paths"], queryFn: () => api<any[]>("/learning-paths") });
  const certs = useQuery({ queryKey: ["certificates"], queryFn: () => api("/certificates") });
  const gen = useMutation({
    mutationFn: () => api("/recommendations/generate", { body: {} }),
    onSuccess: (d: any) => { qc.invalidateQueries({ queryKey: ["recommendations"] }); toast("ok", `${d.items.length} recomendaciones generadas por la red de recomendación`); },
    onError: (e) => toast("error", errorText(e)),
  });
  return (
    <div>
      <PageHeader title={`Hola, ${me.full_name.split(" ")[0]}`} subtitle="Tu avance, tus próximos pasos y lo que te sugiere la IA. Las sugerencias son orientativas; tu docente tiene la última palabra." />
      <div className="grid gap-4 xl:grid-cols-12">
        <Panel className="xl:col-span-7" glow title="Mis cursos" icon={<BookOpenCheck />}>
          <QueryState q={prog} empty={(d: any) => d.courses.length === 0 ? <p className="py-8 text-center text-mist">Aún no estás matriculado. <Link className="text-cyan" to="/cursos">Explora el catálogo</Link>.</p> : false}>
            {(d: any) => (
              <ul className="grid gap-2 md:grid-cols-2">
                {d.courses.map((c: any) => (
                  <li key={c.enrollment_id} className="panel-inner p-3">
                    <div className="flex items-start gap-2">
                      <Link to={`/cursos/${c.course_id}`} className="min-w-0 flex-1 font-medium hover:text-cyan">{c.course_title}</Link>
                      <StatusBadge status={c.status} />
                    </div>
                    <div className="mt-2 flex items-center gap-2"><Progress value={c.progress} /><span className="w-10 text-right text-[12px] tabular">{pct(c.progress, 0)}</span></div>
                    {c.attempts.length > 0 && <div className="mt-1 text-[11px] text-mist">Última nota: {Math.round(c.attempts.at(-1).score ?? 0)}/{c.attempts.at(-1).max_score}</div>}
                  </li>
                ))}
              </ul>
            )}
          </QueryState>
        </Panel>
        <Panel className="xl:col-span-5" title="Mi actividad semanal" icon={<Clock />}>
          <QueryState q={prog} empty={(d: any) => d.weekly_activity.length === 0}>
            {(d: any) => <Bars labels={d.weekly_activity.map((w: any) => w.week)} values={d.weekly_activity.map((w: any) => w.hours)} height={150} label="Horas de estudio por semana" />}
          </QueryState>
          <p className="mt-1 text-[11px] text-dim">Horas registradas por semana (duración acotada; no equivale a atención real).</p>
        </Panel>
        <Panel className="xl:col-span-6" title="Recomendaciones de IA" icon={<Lightbulb />}
          actions={<Button size="sm" variant="violet" onClick={() => gen.mutate()} loading={gen.isPending}><Sparkles /> Generar con IA</Button>}>
          <QueryState q={recs} empty={(d: any) => d.items.length === 0}>{(d: any) => <RecommendationList items={d.items} />}</QueryState>
        </Panel>
        <Panel className="xl:col-span-6" title="Mis competencias" icon={<Brain />}>
          <QueryState q={prog} empty={(d: any) => d.skills.length === 0}>
            {(d: any) => (
              <ul className="space-y-2">
                {d.skills.map((s: any) => (
                  <li key={s.skill + s.source} className="flex items-center gap-3 text-[13px]">
                    <span className="w-40 truncate">{s.skill}</span>
                    <Progress value={s.score} tone={s.source === "ai_estimate" ? "violet" : "teal"} />
                    <Badge tone={s.source === "ai_estimate" ? "violet" : "teal"}>{s.source === "ai_estimate" ? "Estimación IA" : s.source === "instructor" ? "Validado docente" : "Evaluación"}</Badge>
                    <span className="w-24 text-right text-[12px] text-mist">{LEVELS[s.level]}</span>
                  </li>
                ))}
              </ul>
            )}
          </QueryState>
        </Panel>
        <Panel className="xl:col-span-4" title="Mis rutas" icon={<MapIcon />}>
          <QueryState q={paths} empty={(d) => d.length === 0}>
            {(d) => <ul className="space-y-3">{d.filter((p) => p.my_progress).map((p) => (
              <li key={p.id}><div className="flex text-[13px]"><span className="flex-1 truncate">{p.title}</span><span className="tabular text-mist">{pct(p.my_progress.progress, 0)}</span></div><Progress value={p.my_progress.progress} tone="violet" className="mt-1" /></li>
            ))}</ul>}
          </QueryState>
        </Panel>
        <Panel className="xl:col-span-4" title="Certificados" icon={<Award />} actions={<Link to="/certificados" className="text-[13px] text-cyan">Ver todos</Link>}>
          <QueryState q={certs}>
            {(d: any) => (
              <div className="text-[13px]">
                <div className="font-display text-3xl font-semibold">{d.items.length}</div>
                <div className="text-mist">certificados emitidos</div>
                {d.eligible.length > 0 && <p className="mt-2 text-teal">Puedes solicitar {d.eligible.length} certificado(s) nuevo(s).</p>}
              </div>
            )}
          </QueryState>
        </Panel>
        <Panel className="xl:col-span-4" title="Actividad reciente" icon={<Clock />}><ActivityFeed limit={5} /></Panel>
      </div>
    </div>
  );
}

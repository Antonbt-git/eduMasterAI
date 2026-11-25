import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Rocket, Route, UserPlus } from "lucide-react";
import { useState } from "react";
import { EmptyState, errorText, QueryState } from "@/components/feedback/states";
import { Badge, Button, Field, Modal, PageHeader, Panel, PermissionGate, Progress, StatusBadge } from "@/components/ui/primitives";
import { pct } from "@/lib/format";
import { api } from "@/services/api";
import { useUI } from "@/stores/ui";

export function PathsPage() {
  const q = useQuery({ queryKey: ["paths"], queryFn: () => api<any[]>("/learning-paths") });
  const [create, setCreate] = useState(false);
  const [assign, setAssign] = useState<any>(null);
  const qc = useQueryClient();
  const toast = useUI((s) => s.toast);
  const publish = useMutation({
    mutationFn: (id: string) => api(`/learning-paths/${id}/publish`, { method: "POST" }),
    onSuccess: () => { toast("ok", "Ruta publicada"); qc.invalidateQueries({ queryKey: ["paths"] }); },
    onError: (e) => toast("error", errorText(e)),
  });
  return (
    <div>
      <PageHeader title="Planes de aprendizaje" subtitle="Rutas con objetivos, competencias, prerrequisitos y criterios de logro, asignables a estudiantes o cohortes."
        actions={<PermissionGate perm="paths:write"><Button onClick={() => setCreate(true)}><Plus /> Nueva ruta</Button></PermissionGate>} />
      <QueryState q={q} empty={(d) => d.length === 0 ? <EmptyState title="Aún no hay rutas" text="Crea una ruta combinando cursos publicados." /> : false}>
        {(d) => (
          <div className="grid gap-4 lg:grid-cols-2">
            {d.map((p) => (
              <Panel key={p.id} title={p.title} icon={<Route />} actions={<StatusBadge status={p.status} />}>
                <p className="text-[13px] text-mist">{p.objective}</p>
                <div className="mt-2 flex flex-wrap gap-1">{p.competencies.map((c: string) => <Badge key={c} tone="violet">{c}</Badge>)}<Badge>{p.duration_weeks} semanas</Badge><Badge>v{p.version}</Badge></div>
                <ol className="mt-4 flex flex-col gap-0">
                  {p.steps.map((s: any, i: number) => {
                    const mine = p.my_progress?.steps?.find((x: any) => x.course_id === s.course_id);
                    return (
                      <li key={s.id} className="relative flex gap-3 pb-3 pl-1">
                        {i < p.steps.length - 1 && <span className="absolute top-7 left-[15px] h-[calc(100%-20px)] w-px bg-gradient-to-b from-cyan/60 to-violet/30" aria-hidden />}
                        <span className={`z-10 grid size-7 shrink-0 place-items-center rounded-full border text-[12px] font-semibold ${mine?.status === "completed" ? "border-teal bg-teal/20 text-teal" : "border-cyan/50 bg-ink text-cyan"}`}>{i + 1}</span>
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2 text-[13px]"><span className="font-medium">{s.course_title}</span><span className="text-dim">{s.course_code}</span>
                            {s.course_status !== "published" && <Badge tone="warn">No publicado</Badge>}</div>
                          {i > 0 && <div className="text-[11px] text-dim">Requiere completar el paso {i}</div>}
                          {mine && <div className="mt-1 flex items-center gap-2"><Progress value={mine.progress} /><span className="text-[11px] tabular">{pct(mine.progress, 0)}</span></div>}
                        </div>
                      </li>
                    );
                  })}
                </ol>
                <div className="mt-1 flex items-center gap-3 border-t border-line/40 pt-3 text-[12px] text-mist">
                  <span>{p.assignments} asignaciones</span><span>Avance medio {pct(p.avg_progress, 0)}</span>
                  {p.my_progress && <span className="text-cyan">Mi avance {pct(p.my_progress.progress, 0)}</span>}
                  <PermissionGate perm="paths:write">
                    <span className="ml-auto flex gap-2">
                      {p.status !== "published" && <Button size="sm" onClick={() => publish.mutate(p.id)}><Rocket /> Publicar</Button>}
                      {p.status === "published" && <Button size="sm" variant="outline" onClick={() => setAssign(p)}><UserPlus /> Asignar</Button>}
                    </span>
                  </PermissionGate>
                </div>
                <p className="mt-2 text-[11px] text-dim">Criterio de logro: {p.criteria}</p>
              </Panel>
            ))}
          </div>
        )}
      </QueryState>
      <CreatePath open={create} onClose={() => setCreate(false)} />
      {assign && <AssignPath path={assign} onClose={() => setAssign(null)} />}
    </div>
  );
}

function CreatePath({ open, onClose }: { open: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const toast = useUI((s) => s.toast);
  const courses = useQuery({ queryKey: ["courses", "all"], queryFn: () => api("/courses?page_size=100"), enabled: open });
  const [f, setF] = useState({ title: "", objective: "", competencies: "", duration_weeks: 12, course_ids: [] as string[] });
  const m = useMutation({
    mutationFn: () => api("/learning-paths", { body: { ...f, competencies: f.competencies.split(",").map((x) => x.trim()).filter(Boolean) } }),
    onSuccess: () => { toast("ok", "Ruta creada como borrador"); qc.invalidateQueries({ queryKey: ["paths"] }); onClose(); },
    onError: (e) => toast("error", errorText(e)),
  });
  return (
    <Modal open={open} onClose={onClose} title="Nueva ruta de aprendizaje" wide>
      <form className="grid gap-3" onSubmit={(e) => { e.preventDefault(); m.mutate(); }}>
        <Field label="Título"><input required minLength={3} value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></Field>
        <Field label="Objetivo"><textarea rows={2} value={f.objective} onChange={(e) => setF({ ...f, objective: e.target.value })} /></Field>
        <div className="grid gap-3 md:grid-cols-2">
          <Field label="Competencias (separadas por coma)"><input value={f.competencies} onChange={(e) => setF({ ...f, competencies: e.target.value })} /></Field>
          <Field label="Duración (semanas)"><input type="number" min={1} max={104} value={f.duration_weeks} onChange={(e) => setF({ ...f, duration_weeks: +e.target.value })} /></Field>
        </div>
        <Field label="Secuencia de cursos (en orden de selección; cada uno es prerrequisito del siguiente)">
          <div className="flex max-h-48 flex-wrap gap-1.5 overflow-auto">
            {courses.data?.items.map((c: any) => {
              const pos = f.course_ids.indexOf(c.id);
              return <button type="button" key={c.id} onClick={() => setF({ ...f, course_ids: pos >= 0 ? f.course_ids.filter((x) => x !== c.id) : [...f.course_ids, c.id] })}
                className={`rounded-full border px-2.5 py-1 text-[12px] ${pos >= 0 ? "border-cyan bg-cyan/15" : "border-line text-mist"}`}>{pos >= 0 && `${pos + 1}. `}{c.code}</button>;
            })}
          </div>
        </Field>
        <div className="flex justify-end"><Button type="submit" loading={m.isPending} disabled={!f.course_ids.length}>Crear ruta</Button></div>
      </form>
    </Modal>
  );
}

function AssignPath({ path, onClose }: { path: any; onClose: () => void }) {
  const qc = useQueryClient();
  const toast = useUI((s) => s.toast);
  const cohorts = useQuery({ queryKey: ["cohorts"], queryFn: () => api<any[]>("/cohorts") });
  const [cohort, setCohort] = useState("");
  const [target, setTarget] = useState("");
  const [note, setNote] = useState("");
  const m = useMutation({
    mutationFn: () => api(`/learning-paths/${path.id}/assign`, { body: { cohort_id: cohort || null, target_date: target || null, exception_note: note || null } }),
    onSuccess: () => { toast("ok", "Ruta asignada"); qc.invalidateQueries({ queryKey: ["paths"] }); onClose(); },
    onError: (e) => toast("error", errorText(e)),
  });
  return (
    <Modal open onClose={onClose} title={`Asignar: ${path.title}`}>
      <div className="grid gap-3">
        <Field label="Cohorte"><select value={cohort} onChange={(e) => setCohort(e.target.value)}><option value="">Seleccione</option>{cohorts.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field>
        <Field label="Fecha objetivo"><input type="date" value={target} onChange={(e) => setTarget(e.target.value)} /></Field>
        <Field label="Excepción autorizada (opcional)"><input value={note} onChange={(e) => setNote(e.target.value)} /></Field>
        <div className="flex justify-end"><Button onClick={() => m.mutate()} loading={m.isPending} disabled={!cohort}>Asignar</Button></div>
      </div>
    </Modal>
  );
}

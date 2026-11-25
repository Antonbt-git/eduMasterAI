import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { ArrowLeft, BookOpen, CheckCircle2, Download, FileUp, Plus, Rocket, Trash2, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { EmptyState, errorText, QueryState, Skeleton } from "@/components/feedback/states";
import { Avatar, Badge, Button, Field, Modal, PageHeader, Panel, PermissionGate, Progress, StatusBadge } from "@/components/ui/primitives";
import { int, LEVEL_ES, pct } from "@/lib/format";
import { api, download, qs } from "@/services/api";
import { useAuth } from "@/stores/auth";
import { useUI } from "@/stores/ui";

export function CoursesPage() {
  const [sp, setSp] = useSearchParams();
  const [page, setPage] = useState(1);
  const params = { q: sp.get("q") ?? "", level: sp.get("level") ?? "", status: sp.get("status") ?? "", skill_id: sp.get("skill") ?? "" };
  const list = useQuery({ queryKey: ["courses", params, page], queryFn: () => api(`/courses${qs({ ...params, page, page_size: 12 })}`) });
  const skills = useQuery({ queryKey: ["skills"], queryFn: () => api<any[]>("/skills") });
  const [creating, setCreating] = useState(false);
  const set = (k: string, v: string) => { const n = new URLSearchParams(sp); v ? n.set(k, v) : n.delete(k); setSp(n); setPage(1); };
  return (
    <div>
      <PageHeader title="Cursos y contenidos" subtitle="Catálogo con versionado de contenido y control de publicación. Cada cambio queda auditado."
        actions={<PermissionGate perm="courses:write"><ImportExport /><Button onClick={() => setCreating(true)}><Plus /> Nuevo curso</Button></PermissionGate>} />
      <div className="mb-4 flex flex-wrap gap-2">
        <input type="search" placeholder="Buscar por nombre, código o descripción" aria-label="Buscar" defaultValue={params.q} onKeyDown={(e) => e.key === "Enter" && set("q", (e.target as HTMLInputElement).value)} className="w-72" />
        <select aria-label="Nivel" value={params.level} onChange={(e) => set("level", e.target.value)}><option value="">Todos los niveles</option><option value="basico">Básico</option><option value="intermedio">Intermedio</option><option value="avanzado">Avanzado</option></select>
        <PermissionGate perm="courses:write"><select aria-label="Estado" value={params.status} onChange={(e) => set("status", e.target.value)}><option value="">Todos los estados</option><option value="published">Publicados</option><option value="draft">Borradores</option><option value="archived">Archivados</option></select></PermissionGate>
        <select aria-label="Competencia" value={params.skill_id} onChange={(e) => set("skill", e.target.value)}><option value="">Todas las competencias</option>{skills.data?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select>
      </div>
      <QueryState q={list} skeleton={<div className="grid gap-3 md:grid-cols-3">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-44" />)}</div>}
        empty={(d: any) => d.items.length === 0 ? <EmptyState title="No hay cursos con estos filtros" text="Cambia la búsqueda o crea un curso nuevo." /> : false}>
        {(d: any) => (
          <>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{d.items.map((c: any) => <CourseCard key={c.id} c={c} />)}</div>
            <div className="mt-4 flex items-center justify-center gap-3 text-[13px] text-mist">
              <Button size="sm" variant="outline" disabled={page === 1} onClick={() => setPage(page - 1)}>Anterior</Button>
              Página {page} de {Math.max(1, Math.ceil(d.total / d.page_size))} · {int(d.total)} cursos
              <Button size="sm" variant="outline" disabled={page * d.page_size >= d.total} onClick={() => setPage(page + 1)}>Siguiente</Button>
            </div>
          </>
        )}
      </QueryState>
      <CreateCourse open={creating} onClose={() => setCreating(false)} />
    </div>
  );
}

function CourseCard({ c }: { c: any }) {
  return (
    <Link to={`/cursos/${c.id}`} className="panel group flex flex-col overflow-hidden transition-colors hover:!border-cyan/50">
      <div className="h-1.5" style={{ background: `linear-gradient(90deg, ${c.cover_color}, #FF9F43)` }} />
      <div className="flex flex-1 flex-col p-4">
        <div className="flex items-center gap-2 text-[12px] text-mist"><span className="font-medium text-cyan">{c.code}</span>{LEVEL_ES[c.level]}<span className="ml-auto"><StatusBadge status={c.status} /></span></div>
        <h3 className="font-display mt-1.5 text-[16px] leading-snug font-semibold group-hover:text-cyan">{c.title}</h3>
        <p className="mt-1 line-clamp-2 text-[13px] text-mist">{c.description}</p>
        <div className="mt-2 flex flex-wrap gap-1">{c.skills.map((s: any) => <Badge key={s.id} tone="violet">{s.name}</Badge>)}</div>
        <div className="mt-auto flex items-center gap-2 pt-3 text-[12px] text-mist">
          {c.instructor && <Avatar src={c.instructor.avatar_url} name={c.instructor.name} size={22} />}
          <span className="truncate">{c.instructor?.name ?? "Sin docente"}</span>
          <span className="ml-auto tabular">{int(c.stats.enrolled)} matriculados · {c.duration_hours} h</span>
        </div>
        {c.my_enrollment && <div className="mt-2 flex items-center gap-2"><Progress value={c.my_enrollment.progress} /><span className="text-[12px] tabular">{pct(c.my_enrollment.progress, 0)}</span></div>}
      </div>
    </Link>
  );
}

function ImportExport() {
  const ref = useRef<HTMLInputElement>(null);
  const toast = useUI((s) => s.toast);
  const qc = useQueryClient();
  const onFile = async (f: File) => {
    const form = new FormData();
    form.append("file", f);
    try {
      const r = await api("/courses/import", { form, headers: { "Idempotency-Key": `${f.name}-${f.size}-${f.lastModified}` } });
      toast(r.errors.length ? "info" : "ok", `Importación: ${r.created} creados, ${r.skipped} existentes, ${r.errors.length} con errores${r.idempotent_replay ? " (ya importado antes)" : ""}`);
      qc.invalidateQueries({ queryKey: ["courses"] });
    } catch (e) { toast("error", errorText(e)); }
  };
  return (
    <>
      <input ref={ref} type="file" accept=".csv" hidden onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])} />
      <Button variant="outline" onClick={() => ref.current?.click()}><Upload /> Importar CSV</Button>
      <Button variant="outline" onClick={() => download("/courses/export", "cursos.csv")}><Download /> Exportar</Button>
    </>
  );
}

function CreateCourse({ open, onClose }: { open: boolean; onClose: () => void }) {
  const nav = useNavigate();
  const toast = useUI((s) => s.toast);
  const skills = useQuery({ queryKey: ["skills"], queryFn: () => api<any[]>("/skills") });
  const instructors = useQuery({ queryKey: ["instructors"], queryFn: () => api<any[]>("/instructors"), enabled: open });
  const [f, setF] = useState({ code: "", title: "", description: "", level: "basico", duration_hours: 20, skill_ids: [] as string[], instructor_id: "", unit: "Unidad 1: Fundamentos", lessons: "Introducción\nConceptos clave\nLaboratorio" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const m = useMutation({
    mutationFn: () => api("/courses", { body: { code: f.code, title: f.title, description: f.description, level: f.level, duration_hours: +f.duration_hours, skill_ids: f.skill_ids,
      instructor_id: f.instructor_id || null, units: f.unit ? [{ title: f.unit, lessons: f.lessons.split("\n").filter(Boolean).map((t) => ({ title: t })) }] : [] } }),
    onSuccess: (c: any) => { toast("ok", `Curso ${c.code} creado como borrador`); onClose(); nav(`/cursos/${c.id}`); },
    onError: (e: any) => { if (Array.isArray(e.details)) setErrors(Object.fromEntries(e.details.map((d: any) => [d.field, d.message]))); toast("error", errorText(e)); },
  });
  return (
    <Modal open={open} onClose={onClose} title="Nuevo curso" wide>
      <form className="grid gap-3 md:grid-cols-2" onSubmit={(e) => { e.preventDefault(); m.mutate(); }}>
        <Field label="Código" hint="Único en la institución, p. ej. IA-401" error={errors.code}><input required value={f.code} onChange={(e) => setF({ ...f, code: e.target.value })} pattern="[A-Za-z0-9\-_]+" /></Field>
        <Field label="Nombre" error={errors.title}><input required minLength={3} value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></Field>
        <Field label="Nivel"><select value={f.level} onChange={(e) => setF({ ...f, level: e.target.value })}><option value="basico">Básico</option><option value="intermedio">Intermedio</option><option value="avanzado">Avanzado</option></select></Field>
        <Field label="Duración (horas)"><input type="number" min={1} max={1000} value={f.duration_hours} onChange={(e) => setF({ ...f, duration_hours: +e.target.value })} /></Field>
        <Field label="Docente"><select value={f.instructor_id} onChange={(e) => setF({ ...f, instructor_id: e.target.value })}><option value="">Sin asignar</option>{instructors.data?.map((i) => <option key={i.id} value={i.id}>{i.name}</option>)}</select></Field>
        <Field label="Competencias">
          <div className="flex flex-wrap gap-1.5">{skills.data?.map((s) => (
            <button type="button" key={s.id} onClick={() => setF({ ...f, skill_ids: f.skill_ids.includes(s.id) ? f.skill_ids.filter((x) => x !== s.id) : [...f.skill_ids, s.id] })}
              className={clsx("rounded-full border px-2.5 py-1 text-[12px]", f.skill_ids.includes(s.id) ? "border-violet bg-violet/20" : "border-line text-mist")}>{s.name}</button>))}</div>
        </Field>
        <div className="md:col-span-2"><Field label="Descripción"><textarea rows={2} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} /></Field></div>
        <Field label="Primera unidad"><input value={f.unit} onChange={(e) => setF({ ...f, unit: e.target.value })} /></Field>
        <Field label="Lecciones (una por línea)"><textarea rows={3} value={f.lessons} onChange={(e) => setF({ ...f, lessons: e.target.value })} /></Field>
        <div className="flex justify-end gap-2 md:col-span-2"><Button type="button" variant="ghost" onClick={onClose}>Cancelar</Button><Button type="submit" loading={m.isPending}>Crear borrador</Button></div>
      </form>
    </Modal>
  );
}

export function CourseDetailPage() {
  const { id } = useParams();
  const me = useAuth((s) => s.me)!;
  const qc = useQueryClient();
  const toast = useUI((s) => s.toast);
  const c = useQuery({ queryKey: ["courses", "detail", id], queryFn: () => api(`/courses/${id}`) });
  const prog = useQuery({ queryKey: ["dashboard", "me"], queryFn: () => api("/me/progress"), enabled: !!me.student_id });
  const [unitOpen, setUnitOpen] = useState(false);
  const refresh = () => { qc.invalidateQueries({ queryKey: ["courses"] }); qc.invalidateQueries({ queryKey: ["dashboard"] }); };
  const act = useMutation({
    mutationFn: ({ path, method = "POST" }: { path: string; method?: string }) => api(path, { method }),
    onSuccess: (_d, v) => { toast("ok", v.path.endsWith("publish") ? "Curso publicado" : v.path.endsWith("archive") ? "Curso archivado" : v.path.endsWith("enroll") ? "Matrícula confirmada" : "Lección eliminada"); refresh(); },
    onError: (e) => toast("error", errorText(e)),
  });
  const view = useMutation({
    mutationFn: (lessonId: string) => api("/learning-events", { body: { event_id: crypto.randomUUID(), event_type: "lesson_viewed", occurred_at: new Date().toISOString(), course_id: id, activity_id: lessonId, duration_seconds: 600, source: "web" } }),
    onSuccess: (r: any) => { toast("ok", `Lección registrada. Avance del curso: ${pct(r.progress, 0)}`); refresh(); },
    onError: (e) => toast("error", errorText(e)),
  });
  return (
    <QueryState q={c} skeleton={<Skeleton className="h-96" />}>
      {(d: any) => {
        const mine = d.my_enrollment;
        return (
          <div>
            <Link to="/cursos" className="mb-3 inline-flex items-center gap-1 text-[13px] text-mist hover:text-frost"><ArrowLeft className="size-4" /> Catálogo</Link>
            <PageHeader title={d.title} subtitle={<>{d.code} · {LEVEL_ES[d.level]} · versión {d.version} · {d.duration_hours} h</>}
              actions={<>
                <StatusBadge status={d.status} />
                {me.student_id && !mine && d.status === "published" && <Button onClick={() => act.mutate({ path: `/courses/${d.id}/enroll` })}>Matricularme</Button>}
                <PermissionGate perm="courses:write">
                  {d.status !== "published" && <Button onClick={() => act.mutate({ path: `/courses/${d.id}/publish` })} loading={act.isPending}><Rocket /> Publicar</Button>}
                  {d.status === "published" && <Button variant="outline" onClick={() => act.mutate({ path: `/courses/${d.id}/archive` })}>Archivar</Button>}
                </PermissionGate>
              </>} />
            <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
              <Panel title="Contenido" icon={<BookOpen />} actions={<PermissionGate perm={["courses:write", "assessments:write"]}><Button size="sm" variant="outline" onClick={() => setUnitOpen(true)}><Plus /> Unidad</Button></PermissionGate>}>
                {d.units.length === 0 && <EmptyState title="Este curso aún no tiene unidades" text="Agrega una unidad con lecciones para poder publicarlo." />}
                <ol className="space-y-3">
                  {d.units.map((u: any) => (
                    <li key={u.id} className="panel-inner p-3">
                      <h3 className="font-display font-semibold">{u.title}</h3>
                      <ul className="mt-2 divide-y divide-line/40">
                        {u.lessons.map((l: any) => (
                          <li key={l.id} className="flex items-center gap-3 py-2 text-[13px]">
                            <Badge tone={l.kind === "activity" ? "violet" : "cyan"}>{l.kind === "activity" ? "Actividad" : l.kind === "resource" ? "Recurso" : "Lección"}</Badge>
                            <span className="flex-1">{l.title}</span><span className="text-dim">{l.duration_min} min</span>
                            {mine && <Button size="sm" variant="ghost" onClick={() => view.mutate(l.id)}><CheckCircle2 /> Registrar avance</Button>}
                            <PermissionGate perm="courses:write"><button onClick={() => act.mutate({ path: `/courses/${d.id}/lessons/${l.id}`, method: "DELETE" })} aria-label={`Eliminar ${l.title}`} className="text-dim hover:text-danger"><Trash2 className="size-4" /></button></PermissionGate>
                          </li>
                        ))}
                      </ul>
                    </li>
                  ))}
                </ol>
              </Panel>
              <div className="flex flex-col gap-4">
                {mine && <Panel title="Mi avance"><div className="font-display text-3xl font-semibold">{pct(mine.progress, 0)}</div><Progress value={mine.progress} className="mt-2" />
                  <p className="mt-2 text-[12px] text-mist">60% lecciones vistas + 40% evaluaciones aprobadas. {prog.data && "Se actualiza en tiempo real."}</p></Panel>}
                <Panel title="Resumen">
                  <dl className="grid grid-cols-2 gap-y-1.5 text-[13px]">
                    <dt className="text-mist">Matriculados</dt><dd className="tabular">{int(d.stats.enrolled)}</dd>
                    <dt className="text-mist">Completados</dt><dd className="tabular">{int(d.stats.completed)}</dd>
                    <dt className="text-mist">Avance medio</dt><dd className="tabular">{pct(d.stats.avg_progress, 0)}</dd>
                    <dt className="text-mist">Docente</dt><dd>{d.instructor?.name ?? "—"}</dd>
                  </dl>
                  <div className="mt-3 flex flex-wrap gap-1">{d.skills.map((s: any) => <Badge key={s.id} tone="violet">{s.name}</Badge>)}</div>
                </Panel>
                <Panel title="Evaluaciones">{d.assessments.length ? <ul className="space-y-1 text-[13px]">{d.assessments.map((a: any) => <li key={a.id}><Link to="/evaluaciones" className="hover:text-cyan">{a.title}</Link></li>)}</ul> : <p className="text-[13px] text-mist">Sin evaluaciones.</p>}</Panel>
              </div>
            </div>
            <AddUnit open={unitOpen} onClose={() => setUnitOpen(false)} courseId={d.id} onDone={refresh} />
          </div>
        );
      }}
    </QueryState>
  );
}

function AddUnit({ open, onClose, courseId, onDone }: { open: boolean; onClose: () => void; courseId: string; onDone: () => void }) {
  const toast = useUI((s) => s.toast);
  const [title, setTitle] = useState("");
  const [lessons, setLessons] = useState("");
  const m = useMutation({
    mutationFn: () => api(`/courses/${courseId}/units`, { body: { title, lessons: lessons.split("\n").filter(Boolean).map((t) => ({ title: t })) } }),
    onSuccess: () => { toast("ok", "Unidad agregada; la versión del curso aumentó"); onDone(); onClose(); setTitle(""); setLessons(""); },
    onError: (e) => toast("error", errorText(e)),
  });
  return (
    <Modal open={open} onClose={onClose} title="Agregar unidad">
      <form className="grid gap-3" onSubmit={(e) => { e.preventDefault(); m.mutate(); }}>
        <Field label="Título"><input required minLength={2} value={title} onChange={(e) => setTitle(e.target.value)} /></Field>
        <Field label="Lecciones (una por línea)"><textarea rows={4} value={lessons} onChange={(e) => setLessons(e.target.value)} /></Field>
        <div className="flex justify-end"><Button type="submit" loading={m.isPending}><FileUp /> Guardar unidad</Button></div>
      </form>
    </Modal>
  );
}

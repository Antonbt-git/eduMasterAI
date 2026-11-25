import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ClipboardCheck, Eye, PenLine, Plus } from "lucide-react";
import { useState } from "react";
import { EmptyState, errorText, QueryState } from "@/components/feedback/states";
import { Badge, Button, Field, Modal, PageHeader, Panel, PermissionGate, StatusBadge } from "@/components/ui/primitives";
import { date, num } from "@/lib/format";
import { api } from "@/services/api";
import { useAuth } from "@/stores/auth";
import { useUI } from "@/stores/ui";

const TYPE_ES: Record<string, string> = { multiple_choice: "Opción múltiple", true_false: "Verdadero/Falso", short_answer: "Respuesta corta", file: "Entrega de archivo", practice: "Actividad práctica" };

export function AssessmentsPage() {
  const me = useAuth((s) => s.me)!;
  const q = useQuery({ queryKey: ["assessments"], queryFn: () => api<any[]>("/assessments") });
  const [take, setTake] = useState<any>(null);
  const [review, setReview] = useState<any>(null);
  const [create, setCreate] = useState(false);
  return (
    <div>
      <PageHeader title="Evaluaciones y actividades" subtitle="La calificación oficial se calcula con la regla del curso y se guarda separada de cualquier estimación de IA."
        actions={<PermissionGate perm="assessments:write"><Button onClick={() => setCreate(true)}><Plus /> Nueva evaluación</Button></PermissionGate>} />
      <QueryState q={q} empty={(d) => d.length === 0 ? <EmptyState title="No hay evaluaciones disponibles" text={me.student_id ? "Matricúlate en un curso para ver sus evaluaciones." : "Crea la primera evaluación de un curso."} /> : false}>
        {(d) => (
          <Panel title={`${d.length} evaluaciones`} icon={<ClipboardCheck />}>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-[13px]">
                <thead className="text-left text-[12px] text-mist"><tr>{["Evaluación", "Tipo", "Fecha límite", "Intentos", me.student_id ? "Mi mejor nota" : "Nota media", ""].map((h) => <th key={h} className="pb-2 font-normal">{h}</th>)}</tr></thead>
                <tbody>
                  {d.map((a) => {
                    const best = a.my_attempts?.length ? Math.max(...a.my_attempts.map((t: any) => t.score ?? 0)) : null;
                    const used = a.my_attempts?.length ?? 0;
                    return (
                      <tr key={a.id} className="border-t border-line/40">
                        <td className="py-2"><div>{a.title}</div><div className="text-[11px] text-dim">{a.course_code}</div></td>
                        <td><Badge tone="cyan">{TYPE_ES[a.type]}</Badge></td>
                        <td>{date(a.due_at)}</td>
                        <td className="tabular">{me.student_id ? `${used} / ${a.attempts_allowed}` : a.attempts_count}</td>
                        <td className="tabular">{me.student_id ? (best === null ? "—" : <span className={best >= a.passing_score ? "text-teal" : "text-warn"}>{num(best, 1)}</span>) : (a.avg_score ?? "—")}</td>
                        <td className="text-right">
                          {me.student_id && used < a.attempts_allowed && <Button size="sm" onClick={() => setTake(a)}><PenLine /> Responder</Button>}
                          <PermissionGate perm="assessments:write"><Button size="sm" variant="outline" onClick={() => setReview(a)}><Eye /> Entregas</Button></PermissionGate>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Panel>
        )}
      </QueryState>
      {take && <TakeAssessment a={take} onClose={() => setTake(null)} />}
      {review && <ReviewAttempts a={review} onClose={() => setReview(null)} />}
      <CreateAssessment open={create} onClose={() => setCreate(false)} />
    </div>
  );
}

function TakeAssessment({ a, onClose }: { a: any; onClose: () => void }) {
  const qc = useQueryClient();
  const toast = useUI((s) => s.toast);
  const full = useQuery({ queryKey: ["assessments", a.id], queryFn: () => api(`/assessments/${a.id}`) });
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [fileUrl, setFileUrl] = useState("");
  const [result, setResult] = useState<any>(null);
  const m = useMutation({
    mutationFn: () => api(`/assessments/${a.id}/attempts`, { body: { answers, file_url: fileUrl || null } }),
    onSuccess: (r: any) => { setResult(r); qc.invalidateQueries({ queryKey: ["assessments"] }); qc.invalidateQueries({ queryKey: ["dashboard"] }); },
    onError: (e) => toast("error", errorText(e)),
  });
  return (
    <Modal open onClose={onClose} title={a.title} wide>
      {result ? (
        <div className="py-6 text-center">
          <div className="font-display text-5xl font-semibold">{result.score === null ? "Entregado" : num(result.score, 1)}</div>
          <p className="mt-2 text-mist">{result.score === null ? "Tu docente la revisará con la rúbrica." : result.score >= result.passing_score ? "Aprobado. Tu progreso se actualizó." : `Nota mínima: ${result.passing_score}. Puedes volver a intentarlo si te quedan intentos.`}</p>
          {result.late && <Badge tone="warn" className="mt-2">Entrega fuera de plazo</Badge>}
          <Button className="mt-4" onClick={onClose}>Cerrar</Button>
        </div>
      ) : (
        <form onSubmit={(e) => { e.preventDefault(); m.mutate(); }} className="grid gap-4">
          {full.data?.instructions && <p className="text-[13px] text-mist">{full.data.instructions}</p>}
          {full.data?.questions.map((q: any, i: number) => (
            <fieldset key={q.id} className="panel-inner p-3">
              <legend className="px-1 text-[13px] font-medium">{i + 1}. {q.prompt} <span className="text-dim">({q.points} pts)</span></legend>
              <div className="mt-2 grid gap-1.5">
                {q.options.map((o: string) => (
                  <label key={o} className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-[13px] hover:bg-white/5">
                    <input type="radio" name={`q${q.id}`} required checked={answers[q.id] === o} onChange={() => setAnswers({ ...answers, [q.id]: o })} className="accent-cyan" /> {o}
                  </label>
                ))}
              </div>
            </fieldset>
          ))}
          {full.data && full.data.questions.length === 0 && (
            <Field label="Enlace a tu entrega (repositorio o documento)" hint="Solo http/https. El docente calificará con la rúbrica."><input type="url" required value={fileUrl} onChange={(e) => setFileUrl(e.target.value)} placeholder="https://" /></Field>
          )}
          <div className="flex justify-end gap-2"><Button type="button" variant="ghost" onClick={onClose}>Cancelar</Button><Button type="submit" loading={m.isPending}>Enviar respuestas</Button></div>
        </form>
      )}
    </Modal>
  );
}

function ReviewAttempts({ a, onClose }: { a: any; onClose: () => void }) {
  const qc = useQueryClient();
  const toast = useUI((s) => s.toast);
  const q = useQuery({ queryKey: ["assessments", a.id, "attempts"], queryFn: () => api<any[]>(`/assessments/${a.id}/attempts`) });
  const [grading, setGrading] = useState<Record<string, { score: string; feedback: string }>>({});
  const grade = useMutation({
    mutationFn: (id: string) => api(`/assessments/${a.id}/attempts/${id}/grade`, { body: { score: +grading[id].score, feedback: grading[id].feedback } }),
    onSuccess: () => { toast("ok", "Calificación guardada y notificada"); qc.invalidateQueries({ queryKey: ["assessments"] }); },
    onError: (e) => toast("error", errorText(e)),
  });
  return (
    <Modal open onClose={onClose} title={`Entregas: ${a.title}`} wide>
      <QueryState q={q} empty={(d) => d.length === 0}>
        {(d) => (
          <ul className="max-h-[60vh] divide-y divide-line/40 overflow-auto">
            {d.map((t) => (
              <li key={t.id} className="flex flex-wrap items-center gap-2 py-2 text-[13px]">
                <span className="min-w-40 flex-1">{t.student_name}</span>
                <StatusBadge status={t.status} />{t.late && <Badge tone="warn">Tardía</Badge>}
                <span className="w-16 tabular">{t.score === null ? "—" : num(t.score, 1)}</span>
                <input aria-label="Nota" type="number" min={0} max={a.max_score} className="w-20 !py-1" placeholder="Nota" value={grading[t.id]?.score ?? ""} onChange={(e) => setGrading({ ...grading, [t.id]: { ...(grading[t.id] ?? { feedback: "" }), score: e.target.value } })} />
                <input aria-label="Retroalimentación" className="w-48 !py-1" placeholder="Retroalimentación" value={grading[t.id]?.feedback ?? ""} onChange={(e) => setGrading({ ...grading, [t.id]: { ...(grading[t.id] ?? { score: "" }), feedback: e.target.value } })} />
                <Button size="sm" disabled={!grading[t.id]?.score} onClick={() => grade.mutate(t.id)}>Guardar nota</Button>
              </li>
            ))}
          </ul>
        )}
      </QueryState>
    </Modal>
  );
}

function CreateAssessment({ open, onClose }: { open: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const toast = useUI((s) => s.toast);
  const courses = useQuery({ queryKey: ["courses", "all"], queryFn: () => api("/courses?page_size=100"), enabled: open });
  const [f, setF] = useState({ course_id: "", title: "", type: "multiple_choice", max_score: 100, passing_score: 70, attempts_allowed: 2, due_at: "", grading_rule: "best", instructions: "" });
  const [qs, setQs] = useState([{ prompt: "", options: "Opción A\nOpción B\nOpción C", answer: "Opción A", points: 10 }]);
  const m = useMutation({
    mutationFn: () => api("/assessments", { body: { ...f, due_at: f.due_at ? new Date(f.due_at).toISOString() : null,
      questions: ["multiple_choice", "true_false"].includes(f.type) ? qs.map((q) => ({ ...q, options: q.options.split("\n").filter(Boolean) })) : [] } }),
    onSuccess: () => { toast("ok", "Evaluación publicada y estudiantes notificados"); qc.invalidateQueries({ queryKey: ["assessments"] }); onClose(); },
    onError: (e) => toast("error", errorText(e)),
  });
  return (
    <Modal open={open} onClose={onClose} title="Nueva evaluación" wide>
      <form className="grid gap-3 md:grid-cols-2" onSubmit={(e) => { e.preventDefault(); m.mutate(); }}>
        <Field label="Curso"><select required value={f.course_id} onChange={(e) => setF({ ...f, course_id: e.target.value })}><option value="">Seleccione</option>{courses.data?.items.map((c: any) => <option key={c.id} value={c.id}>{c.code} · {c.title}</option>)}</select></Field>
        <Field label="Título"><input required minLength={3} value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></Field>
        <Field label="Tipo"><select value={f.type} onChange={(e) => setF({ ...f, type: e.target.value })}>{Object.entries(TYPE_ES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Field>
        <Field label="Fecha límite"><input type="datetime-local" value={f.due_at} onChange={(e) => setF({ ...f, due_at: e.target.value })} /></Field>
        <Field label="Puntaje máximo / mínimo aprobatorio"><div className="flex gap-2"><input type="number" value={f.max_score} onChange={(e) => setF({ ...f, max_score: +e.target.value })} /><input type="number" value={f.passing_score} onChange={(e) => setF({ ...f, passing_score: +e.target.value })} /></div></Field>
        <Field label="Intentos y regla"><div className="flex gap-2"><input type="number" min={1} max={10} value={f.attempts_allowed} onChange={(e) => setF({ ...f, attempts_allowed: +e.target.value })} />
          <select value={f.grading_rule} onChange={(e) => setF({ ...f, grading_rule: e.target.value })}><option value="best">Mejor intento</option><option value="last">Último</option><option value="average">Promedio</option></select></div></Field>
        <div className="md:col-span-2"><Field label="Instrucciones"><textarea rows={2} value={f.instructions} onChange={(e) => setF({ ...f, instructions: e.target.value })} /></Field></div>
        {["multiple_choice", "true_false"].includes(f.type) && (
          <div className="grid gap-2 md:col-span-2">
            {qs.map((q, i) => (
              <div key={i} className="panel-inner grid gap-2 p-3 md:grid-cols-[2fr_1fr_1fr]">
                <input placeholder={`Pregunta ${i + 1}`} required value={q.prompt} onChange={(e) => setQs(qs.map((x, j) => (j === i ? { ...x, prompt: e.target.value } : x)))} />
                <textarea rows={2} value={q.options} aria-label="Opciones" onChange={(e) => setQs(qs.map((x, j) => (j === i ? { ...x, options: e.target.value } : x)))} />
                <input placeholder="Respuesta correcta" value={q.answer} onChange={(e) => setQs(qs.map((x, j) => (j === i ? { ...x, answer: e.target.value } : x)))} />
              </div>
            ))}
            <Button type="button" size="sm" variant="ghost" onClick={() => setQs([...qs, { prompt: "", options: "Verdadero\nFalso", answer: "Verdadero", points: 10 }])}><Plus /> Pregunta</Button>
          </div>
        )}
        <div className="flex justify-end md:col-span-2"><Button type="submit" loading={m.isPending}>Publicar evaluación</Button></div>
      </form>
    </Modal>
  );
}

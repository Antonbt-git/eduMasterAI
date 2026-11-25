import { useMutation, useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { Bot, SendHorizontal } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { errorText } from "@/components/feedback/states";
import { Avatar, Badge, Button, PageHeader, Panel } from "@/components/ui/primitives";
import { api } from "@/services/api";
import { useAuth } from "@/stores/auth";
import { useUI } from "@/stores/ui";

type Msg = { role: "user" | "assistant"; content: string; provider?: string; model?: string; model_version?: string; confidence?: number | null };
const SUGGESTED = ["¿Cómo funciona la retropropagación en una red neuronal?", "¿Qué debería estudiar esta semana?", "Dame un plan para mi próxima evaluación"];

function Rich({ text }: { text: string }) {
  return <>{text.split("\n").map((line, i) => (
    <p key={i} className="min-h-[0.5em]">{line.split(/(\*\*[^*]+\*\*|_[^_]+_)/g).map((p, j) =>
      p.startsWith("**") ? <strong key={j} className="text-frost">{p.slice(2, -2)}</strong> : p.startsWith("_") && p.endsWith("_") ? <em key={j} className="text-dim">{p.slice(1, -1)}</em> : p)}</p>
  ))}</>;
}

export function TutorPage() {
  const me = useAuth((s) => s.me)!;
  const toast = useUI((s) => s.toast);
  const [msgs, setMsgs] = useState<Msg[]>([{ role: "assistant", content: `Hola ${me.full_name.split(" ")[0]}. Soy tu tutor de EduMaster. Uso tu progreso registrado (sin datos personales) para orientarte. ¿En qué te ayudo?` }]);
  const [text, setText] = useState("");
  const [course, setCourse] = useState("");
  const end = useRef<HTMLDivElement>(null);
  const courses = useQuery({ queryKey: ["courses", "all"], queryFn: () => api("/courses?page_size=100") });
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth", block: "nearest" }); }, [msgs]);
  const ask = useMutation({
    mutationFn: (question: string) => api("/ai-tutor/ask", { body: { question, course_id: course || null, history: msgs.slice(-6).map(({ role, content }) => ({ role, content })) } }),
    onSuccess: (r: any) => setMsgs((m) => [...m, { role: "assistant", content: r.answer, provider: r.provider, model: r.model, model_version: r.model_version, confidence: r.confidence }]),
    onError: (e) => { toast("error", errorText(e)); setMsgs((m) => m.slice(0, -1)); },
  });
  const send = (q: string) => { if (!q.trim()) return; setMsgs((m) => [...m, { role: "user", content: q }]); setText(""); ask.mutate(q); };
  return (
    <div>
      <PageHeader title="IA Tutor" subtitle="Explicaciones y siguiente paso concreto según tu avance. Funciona con un modelo generativo externo si está configurado, o con reglas y recomendaciones propias si no." />
      <Panel glow title="Conversación" icon={<Bot />} actions={
        <select aria-label="Contexto de curso" value={course} onChange={(e) => setCourse(e.target.value)} className="!py-1 text-[12px]">
          <option value="">Todos mis cursos</option>{courses.data?.items.map((c: any) => <option key={c.id} value={c.id}>{c.title}</option>)}
        </select>} bodyClass="flex flex-col">
        <div className="h-[52vh] space-y-3 overflow-y-auto pr-1" aria-live="polite">
          {msgs.map((m, i) => (
            <div key={i} className={clsx("flex gap-3", m.role === "user" && "flex-row-reverse")}>
              {m.role === "assistant" ? <span className="grid size-8 shrink-0 place-items-center rounded-full bg-gradient-to-br from-cyan to-violet"><Bot className="size-4 text-white" /></span> : <Avatar src={me.avatar_url} name={me.full_name} size={32} />}
              <div className={clsx("max-w-[72ch] rounded-2xl px-4 py-2.5 text-[14px] leading-relaxed", m.role === "user" ? "bg-electric/25 text-frost" : "panel-inner text-[#DED5F2]")}>
                <Rich text={m.content} />
                {m.provider && <div className="mt-1.5 flex flex-wrap gap-1.5"><Badge tone={m.provider === "rules" ? "muted" : "violet"}>{m.provider === "rules" ? "Tutor por reglas" : m.provider}</Badge>
                  {m.model && <Badge tone="cyan">Modelo {m.model}{m.model_version ? ` · v${m.model_version}` : ""}</Badge>}
                  {m.confidence != null && <Badge>Confianza {Math.round(m.confidence * 100)}%</Badge>}</div>}
              </div>
            </div>
          ))}
          {ask.isPending && <div className="flex gap-2 pl-11 text-[13px] text-mist"><span className="live-dot">●</span> Pensando…</div>}
          <div ref={end} />
        </div>
        <div className="mt-3 flex flex-wrap gap-1.5">{SUGGESTED.map((s) => <button key={s} onClick={() => send(s)} className="rounded-full border border-line px-3 py-1 text-[12px] text-mist hover:border-cyan/50 hover:text-frost">{s}</button>)}</div>
        <form className="mt-3 flex gap-2" onSubmit={(e) => { e.preventDefault(); send(text); }}>
          <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Escribe tu pregunta" aria-label="Pregunta" className="flex-1" maxLength={2000} />
          <Button type="submit" loading={ask.isPending} disabled={!text.trim()}><SendHorizontal /> Enviar</Button>
        </form>
        <p className="mt-2 text-[11px] text-dim">Respuestas de apoyo generadas por IA; verifica con tu docente. Límite: 12 preguntas por minuto.</p>
      </Panel>
    </div>
  );
}

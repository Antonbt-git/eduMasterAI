import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { EyeOff, Flag, MessageSquare, Megaphone, Pin, Plus, RotateCcw } from "lucide-react";
import { useState } from "react";
import { EmptyState, errorText, QueryState } from "@/components/feedback/states";
import { Avatar, Badge, Button, Field, Modal, PageHeader, PermissionGate } from "@/components/ui/primitives";
import { ago } from "@/lib/format";
import { api } from "@/services/api";
import { useUI } from "@/stores/ui";

const unescape = (s: string) => new DOMParser().parseFromString(s, "text/html").documentElement.textContent ?? s; // render seguro como texto

export function CommunityPage() {
  const [kind, setKind] = useState("");
  const q = useQuery({ queryKey: ["community", kind], queryFn: () => api(`/community/threads${kind ? `?kind=${kind}` : ""}`) });
  const [open, setOpen] = useState<string | null>(null);
  const [create, setCreate] = useState(false);
  return (
    <div>
      <PageHeader title="Comunidad" subtitle="Espacios por curso para anuncios y debates, con moderación y reportes."
        actions={<><select aria-label="Tipo" value={kind} onChange={(e) => setKind(e.target.value)}><option value="">Todo</option><option value="announcement">Anuncios</option><option value="discussion">Debates</option></select>
          <PermissionGate perm="community:write"><Button onClick={() => setCreate(true)}><Plus /> Nueva publicación</Button></PermissionGate></>} />
      <QueryState q={q} empty={(d: any) => d.items.length === 0 ? <EmptyState title="Todavía no hay conversaciones" text="Abre el primer debate de tu curso." /> : false}>
        {(d: any) => (
          <div className="grid gap-3">
            {d.open_reports > 0 && <p className="rounded-lg border border-warn/40 bg-warn/10 px-3 py-2 text-[13px] text-warn">{d.open_reports} reporte(s) pendiente(s) de moderación.</p>}
            {d.items.map((t: any) => (
              <button key={t.id} onClick={() => setOpen(t.id)} className="panel flex gap-3 p-4 text-left hover:!border-cyan/40">
                <Avatar src={t.author.avatar_url} name={t.author.name} size={38} />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    {t.pinned && <Pin className="size-3.5 text-cyan" aria-label="Fijado" />}
                    {t.kind === "announcement" ? <Badge tone="violet"><Megaphone className="size-3" /> Anuncio</Badge> : <Badge tone="cyan">Debate</Badge>}
                    {t.status !== "visible" && <Badge tone="warn">{t.status === "pending" ? "En moderación" : "Oculto"}</Badge>}
                    <h3 className="font-display font-semibold">{unescape(t.title)}</h3>
                  </div>
                  <p className="mt-1 line-clamp-2 text-[13px] text-mist">{unescape(t.body)}</p>
                  <div className="mt-1.5 text-[12px] text-dim">{t.author.name} · {t.course_title ?? "General"} · {ago(t.created_at)} · {t.replies} respuestas</div>
                </div>
              </button>
            ))}
          </div>
        )}
      </QueryState>
      {open && <ThreadModal id={open} onClose={() => setOpen(null)} />}
      <CreateThread open={create} onClose={() => setCreate(false)} />
    </div>
  );
}

function ThreadModal({ id, onClose }: { id: string; onClose: () => void }) {
  const qc = useQueryClient();
  const toast = useUI((s) => s.toast);
  const q = useQuery({ queryKey: ["community", "thread", id], queryFn: () => api(`/community/threads/${id}`) });
  const [body, setBody] = useState("");
  const reply = useMutation({
    mutationFn: () => api(`/community/threads/${id}/posts`, { body: { body } }),
    onSuccess: () => { setBody(""); qc.invalidateQueries({ queryKey: ["community"] }); },
    onError: (e) => toast("error", errorText(e)),
  });
  const report = useMutation({ mutationFn: () => api(`/community/threads/${id}/report`, { body: { reason: "Contenido inapropiado" } }), onSuccess: () => toast("ok", "Reporte enviado a moderación") });
  const mod = useMutation({
    mutationFn: (action: string) => api(`/community/threads/${id}/moderate`, { body: { action } }),
    onSuccess: () => { toast("ok", "Moderación aplicada"); qc.invalidateQueries({ queryKey: ["community"] }); },
  });
  return (
    <Modal open onClose={onClose} title={q.data ? unescape(q.data.title) : "Hilo"} wide>
      <QueryState q={q}>
        {(t: any) => (
          <div>
            <p className="text-[14px] whitespace-pre-wrap text-[#DED5F2]">{unescape(t.body)}</p>
            <div className="mt-2 flex flex-wrap gap-1.5 text-[12px]">
              <Button size="sm" variant="ghost" onClick={() => report.mutate()}><Flag /> Reportar</Button>
              <PermissionGate perm="community:moderate">
                <Button size="sm" variant="ghost" onClick={() => mod.mutate(t.pinned ? "unpin" : "pin")}><Pin /> {t.pinned ? "Desfijar" : "Fijar"}</Button>
                {t.status === "visible" ? <Button size="sm" variant="ghost" onClick={() => mod.mutate("hide")}><EyeOff /> Ocultar</Button> : <Button size="sm" variant="ghost" onClick={() => mod.mutate("restore")}><RotateCcw /> Restaurar</Button>}
              </PermissionGate>
            </div>
            <ul className="mt-3 space-y-2 border-t border-line/40 pt-3">
              {t.posts.length === 0 && <li className="text-[13px] text-mist">Sé el primero en responder.</li>}
              {t.posts.map((p: any) => (
                <li key={p.id} className="flex gap-2.5"><Avatar src={p.author.avatar_url} name={p.author.name} size={30} />
                  <div className="panel-inner flex-1 px-3 py-2 text-[13px]"><div className="text-[12px] text-mist">{p.author.name} · {ago(p.created_at)}</div>{unescape(p.body)}</div></li>
              ))}
            </ul>
            <PermissionGate perm="community:write">
              <form className="mt-3 flex gap-2" onSubmit={(e) => { e.preventDefault(); reply.mutate(); }}>
                <input className="flex-1" value={body} onChange={(e) => setBody(e.target.value)} placeholder="Escribe una respuesta" aria-label="Respuesta" />
                <Button type="submit" loading={reply.isPending} disabled={!body.trim()}><MessageSquare /> Responder</Button>
              </form>
            </PermissionGate>
          </div>
        )}
      </QueryState>
    </Modal>
  );
}

function CreateThread({ open, onClose }: { open: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const toast = useUI((s) => s.toast);
  const courses = useQuery({ queryKey: ["courses", "all"], queryFn: () => api("/courses?page_size=100"), enabled: open });
  const [f, setF] = useState({ title: "", body: "", course_id: "", kind: "discussion" });
  const m = useMutation({
    mutationFn: () => api("/community/threads", { body: { ...f, course_id: f.course_id || null } }),
    onSuccess: (r: any) => { toast(r.moderation === "pending" ? "info" : "ok", r.moderation === "pending" ? "Tu publicación quedó en revisión de moderación" : "Publicado"); qc.invalidateQueries({ queryKey: ["community"] }); onClose(); setF({ title: "", body: "", course_id: "", kind: "discussion" }); },
    onError: (e) => toast("error", errorText(e)),
  });
  return (
    <Modal open={open} onClose={onClose} title="Nueva publicación">
      <form className="grid gap-3" onSubmit={(e) => { e.preventDefault(); m.mutate(); }}>
        <Field label="Espacio"><select value={f.course_id} onChange={(e) => setF({ ...f, course_id: e.target.value })}><option value="">General</option>{courses.data?.items.map((c: any) => <option key={c.id} value={c.id}>{c.title}</option>)}</select></Field>
        <PermissionGate perm={["community:moderate", "courses:write"]}><Field label="Tipo"><select value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value })}><option value="discussion">Debate</option><option value="announcement">Anuncio</option></select></Field></PermissionGate>
        <Field label="Título"><input required minLength={4} value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></Field>
        <Field label="Mensaje"><textarea required rows={4} value={f.body} onChange={(e) => setF({ ...f, body: e.target.value })} /></Field>
        <div className="flex justify-end"><Button type="submit" loading={m.isPending}>Publicar</Button></div>
      </form>
    </Modal>
  );
}

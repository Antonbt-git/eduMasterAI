import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Award, BadgeCheck, Download, QrCode, RefreshCw, ShieldX } from "lucide-react";
import { useState } from "react";
import { useParams } from "react-router-dom";
import { EmptyState, errorText, QueryState, Skeleton } from "@/components/feedback/states";
import { Button, Field, Modal, PageHeader, Panel, PermissionGate, StatusBadge } from "@/components/ui/primitives";
import { date } from "@/lib/format";
import { api, download } from "@/services/api";
import { useUI } from "@/stores/ui";

export function CertificatesPage() {
  const qc = useQueryClient();
  const toast = useUI((s) => s.toast);
  const [status, setStatus] = useState("");
  const q = useQuery({ queryKey: ["certificates", status], queryFn: () => api(`/certificates${status ? `?status=${status}` : ""}`) });
  const [revoke, setRevoke] = useState<any>(null);
  const act = useMutation({
    mutationFn: ({ path, body }: { path: string; body?: any }) => api(path, { method: "POST", body }),
    onSuccess: (_d, v) => { toast("ok", v.path.includes("revoke") ? "Certificado anulado" : v.path.includes("reissue") ? "Certificado reemitido con nuevo folio" : "Certificado emitido"); qc.invalidateQueries({ queryKey: ["certificates"] }); setRevoke(null); },
    onError: (e) => toast("error", errorText(e)),
  });
  return (
    <div>
      <PageHeader title="Certificados" subtitle="Folio único, PDF con código QR y verificación pública que muestra solo datos mínimos."
        actions={<select aria-label="Estado" value={status} onChange={(e) => setStatus(e.target.value)}><option value="">Todos</option><option value="issued">Emitidos</option><option value="revoked">Anulados</option></select>} />
      <QueryState q={q} skeleton={<Skeleton className="h-64" />}>
        {(d: any) => (
          <>
            {d.eligible.length > 0 && (
              <Panel glow className="mb-4" title="Listos para emitir" icon={<BadgeCheck />}>
                <ul className="flex flex-wrap gap-2">{d.eligible.map((e: any) => (
                  <li key={e.enrollment_id} className="panel-inner flex items-center gap-3 px-3 py-2 text-[13px]">{e.course_title}
                    <Button size="sm" onClick={() => act.mutate({ path: "/certificates", body: { enrollment_id: e.enrollment_id } })}>Emitir certificado</Button></li>))}</ul>
              </Panel>
            )}
            {d.items.length === 0 ? <EmptyState icon={<Award className="size-5" />} title="Aún no hay certificados" text="Se habilitan al cumplir los criterios oficiales de finalización." /> : (
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {d.items.map((c: any) => (
                  <article key={c.id} className="panel relative overflow-hidden p-4">
                    <div className="absolute -top-10 -right-10 size-32 rounded-full bg-violet/20 blur-2xl" aria-hidden />
                    <div className="flex items-center gap-2"><Award className="size-5 text-cyan" /><span className="text-[12px] text-mist">{c.folio}</span><span className="ml-auto"><StatusBadge status={c.status} /></span></div>
                    <h3 className="font-display mt-2 text-[16px] font-semibold">{c.course.title}</h3>
                    <p className="text-[13px] text-mist">{c.student.name}</p>
                    <p className="mt-2 text-[12px] text-dim">Emitido {date(c.issued_at)} · vigente hasta {date(c.expires_at)}</p>
                    {c.revoked_reason && <p className="mt-1 text-[12px] text-danger">Motivo: {c.revoked_reason}</p>}
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      <Button size="sm" variant="outline" onClick={() => download(`/certificates/${c.id}/pdf`, `certificado_${c.folio}.pdf`)}><Download /> PDF</Button>
                      <a className="inline-flex h-8 items-center gap-1.5 rounded-[10px] px-3 text-[13px] text-mist hover:text-frost" href={`/verificar/${c.verification_code}`} target="_blank" rel="noreferrer"><QrCode className="size-4" /> Verificar</a>
                      <PermissionGate perm="certificates:issue">
                        {c.status === "issued" ? <Button size="sm" variant="ghost" onClick={() => setRevoke(c)}><ShieldX /> Anular</Button>
                          : <Button size="sm" variant="ghost" onClick={() => act.mutate({ path: `/certificates/${c.id}/reissue` })}><RefreshCw /> Reemitir</Button>}
                      </PermissionGate>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </>
        )}
      </QueryState>
      {revoke && <RevokeDialog c={revoke} onClose={() => setRevoke(null)} onConfirm={(reason) => act.mutate({ path: `/certificates/${revoke.id}/revoke`, body: { reason } })} />}
    </div>
  );
}

function RevokeDialog({ c, onClose, onConfirm }: { c: any; onClose: () => void; onConfirm: (r: string) => void }) {
  const [reason, setReason] = useState("");
  return (
    <Modal open onClose={onClose} title={`Anular ${c.folio}`}>
      <Field label="Motivo (queda en auditoría)"><textarea rows={3} value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
      <div className="mt-4 flex justify-end gap-2"><Button variant="ghost" onClick={onClose}>Cancelar</Button><Button variant="danger" disabled={reason.length < 5} onClick={() => onConfirm(reason)}>Anular certificado</Button></div>
    </Modal>
  );
}

export function VerifyPage() {
  const { code } = useParams();
  const q = useQuery({ queryKey: ["verify", code], queryFn: () => api(`/certificates/verify/${code}`), retry: false });
  return (
    <div className="grid min-h-full place-items-center p-6">
      <div className="panel panel-glow w-full max-w-md p-7 text-center">
        <img src="/favicon.svg" alt="" className="mx-auto size-12" />
        <h1 className="font-display mt-3 text-xl font-semibold">Verificación de certificado</h1>
        {q.isLoading && <Skeleton className="mt-6 h-32" />}
        {q.error && <p className="mt-6 text-danger">El código {code} no corresponde a ningún certificado.</p>}
        {q.data && (
          <div className="mt-5">
            <div className={`mx-auto inline-flex items-center gap-2 rounded-full px-4 py-1.5 text-[14px] font-medium ${q.data.valid ? "bg-teal/15 text-teal" : "bg-danger/15 text-danger"}`}>
              {q.data.valid ? <BadgeCheck className="size-4" /> : <ShieldX className="size-4" />}{q.data.valid ? "Certificado válido" : `Certificado ${q.data.status === "revoked" ? "anulado" : "expirado"}`}
            </div>
            <dl className="mt-5 grid grid-cols-2 gap-y-2 text-left text-[14px]">
              <dt className="text-mist">Titular</dt><dd>{q.data.holder}</dd>
              <dt className="text-mist">Curso</dt><dd>{q.data.course}</dd>
              <dt className="text-mist">Institución</dt><dd>{q.data.institution}</dd>
              <dt className="text-mist">Folio</dt><dd>{q.data.folio}</dd>
              <dt className="text-mist">Emisión</dt><dd>{date(q.data.issued_at)}</dd>
            </dl>
            <p className="mt-4 text-[12px] text-dim">Por privacidad solo se muestran datos mínimos.</p>
          </div>
        )}
      </div>
    </div>
  );
}

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, Database, Fingerprint, Settings, ShieldCheck, UserPlus, Users } from "lucide-react";
import { useState } from "react";
import { errorText, QueryState } from "@/components/feedback/states";
import { ActivityFeed } from "@/components/ui/lists";
import { Avatar, Badge, Button, DemoBadge, Field, Modal, PageHeader, Panel, PermissionGate, StatusBadge, Tabs } from "@/components/ui/primitives";
import { ago, date, int, pct, ROLE_ES } from "@/lib/format";
import { api } from "@/services/api";
import { usePerm } from "@/stores/auth";
import { useUI } from "@/stores/ui";

export function AdminPage() {
  const canUsers = usePerm("users:read"), canAudit = usePerm("audit:read"), canData = usePerm("datasets:read");
  const [tab, setTab] = useState(canUsers ? "users" : canAudit ? "audit" : "datasets");
  const items = [canUsers && { value: "users", label: "Usuarios y roles" }, (canAudit || true) && { value: "audit", label: "Auditoría" }, canData && { value: "datasets", label: "Datasets" }].filter(Boolean) as any[];
  return (
    <div>
      <PageHeader title="Administración y gobierno" subtitle="Usuarios, roles, bitácora con cadena de integridad y datasets versionados." actions={<Tabs value={tab} onChange={setTab} items={items} />} />
      {tab === "users" && <UsersPanel />}
      {tab === "audit" && <AuditPanel />}
      {tab === "datasets" && <DatasetsPanel />}
    </div>
  );
}

function UsersPanel() {
  const [q, setQ] = useState("");
  const [role, setRole] = useState("");
  const users = useQuery({ queryKey: ["users", q, role], queryFn: () => api(`/users?limit=100&q=${encodeURIComponent(q)}&role=${role}`) });
  const roles = useQuery({ queryKey: ["roles"], queryFn: () => api<any[]>("/roles") });
  const [create, setCreate] = useState(false);
  const qc = useQueryClient();
  const toast = useUI((s) => s.toast);
  const upd = useMutation({
    mutationFn: ({ id, body }: { id: string; body: any }) => api(`/users/${id}`, { method: "PATCH", body }),
    onSuccess: () => { toast("ok", "Usuario actualizado; sus sesiones activas fueron renovadas"); qc.invalidateQueries({ queryKey: ["users"] }); },
    onError: (e) => toast("error", errorText(e)),
  });
  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
      <Panel title="Usuarios" icon={<Users />} actions={<PermissionGate perm="users:write"><Button size="sm" onClick={() => setCreate(true)}><UserPlus /> Nuevo usuario</Button></PermissionGate>}>
        <div className="mb-3 flex gap-2">
          <input type="search" placeholder="Buscar por nombre o correo" aria-label="Buscar usuarios" value={q} onChange={(e) => setQ(e.target.value)} className="flex-1" />
          <select aria-label="Rol" value={role} onChange={(e) => setRole(e.target.value)}><option value="">Todos los roles</option>{roles.data?.map((r) => <option key={r.code} value={r.code}>{ROLE_ES[r.code]}</option>)}</select>
        </div>
        <QueryState q={users}>
          {(d: any) => (
            <div className="max-h-[60vh] overflow-auto">
              <table className="w-full text-[13px]">
                <thead className="sticky top-0 bg-surface text-left text-[12px] text-mist"><tr><th className="py-1.5 font-normal">Usuario</th><th className="font-normal">Roles</th><th className="font-normal">Último acceso</th><th className="font-normal">Estado</th><th /></tr></thead>
                <tbody>
                  {d.items.map((u: any) => (
                    <tr key={u.id} className="border-t border-line/40">
                      <td className="py-2"><div className="flex items-center gap-2"><Avatar src={u.avatar_url} name={u.full_name} size={28} /><div><div>{u.full_name}</div><div className="text-[11px] text-dim">{u.email}</div></div></div></td>
                      <td><div className="flex flex-wrap gap-1">{u.roles.map((r: string) => <Badge key={r} tone="blue">{ROLE_ES[r]}</Badge>)}</div></td>
                      <td className="text-mist">{ago(u.last_login_at)}</td>
                      <td><Badge tone={u.status === "active" ? "teal" : "danger"}>{u.status === "active" ? "Activo" : "Suspendido"}</Badge></td>
                      <td className="text-right"><PermissionGate perm="users:write">
                        <Button size="sm" variant="ghost" onClick={() => upd.mutate({ id: u.id, body: { status: u.status === "active" ? "suspended" : "active" } })}>{u.status === "active" ? "Suspender" : "Reactivar"}</Button>
                      </PermissionGate></td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-2 text-[12px] text-dim">{int(d.total)} usuarios en la institución.</p>
            </div>
          )}
        </QueryState>
      </Panel>
      <Panel title="Matriz de permisos" icon={<ShieldCheck />}>
        <QueryState q={roles}>
          {(d) => <ul className="space-y-2 text-[12px]">{d.map((r) => <li key={r.code}><div className="font-medium text-frost">{ROLE_ES[r.code]}</div><div className="text-dim">{r.permissions.length} permisos: {r.permissions.slice(0, 6).join(", ")}{r.permissions.length > 6 && "…"}</div></li>)}</ul>}
        </QueryState>
        <p className="mt-3 text-[11px] text-dim">RBAC + ABAC validados en el backend (institución, curso asignado y propiedad del registro).</p>
      </Panel>
      <CreateUser open={create} onClose={() => setCreate(false)} roles={roles.data ?? []} />
    </div>
  );
}

function CreateUser({ open, onClose, roles }: { open: boolean; onClose: () => void; roles: any[] }) {
  const qc = useQueryClient();
  const toast = useUI((s) => s.toast);
  const [f, setF] = useState({ email: "", full_name: "", password: "", roles: ["student"] });
  const m = useMutation({
    mutationFn: () => api("/users", { body: f }),
    onSuccess: () => { toast("ok", "Usuario creado"); qc.invalidateQueries({ queryKey: ["users"] }); onClose(); },
    onError: (e) => toast("error", errorText(e)),
  });
  return (
    <Modal open={open} onClose={onClose} title="Nuevo usuario">
      <form className="grid gap-3" onSubmit={(e) => { e.preventDefault(); m.mutate(); }}>
        <Field label="Nombre completo"><input required minLength={3} value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} /></Field>
        <Field label="Correo"><input type="email" required value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></Field>
        <Field label="Contraseña temporal" hint="Mínimo 10 caracteres."><input type="password" required minLength={10} value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} /></Field>
        <Field label="Roles"><div className="flex flex-wrap gap-1.5">{roles.map((r) => (
          <button type="button" key={r.code} onClick={() => setF({ ...f, roles: f.roles.includes(r.code) ? f.roles.filter((x) => x !== r.code) : [...f.roles, r.code] })}
            className={`rounded-full border px-2.5 py-1 text-[12px] ${f.roles.includes(r.code) ? "border-cyan bg-cyan/15" : "border-line text-mist"}`}>{ROLE_ES[r.code]}</button>))}</div></Field>
        <div className="flex justify-end"><Button type="submit" loading={m.isPending} disabled={!f.roles.length}>Crear usuario</Button></div>
      </form>
    </Modal>
  );
}

function AuditPanel() {
  const [action, setAction] = useState("");
  const q = useInfiniteQuery({
    queryKey: ["audit", action], initialPageParam: "" as string,
    queryFn: ({ pageParam }) => api(`/audit-logs?limit=40${pageParam ? `&cursor=${pageParam}` : ""}${action ? `&action=${action}` : ""}`),
    getNextPageParam: (last: any) => last.next_cursor ?? undefined,
  });
  const canVerify = usePerm("audit:read");
  const verify = useQuery({ queryKey: ["audit", "verify"], queryFn: () => api("/audit-logs/verify"), enabled: false });
  const rows = q.data?.pages.flatMap((p: any) => p.items) ?? [];
  return (
    <Panel title="Bitácora de auditoría" icon={<Fingerprint />}
      actions={<>
        <select aria-label="Acción" value={action} onChange={(e) => setAction(e.target.value)} className="!py-1 text-[12px]">
          <option value="">Todas las acciones</option>{["auth", "user", "course", "grade", "certificate", "analytics", "model", "dataset", "recommendation"].map((a) => <option key={a} value={a}>{a}.*</option>)}
        </select>
        {canVerify && <Button size="sm" variant="outline" onClick={() => verify.refetch()} loading={verify.isFetching}><ShieldCheck /> Verificar integridad</Button>}
      </>}>
      {verify.data && <p className={`mb-3 rounded-lg px-3 py-2 text-[13px] ${verify.data.valid ? "bg-teal/10 text-teal" : "bg-danger/10 text-danger"}`}>
        {verify.data.valid ? `Cadena íntegra: ${int(verify.data.entries)} registros verificados con hash encadenado.` : `Alteración detectada en registros ${verify.data.broken_ids.join(", ")}`}</p>}
      <div className="max-h-[62vh] overflow-auto">
        <table className="w-full min-w-[820px] text-[12px]">
          <thead className="sticky top-0 bg-surface text-left text-mist"><tr>{["Fecha", "Acción", "Recurso", "Actor", "Detalle", "Hash"].map((h) => <th key={h} className="py-1.5 font-normal">{h}</th>)}</tr></thead>
          <tbody>{rows.map((a: any) => (
            <tr key={a.id} className="border-t border-line/40 align-top">
              <td className="py-1.5 whitespace-nowrap text-mist">{new Date(a.occurred_at).toLocaleString("es-PE")}</td>
              <td><Badge tone={a.action.startsWith("model") ? "violet" : a.action.includes("failed") ? "danger" : "cyan"}>{a.action}</Badge></td>
              <td className="text-mist">{a.resource}</td><td>{a.actor_email ?? "sistema"}</td>
              <td className="max-w-[260px] truncate text-dim" title={JSON.stringify(a.details)}>{JSON.stringify(a.details)}</td>
              <td className="text-dim">{a.hash}</td>
            </tr>))}</tbody>
        </table>
      </div>
      {q.hasNextPage && <div className="mt-3 text-center"><Button size="sm" variant="outline" onClick={() => q.fetchNextPage()} loading={q.isFetchingNextPage}>Cargar más</Button></div>}
    </Panel>
  );
}

function DatasetsPanel() {
  const qc = useQueryClient();
  const toast = useUI((s) => s.toast);
  const q = useQuery({ queryKey: ["ml", "datasets"], queryFn: () => api<any[]>("/ml/datasets") });
  const [version, setVersion] = useState("demo-v2");
  const build = useMutation({ mutationFn: () => api("/ml/datasets", { body: { version, seed: 7 } }), onSuccess: () => { toast("ok", "Construcción encolada en el worker"); qc.invalidateQueries({ queryKey: ["ml", "datasets"] }); }, onError: (e) => toast("error", errorText(e)) });
  const approve = useMutation({ mutationFn: (id: string) => api(`/ml/datasets/${id}/approve`, { method: "POST" }), onSuccess: () => { toast("ok", "Dataset aprobado"); qc.invalidateQueries({ queryKey: ["ml", "datasets"] }); }, onError: (e) => toast("error", errorText(e)) });
  return (
    <Panel title="Datasets versionados" icon={<Database />} actions={<PermissionGate perm="datasets:build"><input aria-label="Versión" value={version} onChange={(e) => setVersion(e.target.value)} className="w-32 !py-1 text-[12px]" /><Button size="sm" onClick={() => build.mutate()} loading={build.isPending}>Construir versión</Button></PermissionGate>}>
      <QueryState q={q} empty={(d) => d.length === 0}>
        {(d) => (
          <div className="grid gap-3 lg:grid-cols-2">
            {d.map((ds) => (
              <article key={ds.id} className="panel-inner p-4 text-[13px]">
                <div className="flex items-center gap-2"><span className="font-display font-semibold">{ds.name}</span><Badge tone="blue">{ds.version}</Badge><DemoBadge /><span className="ml-auto"><StatusBadge status={ds.status} /></span></div>
                {ds.status === "building" && <p className="mt-2 text-cyan">Paso {ds.progress?.step ?? 0}/10 · {ds.progress?.message}</p>}
                {ds.checksum && <p className="mt-1 truncate text-[11px] text-dim" title={ds.checksum}>sha256 {ds.checksum}</p>}
                {ds.quality?.rows_ingested && (
                  <dl className="mt-2 grid grid-cols-2 gap-y-1 text-[12px]">
                    <dt className="text-mist">Eventos ingeridos</dt><dd className="tabular">{int(ds.quality.rows_ingested)}</dd>
                    <dt className="text-mist">Duplicados eliminados</dt><dd className="tabular">{int(ds.quality.duplicates_removed)}</dd>
                    <dt className="text-mist">En cuarentena</dt><dd className="tabular">{int(ds.quality.quarantined_rows)}</dd>
                    <dt className="text-mist">Completitud crítica</dt><dd className="tabular">{pct(ds.quality.completeness_critical)}</dd>
                    <dt className="text-mist">Split train/val/test</dt><dd className="tabular">{Object.values(ds.quality.split_sizes).join(" / ")}</dd>
                    <dt className="text-mist">Puertas de calidad</dt><dd>{ds.quality.passed ? <span className="text-teal">Superadas</span> : <span className="text-danger">No superadas</span>}</dd>
                  </dl>
                )}
                <div className="mt-2 flex items-center gap-2 text-[11px] text-dim">{date(ds.created_at)}
                  <PermissionGate perm="datasets:approve">{ds.status === "ready" && <Button size="sm" className="ml-auto" onClick={() => approve.mutate(ds.id)}>Aprobar uso</Button>}</PermissionGate>
                </div>
              </article>
            ))}
          </div>
        )}
      </QueryState>
    </Panel>
  );
}

export function ActivityPage() {
  const [type, setType] = useState("");
  return (
    <div>
      <PageHeader title="Actividad reciente" subtitle="Eventos autorizados para tu rol, ordenados por fecha. Se actualiza en tiempo real." actions={
        <select aria-label="Tipo" value={type} onChange={(e) => setType(e.target.value)}><option value="">Todos</option><option value="course_completed">Cursos completados</option><option value="certificate_issued">Certificados</option><option value="assessment_graded">Evaluaciones</option><option value="enrollment">Matrículas</option><option value="session">Sesiones</option><option value="model_deployed">Modelos</option></select>} />
      <Panel title="Feed" icon={<Activity />}><ActivityFeed limit={50} type={type || undefined} /></Panel>
    </div>
  );
}

export function SettingsPage() {
  const qc = useQueryClient();
  const toast = useUI((s) => s.toast);
  const s = useQuery({ queryKey: ["settings"], queryFn: () => api("/settings") });
  const prefs = useQuery({ queryKey: ["notifications", "prefs"], queryFn: () => api("/notifications/preferences") });
  const canWrite = usePerm("settings:write");
  const save = useMutation({ mutationFn: (body: any) => api("/settings", { method: "PUT", body }), onSuccess: () => { toast("ok", "Configuración guardada"); qc.invalidateQueries({ queryKey: ["settings"] }); }, onError: (e) => toast("error", errorText(e)) });
  const savePrefs = useMutation({ mutationFn: (muted: string[]) => api("/notifications/preferences", { method: "PUT", body: { muted_types: muted } }), onSuccess: () => { toast("ok", "Preferencias guardadas"); qc.invalidateQueries({ queryKey: ["notifications", "prefs"] }); } });
  return (
    <div>
      <PageHeader title="Configuración" />
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Institución" icon={<Settings />}>
          <QueryState q={s}>
            {(d: any) => (
              <div className="grid gap-3 text-[13px]">
                <div><span className="text-mist">Institución:</span> {d.organization.name} ({d.organization.code}) · {d.organization.timezone}</div>
                <label className="flex items-center gap-3"><input type="checkbox" disabled={!canWrite} checked={!!d.settings.demo_simulator} onChange={(e) => save.mutate({ demo_simulator: e.target.checked })} className="accent-cyan" />
                  Simulador DEMO de actividad <span className="text-dim">(genera eventos reales rotulados demo-simulator)</span></label>
                <Field label={`Umbral de confianza para recomendaciones: ${pct(d.settings.recommendation_threshold, 0)}`}>
                  <input type="range" min={0} max={1} step={0.05} disabled={!canWrite} defaultValue={d.settings.recommendation_threshold} onMouseUp={(e) => save.mutate({ recommendation_threshold: +(e.target as HTMLInputElement).value })} className="!p-0 accent-cyan" />
                </Field>
                <Field label={`Umbral de alerta de riesgo: ${pct(d.settings.risk_alert_threshold, 0)}`}>
                  <input type="range" min={0} max={1} step={0.05} disabled={!canWrite} defaultValue={d.settings.risk_alert_threshold} onMouseUp={(e) => save.mutate({ risk_alert_threshold: +(e.target as HTMLInputElement).value })} className="!p-0 accent-cyan" />
                </Field>
                <div className="flex flex-wrap gap-2 border-t border-line/40 pt-3">
                  <Badge tone={d.integrations.redis ? "teal" : "warn"}>Redis {d.integrations.redis ? "conectado" : "memoria"}</Badge>
                  <Badge tone={d.integrations.supabase ? "teal" : "muted"}>Supabase {d.integrations.supabase ? "configurado" : "no configurado"}</Badge>
                  <Badge tone={d.integrations.ai_tutor_provider !== "none" ? "violet" : "muted"}>Tutor IA: {d.integrations.ai_tutor_provider === "none" ? "reglas" : d.integrations.ai_tutor_provider}</Badge>
                </div>
                {!canWrite && <p className="text-[12px] text-dim">Solo administración puede cambiar estos valores.</p>}
              </div>
            )}
          </QueryState>
        </Panel>
        <Panel title="Mis notificaciones" icon={<Settings />}>
          <QueryState q={prefs}>
            {(d: any) => (
              <ul className="grid gap-2 text-[13px]">
                {d.available_types.map((t: string) => (
                  <li key={t}><label className="flex items-center gap-3"><input type="checkbox" className="accent-cyan" checked={!d.muted_types.includes(t)}
                    onChange={(e) => savePrefs.mutate(e.target.checked ? d.muted_types.filter((x: string) => x !== t) : [...d.muted_types, t])} />{t}</label></li>
                ))}
              </ul>
            )}
          </QueryState>
        </Panel>
      </div>
    </div>
  );
}

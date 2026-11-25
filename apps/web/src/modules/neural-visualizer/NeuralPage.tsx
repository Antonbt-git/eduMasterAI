import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { BrainCircuit, CheckCircle2, FileText, FlaskConical, Pause, Play, RotateCcw, Rocket, ShieldAlert, Sparkles, Undo2, Zap } from "lucide-react";
import { useMemo, useState } from "react";
import { LossChart } from "@/components/charts/charts";
import { errorText, QueryState, Skeleton } from "@/components/feedback/states";
import { Badge, Button, DemoBadge, Field, Modal, PageHeader, Panel, PermissionGate, StatusBadge } from "@/components/ui/primitives";
import { STATE_LABEL, useNetworkLive, vizMode } from "@/hooks/useNetworkLive";
import { date, int, num, pct } from "@/lib/format";
import { api } from "@/services/api";
import { useUI } from "@/stores/ui";
import { type Graph, NeuralNetworkCanvas } from "./NeuralNetworkCanvas";

type Net = { key: string; title: string; description: string; task: string; primary_metric: string; state: string; production: any; versions: any[]; last_run: any };

const STATE_TONE: Record<string, string> = { entrenando: "violet", validando: "violet", "cargando datos": "cyan", publicado: "teal", detenido: "muted", error: "danger" };

export function NeuralPage() {
  const nets = useQuery({ queryKey: ["ml", "networks"], queryFn: () => api<Net[]>("/ml/networks"), staleTime: 60000 });
  const [sel, setSel] = useState("edumaster_mtl");
  const net = nets.data?.find((n) => n.key === sel);
  return (
    <div>
      <PageHeader
        title="Redes neuronales"
        subtitle="Cinco redes PyTorch entrenadas, versionadas y servidas en producción. La topología, los pesos y las activaciones vienen del modelo real; las sinapsis se encienden cuando llega una inferencia o una época de entrenamiento."
        actions={<DemoBadge title="Modelos entrenados con el dataset sintético DEMO" />}
      />
      {nets.isError && <div className="mb-4 text-[13px] text-danger">No se pudieron cargar las redes: {String((nets.error as any)?.message ?? nets.error)}</div>}
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
        {nets.isLoading && Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-40" />)}
        {nets.data?.map((n) => <NetCard key={n.key} n={n} active={n.key === sel} onClick={() => setSel(n.key)} />)}
      </div>
      {!nets.isLoading && !nets.isError && (!nets.data || nets.data.length === 0) && <div className="mb-4 text-[13px] text-mist">No hay redes registradas todavía.</div>}
      {net && <NetworkWorkbench key={net.key} net={net} />}
    </div>
  );
}

function NetCard({ n, active, onClick }: { n: Net; active: boolean; onClick: () => void }) {
  const g = useQuery({ queryKey: ["ml", "graph", n.key, "mini"], queryFn: () => api<Graph>(`/ml/networks/${n.key}/graph?weights=false`), staleTime: 300000 });
  const live = useNetworkLive(n.key, { runId: n.last_run?.id, status: n.last_run?.status });
  return (
    <button onClick={onClick} aria-pressed={active}
      className={clsx("panel flex flex-col p-3 text-left transition-colors", active ? "panel-glow !border-cyan/60" : "hover:!border-cyan/40")}>
      <div className="flex items-start gap-2">
        <span className="font-display text-[13px] leading-snug font-semibold">{n.title}</span>
        <Badge tone={live.training ? "violet" : STATE_TONE[n.state]} className="ml-auto">{live.training ? "entrenando" : n.state}</Badge>
      </div>
      <div className="grid-bg mt-2 h-20 overflow-hidden rounded-lg">
        {g.data && <NeuralNetworkCanvas graph={g.data} compact height={80} mode={vizMode(live, false, !!live.activations)} activations={live.activations}
          pulseKey={live.pulseKey} backKey={live.backKey} gradNorms={live.gradNorms} />}
      </div>
      <div className="mt-2 flex items-center justify-between text-[12px] text-mist">
        <span>{n.primary_metric}</span>
        <span className="font-display text-[14px] font-semibold text-frost tabular">{n.production ? num(n.production.primary_metric, 3) : "—"}</span>
      </div>
    </button>
  );
}

function NetworkWorkbench({ net }: { net: Net }) {
  const qc = useQueryClient();
  const toast = useUI((s) => s.toast);
  const [version, setVersion] = useState<string | undefined>(undefined);
  const graph = useQuery({ queryKey: ["ml", "graph", net.key, version], queryFn: () => api<Graph & any>(`/ml/networks/${net.key}/graph${version ? `?version=${version}` : ""}`), staleTime: 300000 });
  const examples = useQuery({ queryKey: ["ml", "examples"], queryFn: () => api<any>("/ml/examples?n=8"), staleTime: Infinity });
  const live = useNetworkLive(net.key, { runId: net.last_run?.id, status: net.last_run?.status, history: net.last_run?.history });
  const [demo, setDemo] = useState(false);
  const [playing, setPlaying] = useState(true);
  const [speed, setSpeed] = useState(1);
  const [showWeights, setShowWeights] = useState(true);
  const [layer, setLayer] = useState<string | null>(null);
  const [exIdx, setExIdx] = useState(0);
  const [result, setResult] = useState<any>(null);
  const mode = vizMode(live, demo, !!live.activations);

  const infer = useMutation({
    mutationFn: () => api("/ml/predictions", { body: { network_key: net.key, features: examples.data.examples[exIdx].features, version } }),
    onSuccess: (r: any) => { setResult(r); setDemo(false); live.setActivations(r.activations, r.latency_ms); },
    onError: (e) => toast("error", errorText(e)),
  });

  const selLayer = graph.data?.layers.find((l: any) => l.id === layer);
  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
      <Panel glow title={graph.data?.title ?? net.title} icon={<BrainCircuit />}
        live={<StatusChip mode={mode} published={!!net.production} />}
        actions={
          <div className="flex flex-wrap items-center gap-1.5">
            <select aria-label="Versión del modelo" value={version ?? ""} onChange={(e) => setVersion(e.target.value || undefined)} className="!py-1 text-[12px]">
              <option value="">Producción{net.production ? ` · v${net.production.version}` : ""}</option>
              {net.versions.map((v) => <option key={v.id} value={v.version}>v{v.version} · {v.stage}</option>)}
            </select>
          </div>
        }>
        <p className="-mt-1 mb-3 max-w-3xl text-[13px] text-mist">{net.description}</p>
        <div className="grid-bg relative h-[440px] overflow-hidden rounded-xl border border-cyan/15 bg-ink/40">
          {graph.isLoading && <Skeleton className="absolute inset-4" />}
          {graph.data && (
            <NeuralNetworkCanvas graph={graph.data} mode={mode} activations={live.activations} gradNorms={live.gradNorms} pulseKey={live.pulseKey}
              backKey={live.backKey} playing={playing} speed={speed} showWeights={showWeights} selectedLayer={layer} onSelectLayer={setLayer} />
          )}
          {mode === "demo" && <span className="absolute top-3 left-3 rounded-md border border-warn/40 bg-ink/80 px-2 py-1 text-[11px] text-warn">Simulación de muestra — no hay inferencia real en curso</span>}
        </div>
        <Legend />
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Button size="sm" variant="violet" onClick={() => infer.mutate()} loading={infer.isPending} disabled={!examples.data || !net.production && !version}>
            <Zap /> Ejecutar inferencia real
          </Button>
          <select aria-label="Ejemplo de entrada" value={exIdx} onChange={(e) => setExIdx(+e.target.value)} className="!py-1.5 text-[12px]">
            {examples.data?.examples.map((x: any, i: number) => <option key={x.example_id} value={i}>Ejemplo {i + 1} (DEMO) · nivel {x.features.course_level}</option>)}
          </select>
          <span className="mx-1 h-5 w-px bg-line" />
          <Button size="sm" variant="outline" onClick={() => { setDemo(true); setPlaying(true); }} disabled={live.training}><Play /> Iniciar simulación</Button>
          <Button size="sm" variant="ghost" onClick={() => setPlaying((p) => !p)} aria-pressed={!playing}>{playing ? <><Pause /> Pausar</> : <><Play /> Reanudar</>}</Button>
          <Button size="sm" variant="ghost" onClick={() => { setDemo(false); setResult(null); live.setActivations(undefined as any); }}><RotateCcw /> Reiniciar</Button>
          <label className="ml-auto flex items-center gap-2 text-[12px] text-mist">
            Velocidad
            <input type="range" min={0.25} max={3} step={0.25} value={speed} onChange={(e) => setSpeed(+e.target.value)} className="w-24 !p-0 accent-cyan" aria-label="Velocidad de animación" />
            <span className="w-8 text-frost tabular">{speed}×</span>
          </label>
          <label className="flex items-center gap-1.5 text-[12px] text-mist"><input type="checkbox" checked={showWeights} onChange={(e) => setShowWeights(e.target.checked)} className="accent-cyan" /> Mostrar pesos</label>
        </div>
        {result && <InferenceResult r={result} />}
      </Panel>

      <div className="flex flex-col gap-4">
        <TrainingStatus net={net} live={live} graph={graph.data} mode={mode} />
        <Panel title="Inspector de capa" icon={<FlaskConical />}>
          {!graph.data ? <Skeleton className="h-32" /> : (
            <>
              <div className="mb-2 flex flex-wrap gap-1">
                {graph.data.layers.map((l: any) => (
                  <button key={l.id} onClick={() => setLayer(l.id)} className={clsx("rounded-md border px-2 py-0.5 text-[11px]", layer === l.id ? "border-cyan bg-cyan/15 text-frost" : "border-line text-mist hover:text-frost")}>{l.name}</button>
                ))}
              </div>
              {selLayer ? (
                <dl className="grid grid-cols-2 gap-x-3 gap-y-1.5 text-[12px]">
                  <dt className="text-mist">Operación</dt><dd>{selLayer.op}</dd>
                  <dt className="text-mist">Neuronas</dt><dd className="tabular">{int(selLayer.units)} <span className="text-dim">({selLayer.display_idx.length} visibles)</span></dd>
                  <dt className="text-mist">Tensor</dt><dd className="font-medium text-cyan">{selLayer.shape}</dd>
                  <dt className="text-mist">Parámetros</dt><dd className="tabular">{int(selLayer.params)}</dd>
                  <dt className="text-mist">Tipo</dt><dd>{selLayer.kind}</dd>
                  <dt className="text-mist">Gradiente</dt><dd className="tabular">{live.gradNorms?.[selLayer.id] !== undefined ? num(live.gradNorms[selLayer.id], 4) : "—"}</dd>
                  {live.activations?.[selLayer.id] && <>
                    <dt className="col-span-2 mt-1 text-mist">Activaciones (normalizadas)</dt>
                    <dd className="col-span-2 flex h-10 items-end gap-0.5">
                      {live.activations[selLayer.id].map((a, i) => <span key={i} title={a.toFixed(3)} className="flex-1 rounded-t bg-gradient-to-t from-electric to-cyan" style={{ height: `${Math.max(4, a * 100)}%` }} />)}
                    </dd>
                  </>}
                </dl>
              ) : <p className="text-[13px] text-mist">Haz clic en una neurona o elige una capa para ver su operación, dimensión tensorial y activaciones.</p>}
              <p className="mt-3 text-[12px] text-dim">Total de parámetros: <span className="text-frost tabular">{int(graph.data.params_total)}</span></p>
            </>
          )}
        </Panel>
      </div>

      <div className="xl:col-span-2 grid gap-4 lg:grid-cols-2">
        <ModelRegistry net={net} onChanged={() => qc.invalidateQueries({ queryKey: ["ml"] })} />
        <TrainPanel net={net} disabled={live.training} />
      </div>
    </div>
  );
}

function StatusChip({ mode, published }: { mode: string; published?: boolean }) {
  const tone = { training: "bg-violet", inference: "bg-teal", demo: "bg-warn", idle: "bg-dim", error: "bg-danger" }[mode] ?? "bg-dim";
  return (
    <span className="ml-1 inline-flex items-center gap-1.5 text-[12px] text-mist">
      <span className={clsx("size-2 rounded-full", tone, mode !== "idle" && "live-dot")} /> {mode === "idle" && published ? "Publicado" : STATE_LABEL[mode]}
    </span>
  );
}

function Legend() {
  const items = [["Entrada", "#FF5FD2"], ["Embedding", "#FF96E6"], ["Oculta", "#7C5CFF"], ["Temporal", "#FF9F43"], ["Fusión", "#B57CFF"], ["Salida", "#2DE2A6"]];
  return (
    <div className="mt-2 flex flex-wrap gap-3 text-[11px] text-mist">
      {items.map(([l, c]) => <span key={l} className="inline-flex items-center gap-1"><span className="size-2 rounded-full" style={{ background: c }} />{l}</span>)}
      <span className="inline-flex items-center gap-1"><span className="h-0.5 w-3 rounded" style={{ background: "#FF9F43" }} />Retropropagación</span>
    </div>
  );
}

function TrainingStatus({ net, live, graph, mode }: { net: Net; live: any; graph: any; mode: string }) {
  const prod = net.production;
  const run = net.last_run;
  return (
    <Panel title="Estado del proceso" icon={<Sparkles />}>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1.5 text-[12px]">
        <dt className="text-mist">Modelo</dt><dd className="truncate">{net.key}</dd>
        <dt className="text-mist">Versión activa</dt><dd>{prod ? `v${prod.version}` : <span className="text-warn">Sin publicar</span>}</dd>
        <dt className="text-mist">Dataset</dt><dd>{prod?.dataset_version ?? run?.dataset_version ?? "—"} <DemoBadge /></dd>
        <dt className="text-mist">Estado</dt><dd>{live.training ? <StatusBadge status={live.status} /> : mode === "idle" && prod ? `Publicado · ${date(prod.promoted_at)}` : STATE_LABEL[mode]}</dd>
        <dt className="text-mist">Época</dt><dd className="tabular">{live.epoch ? `${live.epoch}${live.epochs ? ` / ${live.epochs}` : ""}` : "—"}</dd>
        <dt className="text-mist">Loss (train / val)</dt><dd className="tabular">{live.train_loss !== undefined ? `${num(live.train_loss, 4)} / ${num(live.val_loss, 4)}` : "—"}</dd>
        <dt className="text-mist">Métrica validación</dt><dd className="tabular">{live.val_metric !== undefined ? num(live.val_metric, 4) : "—"}</dd>
        <dt className="text-mist">Latencia inferencia</dt><dd className="tabular">{live.latency !== undefined ? `${num(live.latency, 1)} ms` : "—"}</dd>
      </dl>
      {live.message && <p className="mt-2 text-[12px] text-mist">{live.message}</p>}
      {live.history.length > 1 && <div className="mt-2"><LossChart history={live.history} /></div>}
      {!graph && null}
    </Panel>
  );
}

function InferenceResult({ r }: { r: any }) {
  const s = r.scores;
  return (
    <div className="panel-inner mt-3 grid gap-3 p-3 text-[13px] md:grid-cols-[1fr_1fr]">
      <div>
        <div className="mb-1 flex items-center gap-2 text-mist">Resultado <Badge tone="violet">v{r.model_version}</Badge><span className="text-dim">{num(r.latency_ms, 1)} ms</span></div>
        <div className="flex flex-wrap gap-4">
          {s.completion_probability !== undefined && <Metric label="P(finalizar)" value={pct(s.completion_probability)} />}
          {s.risk_probability !== undefined && <Metric label="P(desconexión)" value={pct(s.risk_probability)} tone={s.risk_probability > 0.6 ? "text-warn" : undefined} />}
          {s.mastery_level && <Metric label="Dominio estimado" value={s.mastery_level} sub={`confianza ${pct(s.mastery_confidence, 0)}`} />}
        </div>
        {s.ranking && <ol className="mt-2 space-y-0.5 text-[12px]">{s.ranking.slice(0, 3).map((x: any, i: number) => <li key={x.code} className="text-mist"><span className="text-frost">{i + 1}.</span> {x.title}</li>)}</ol>}
      </div>
      <div>
        <div className="mb-1 text-mist">Factores principales (atribución gradiente × entrada)</div>
        <ul className="space-y-1">
          {r.explanation.map((f: any) => (
            <li key={f.feature} className="flex items-center gap-2 text-[12px]">
              <span className="w-40 truncate">{f.label}</span>
              <span className={clsx("h-1.5 rounded-full", f.contribution > 0 ? "bg-cyan" : "bg-violet")} style={{ width: `${Math.min(100, Math.abs(f.contribution) * 60 + 8)}px` }} />
              <span className="text-dim">{f.direction}</span>
            </li>
          ))}
        </ul>
        <p className="mt-2 text-[11px] text-dim">{r.disclaimer}</p>
      </div>
    </div>
  );
}

const Metric = ({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: string }) => (
  <div><div className="text-[11px] text-mist">{label}</div><div className={clsx("font-display text-xl font-semibold tabular", tone)}>{value}</div>{sub && <div className="text-[11px] text-dim">{sub}</div>}</div>
);

function ModelRegistry({ net, onChanged }: { net: Net; onChanged: () => void }) {
  const toast = useUI((s) => s.toast);
  const [card, setCard] = useState<string | null>(null);
  const [approve, setApprove] = useState<any>(null);
  const act = useMutation({
    mutationFn: ({ path, body }: { path: string; body?: any }) => api(path, { method: "POST", body }),
    onSuccess: (_d, v) => { toast("ok", v.path.includes("rollback") ? "Rollback aplicado" : v.path.includes("promote") ? "Versión publicada en producción" : v.path.includes("reject") ? "Versión rechazada" : "Versión aprobada"); onChanged(); setApprove(null); },
    onError: (e) => toast("error", errorText(e)),
  });
  const openCard = async (id: string) => setCard((await api(`/ml/models/${id}`)).model_card ?? "Sin model card");
  return (
    <Panel title="Registro de modelos" icon={<FileText />}
      actions={<PermissionGate perm="ml:approve"><Button size="sm" variant="ghost" onClick={() => act.mutate({ path: `/ml/networks/${net.key}/rollback` })}><Undo2 /> Rollback</Button></PermissionGate>}>
      {net.versions.length === 0 ? <p className="text-[13px] text-mist">Aún no hay versiones entrenadas.</p> : (
        <div className="overflow-x-auto">
          <table className="w-full text-[12px]">
            <thead className="text-left text-mist"><tr><th className="py-1 font-normal">Versión</th><th className="font-normal">{net.primary_metric}</th><th className="font-normal">Baseline</th><th className="font-normal">Etapa</th><th className="font-normal">Aprobación</th><th /></tr></thead>
            <tbody>
              {net.versions.map((v) => (
                <tr key={v.id} className="border-t border-line/50">
                  <td className="py-1.5">v{v.version}<div className="text-[11px] text-dim">{date(v.created_at)}</div></td>
                  <td className="tabular">{num(v.primary_metric, 4)} {v.beats_baseline ? <CheckCircle2 className="inline size-3.5 text-teal" aria-label="Supera baseline" /> : <ShieldAlert className="inline size-3.5 text-warn" aria-label="No supera baseline" />}</td>
                  <td className="tabular text-mist">{num(v.baseline_metric, 4)}</td>
                  <td><StatusBadge status={v.stage} /></td>
                  <td><StatusBadge status={v.approval_status} /></td>
                  <td className="text-right whitespace-nowrap">
                    <Button size="sm" variant="ghost" onClick={() => openCard(v.id)} aria-label="Ver model card"><FileText /></Button>
                    <PermissionGate perm="ml:approve">
                      {v.approval_status === "pending" && <Button size="sm" variant="outline" onClick={() => setApprove(v)}>Revisar</Button>}
                      {v.approval_status === "approved" && v.stage !== "production" && <Button size="sm" variant="outline" onClick={() => act.mutate({ path: `/ml/models/${v.id}/promote` })}><Rocket /> Publicar</Button>}
                    </PermissionGate>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="mt-2 text-[11px] text-dim">Una versión solo se publica si supera el baseline interpretable o con justificación auditada.</p>
      <Modal open={!!card} onClose={() => setCard(null)} title="Model card" wide><pre className="text-[12px] whitespace-pre-wrap text-mist">{card}</pre></Modal>
      <ApproveDialog v={approve} onClose={() => setApprove(null)} onSubmit={(path, body) => act.mutate({ path, body })} loading={act.isPending} />
    </Panel>
  );
}

function ApproveDialog({ v, onClose, onSubmit, loading }: { v: any; onClose: () => void; onSubmit: (p: string, b: any) => void; loading: boolean }) {
  const [note, setNote] = useState("");
  if (!v) return null;
  return (
    <Modal open onClose={onClose} title={`Revisar v${v.version}`}>
      <p className="mb-3 text-[13px] text-mist">Métrica {num(v.primary_metric, 4)} frente a baseline {num(v.baseline_metric, 4)}. {v.beats_baseline ? "Supera el baseline." : "No supera el baseline: aprobarla requiere justificación y queda auditada."}</p>
      <Field label="Nota de aprobación o rechazo" hint="Mínimo 5 caracteres; se guarda en la bitácora.">
        <textarea rows={3} value={note} onChange={(e) => setNote(e.target.value)} />
      </Field>
      <div className="mt-4 flex justify-end gap-2">
        <Button variant="outline" disabled={note.length < 5} onClick={() => onSubmit(`/ml/models/${v.id}/reject`, { note })}>Rechazar</Button>
        <Button loading={loading} disabled={note.length < 5} onClick={() => onSubmit(`/ml/models/${v.id}/approve`, { note, force: !v.beats_baseline })}>Aprobar</Button>
      </div>
    </Modal>
  );
}

function TrainPanel({ net, disabled }: { net: Net; disabled: boolean }) {
  const toast = useUI((s) => s.toast);
  const qc = useQueryClient();
  const [p, setP] = useState({ epochs: 40, lr: 0.003, batch_size: 128, patience: 7, seed: 42 });
  const runs = useQuery({ queryKey: ["ml", "runs", net.key], queryFn: () => api<any[]>(`/ml/training-runs?network_key=${net.key}&limit=6`) });
  const train = useMutation({
    mutationFn: () => api("/ml/training-runs", { body: { network_key: net.key, ...p } }),
    onSuccess: () => { toast("ok", "Entrenamiento en cola. Verás el progreso en vivo."); qc.invalidateQueries({ queryKey: ["ml"] }); },
    onError: (e) => toast("error", errorText(e)),
  });
  const fields = useMemo(() => [["epochs", "Épocas", 1], ["lr", "Tasa de aprendizaje", 0.0005], ["batch_size", "Tamaño de lote", 8], ["patience", "Paciencia (early stopping)", 1]] as const, []);
  return (
    <Panel title="Entrenamiento asíncrono" icon={<FlaskConical />}>
      <PermissionGate perm="ml:train" fallback={<p className="mb-3 text-[13px] text-mist">Solo el rol ML Engineer puede lanzar entrenamientos. Puedes consultar el historial.</p>}>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {fields.map(([k, l, step]) => (
            <Field key={k} label={l}><input type="number" step={step} value={(p as any)[k]} onChange={(e) => setP({ ...p, [k]: +e.target.value })} /></Field>
          ))}
        </div>
        <div className="mt-3 flex items-center gap-3">
          <Button variant="violet" onClick={() => train.mutate()} loading={train.isPending} disabled={disabled}><Play /> Entrenar nueva versión</Button>
          <span className="text-[12px] text-dim">Se ejecuta en el worker, nunca en el hilo HTTP.</span>
        </div>
      </PermissionGate>
      <QueryState q={runs} empty={(d) => d.length === 0}>
        {(d) => (
          <ul className="mt-3 space-y-1 text-[12px]">
            {d.map((r) => (
              <li key={r.id} className="flex items-center gap-2 border-t border-line/40 pt-1">
                <StatusBadge status={r.status} />
                <span className="text-mist">{date(r.created_at)}</span>
                <span className="text-dim">{r.history?.length ?? 0} épocas</span>
                {r.metrics?.primary !== undefined && <span className="ml-auto tabular">{num(r.metrics.primary, 4)} <span className="text-dim">vs {num(r.metrics.baseline_primary, 4)}</span></span>}
                {r.error && <span className="ml-auto truncate text-danger" title={r.error}>{r.error}</span>}
              </li>
            ))}
          </ul>
        )}
      </QueryState>
    </Panel>
  );
}


/**
 * Visualizador de topología neuronal (documento maestro §4.10, §5.3, §5.4).
 * - Canvas 2D aislado de React: el bucle requestAnimationFrame lee props desde refs (no re-renderiza la app por frame).
 * - Nodos/aristas = topología REAL entregada por la API (capas, neuronas mostradas, pesos muestreados).
 * - Propagación hacia delante (izq→der) solo con inferencia real o simulación rotulada; retropropagación (der→izq)
 *   solo con entrenamiento real. Intensidad = activación·|peso| o norma del gradiente, nunca colores aleatorios.
 * - Respeta prefers-reduced-motion, se pausa fuera de pantalla y limita FPS en modo compacto.
 */
import { useEffect, useRef, useState } from "react";

export type GLayer = { id: string; name: string; kind: string; op: string; units: number; shape: string; col: number; display_idx: number[]; labels: string[] | null; params: number };
export type GEdge = { from: string; to: string; weights: number[][] | null };
export type Graph = { key: string; title: string; layers: GLayer[]; edges: GEdge[] };
export type VizMode = "idle" | "inference" | "training" | "demo" | "error";

type Props = {
  graph: Graph;
  mode: VizMode;
  activations?: Record<string, number[]>;
  gradNorms?: Record<string, number>;
  pulseKey?: number;          // cambia ⇒ dispara una onda hacia delante (inferencia real)
  backKey?: number;           // cambia ⇒ dispara onda de retropropagación (época real)
  playing?: boolean;
  speed?: number;
  showWeights?: boolean;
  compact?: boolean;
  height?: number;
  selectedLayer?: string | null;
  onSelectLayer?: (id: string) => void;
};

const KIND_COLOR: Record<string, [number, number, number]> = {
  input: [255, 95, 210], embedding: [255, 150, 230], hidden: [124, 92, 255], temporal: [255, 159, 67], fusion: [181, 124, 255], output: [45, 226, 166],
};
const rgba = (c: [number, number, number], a: number) => `rgba(${c[0]},${c[1]},${c[2]},${a})`;

type Node = { layer: string; i: number; x: number; y: number; r: number; kind: string; label?: string; flash: number };
type Particle = { x0: number; y0: number; x1: number; y1: number; t0: number; dur: number; c: [number, number, number]; s: number; to: Node };
type Wave = { dir: 1 | -1; t0: number; fired: Set<number> };

export function NeuralNetworkCanvas(props: Props) {
  const wrap = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const P = useRef(props);
  P.current = props;
  const [hover, setHover] = useState<{ x: number; y: number; n: Node } | null>(null);
  const state = useRef({ nodes: [] as Node[], byLayer: new Map<string, Node[]>(), particles: [] as Particle[], waves: [] as Wave[], cols: 1, w: 0, h: 0, hoverNode: null as Node | null, lastDemo: 0, lastTrain: 0, narrow: false });
  const reduced = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

  // ---------------------------------------------------------------- layout
  const layout = () => {
    const el = wrap.current, cv = canvas.current;
    if (!el || !cv) return;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const w = el.clientWidth, h = props.height ?? el.clientHeight;
    cv.width = w * dpr; cv.height = h * dpr; cv.style.width = `${w}px`; cv.style.height = `${h}px`;
    cv.getContext("2d")!.setTransform(dpr, 0, 0, dpr, 0, 0);
    const g = P.current.graph;
    const cols = Math.max(...g.layers.map((l) => l.col)) + 1;
    const narrow = w < 640;
    state.current.narrow = narrow;
    const padL = props.compact || narrow ? 14 : 118, padR = props.compact || narrow ? 14 : 112, padT = props.compact ? 10 : 34, padB = props.compact ? 10 : 18;
    const nodes: Node[] = [];
    const byLayer = new Map<string, Node[]>();
    for (let c = 0; c < cols; c++) {
      const ls = g.layers.filter((l) => l.col === c);
      const x = cols === 1 ? w / 2 : padL + ((w - padL - padR) * c) / (cols - 1);
      const total = ls.reduce((s, l) => s + l.display_idx.length, 0) + (ls.length - 1) * 2.6;
      const avail = h - padT - padB;
      const step = Math.min(props.compact ? 16 : 34, avail / Math.max(1, total));
      let y = padT + (avail - step * total) / 2 + step / 2;
      const r = Math.max(2.5, Math.min(props.compact ? 4.5 : 10, step * 0.32));
      ls.forEach((l) => {
        const arr: Node[] = l.display_idx.map((_, k) => ({ layer: l.id, i: k, x, y: y + k * step, r, kind: l.kind, label: l.labels?.[k], flash: 0 }));
        y += (l.display_idx.length + 2.6) * step;
        arr.forEach((n) => nodes.push(n));
        byLayer.set(l.id, arr);
      });
    }
    Object.assign(state.current, { nodes, byLayer, cols, w, h, particles: [], waves: state.current.waves });
  };

  useEffect(() => {
    layout();
    const ro = new ResizeObserver(layout);
    if (wrap.current) ro.observe(wrap.current);
    return () => ro.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [props.graph, props.compact, props.height]);

  // Ondas disparadas por eventos REALES
  useEffect(() => { if (props.pulseKey) state.current.waves.push({ dir: 1, t0: performance.now(), fired: new Set() }); }, [props.pulseKey]);
  useEffect(() => { if (props.backKey) state.current.waves.push({ dir: -1, t0: performance.now(), fired: new Set() }); }, [props.backKey]);

  // ---------------------------------------------------------------- bucle de animación
  useEffect(() => {
    let raf = 0, last = 0, visible = true;
    const io = new IntersectionObserver(([e]) => (visible = e.isIntersecting));
    if (wrap.current) io.observe(wrap.current);
    const ctx = canvas.current!.getContext("2d")!;
    const S = state.current;

    const strengthOf = (layerId: string, i: number) => {
      const a = P.current.activations?.[layerId];
      return a ? (a[i] ?? 0.3) : 0.55;
    };
    const weightOf = (e: GEdge, i: number, j: number) => e.weights?.[j]?.[i];

    const fireColumn = (wave: Wave, col: number, now: number) => {
      const p = P.current;
      const spd = (p.speed ?? 1) * (p.compact ? 0.9 : 1);
      const colDur = 650 / spd;
      const edges = p.graph.edges.filter((e) => {
        const a = p.graph.layers.find((l) => l.id === e.from)!.col, b = p.graph.layers.find((l) => l.id === e.to)!.col;
        return wave.dir === 1 ? a === col : b === col;
      });
      const gmax = Math.max(1e-6, ...Object.values(p.gradNorms ?? { x: 1 }));
      for (const e of edges) {
        const src = S.byLayer.get(e.from) ?? [], dst = S.byLayer.get(e.to) ?? [];
        const la = p.graph.layers.find((l) => l.id === e.from)!.col, lb = p.graph.layers.find((l) => l.id === e.to)!.col;
        let budget = p.compact ? 10 : 34;
        for (const s of src) for (const d of dst) {
          const w = weightOf(e, s.i, d.i);
          let str: number;
          let color: [number, number, number];
          if (wave.dir === 1) {
            str = strengthOf(e.from, s.i) * (w === undefined ? 0.6 : Math.abs(w));
            color = w !== undefined && w < 0 ? [255, 180, 120] : KIND_COLOR[d.kind] ?? KIND_COLOR.hidden;
          } else {
            str = ((p.gradNorms?.[e.to] ?? gmax * 0.6) / gmax) * (w === undefined ? 0.6 : 0.4 + Math.abs(w) * 0.6);
            color = [255, 159, 67];
          }
          if (str < 0.18 && Math.random() > str * 2) continue;
          if (budget-- <= 0) break;
          const [from, to] = wave.dir === 1 ? [s, d] : [d, s];
          S.particles.push({ x0: from.x, y0: from.y, x1: to.x, y1: to.y, t0: now + Math.random() * 120, dur: colDur * Math.abs(lb - la), c: color, s: Math.min(1, 0.35 + str), to });
        }
      }
    };

    const frame = (now: number) => {
      raf = requestAnimationFrame(frame);
      const p = P.current;
      const fpsCap = p.compact ? 30 : 60;
      if (!visible || document.hidden || now - last < 1000 / fpsCap - 1) return;
      last = now;
      const animate = !reduced && (p.playing ?? true);

      // Fuentes de ondas según estado real
      if (animate && p.mode === "demo" && now - S.lastDemo > 2600 / (p.speed ?? 1)) { S.lastDemo = now; S.waves.push({ dir: 1, t0: now, fired: new Set() }); }
      if (animate && p.mode === "training" && !p.backKey && now - S.lastTrain > 2400 / (p.speed ?? 1)) {
        S.lastTrain = now; S.waves.push({ dir: 1, t0: now, fired: new Set() }); S.waves.push({ dir: -1, t0: now + 1300 / (p.speed ?? 1), fired: new Set() });
      }
      if (animate) {
        const spd = p.speed ?? 1;
        for (const wv of S.waves) {
          const front = Math.floor(((now - wv.t0) * spd) / 650);
          if (front < 0) continue;
          const col = wv.dir === 1 ? front : S.cols - 1 - front;
          if (col >= 0 && col < S.cols && !wv.fired.has(col)) { wv.fired.add(col); fireColumn(wv, col, now); }
        }
        S.waves = S.waves.filter((wv) => wv.fired.size < S.cols);
      } else {
        S.particles = [];
      }

      // ---------------------------------------------------------- dibujo
      ctx.clearRect(0, 0, S.w, S.h);
      const hv = S.hoverNode;
      // aristas estáticas
      for (const e of p.graph.edges) {
        const src = S.byLayer.get(e.from) ?? [], dst = S.byLayer.get(e.to) ?? [];
        for (const s of src) for (const d of dst) {
          const w = e.weights?.[d.i]?.[s.i];
          const focus = hv && (hv === s || hv === d);
          let alpha = p.compact ? 0.08 : 0.11;
          let col = "rgba(150,110,255,";
          let lw = 0.6;
          if (p.showWeights && w !== undefined) {
            alpha = 0.05 + Math.abs(w) * 0.45;
            lw = 0.4 + Math.abs(w) * 1.8;
            col = w >= 0 ? "rgba(255,95,210," : "rgba(255,170,110,";
          }
          if (e.weights === null) { alpha *= 0.6; }
          if (hv && !focus) alpha *= 0.25;
          if (focus) { alpha = Math.max(alpha, 0.65); lw += 0.6; }
          ctx.strokeStyle = col + alpha + ")";
          ctx.lineWidth = lw;
          ctx.beginPath();
          ctx.moveTo(s.x, s.y);
          const mx = (s.x + d.x) / 2;
          ctx.bezierCurveTo(mx, s.y, mx, d.y, d.x, d.y);
          ctx.stroke();
        }
      }
      // partículas sinápticas
      ctx.globalCompositeOperation = "lighter";
      const alive: Particle[] = [];
      for (const q of S.particles) {
        const t = (now - q.t0) / q.dur;
        if (t < 0) { alive.push(q); continue; }
        if (t >= 1) { q.to.flash = Math.min(1.4, q.to.flash + 0.35 * q.s); continue; }
        const e = t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2;
        const mx = (q.x0 + q.x1) / 2;
        const u = 1 - e;
        const x = u * u * u * q.x0 + 3 * u * u * e * mx + 3 * u * e * e * mx + e * e * e * q.x1;
        const y = u * u * u * q.y0 + 3 * u * u * e * q.y0 + 3 * u * e * e * q.y1 + e * e * e * q.y1;
        const rad = (p.compact ? 1.6 : 2.6) * (0.6 + q.s);
        const g = ctx.createRadialGradient(x, y, 0, x, y, rad * 4);
        g.addColorStop(0, rgba(q.c, 0.8 * q.s));
        g.addColorStop(1, rgba(q.c, 0));
        ctx.fillStyle = g;
        ctx.beginPath(); ctx.arc(x, y, rad * 4, 0, Math.PI * 2); ctx.fill();
        alive.push(q);
      }
      S.particles = alive.slice(-2500);
      ctx.globalCompositeOperation = "source-over";

      // neuronas
      for (const n of S.nodes) {
        const base = KIND_COLOR[n.kind] ?? KIND_COLOR.hidden;
        const act = p.activations?.[n.layer]?.[n.i];
        const intensity = act === undefined ? 0.45 : 0.25 + act * 0.75;
        const glow = Math.min(1.6, intensity * 0.6 + n.flash);
        const sel = p.selectedLayer === n.layer;
        const R = n.r * (1 + n.flash * 0.25);
        const g = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, R * 3.4);
        g.addColorStop(0, rgba(base, 0.55 * glow));
        g.addColorStop(1, rgba(base, 0));
        ctx.fillStyle = g;
        ctx.beginPath(); ctx.arc(n.x, n.y, R * 3.4, 0, Math.PI * 2); ctx.fill();
        const core = ctx.createRadialGradient(n.x - R * 0.3, n.y - R * 0.3, 0, n.x, n.y, R);
        core.addColorStop(0, `rgba(255,255,255,${0.55 + 0.4 * intensity})`);
        core.addColorStop(0.45, rgba(base, 0.95));
        core.addColorStop(1, rgba([13, 10, 30], 0.9));
        ctx.fillStyle = core;
        ctx.beginPath(); ctx.arc(n.x, n.y, R, 0, Math.PI * 2); ctx.fill();
        ctx.lineWidth = sel || hv === n ? 2 : 1;
        ctx.strokeStyle = sel || hv === n ? "rgba(255,255,255,0.9)" : rgba(base, 0.8);
        ctx.stroke();
        n.flash *= 0.9;
      }

      if (!p.compact) {
        ctx.font = "500 11px Inter, sans-serif";
        ctx.textBaseline = "middle";
        for (const l of p.graph.layers) {
          const arr = S.byLayer.get(l.id) ?? [];
          if (!arr.length) continue;
          const isFirst = l.col === 0, isLast = l.col === S.cols - 1;
          if (l.labels && (isFirst || isLast) && !S.narrow) {
            ctx.fillStyle = "rgba(236,228,255,0.88)";
            ctx.textAlign = isFirst ? "right" : "left";
            arr.forEach((n) => n.label && ctx.fillText(trunc(n.label, 18), n.x + (isFirst ? -n.r - 8 : n.r + 8), n.y));
          }
          ctx.textAlign = "center";
          ctx.fillStyle = rgba(KIND_COLOR[l.kind] ?? KIND_COLOR.hidden, 1);
          ctx.font = "600 11px Sora, Inter, sans-serif";
          if (!S.narrow) ctx.fillText(trunc(l.name, 22), arr[0].x, arr[0].y - arr[0].r - 12);
          if (l.units > l.display_idx.length) {
            ctx.font = "500 10px Inter, sans-serif";
            ctx.fillStyle = "rgba(169,156,201,0.9)";
            const lastN = arr[arr.length - 1];
            ctx.fillText(`+${l.units - l.display_idx.length} neuronas`, lastN.x, lastN.y + lastN.r + 11);
          }
          ctx.font = "500 11px Inter, sans-serif";
        }
      }
    };
    raf = requestAnimationFrame(frame);
    return () => { cancelAnimationFrame(raf); io.disconnect(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ---------------------------------------------------------------- interacción
  const pick = (ev: React.MouseEvent) => {
    const rect = canvas.current!.getBoundingClientRect();
    const x = ev.clientX - rect.left, y = ev.clientY - rect.top;
    let best: Node | null = null, bd = 18 * 18;
    for (const n of state.current.nodes) { const d = (n.x - x) ** 2 + (n.y - y) ** 2; if (d < bd) { bd = d; best = n; } }
    return { best, x, y };
  };

  const layerOf = (id: string) => props.graph.layers.find((l) => l.id === id);
  return (
    <div ref={wrap} className="relative w-full" style={{ height: props.height ?? "100%" }}>
      <canvas
        ref={canvas}
        role="img"
        aria-label={`Topología de ${props.graph.title}: ${props.graph.layers.map((l) => `${l.name} ${l.units} neuronas`).join(", ")}`}
        className={props.compact ? "" : "cursor-crosshair"}
        onMouseMove={props.compact ? undefined : (e) => { const { best, x, y } = pick(e); state.current.hoverNode = best; setHover(best ? { x, y, n: best } : null); }}
        onMouseLeave={() => { state.current.hoverNode = null; setHover(null); }}
        onClick={props.compact ? undefined : (e) => { const { best } = pick(e); if (best) props.onSelectLayer?.(best.layer); }}
      />
      {hover && !props.compact && (() => {
        const l = layerOf(hover.n.layer)!;
        const act = props.activations?.[l.id]?.[hover.n.i];
        return (
          <div className="pointer-events-none absolute z-10 w-52 rounded-lg border border-cyan/40 bg-ink/95 p-2.5 text-[11px] shadow-[0_0_24px_-6px_#7C5CFF]"
            style={{ left: Math.min(hover.x + 14, (wrap.current?.clientWidth ?? 400) - 215), top: hover.y + 10 }}>
            <div className="font-display text-[12px] font-semibold text-frost">{l.name}</div>
            <div className="text-mist">{hover.n.label ?? `Neurona #${l.display_idx[hover.n.i]}`} · {l.op}</div>
            <div className="mt-1 text-mist">Tensor <span className="text-frost">{l.shape}</span></div>
            <div className="text-mist">Activación {act === undefined ? <span className="text-dim">sin inferencia</span> : <span className="text-cyan">{act.toFixed(3)}</span>}</div>
          </div>
        );
      })()}
    </div>
  );
}

const trunc = (s: string, n: number) => (s.length > n ? `${s.slice(0, n - 1)}…` : s);

import { C, EChart, tooltip } from "./echarts";
import { int, pct } from "@/lib/format";

const COLORS = [C.electric, C.violet, C.teal, C.cyan];

export function TrendChart({ labels, series, height = 250 }: { labels: string[]; series: { name: string; unit: string; data: number[] }[]; height?: number }) {
  const option = {
    grid: { left: 44, right: 64, top: 36, bottom: 28 },
    tooltip: { ...tooltip, trigger: "axis", valueFormatter: (v: number) => int(v) },
    legend: { top: 0, right: 0, icon: "circle", itemWidth: 9, textStyle: { color: C.mist, fontSize: 12 } },
    xAxis: { type: "category", data: labels, boundaryGap: false, axisLine: { lineStyle: { color: C.line } }, axisLabel: { color: C.mist, fontSize: 11 }, axisTick: { show: false } },
    yAxis: { type: "value", splitLine: { lineStyle: { color: "rgba(124,92,255,0.12)" } }, axisLabel: { color: C.mist, fontSize: 11, formatter: (v: number) => (v >= 1000 ? `${v / 1000}k` : v) } },
    series: series.map((s, i) => ({
      name: `${s.name} (${s.unit})`, type: "line", smooth: 0.35, data: s.data, symbol: "circle", symbolSize: 6, showSymbol: true,
      lineStyle: { width: 2.5, color: COLORS[i], shadowColor: COLORS[i], shadowBlur: 12 },
      itemStyle: { color: COLORS[i], borderColor: C.ink, borderWidth: 1.5 },
      areaStyle: i === 0 ? { color: { type: "linear", x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: "rgba(124,92,255,0.28)" }, { offset: 1, color: "rgba(124,92,255,0)" }] } } : undefined,
      endLabel: { show: true, color: "#fff", backgroundColor: COLORS[i], padding: [3, 6], borderRadius: 6, fontWeight: 600, fontSize: 11, formatter: (p: any) => int(p.value) },
    })),
  };
  return <EChart option={option} height={height} label={`Tendencia: ${series.map((s) => s.name).join(", ")}`} />;
}

export function CompletionDonut({ breakdown }: { breakdown: { label: string; pct: number; count: number }[] }) {
  const main = breakdown[0];
  const option = {
    tooltip: { ...tooltip, formatter: (p: any) => `${p.name}: ${int(p.data.count)} (${pct(p.data.pct)})` },
    series: [{
      type: "pie", radius: ["66%", "84%"], center: ["50%", "50%"], avoidLabelOverlap: false, label: { show: false }, padAngle: 2,
      itemStyle: { borderRadius: 6, shadowBlur: 14, shadowColor: "rgba(255,95,210,0.45)" },
      data: breakdown.map((b, i) => ({ name: b.label, value: b.count, count: b.count, pct: b.pct, itemStyle: { color: [C.cyan, C.violet, "#6E7BFF"][i] } })),
    }],
  };
  return (
    <div className="relative">
      <EChart option={option} height={170} label={`Finalización: ${breakdown.map((b) => `${b.label} ${pct(b.pct, 0)}`).join(", ")}`} />
      <div className="pointer-events-none absolute inset-0 grid place-items-center text-center">
        <div>
          <div className="font-display text-3xl font-semibold tabular">{pct(main?.pct ?? 0, 0)}</div>
          <div className="text-[12px] text-mist">Completados</div>
        </div>
      </div>
    </div>
  );
}

export function SkillHeatmap({ skills, levels, matrix, height = 260 }: { skills: { name: string }[]; levels: string[]; matrix: number[][]; height?: number }) {
  const option = {
    grid: { left: 8, right: 70, top: 8, bottom: 30, containLabel: true },
    tooltip: { ...tooltip, formatter: (p: any) => `${skills[p.data[1]].name} · ${levels[p.data[0]]}: ${p.data[2]}% de estudiantes` },
    xAxis: { type: "category", data: levels, axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: C.mist, fontSize: 11 }, splitArea: { show: false } },
    yAxis: { type: "category", data: skills.map((s) => s.name), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: C.frost, fontSize: 12 } },
    visualMap: {
      min: 0, max: 60, calculable: false, orient: "vertical", right: 0, top: 6, itemHeight: 170, itemWidth: 10, text: ["Nivel %", ""],
      textStyle: { color: C.mist, fontSize: 11 }, inRange: { color: ["#211A4A", "#4B2FA8", "#7C5CFF", "#FF9F43", "#FF8FE0"] },
      formatter: (v: number) => `${Math.round(v)}%`,
    },
    series: [{ type: "heatmap", data: matrix, itemStyle: { borderColor: "rgba(13,10,30,0.7)", borderWidth: 2, borderRadius: 4 },
      emphasis: { itemStyle: { shadowBlur: 14, shadowColor: C.cyan } }, label: { show: true, color: "rgba(243,238,255,0.75)", fontSize: 10, formatter: (p: any) => `${Math.round(p.data[2])}` } }],
  };
  return <EChart option={option} height={height} label="Mapa de calor de dominio por competencia y nivel" />;
}

export function Bars({ labels, values, color = C.cyan, height = 60, label }: { labels?: string[]; values: number[]; color?: string; height?: number; label: string }) {
  const option = {
    grid: { left: 0, right: 0, top: 4, bottom: 0 }, tooltip: { ...tooltip, trigger: "axis" },
    xAxis: { type: "category", show: false, data: labels ?? values.map((_, i) => i + 1) }, yAxis: { type: "value", show: false },
    series: [{ type: "bar", data: values, barWidth: "62%", itemStyle: { borderRadius: [3, 3, 0, 0], color: { type: "linear", x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color }, { offset: 1, color: "rgba(124,92,255,0.25)" }] } } }],
  };
  return <EChart option={option} height={height} label={label} />;
}

export function Sparkline({ data, color = C.teal, w = 120, h = 34 }: { data: number[]; color?: string; w?: number; h?: number }) {
  if (data.length < 2) return <svg width={w} height={h} aria-hidden />;
  const mn = Math.min(...data), mx = Math.max(...data);
  const pts = data.map((v, i) => [(i / (data.length - 1)) * w, h - 3 - ((v - mn) / (mx - mn || 1)) * (h - 6)]);
  const d = pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ");
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden>
      <defs><linearGradient id="spk" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor={color} stopOpacity=".35" /><stop offset="1" stopColor={color} stopOpacity="0" /></linearGradient></defs>
      <path d={`${d} L${w},${h} L0,${h} Z`} fill="url(#spk)" />
      <path d={d} fill="none" stroke={color} strokeWidth={2} style={{ filter: `drop-shadow(0 0 4px ${color})` }} />
      <circle cx={pts.at(-1)![0]} cy={pts.at(-1)![1]} r={2.6} fill={color} />
    </svg>
  );
}

export function LossChart({ history }: { history: { epoch: number; train_loss: number; val_loss: number; val_metric: number }[] }) {
  const option = {
    grid: { left: 36, right: 40, top: 54, bottom: 22 },
    tooltip: { ...tooltip, trigger: "axis", valueFormatter: (v: number) => v?.toFixed(4) },
    legend: { top: 0, left: 0, icon: "roundRect", itemWidth: 10, textStyle: { color: C.mist, fontSize: 11 } },
    xAxis: { type: "category", data: history.map((h) => h.epoch), axisLabel: { color: C.dim, fontSize: 10 }, axisLine: { lineStyle: { color: C.line } } },
    yAxis: [{ type: "value", scale: true, splitLine: { lineStyle: { color: "rgba(124,92,255,0.1)" } }, axisLabel: { color: C.dim, fontSize: 10 } },
      { type: "value", scale: true, splitLine: { show: false }, axisLabel: { color: C.dim, fontSize: 10 } }],
    series: [
      { name: "Loss entrenamiento", type: "line", itemStyle: { color: C.electric }, data: history.map((h) => h.train_loss), smooth: true, showSymbol: false, lineStyle: { color: C.electric, width: 2 } },
      { name: "Loss validación", type: "line", itemStyle: { color: C.violet }, data: history.map((h) => h.val_loss), smooth: true, showSymbol: false, lineStyle: { color: C.violet, width: 2 } },
      { name: "Métrica val.", type: "line", itemStyle: { color: C.teal }, yAxisIndex: 1, data: history.map((h) => h.val_metric), smooth: true, showSymbol: false, lineStyle: { color: C.teal, width: 2, type: "dashed" } },
    ],
  };
  return <EChart option={option} height={170} label="Curvas de pérdida y métrica de validación por época" />;
}

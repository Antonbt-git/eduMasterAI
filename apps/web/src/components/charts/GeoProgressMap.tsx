import { geoNaturalEarth1, geoPath } from "d3-geo";
import { useMemo } from "react";
import { feature } from "topojson-client";
import world from "world-atlas/countries-110m.json";
import { int } from "@/lib/format";

const ANCHORS: Record<string, [number, number]> = {
  "América del Norte": [-100, 44], "América del Sur": [-60, -16], "Europa": [14, 50], "Asia": [92, 36], "África": [20, 4], "Oceanía": [134, -25],
};
const W = 560, H = 270;

type Region = { region: string; active: number; students: number; delta_pct: number | null; avg_progress: number };

/** Mapa geográfico AGREGADO por región (nunca ubicación individual). */
export function GeoProgressMap({ regions, onSelect, selected }: { regions: Region[]; onSelect?: (r: string | undefined) => void; selected?: string }) {
  const { paths, proj } = useMemo(() => {
    const geo = feature(world as any, (world as any).objects.countries) as any;
    const proj = geoNaturalEarth1().fitExtent([[4, 4], [W - 4, H - 4]], geo);
    const gp = geoPath(proj);
    return { paths: geo.features.filter((f: any) => f.properties?.name !== "Antarctica").map((f: any) => gp(f) as string), proj };
  }, []);
  const max = Math.max(1, ...regions.map((r) => r.active));
  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={`Progreso por región: ${regions.map((r) => `${r.region} ${r.active} activos`).join(", ")}`}>
        <defs>
          <radialGradient id="geo-glow"><stop offset="0" stopColor="#FF5FD2" stopOpacity=".9" /><stop offset=".4" stopColor="#7C5CFF" stopOpacity=".35" /><stop offset="1" stopColor="#7C5CFF" stopOpacity="0" /></radialGradient>
        </defs>
        <g>{paths.map((d: string, i: number) => <path key={i} d={d} fill="#261C55" stroke="#4A3A94" strokeWidth={0.4} opacity={0.85} />)}</g>
        {regions.map((r) => {
          const [x, y] = proj(ANCHORS[r.region] ?? [0, 0])!;
          const rad = 14 + 30 * Math.sqrt(r.active / max);
          const sel = selected === r.region;
          return (
            <g key={r.region} className="cursor-pointer" onClick={() => onSelect?.(sel ? undefined : r.region)} tabIndex={0} role="button"
               aria-pressed={sel} aria-label={`Filtrar por ${r.region}`} onKeyDown={(e) => e.key === "Enter" && onSelect?.(sel ? undefined : r.region)}>
              <circle cx={x} cy={y} r={rad} fill="url(#geo-glow)" />
              <circle cx={x} cy={y} r={3.2} fill={sel ? "#FF9F43" : "#F3EEFF"} />
            </g>
          );
        })}
      </svg>
      <div className="pointer-events-none absolute inset-0">
        {regions.map((r) => {
          const [x, y] = proj(ANCHORS[r.region] ?? [0, 0])!;
          const left = Math.min(78, Math.max(0, (x / W) * 100 - 9));
          const top = Math.min(74, Math.max(0, (y / H) * 100 - 16));
          return (
            <div key={r.region} style={{ left: `${left}%`, top: `${top}%` }}
              className={`absolute rounded-lg border px-2 py-1 text-[11px] leading-tight backdrop-blur ${selected === r.region ? "border-violet/70 bg-violet/20" : "border-cyan/25 bg-ink/70"}`}>
              <div className="text-mist">{r.region}</div>
              <div className="font-display text-[14px] font-semibold tabular">{int(r.active)}</div>
              {r.delta_pct !== null && <div className={r.delta_pct >= 0 ? "text-teal" : "text-danger"}>{r.delta_pct >= 0 ? "↑" : "↓"} {Math.abs(r.delta_pct)}%</div>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

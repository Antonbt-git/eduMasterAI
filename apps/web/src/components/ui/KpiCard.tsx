import clsx from "clsx";
import { ArrowDownRight, ArrowUpRight, Info } from "lucide-react";
import { ago } from "@/lib/format";

export type Kpi = { value: number | null; delta_pct?: number | null; source: string; updated_at: string; unit?: string };

export function KpiCard({ label, kpi, format, accent = "cyan", note }: { label: string; kpi?: Kpi; format: (v: number | null) => string; accent?: "cyan" | "violet" | "teal" | "blue"; note?: string }) {
  const d = kpi?.delta_pct;
  return (
    <div className="panel-inner group relative flex min-w-0 flex-col gap-1 px-4 py-3">
      <div className="flex items-center gap-1.5 text-[13px] text-mist">
        {label}
        {kpi && (
          <span className="relative ml-auto">
            <Info className="size-3.5 text-dim" aria-hidden />
            <span role="tooltip" className="pointer-events-none absolute right-0 bottom-5 z-20 hidden w-56 rounded-lg border border-cyan/30 bg-ink/95 p-2 text-[11px] text-mist group-hover:block group-focus-within:block">
              Fuente: {kpi.source}<br />Actualizado: {ago(kpi.updated_at)}{note && <><br />{note}</>}
            </span>
          </span>
        )}
      </div>
      <div className={clsx("font-display text-[26px] leading-tight font-semibold tabular", accent === "violet" && "text-[#FFD2A8]", accent === "teal" && "text-[#9FF5D6]")}>
        {kpi ? format(kpi.value) : <span className="skeleton inline-block h-7 w-24" />}
      </div>
      <div className="flex items-center gap-1 text-[12px]">
        {d === null || d === undefined ? <span className="text-dim">Sin periodo comparable</span> : (
          <span className={clsx("inline-flex items-center gap-0.5 font-medium", d >= 0 ? "text-teal" : "text-danger")}>
            {d >= 0 ? <ArrowUpRight className="size-3.5" /> : <ArrowDownRight className="size-3.5" />}{d >= 0 ? "+" : ""}{d}%
            <span className="font-normal text-dim">vs. anterior</span>
          </span>
        )}
      </div>
    </div>
  );
}

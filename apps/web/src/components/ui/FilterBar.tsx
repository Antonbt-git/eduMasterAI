import { useQuery } from "@tanstack/react-query";
import { Download, Filter } from "lucide-react";
import { useState } from "react";
import { errorText } from "@/components/feedback/states";
import { api, download, qs } from "@/services/api";
import { usePerm } from "@/stores/auth";
import { useUI } from "@/stores/ui";
import { Button, Field, Modal } from "./primitives";

export const REGIONS = ["América del Norte", "América del Sur", "Europa", "Asia", "África", "Oceanía"];

/** Filtros globales: periodo, curso, cohorte y región. Todos los gráficos los respetan. */
export function FilterBar({ exportable = true }: { exportable?: boolean }) {
  const { filters, setFilters } = useUI();
  const courses = useQuery({ queryKey: ["courses", "all"], queryFn: () => api("/courses?page_size=100"), staleTime: 60000 });
  const cohorts = useQuery({ queryKey: ["cohorts"], queryFn: () => api<any[]>("/cohorts"), staleTime: 60000 });
  const canExport = usePerm("analytics:export");
  const [open, setOpen] = useState(false);
  return (
    <div className="mb-4 flex flex-wrap items-center gap-2" role="group" aria-label="Filtros globales">
      <Filter className="size-4 text-dim" aria-hidden />
      <select aria-label="Periodo" value={filters.period} onChange={(e) => setFilters({ period: e.target.value as any })} className="!py-1.5 text-[13px]">
        <option value="7d">Últimos 7 días</option><option value="30d">Últimos 30 días</option><option value="90d">Últimos 90 días</option><option value="365d">Último año</option>
      </select>
      <select aria-label="Curso" value={filters.course_id ?? ""} onChange={(e) => setFilters({ course_id: e.target.value || undefined })} className="max-w-56 !py-1.5 text-[13px]">
        <option value="">Todos los cursos</option>
        {courses.data?.items.map((c: any) => <option key={c.id} value={c.id}>{c.code} · {c.title}</option>)}
      </select>
      <select aria-label="Cohorte" value={filters.cohort_id ?? ""} onChange={(e) => setFilters({ cohort_id: e.target.value || undefined })} className="!py-1.5 text-[13px]">
        <option value="">Todas las cohortes</option>
        {cohorts.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
      </select>
      <select aria-label="Región" value={filters.region ?? ""} onChange={(e) => setFilters({ region: e.target.value || undefined })} className="!py-1.5 text-[13px]">
        <option value="">Todas las regiones</option>
        {REGIONS.map((r) => <option key={r}>{r}</option>)}
      </select>
      {(filters.course_id || filters.region || filters.cohort_id) && (
        <Button size="sm" variant="ghost" onClick={() => setFilters({ course_id: undefined, region: undefined, cohort_id: undefined })}>Quitar filtros</Button>
      )}
      {exportable && canExport && <Button size="sm" variant="outline" className="ml-auto" onClick={() => setOpen(true)}><Download /> Exportar</Button>}
      <ExportDialog open={open} onClose={() => setOpen(false)} />
    </div>
  );
}

export function useFilterQs() {
  const f = useUI((s) => s.filters);
  return { f, q: qs(f) };
}

export function ExportDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { q } = useFilterQs();
  const toast = useUI((s) => s.toast);
  const [report, setReport] = useState("courses");
  const [format, setFormat] = useState("xlsx");
  const [busy, setBusy] = useState(false);
  const go = async () => {
    setBusy(true);
    try {
      await download(`/analytics/export${q}${q ? "&" : "?"}report=${report}&format=${format}`, `edumaster.${format}`);
      toast("ok", "Reporte exportado. La exportación quedó registrada en auditoría.");
      onClose();
    } catch (e) { toast("error", errorText(e)); } finally { setBusy(false); }
  };
  return (
    <Modal open={open} onClose={onClose} title="Exportar reporte">
      <div className="grid gap-3">
        <Field label="Reporte"><select value={report} onChange={(e) => setReport(e.target.value)}><option value="courses">Indicadores por curso</option><option value="summary">Resumen de KPIs</option></select></Field>
        <Field label="Formato"><select value={format} onChange={(e) => setFormat(e.target.value)}><option value="xlsx">Excel (XLSX)</option><option value="csv">CSV</option><option value="pdf">PDF</option></select></Field>
        <p className="text-[12px] text-dim">Incluye fecha de generación y los filtros aplicados.</p>
        <div className="flex justify-end"><Button onClick={go} loading={busy}><Download /> Descargar</Button></div>
      </div>
    </Modal>
  );
}

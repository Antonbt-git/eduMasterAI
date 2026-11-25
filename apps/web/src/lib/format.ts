const nf = new Intl.NumberFormat("es-PE");
export const num = (v: number | null | undefined, d = 0) =>
  v === null || v === undefined || Number.isNaN(v) ? "—" : new Intl.NumberFormat("es-PE", { maximumFractionDigits: d, minimumFractionDigits: d }).format(v);
export const int = (v: number | null | undefined) => (v === null || v === undefined ? "—" : nf.format(Math.round(v)));
export const pct = (v: number | null | undefined, d = 1) => (v === null || v === undefined ? "—" : `${num(v * 100, d)}%`);

export function ago(iso?: string | null) {
  if (!iso) return "—";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 45) return "Hace un momento";
  if (s < 3600) return `Hace ${Math.round(s / 60)} min`;
  if (s < 86400) return `Hace ${Math.round(s / 3600)} h`;
  const d = Math.round(s / 86400);
  return d === 1 ? "Hace 1 día" : `Hace ${d} días`;
}
export const date = (iso?: string | null) => (iso ? new Date(iso).toLocaleDateString("es-PE", { day: "2-digit", month: "short", year: "numeric" }) : "—");
export const time = (iso?: string | null) => (iso ? new Date(iso).toLocaleTimeString("es-PE", { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "—");

export const LEVEL_ES: Record<string, string> = { basico: "Básico", intermedio: "Intermedio", avanzado: "Avanzado" };
export const STATUS_ES: Record<string, string> = {
  draft: "Borrador", published: "Publicado", archived: "Archivado", in_progress: "En progreso", completed: "Completado", not_started: "No iniciado",
  dropped: "Retirado", new: "Nueva", accepted: "Aceptada", dismissed: "Descartada", expired: "Expirada", issued: "Emitido", revoked: "Anulado",
  queued: "En cola", loading_data: "Cargando datos", training: "Entrenando", validating: "Validando", failed: "Error", graded: "Calificado",
  submitted: "Entregado", pending: "Pendiente", approved: "Aprobado", rejected: "Rechazado", production: "Producción", staging: "Staging",
  experimental: "Experimental", building: "Construyendo", ready: "Listo",
};
export const ROLE_ES: Record<string, string> = {
  superadmin: "Superadministrador", admin: "Administrador", coordinator: "Coordinador", instructor: "Docente", student: "Estudiante",
  analyst: "Analista de datos", ml_engineer: "ML Engineer", auditor: "Auditor",
};

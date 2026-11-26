import { useAuth } from "@/stores/auth";

export const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? "/api/v1";

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public details?: unknown, public correlationId?: string) {
    super(message);
  }
}

let refreshing: Promise<boolean> | null = null;

async function refresh(): Promise<boolean> {
  const { refreshToken, setTokens, logout } = useAuth.getState();
  if (!refreshToken) return false;
  const r = await fetch(`${API_BASE}/auth/refresh`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ refresh_token: refreshToken }) });
  if (!r.ok) {
    logout();
    return false;
  }
  const t = await r.json();
  setTokens(t.access_token, t.refresh_token);
  return true;
}

type Opts = { method?: string; body?: unknown; raw?: boolean; headers?: Record<string, string>; form?: FormData };

export async function api<T = any>(path: string, opts: Opts = {}, retry = true): Promise<T> {
  const token = useAuth.getState().accessToken;
  const headers: Record<string, string> = { ...(opts.headers ?? {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";
  const doFetch = () => fetch(`${API_BASE}${path}`, {
    method: opts.method ?? (opts.body !== undefined || opts.form ? "POST" : "GET"),
    headers,
    body: opts.form ?? (opts.body !== undefined ? JSON.stringify(opts.body) : undefined),
  });
  let res = await doFetch();
  // Reintentos con backoff ante saturación del proxy (429) o servicio temporalmente no disponible (503).
  for (let attempt = 0; attempt < 3 && (res.status === 429 || res.status === 503); attempt++) {
    await new Promise((r) => setTimeout(r, 400 * 2 ** attempt + Math.random() * 300));
    res = await doFetch();
  }
  if (res.status === 401 && retry && token) {
    refreshing ??= refresh().finally(() => (refreshing = null));
    if (await refreshing) return api<T>(path, opts, false);
  }
  if (!res.ok) {
    let body: any = {};
    try { body = await res.json(); } catch { /* sin cuerpo */ }
    throw new ApiError(res.status, body.code ?? "error", body.message ?? `Error ${res.status}`, body.details, body.correlation_id);
  }
  if (opts.raw) return res as unknown as T;
  if (res.status === 204) return undefined as T;
  return res.json();
}

export async function download(path: string, fallbackName: string) {
  const res = await api<Response>(path, { raw: true });
  const blob = await res.blob();
  const cd = res.headers.get("Content-Disposition") ?? "";
  const name = /filename=([^;]+)/.exec(cd)?.[1] ?? fallbackName;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

export function qs(params: Record<string, unknown>) {
  const s = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => v !== undefined && v !== null && v !== "" && s.set(k, String(v)));
  const out = s.toString();
  return out ? `?${out}` : "";
}

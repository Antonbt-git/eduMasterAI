import { useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import {
  Award, BarChart3, Bell, Bot, BrainCircuit, ClipboardCheck, Gauge, Home, LogOut, Map as MapIcon, Menu, PlayCircle, Search, Settings,
  ShieldCheck, Sparkles, Users, Activity as ActivityIcon, X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { Sparkline } from "@/components/charts/charts";
import { Toaster } from "@/components/feedback/states";
import { Avatar } from "@/components/ui/primitives";
import { ago, int, pct, ROLE_ES, time } from "@/lib/format";
import { api } from "@/services/api";
import { connectRealtime, onEvent } from "@/services/realtime";
import { useAuth } from "@/stores/auth";
import { useUI } from "@/stores/ui";

const NAV = [
  { to: "/", label: "Resumen", icon: Home, perm: null, end: true },
  { to: "/rutas", label: "Planes de aprendizaje", icon: MapIcon, perm: "paths:read" },
  { to: "/cursos", label: "Cursos", icon: PlayCircle, perm: "courses:read" },
  { to: "/analisis", label: "Análisis", icon: BarChart3, perm: "analytics:read" },
  { to: "/tutor", label: "IA Tutor", icon: Bot, perm: null },
  { to: "/evaluaciones", label: "Evaluaciones", icon: ClipboardCheck, perm: "assessments:read" },
  { to: "/certificados", label: "Certificados", icon: Award, perm: "certificates:read" },
  { to: "/comunidad", label: "Comunidad", icon: Users, perm: "community:read" },
  { to: "/habilidades", label: "Dominio de habilidades", icon: Gauge, perm: "analytics:read" },
  { to: "/redes", label: "Redes neuronales", icon: BrainCircuit, perm: "ml:read" },
  { to: "/recomendaciones", label: "Recomendaciones IA", icon: Sparkles, perm: "recommendations:read" },
  { to: "/actividad", label: "Actividad", icon: ActivityIcon, perm: null },
  { to: "/administracion", label: "Administración", icon: ShieldCheck, perm: ["users:read", "audit:read", "datasets:read"] },
  { to: "/configuracion", label: "Configuración", icon: Settings, perm: null },
];

/** Invalida caché del servidor según eventos de dominio (actualización sin recargar). */
function useRealtimeSync() {
  const qc = useQueryClient();
  const toast = useUI((s) => s.toast);
  useEffect(() => {
    const stop = connectRealtime();
    let t: number | undefined;
    const debounced = (keys: string[][]) => {
      clearTimeout(t);
      t = window.setTimeout(() => keys.forEach((k) => qc.invalidateQueries({ queryKey: k })), 900);
    };
    const offs = [
      onEvent("learning.progress.updated", () => debounced([["dashboard"], ["analytics"]])),
      onEvent("assessment.submitted", () => debounced([["dashboard"], ["assessments"]])),
      onEvent("course.completed", () => debounced([["dashboard"], ["analytics"], ["certificates"]])),
      onEvent("activity.created", () => qc.invalidateQueries({ queryKey: ["activity"] })),
      onEvent("recommendation.created", () => qc.invalidateQueries({ queryKey: ["recommendations"] })),
      onEvent("certificate.issued", () => qc.invalidateQueries({ queryKey: ["certificates"] })),
      onEvent("community.posted", () => qc.invalidateQueries({ queryKey: ["community"] })),
      onEvent("dataset.updated", () => qc.invalidateQueries({ queryKey: ["ml", "datasets"] })),
      onEvent("model.training.completed", (e) => { qc.invalidateQueries({ queryKey: ["ml"] }); toast("ok", `${e.payload.network_key}: versión ${e.payload.version} registrada`); }),
      onEvent("model.deployed", (e) => { qc.invalidateQueries({ queryKey: ["ml"] }); qc.invalidateQueries({ queryKey: ["dashboard"] }); toast("info", `${e.payload.network_key} v${e.payload.version} en producción`); }),
      onEvent("notification.created", (e) => { qc.invalidateQueries({ queryKey: ["notifications"] }); toast("info", e.payload.title); }),
    ];
    return () => { stop(); offs.forEach((f) => f()); clearTimeout(t); };
  }, [qc, toast]);
}

export function AppShell() {
  const me = useAuth((s) => s.me)!;
  const { sidebarOpen, toggleSidebar } = useUI();
  useRealtimeSync();
  const perms = me.permissions;
  const items = NAV.filter((n) => !n.perm || (Array.isArray(n.perm) ? n.perm.some((p) => perms.includes(p)) : perms.includes(n.perm)));
  return (
    <div className="flex min-h-full">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:p-2">Saltar al contenido</a>
      <aside className={clsx("fixed inset-y-0 left-0 z-40 flex w-[248px] flex-col gap-3 p-3 transition-transform lg:sticky lg:top-0 lg:h-screen lg:translate-x-0",
        sidebarOpen ? "translate-x-0" : "-translate-x-full")}>
        <div className="panel flex min-h-0 flex-1 flex-col p-3">
          <div className="flex items-center gap-2.5 px-2 pt-1 pb-4">
            <img src="/favicon.svg" alt="" className="size-9" />
            <span className="font-display text-[19px] font-semibold">EduMaster<span className="text-[12px] font-medium text-cyan">.ai</span></span>
            <button className="ml-auto lg:hidden" onClick={() => toggleSidebar(false)} aria-label="Cerrar menú"><X className="size-5" /></button>
          </div>
          <nav aria-label="Principal" className="-mx-1 flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto px-1">
            {items.map(({ to, label, icon: Icon, end }) => (
              <NavLink key={to} to={to} end={end} onClick={() => toggleSidebar(false)}
                className={({ isActive }) => clsx("flex items-center gap-3 rounded-[10px] px-3 py-2 text-[14px] transition-colors",
                  isActive ? "bg-gradient-to-r from-electric to-[#5B3FE0] font-medium text-white shadow-[0_0_22px_-6px_#7C5CFF]" : "text-[#D8CFF0] hover:bg-white/5 hover:text-white")}>
                <Icon className="size-[18px] shrink-0" />{label}
              </NavLink>
            ))}
          </nav>
        </div>
        <ModelQualityCard />
        <OnlineCard />
      </aside>
      {sidebarOpen && <div className="fixed inset-0 z-30 bg-black/50 lg:hidden" onClick={() => toggleSidebar(false)} />}
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        <main id="main" className="min-w-0 flex-1 px-3 pb-8 sm:px-5"><Outlet /></main>
      </div>
      <Toaster />
    </div>
  );
}

function ModelQualityCard() {
  const q = useQuery({ queryKey: ["dashboard", "summary", "sidebar"], queryFn: () => api("/dashboard/summary"), enabled: useAuth.getState().me?.permissions.includes("analytics:read") });
  const mq = q.data?.kpis?.model_quality;
  if (!mq) return null;
  const v = mq.value ?? 0;
  return (
    <div className="panel hidden items-center gap-3 p-3 lg:[@media(min-height:940px)]:flex" title={`Fuente: ${mq.source}`}>
      <svg viewBox="0 0 48 48" className="size-14 -rotate-90" aria-hidden>
        <circle cx="24" cy="24" r="20" fill="none" stroke="rgba(124,92,255,.15)" strokeWidth="5" />
        <circle cx="24" cy="24" r="20" fill="none" stroke="url(#mq)" strokeWidth="5" strokeLinecap="round" strokeDasharray={`${v * 125.6} 200`} />
        <defs><linearGradient id="mq"><stop offset="0" stopColor="#FF5FD2" /><stop offset="1" stopColor="#FF9F43" /></linearGradient></defs>
      </svg>
      <div className="min-w-0">
        <div className="text-[12px] text-mist">Calidad del modelo</div>
        <div className="font-display text-xl font-semibold tabular">{mq.value !== null ? pct(mq.value) : "—"}</div>
        <div className="truncate text-[11px] text-dim">{mq.network ? `${mq.metric ?? ""} · v${mq.version} · DEMO` : mq.source}</div>
      </div>
    </div>
  );
}

function OnlineCard() {
  const q = useQuery({ queryKey: ["users", "online"], queryFn: () => api("/students?limit=4"), retry: false, enabled: useAuth.getState().me?.permissions.includes("users:read") });
  const d = useQuery({ queryKey: ["dashboard", "summary", "sidebar"], queryFn: () => api("/dashboard/summary"), enabled: false });
  if (!q.data) return null;
  return (
    <div className="panel hidden p-3 lg:[@media(min-height:1040px)]:block">
      <div className="mb-2 font-display text-[14px] font-semibold">Nuestros alumnos</div>
      <div className="flex -space-x-2">{q.data.items.map((s: any) => <Avatar key={s.id} src={s.avatar_url} name={s.name} size={36} />)}</div>
      <div className="mt-2 flex items-center gap-1.5 text-[12px] text-mist"><span className="live-dot size-2 rounded-full bg-teal" />{int(d.data?.kpis?.online_now?.value ?? 0)} en línea (últimos 15 min)</div>
    </div>
  );
}

function Topbar() {
  const me = useAuth((s) => s.me)!;
  const logout = useAuth((s) => s.logout);
  const { rt, lastEventAt, toggleSidebar } = useUI();
  const nav = useNavigate();
  const [term, setTerm] = useState("");
  const sum = useQuery({ queryKey: ["dashboard", "summary", "sidebar"], queryFn: () => api("/dashboard/summary"), enabled: me.permissions.includes("analytics:read") });
  const gs = sum.data?.kpis?.global_score;
  return (
    <header className="sticky top-0 z-20 flex flex-wrap items-center gap-3 bg-ink/70 px-3 py-3 backdrop-blur sm:px-5">
      <button className="rounded-lg p-2 text-mist hover:text-frost lg:hidden" onClick={() => toggleSidebar(true)} aria-label="Abrir menú"><Menu className="size-5" /></button>
      <p className="hidden font-display text-[15px] font-medium text-[#E4DCF7] md:block">Aprende • Practica • Destaca</p>
      <ConnectionChip rt={rt} last={lastEventAt} />
      <div className="ml-auto flex items-center gap-2">
        {gs && gs.value !== null && (
          <div className="panel hidden items-center gap-3 px-3 py-1.5 2xl:flex" title={`Fuente: ${gs.source}`}>
            <div><div className="text-[11px] text-mist">Puntuación global</div><div className="font-display text-[17px] font-semibold tabular">{pct(gs.value)}</div></div>
            <Sparkline data={gs.spark} />
          </div>
        )}
        <form className="relative hidden sm:block" onSubmit={(e) => { e.preventDefault(); nav(`/cursos?q=${encodeURIComponent(term)}`); }} role="search">
          <Search className="pointer-events-none absolute top-2.5 left-3 size-4 text-dim" />
          <input value={term} onChange={(e) => setTerm(e.target.value)} placeholder="Buscar cursos" aria-label="Buscar cursos" className="w-48 !pl-9 lg:w-56" />
        </form>
        <NotificationBell />
        <div className="flex items-center gap-2.5 pl-1">
          <Avatar src={me.avatar_url} name={me.full_name} size={38} />
          <div className="hidden leading-tight md:block">
            <div className="text-[13px] font-semibold">{me.full_name}</div>
            <div className="text-[11px] text-mist">{me.roles.map((r) => ROLE_ES[r] ?? r).join(", ")}</div>
          </div>
          <button onClick={async () => { try { await api("/auth/logout", { method: "POST" }); } finally { logout(); nav("/login"); } }}
            className="rounded-lg p-2 text-mist hover:text-frost" aria-label="Cerrar sesión" title="Cerrar sesión"><LogOut className="size-4" /></button>
        </div>
      </div>
    </header>
  );
}

function ConnectionChip({ rt, last }: { rt: string; last: string | null }) {
  const [, force] = useState(0);
  useEffect(() => { const i = setInterval(() => force((x) => x + 1), 10000); return () => clearInterval(i); }, []);
  const label = rt === "live" ? "En vivo" : rt === "connecting" ? "Conectando" : "Sin conexión";
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-line/70 bg-surface/60 px-3 py-1 text-[12px]" role="status"
      title={last ? `Último evento: ${time(last)}` : "Sin eventos recibidos todavía"}>
      <span className={clsx("size-2 rounded-full", rt === "live" ? "live-dot bg-teal" : rt === "connecting" ? "bg-warn" : "bg-danger")} />
      <span className={rt === "live" ? "text-teal" : "text-mist"}>{label}</span>
      <span className="hidden text-dim sm:inline">· último evento {last ? ago(last).toLowerCase() : "—"}</span>
    </span>
  );
}

function NotificationBell() {
  const [open, setOpen] = useState(false);
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["notifications"], queryFn: () => api("/notifications?limit=12") });
  const unread = q.data?.unread ?? 0;
  const markAll = async () => { await api("/notifications/read-all", { method: "POST" }); qc.invalidateQueries({ queryKey: ["notifications"] }); };
  return (
    <div className="relative">
      <button onClick={() => setOpen((o) => !o)} className="panel relative grid size-10 place-items-center !rounded-[10px]" aria-label={`Notificaciones: ${unread} sin leer`} aria-expanded={open}>
        <Bell className="size-[18px]" />
        {unread > 0 && <span className="absolute -top-1 -right-1 grid h-4 min-w-4 place-items-center rounded-full bg-violet px-1 text-[10px] font-semibold">{unread > 99 ? "99+" : unread}</span>}
      </button>
      {open && (
        <div className="panel panel-glow absolute right-0 z-30 mt-2 w-[340px] p-2">
          <div className="flex items-center px-2 py-1"><span className="font-display font-semibold">Notificaciones</span>
            <button onClick={markAll} className="ml-auto text-[12px] text-cyan hover:underline">Marcar todas como leídas</button></div>
          <ul className="max-h-[360px] overflow-auto">
            {q.data?.items.length === 0 && <li className="px-2 py-6 text-center text-[13px] text-mist">No tienes notificaciones.</li>}
            {q.data?.items.map((n: any) => (
              <li key={n.id}>
                <a href={n.link ?? "#"} onClick={() => api(`/notifications/${n.id}/read`, { method: "POST" }).then(() => qc.invalidateQueries({ queryKey: ["notifications"] }))}
                  className={clsx("block rounded-lg px-2 py-2 hover:bg-white/5", !n.read && "bg-electric/10")}>
                  <div className="text-[13px] font-medium">{n.title}</div>
                  {n.body && <div className="text-[12px] text-mist">{n.body}</div>}
                  <div className="text-[11px] text-dim">{ago(n.created_at)}</div>
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}


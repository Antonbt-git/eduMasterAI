import clsx from "clsx";
import { X } from "lucide-react";
import { type ButtonHTMLAttributes, type ReactNode, useEffect, useRef, useState } from "react";
import { useAuth } from "@/stores/auth";
import { STATUS_ES } from "@/lib/format";

export function Panel({ title, icon, actions, children, className, glow, live, bodyClass, id }: {
  title?: ReactNode; icon?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string; glow?: boolean; live?: ReactNode; bodyClass?: string; id?: string;
}) {
  return (
    <section className={clsx("panel flex min-w-0 flex-col", glow && "panel-glow", className)} aria-labelledby={id}>
      {(title || actions) && (
        <header className="flex flex-wrap items-center gap-x-3 gap-y-1 px-4 pt-4 pb-3 sm:px-5">
          {icon && <span className="text-cyan [&>svg]:size-[18px]">{icon}</span>}
          <h2 id={id} className="font-display text-[15px] font-semibold text-frost">{title}</h2>
          {live}
          <div className="ml-auto flex items-center gap-2">{actions}</div>
        </header>
      )}
      <div className={clsx("min-h-0 min-w-0 flex-1 px-4 pb-5 sm:px-5", bodyClass)}>{children}</div>
    </section>
  );
}

type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" | "outline" | "danger" | "violet"; size?: "sm" | "md"; loading?: boolean };
export function Button({ variant = "primary", size = "md", loading, className, children, disabled, ...rest }: BtnProps) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={clsx(
        "inline-flex items-center justify-center gap-2 rounded-[10px] font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 [&>svg]:size-4",
        size === "sm" ? "h-8 px-3 text-[13px]" : "h-10 px-4 text-sm",
        variant === "primary" && "bg-electric text-ink hover:bg-[#9177FF] shadow-[0_0_20px_-6px_#7C5CFF]",
        variant === "violet" && "bg-violet text-white hover:bg-[#FFB06A] shadow-[0_0_20px_-6px_#FF9F43]",
        variant === "ghost" && "text-mist hover:bg-white/5 hover:text-frost",
        variant === "outline" && "border border-line text-frost hover:border-cyan/60 hover:bg-cyan/5",
        variant === "danger" && "bg-danger/90 text-white hover:bg-danger",
        className,
      )}
    >
      {loading && <span className="size-3.5 animate-spin rounded-full border-2 border-white/30 border-t-white" aria-hidden />}
      {children}
    </button>
  );
}

const TONES: Record<string, string> = {
  cyan: "bg-cyan/10 text-cyan border-cyan/30", violet: "bg-violet/15 text-[#FFC48A] border-violet/40", teal: "bg-teal/10 text-teal border-teal/30",
  blue: "bg-electric/15 text-[#A996FF] border-electric/40", danger: "bg-danger/10 text-danger border-danger/30", warn: "bg-warn/10 text-warn border-warn/30",
  muted: "bg-white/5 text-mist border-white/10",
};
export function Badge({ tone = "muted", children, className }: { tone?: keyof typeof TONES | string; children: ReactNode; className?: string }) {
  return <span className={clsx("inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium whitespace-nowrap", TONES[tone] ?? TONES.muted, className)}>{children}</span>;
}

const STATUS_TONE: Record<string, string> = {
  published: "teal", completed: "teal", issued: "teal", approved: "teal", production: "teal", accepted: "teal", ready: "teal", graded: "teal",
  in_progress: "blue", training: "violet", validating: "violet", loading_data: "cyan", queued: "cyan", staging: "cyan", new: "cyan", building: "cyan",
  draft: "muted", not_started: "muted", archived: "muted", expired: "muted", experimental: "violet", submitted: "warn", pending: "warn",
  failed: "danger", revoked: "danger", rejected: "danger", dismissed: "muted", dropped: "danger",
};
export const StatusBadge = ({ status }: { status: string }) => <Badge tone={STATUS_TONE[status] ?? "muted"}>{STATUS_ES[status] ?? status}</Badge>;

export const DemoBadge = ({ title = "Dato de demostración: sintético y rotulado" }: { title?: string }) => (
  <span title={title} className="rounded border border-warn/40 bg-warn/10 px-1.5 py-px text-[10px] font-semibold tracking-wide text-warn">DEMO</span>
);

export function Avatar({ src, name, size = 32 }: { src?: string | null; name: string; size?: number }) {
  const [failed, setFailed] = useState(false);
  const initials = name.split(" ").filter(Boolean).slice(0, 2).map((p) => p[0]).join("");
  return src && !failed ? (
    <img src={src} alt="" width={size} height={size} loading="lazy" onError={() => setFailed(true)} className="shrink-0 rounded-full bg-surface-2 ring-2 ring-cyan/30" style={{ width: size, height: size }} />
  ) : (
    <span className="grid shrink-0 place-items-center rounded-full bg-gradient-to-br from-electric to-violet font-semibold text-white" style={{ width: size, height: size, fontSize: size * 0.38 }}>{initials}</span>
  );
}

export function Progress({ value, tone = "cyan", className }: { value: number; tone?: "cyan" | "violet" | "teal"; className?: string }) {
  const col = { cyan: "from-electric to-cyan", violet: "from-electric to-violet", teal: "from-cyan to-teal" }[tone];
  return (
    <div className={clsx("h-1.5 w-full overflow-hidden rounded-full bg-white/8", className)} role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(value * 100)}>
      <div className={clsx("h-full rounded-full bg-gradient-to-r transition-[width] duration-700", col)} style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%` }} />
    </div>
  );
}

export function Modal({ open, onClose, title, children, wide }: { open: boolean; onClose: () => void; title: string; children: ReactNode; wide?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    ref.current?.querySelector<HTMLElement>("input,select,textarea,button")?.focus();
    return () => window.removeEventListener("keydown", k);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-[#07050F]/75 p-4 backdrop-blur-sm" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div ref={ref} role="dialog" aria-modal="true" aria-label={title} className={clsx("panel panel-glow max-h-[90vh] w-full overflow-auto", wide ? "max-w-3xl" : "max-w-lg")}>
        <header className="flex items-center px-5 pt-4 pb-2">
          <h2 className="font-display text-lg font-semibold">{title}</h2>
          <button onClick={onClose} className="ml-auto rounded-md p-1 text-mist hover:text-frost" aria-label="Cerrar"><X className="size-5" /></button>
        </header>
        <div className="px-5 pb-5">{children}</div>
      </div>
    </div>
  );
}

export function Field({ label, error, children, hint }: { label: string; error?: string; hint?: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5 text-[13px]">
      <span className="text-mist">{label}</span>
      {children}
      {hint && !error && <span className="text-[12px] text-dim">{hint}</span>}
      {error && <span className="text-[12px] text-danger">{error}</span>}
    </label>
  );
}

export function Tabs<T extends string>({ value, onChange, items }: { value: T; onChange: (v: T) => void; items: { value: T; label: ReactNode }[] }) {
  return (
    <div role="tablist" className="inline-flex rounded-[10px] border border-line/70 bg-ink/50 p-0.5">
      {items.map((i) => (
        <button key={i.value} role="tab" aria-selected={value === i.value} onClick={() => onChange(i.value)}
          className={clsx("rounded-lg px-3 py-1.5 text-[13px] transition-colors", value === i.value ? "bg-electric/25 text-frost" : "text-mist hover:text-frost")}>
          {i.label}
        </button>
      ))}
    </div>
  );
}

/** Ocultar en UI es solo comodidad: la autorización real ocurre en el backend. */
export function PermissionGate({ perm, children, fallback = null }: { perm: string | string[]; children: ReactNode; fallback?: ReactNode }) {
  const perms = useAuth((s) => s.me?.permissions ?? []);
  const need = Array.isArray(perm) ? perm : [perm];
  return <>{need.some((p) => perms.includes(p)) ? children : fallback}</>;
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end gap-3">
      <div className="min-w-0">
        <h1 className="font-display text-2xl font-semibold text-frost">{title}</h1>
        {subtitle && <p className="mt-1 max-w-3xl text-mist">{subtitle}</p>}
      </div>
      <div className="ml-auto flex flex-wrap items-center gap-2">{actions}</div>
    </div>
  );
}

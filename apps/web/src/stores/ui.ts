import { create } from "zustand";

export type Filters = { period: "7d" | "30d" | "90d" | "365d"; course_id?: string; region?: string; cohort_id?: string };
export type RtStatus = "connecting" | "live" | "offline";
export type Toast = { id: number; kind: "ok" | "error" | "info"; text: string };

type UI = {
  filters: Filters;
  setFilters: (f: Partial<Filters>) => void;
  rt: RtStatus;
  lastEventAt: string | null;
  setRt: (s: RtStatus) => void;
  touch: () => void;
  sidebarOpen: boolean;
  toggleSidebar: (v?: boolean) => void;
  toasts: Toast[];
  toast: (kind: Toast["kind"], text: string) => void;
  dismiss: (id: number) => void;
};

let tid = 0;
export const useUI = create<UI>((set) => ({
  filters: { period: "30d" },
  setFilters: (f) => set((s) => ({ filters: { ...s.filters, ...f } })),
  rt: "connecting",
  lastEventAt: null,
  setRt: (rt) => set({ rt }),
  touch: () => set({ lastEventAt: new Date().toISOString() }),
  sidebarOpen: false,
  toggleSidebar: (v) => set((s) => ({ sidebarOpen: v ?? !s.sidebarOpen })),
  toasts: [],
  toast: (kind, text) => {
    const id = ++tid;
    set((s) => ({ toasts: [...s.toasts, { id, kind, text }] }));
    setTimeout(() => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })), 4200);
  },
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));

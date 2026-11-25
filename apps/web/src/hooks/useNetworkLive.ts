import { useEffect, useState } from "react";
import { onEvent } from "@/services/realtime";
import type { VizMode } from "@/modules/neural-visualizer/NeuralNetworkCanvas";

export type LiveState = {
  status: string | null;
  epoch?: number;
  epochs?: number;
  train_loss?: number;
  val_loss?: number;
  val_metric?: number;
  message?: string;
  history: { epoch: number; train_loss: number; val_loss: number; val_metric: number }[];
  gradNorms?: Record<string, number>;
  activations?: Record<string, number[]>;
  latency?: number;
  pulseKey: number;
  backKey: number;
  lastInferenceAt?: string;
};

/** Estado real de una red alimentado por eventos SSE (entrenamiento e inferencia). */
export function useNetworkLive(key: string, initial?: { runId?: string; status?: string; history?: any[]; progress?: any }) {
  const [s, set] = useState<LiveState>({ status: initial?.status ?? null, history: initial?.history ?? [], pulseKey: 0, backKey: 0, ...(initial?.progress ?? {}) });

  // Al cambiar de ejecución (otra red o nuevo run) se toma el estado persistido; luego mandan los eventos SSE.
  useEffect(() => {
    set((p) => ({ ...p, status: initial?.status ?? p.status, history: initial?.history ?? [] }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, initial?.runId]);

  useEffect(() => {
    const offs = [
      onEvent("model.training.started", (e) => e.payload.network_key === key && set((p) => ({ ...p, status: "queued", history: [], message: "En cola" }))),
      onEvent("model.training.progress", (e) => {
        if (e.payload.network_key !== key) return;
        const d = e.payload;
        set((p) => ({
          ...p, status: d.status, epoch: d.epoch ?? p.epoch, epochs: d.epochs ?? p.epochs, train_loss: d.train_loss ?? p.train_loss,
          val_loss: d.val_loss ?? p.val_loss, val_metric: d.val_metric ?? p.val_metric, message: d.message ?? p.message,
          gradNorms: d.grad_norms ?? p.gradNorms,
          history: d.train_loss !== undefined && d.epoch !== undefined
            ? [...p.history.filter((h) => h.epoch < d.epoch), { epoch: d.epoch, train_loss: d.train_loss, val_loss: d.val_loss, val_metric: d.val_metric }] : p.history,
          backKey: d.grad_norms ? p.backKey + 1 : p.backKey,
          pulseKey: d.grad_norms ? p.pulseKey + 1 : p.pulseKey,
        }));
      }),
      onEvent("model.training.completed", (e) => e.payload.network_key === key && set((p) => ({ ...p, status: "completed", message: `Versión ${e.payload.version} registrada` }))),
      onEvent("model.training.failed", (e) => e.payload.network_key === key && set((p) => ({ ...p, status: "failed", message: e.payload.error }))),
      onEvent("model.inference", (e) => {
        if (e.payload.network_key !== key) return;
        set((p) => ({ ...p, activations: e.payload.activations, latency: e.payload.latency_ms, pulseKey: p.pulseKey + 1, lastInferenceAt: e.occurred_at }));
      }),
    ];
    return () => offs.forEach((f) => f());
  }, [key]);

  const training = ["queued", "loading_data", "training", "validating"].includes(s.status ?? "");
  return { ...s, training, setActivations: (a: Record<string, number[]>, latency?: number) => set((p) => ({ ...p, activations: a, latency, pulseKey: p.pulseKey + 1 })) };
}

export function vizMode(live: { training: boolean; status: string | null }, demo: boolean, hasActivations: boolean): VizMode {
  if (live.training) return "training";
  if (live.status === "failed") return "error";
  if (demo) return "demo";
  return hasActivations ? "inference" : "idle";
}

export const STATE_LABEL: Record<string, string> = {
  idle: "Detenido", training: "Entrenando", inference: "Inferencia activa", demo: "Simulación de muestra", error: "Error",
};

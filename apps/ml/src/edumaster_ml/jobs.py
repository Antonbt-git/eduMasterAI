"""Trabajos asíncronos ejecutados por el worker (RQ). Nunca en el hilo HTTP.

Cada progreso se reporta a la API por un endpoint interno autenticado; la API
persiste el estado y publica el evento de dominio vía Outbox → SSE.
"""
from __future__ import annotations

import time
import traceback

import httpx

from .config import settings
from .datasets.pipeline import build_dataset
from .training.trainer import train_network


def _post(path: str, payload: dict, retries: int = 3) -> None:
    url = f"{settings.api_internal_url}/api/v1/internal/ml{path}"
    for i in range(retries):
        try:
            r = httpx.post(url, json=payload, headers={"X-Internal-Token": settings.internal_token}, timeout=10)
            r.raise_for_status()
            return
        except Exception as exc:  # reintento con backoff
            if i == retries - 1:
                print(f"[jobs] no se pudo reportar a la API: {exc}")
            time.sleep(0.5 * (2 ** i))


def train_job(run_id: str, network_key: str, params: dict | None = None) -> dict:
    last = {"t": 0.0}

    def progress(ev: dict) -> None:
        # Limitar a ~4 eventos/s para no saturar el canal realtime
        now = time.time()
        if ev.get("phase") == "training" and "epoch" in ev and now - last["t"] < 0.25:
            time.sleep(0.25 - (now - last["t"]))
        last["t"] = time.time()
        _post(f"/training-runs/{run_id}/events", {"type": "progress", **ev})

    try:
        meta = train_network(network_key, params, progress=progress, run_id=run_id)
        summary = {k: meta[k] for k in ("key", "version", "primary", "baseline_primary", "beats_baseline", "checksum", "params_total", "temperature", "duration_s")}
        summary["metrics"] = meta["metrics"]
        summary["baseline"] = meta["baseline"]
        summary["dataset"] = meta["dataset"]
        _post(f"/training-runs/{run_id}/events", {"type": "completed", **summary})
        return summary
    except Exception as exc:
        _post(f"/training-runs/{run_id}/events", {"type": "failed", "error": str(exc)[:500], "trace": traceback.format_exc()[-1500:]})
        raise


def build_dataset_job(dataset_id: str, version: str, seed: int | None = None) -> dict:
    try:
        m = build_dataset(version, seed=seed, progress=lambda i, msg: _post(f"/datasets/{dataset_id}/events", {"type": "progress", "step": i, "message": msg}))
        _post(f"/datasets/{dataset_id}/events", {"type": "completed", "manifest": m})
        return {"version": m["version"], "checksum": m["checksum"]}
    except Exception as exc:
        _post(f"/datasets/{dataset_id}/events", {"type": "failed", "error": str(exc)[:500]})
        raise

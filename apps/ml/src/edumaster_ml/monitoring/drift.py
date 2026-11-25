"""Monitoreo de drift de features (PSI) y distribución de scores."""
from __future__ import annotations

import numpy as np


def psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    """Population Stability Index. <0.1 estable · 0.1–0.25 moderado · >0.25 drift significativo."""
    q = np.unique(np.quantile(expected, np.linspace(0, 1, bins + 1)))
    if len(q) < 3:
        return 0.0
    e = np.histogram(expected, q)[0] / len(expected)
    a = np.histogram(np.clip(actual, q[0], q[-1]), q)[0] / max(1, len(actual))
    e, a = np.clip(e, 1e-4, None), np.clip(a, 1e-4, None)
    return float(np.sum((a - e) * np.log(a / e)))


def drift_report(reference: np.ndarray, current: np.ndarray, names: list[str]) -> list[dict]:
    out = []
    for i, n in enumerate(names):
        v = psi(reference[:, i], current[:, i])
        out.append({"feature": n, "psi": round(v, 4), "status": "estable" if v < 0.1 else "moderado" if v < 0.25 else "drift"})
    return out

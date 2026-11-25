"""Métricas por tarea (documento maestro §9.5)."""
from __future__ import annotations

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def _safe(fn, *a, **k):
    try:
        return float(fn(*a, **k))
    except ValueError:
        return float("nan")


def ece(y: np.ndarray, p: np.ndarray, bins: int = 10) -> float:
    edges = np.linspace(0, 1, bins + 1)
    e = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (p >= lo) & (p < hi if hi < 1 else p <= hi)
        if m.any():
            e += m.mean() * abs(y[m].mean() - p[m].mean())
    return float(e)


def binary_metrics(y: np.ndarray, p: np.ndarray, threshold: float = 0.5) -> dict:
    yhat = (p >= threshold).astype(int)
    return {
        "roc_auc": _safe(roc_auc_score, y, p),
        "pr_auc": _safe(average_precision_score, y, p),
        "f1": _safe(f1_score, y, yhat, zero_division=0),
        "recall": _safe(recall_score, y, yhat, zero_division=0),
        "precision": _safe(precision_score, y, yhat, zero_division=0),
        "brier": _safe(brier_score_loss, y, p),
        "ece": ece(y, p),
        "false_positive_rate": float(((yhat == 1) & (y == 0)).sum() / max(1, (y == 0).sum())),
        "prevalence": float(y.mean()),
    }


def ordinal_metrics(y: np.ndarray, probs: np.ndarray, mask: np.ndarray | None = None) -> dict:
    if mask is not None:
        y, probs = y[mask > 0], probs[mask > 0]
    yhat = probs.argmax(1)
    return {
        "macro_f1": _safe(f1_score, y, yhat, average="macro", zero_division=0),
        "balanced_accuracy": _safe(balanced_accuracy_score, y, yhat),
        "mae_ordinal": float(np.abs(y - yhat).mean()),
        "confusion_matrix": confusion_matrix(y, yhat, labels=list(range(probs.shape[1]))).tolist(),
    }


def ndcg_at_k(rel: np.ndarray, scores: np.ndarray, k: int = 5) -> float:
    order = np.argsort(-scores, axis=1)[:, :k]
    gains = np.take_along_axis(rel, order, 1)
    disc = 1 / np.log2(np.arange(2, k + 2))
    dcg = ((2 ** gains - 1) * disc).sum(1)
    ideal = np.sort(rel, 1)[:, ::-1][:, :k]
    idcg = ((2 ** ideal - 1) * disc).sum(1)
    return float(np.mean(np.where(idcg > 0, dcg / np.maximum(idcg, 1e-9), 0)))


def ranking_metrics(rel: np.ndarray, scores: np.ndarray, k: int = 5) -> dict:
    order = np.argsort(-scores, axis=1)[:, :k]
    relevant = rel >= 2.0
    hits = np.take_along_axis(relevant, order, 1).sum(1)
    recall = float(np.mean(hits / np.maximum(1, relevant.sum(1))))
    coverage = float(len(np.unique(order)) / rel.shape[1])
    # diversidad: proporción de competencias distintas en el top-k (recursos i % 5)
    diversity = float(np.mean([len(set((row % 5).tolist())) / k for row in order]))
    return {f"ndcg@{k}": ndcg_at_k(rel, scores, k), f"recall@{k}": recall, "coverage": coverage, "diversity": diversity}

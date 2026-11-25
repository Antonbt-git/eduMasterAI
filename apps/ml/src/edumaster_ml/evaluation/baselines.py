"""Baselines interpretables (documento maestro §9.1 — "Importante").

Si la red neuronal no supera estos baselines en la métrica principal, no se marca
como publicable (el admin puede forzar con justificación auditada).
"""
from __future__ import annotations

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression

from .metrics import binary_metrics, ordinal_metrics, ranking_metrics


def _design(arr: dict, idx: np.ndarray) -> np.ndarray:
    tab = arr["x_tab_std"][idx]
    cat = np.eye(3)[arr["x_cat"][idx]]
    return np.hstack([tab, cat])


def _best_binary(Xtr: np.ndarray, ytr: np.ndarray, Xte: np.ndarray, yte: np.ndarray) -> dict:
    """Compara regresión logística y Gradient Boosting; devuelve el mejor por ROC-AUC/PR-AUC."""
    candidates = {
        "LogisticRegression": LogisticRegression(max_iter=2000, class_weight="balanced"),
        "GradientBoosting": GradientBoostingClassifier(random_state=0),
    }
    scores = {}
    for name, model in candidates.items():
        model.fit(Xtr, ytr)
        scores[name] = binary_metrics(yte, model.predict_proba(Xte)[:, 1])
    best = max(scores, key=lambda k: (scores[k]["roc_auc"], scores[k]["pr_auc"]))
    return {"model": best, "candidates": scores, **scores[best]}


def _best_mastery(Xtr: np.ndarray, ytr: np.ndarray, mask: np.ndarray, Xte: np.ndarray, yte: np.ndarray, mask_te: np.ndarray) -> dict:
    candidates = {
        "MultinomialLogisticRegression": LogisticRegression(max_iter=3000),
        "GradientBoosting": GradientBoostingClassifier(random_state=0),
    }
    scores = {}
    for name, model in candidates.items():
        model.fit(Xtr[mask], ytr[mask])
        probs = model.predict_proba(Xte)
        full = np.zeros((len(yte), 5))
        full[:, model.classes_] = probs
        scores[name] = ordinal_metrics(yte, full, mask_te)
    best = max(scores, key=lambda k: (scores[k]["macro_f1"], -scores[k]["mae_ordinal"]))
    return {"model": best, "candidates": scores, **scores[best]}


def run_baselines(arr: dict, tr: np.ndarray, te: np.ndarray) -> dict:
    Xtr, Xte = _design(arr, tr), _design(arr, te)
    out = {}
    for target in ["y_completion", "y_risk"]:
        out[target.replace("y_", "")] = _best_binary(Xtr, arr[target][tr], Xte, arr[target][te])
    m_tr = arr["y_mastery_mask"][tr] > 0
    out["mastery"] = _best_mastery(Xtr, arr["y_mastery"][tr], m_tr, Xte, arr["y_mastery"][te], arr["y_mastery_mask"][te])
    pop = arr["y_rank"][tr].mean(0)
    out["rank"] = {"model": "Popularidad", **ranking_metrics(arr["y_rank"][te], np.tile(pop, (len(te), 1)))}
    return out

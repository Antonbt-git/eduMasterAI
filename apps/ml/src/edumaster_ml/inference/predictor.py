"""Carga de artefactos versionados e inferencia con activaciones reales y explicación."""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import numpy as np
import torch

from ..config import MASTERY_LEVELS, SEQ_WEEKS_OBSERVED, settings
from ..datasets.synthetic import resources_catalog
from ..features.schema import FEATURE_SCHEMA_VERSION, SEQ_FEATURES, TAB_FEATURES, TAB_LABELS_ES, Standardizer
from ..models.networks import activations_for_display, build, describe


class ArtifactNotFound(Exception):
    pass


def artifact_dir(key: str, version: str) -> Path:
    return settings.artifact_dir / key / version


def list_versions(key: str) -> list[dict]:
    base = settings.artifact_dir / key
    if not base.exists():
        return []
    out = []
    for d in sorted(base.iterdir()):
        if (d / "meta.json").exists():
            m = json.loads((d / "meta.json").read_text())
            out.append({k: m.get(k) for k in ("key", "version", "primary", "baseline_primary", "beats_baseline", "created_at", "run_id", "checksum")})
    return out


def latest_version(key: str) -> str | None:
    v = list_versions(key)
    return v[-1]["version"] if v else None


class Predictor:
    def __init__(self, key: str, version: str):
        d = artifact_dir(key, version)
        if not (d / "meta.json").exists():
            raise ArtifactNotFound(f"{key}@{version}")
        self.meta = json.loads((d / "meta.json").read_text())
        self.key, self.version = key, version
        self.model = build(key, **self.meta.get("init_kwargs", {}))
        self.model.load_state_dict(torch.load(d / "model.pt", map_location="cpu", weights_only=True))
        self.model.eval()
        self.tab_s = Standardizer.from_dict(self.meta["scalers"]["tab"])
        self.seq_s = Standardizer.from_dict(self.meta["scalers"]["seq"])
        self.resources = resources_catalog()

    # ------------------------------------------------------------------
    def _batch(self, f: dict) -> dict:
        tab = np.array([[float(f["tab"][k]) for k in TAB_FEATURES]], dtype=np.float32)
        seq = np.array(f.get("seq") or self._seq_from_tab(f["tab"]), dtype=np.float32)[None]
        if seq.shape[1:] != (SEQ_WEEKS_OBSERVED, len(SEQ_FEATURES)):
            raise ValueError(f"seq debe ser [{SEQ_WEEKS_OBSERVED}, {len(SEQ_FEATURES)}]")
        return {
            "x_tab": torch.tensor(self.tab_s.transform(tab)),
            "x_seq": torch.tensor(self.seq_s.transform(seq)),
            "x_cat": torch.tensor([int(f.get("course_level", 0))]),
            "x_skill": torch.tensor([int(f.get("skill_idx", 0))]),
        }

    @staticmethod
    def _seq_from_tab(t: dict) -> list:
        """Si el cliente no envía secuencia, se reconstruye una aproximación uniforme (documentado)."""
        days = float(t["active_days_14d"]) / 2
        sess = float(t["sessions_14d"]) / 2
        return [[days, sess, 1.0, float(t["assessment_mean"]) if w % 2 else 0.0, 0.0, float(t["content_engagement"]) / 8] for w in range(SEQ_WEEKS_OBSERVED)]

    def _primary_tensor(self, out: dict) -> torch.Tensor:
        if "completion_logit" in out and self.key != "edumaster_mtl":
            return out["completion_logit"]
        if "risk_logit" in out and self.key == "risk_transformer":
            return out["risk_logit"]
        if "mastery_probs" in out:
            return (out["mastery_probs"] * torch.arange(5.0)).sum(-1)
        if self.key == "reco_ranker":
            return out["rank_scores"].max(-1).values
        return out["risk_logit"]  # MTL: explicar la señal de riesgo (apoyo humano)

    def explain(self, b: dict) -> list[dict]:
        x = b["x_tab"].clone().requires_grad_(True)
        out = self.model({**b, "x_tab": x})
        self._primary_tensor(out).sum().backward()
        contrib = (x.grad * x).detach()[0].numpy()
        order = np.argsort(-np.abs(contrib))[:3]
        return [
            {"feature": TAB_FEATURES[i], "label": TAB_LABELS_ES[TAB_FEATURES[i]], "contribution": round(float(contrib[i]), 4),
             "direction": "aumenta" if contrib[i] > 0 else "disminuye"}
            for i in order
        ]

    def predict(self, features: dict) -> dict:
        t0 = time.perf_counter()
        b = self._batch(features)
        acts: dict = {}
        with torch.no_grad():
            out = self.model(b, acts=acts)
        scores: dict = {}
        if "completion_logit" in out:
            scores["completion_probability"] = round(float(torch.sigmoid(out["completion_logit"])[0]), 4)
        if "risk_logit" in out:
            scores["risk_probability"] = round(float(torch.sigmoid(out["risk_logit"])[0]), 4)
        probs = out.get("mastery_probs")
        if probs is None and "mastery_logits" in out:
            probs = torch.softmax(out["mastery_logits"], -1)
        if probs is not None:
            p = probs[0].numpy()
            scores["mastery_distribution"] = {MASTERY_LEVELS[i]: round(float(v), 4) for i, v in enumerate(p)}
            scores["mastery_level"] = MASTERY_LEVELS[int(p.argmax())]
            scores["mastery_confidence"] = round(float(p.max()), 4)
        if "rank_scores" in out:
            s = out["rank_scores"][0].numpy()
            top = np.argsort(-s)[:5]
            scores["ranking"] = [
                {"resource_idx": int(i), "code": self.resources.iloc[i]["code"], "title": self.resources.iloc[i]["title"],
                 "skill_idx": int(self.resources.iloc[i]["skill_idx"]), "score": round(float(s[i]), 4)}
                for i in top
            ]
        explanation = self.explain(b)
        return {
            "prediction_id": str(uuid.uuid4()),
            "model_name": self.key,
            "model_version": self.version,
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "label": self.meta.get("label", "DEMO"),
            "scores": scores,
            "explanation": explanation,
            "activations": activations_for_display(self.model, acts),
            "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
            "disclaimer": "Estimación probabilística de apoyo; no es certeza ni diagnóstico. Requiere criterio docente.",
        }

    def graph(self, with_weights: bool = True) -> dict:
        g = describe(self.model, with_weights=with_weights)
        g["version"] = self.version
        g["metrics_summary"] = {"primary": self.meta["primary"], "baseline_primary": self.meta["baseline_primary"],
                                "beats_baseline": self.meta["beats_baseline"]}
        return g


@lru_cache(maxsize=32)
def get_predictor(key: str, version: str) -> Predictor:
    return Predictor(key, version)


def untrained_graph(key: str) -> dict:
    """Topología de la arquitectura aunque aún no exista versión entrenada (pesos de inicialización)."""
    torch.manual_seed(0)
    g = describe(build(key), with_weights=True)
    g["version"] = None
    return g

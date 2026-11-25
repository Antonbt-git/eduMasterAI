"""Entrenamiento reproducible (documento maestro §9.4 / manual §9.1).

- Semillas fijas, configuración versionada, DataLoader.
- Early stopping por métrica de validación + ReduceLROnPlateau + weight decay.
- Calibración por temperature scaling en validación para cabezas binarias.
- Evaluación temporal (test = cohorte más reciente), segmentada y en estudiantes no vistos.
- Comparación contra baselines ⇒ `beats_baseline` (puerta de publicación).
- Artefactos: model.pt, meta.json (scaler, esquema, firma), model_card.md, checksum.
- MLflow opcional (si MLFLOW_TRACKING_URI está definido).
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, TensorDataset

from ..config import MASTERY_LEVELS, settings
from ..datasets.pipeline import load_dataset
from ..evaluation.baselines import run_baselines
from ..evaluation.metrics import binary_metrics, ordinal_metrics, ranking_metrics
from ..features.schema import FEATURE_SCHEMA_VERSION, SEQ_FEATURES, TAB_FEATURES, Standardizer
from ..models.networks import NETWORKS, BaseNet, build, describe
from ..monitoring.drift import drift_report

KEYS = ["x_tab", "x_cat", "x_skill", "x_seq", "y_completion", "y_risk", "y_mastery", "y_mastery_mask", "y_rank"]
ProgressFn = Callable[[dict], None]


@dataclass
class TrainParams:
    epochs: int = 40
    batch_size: int = 128
    lr: float = 3e-3
    weight_decay: float = 1e-4
    patience: int = 7
    seed: int = 42
    dataset_version: str = "demo-v1"
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict | None) -> "TrainParams":
        d = dict(d or {})
        known = {k: d.pop(k) for k in list(d) if k in cls.__dataclass_fields__ and k != "extra"}
        return cls(**known, extra=d)


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True, warn_only=True)


def prepare(arr: dict) -> tuple[dict, Standardizer, Standardizer]:
    split = arr["split"]
    tr = split == "train"
    tab_s = Standardizer.fit(arr["x_tab"][tr])
    seq_s = Standardizer.fit(arr["x_seq"][tr].reshape(-1, arr["x_seq"].shape[-1]))
    arr = dict(arr)
    arr["x_tab_std"] = tab_s.transform(arr["x_tab"])
    arr["x_seq_std"] = seq_s.transform(arr["x_seq"])
    return arr, tab_s, seq_s


def to_tensors(arr: dict, mask: np.ndarray) -> dict[str, torch.Tensor]:
    src = {"x_tab": arr["x_tab_std"], "x_seq": arr["x_seq_std"]}
    out = {}
    for k in KEYS:
        v = np.array(src.get(k, arr[k])[mask])
        out[k] = torch.as_tensor(v, dtype=torch.long if k in ("x_cat", "x_skill", "y_mastery") else torch.float32)
    return out


@torch.no_grad()
def predict_all(model: BaseNet, t: dict) -> dict[str, np.ndarray]:
    model.eval()
    o = model(t)
    res = {}
    if "completion_logit" in o:
        res["p_completion"] = torch.sigmoid(o["completion_logit"]).numpy()
    if "risk_logit" in o:
        res["p_risk"] = torch.sigmoid(o["risk_logit"]).numpy()
    if "mastery_logits" in o:
        res["p_mastery"] = torch.softmax(o["mastery_logits"], -1).numpy()
    if "mastery_probs" in o:
        res["p_mastery"] = o["mastery_probs"].numpy()
    if "rank_scores" in o:
        res["rank_scores"] = o["rank_scores"].numpy()
    return res


def evaluate(model: BaseNet, t: dict) -> dict:
    p = predict_all(model, t)
    m: dict = {}
    if "p_completion" in p:
        m["completion"] = binary_metrics(t["y_completion"].numpy(), p["p_completion"])
    if "p_risk" in p:
        m["risk"] = binary_metrics(t["y_risk"].numpy(), p["p_risk"])
    if "p_mastery" in p:
        m["mastery"] = ordinal_metrics(t["y_mastery"].numpy(), p["p_mastery"], t["y_mastery_mask"].numpy())
    if "rank_scores" in p:
        m["rank"] = ranking_metrics(t["y_rank"].numpy(), p["rank_scores"])
    m["primary"] = primary_value(model.key, m)
    return m


def primary_value(key: str, m: dict) -> float:
    if key == "completion_mlp":
        return m["completion"]["roc_auc"]
    if key == "risk_transformer":
        return m["risk"]["pr_auc"]
    if key == "mastery_ordinal":
        return m["mastery"]["macro_f1"]
    if key == "reco_ranker":
        return m["rank"]["ndcg@5"]
    parts = [m["completion"]["roc_auc"], m["risk"]["pr_auc"], m["mastery"]["macro_f1"], m["rank"]["ndcg@5"]]
    return float(np.nanmean(parts))


def calibrate_temperature(model: BaseNet, t: dict, logit_key: str, y_key: str) -> float:
    model.eval()
    with torch.no_grad():
        model.temperature.fill_(1.0)
        logits = model(t)[logit_key]
    log_t = torch.zeros(1, requires_grad=True)
    opt = torch.optim.LBFGS([log_t], lr=0.1, max_iter=60)
    y = t[y_key]

    def closure():
        opt.zero_grad()
        loss = torch.nn.functional.binary_cross_entropy_with_logits(logits / log_t.exp(), y)
        loss.backward()
        return loss

    opt.step(closure)
    temp = float(log_t.exp().clamp(0.25, 4.0))
    model.temperature.fill_(temp)
    return temp


def _grad_norms(model: BaseNet) -> dict[str, float]:
    norms = {}
    for l in model.visual_spec()["layers"]:
        if not l.get("module"):
            continue
        mod = model.get_submodule(l["module"])
        g = [p.grad.detach().norm() for p in mod.parameters() if p.grad is not None]
        norms[l["id"]] = float(torch.stack(g).norm()) if g else 0.0
    return norms


def _next_version(key: str) -> str:
    base = settings.artifact_dir / key
    base.mkdir(parents=True, exist_ok=True)
    n = len([p for p in base.iterdir() if p.is_dir()]) + 1
    return f"1.0.{n}"


def train_network(key: str, params: dict | None = None, progress: ProgressFn | None = None, run_id: str | None = None) -> dict:
    if key not in NETWORKS:
        raise KeyError(key)
    P = TrainParams.from_dict(params)
    seed_everything(P.seed)
    emit = progress or (lambda e: None)
    t0 = time.time()

    emit({"phase": "loading_data", "message": f"Cargando dataset {P.dataset_version}"})
    raw, manifest = load_dataset(P.dataset_version)
    arr, tab_s, seq_s = prepare(raw)
    split = arr["split"]
    tr, va, te = split == "train", split == "validation", split == "test"
    T_tr, T_va, T_te = to_tensors(arr, tr), to_tensors(arr, va), to_tensors(arr, te)

    pw_c = float((1 - raw["y_completion"][tr].mean()) / max(1e-3, raw["y_completion"][tr].mean()))
    pw_r = float((1 - raw["y_risk"][tr].mean()) / max(1e-3, raw["y_risk"][tr].mean()))
    kw = {"pos_weight": pw_c if key != "risk_transformer" else pw_r}
    if key == "edumaster_mtl":
        kw["risk_pos_weight"] = pw_r
    model = build(key, **kw)

    loader = DataLoader(TensorDataset(*[T_tr[k] for k in KEYS]), batch_size=P.batch_size, shuffle=True,
                        generator=torch.Generator().manual_seed(P.seed))
    opt = torch.optim.AdamW(model.parameters(), lr=P.lr, weight_decay=P.weight_decay)
    sched = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, mode="max", factor=0.5, patience=3)

    best, best_state, bad, history = -1.0, None, 0, []
    emit({"phase": "training", "message": "Entrenamiento iniciado", "epochs": P.epochs, "params_total": model.param_count()})
    for epoch in range(1, P.epochs + 1):
        model.train()
        tot, n = 0.0, 0
        for batch in loader:
            b = dict(zip(KEYS, batch))
            opt.zero_grad()
            loss, _parts = model.loss(b)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            opt.step()
            tot += loss.item() * len(batch[0]); n += len(batch[0])
        gnorms = _grad_norms(model)
        model.eval()
        with torch.no_grad():
            val_loss, parts = model.loss(T_va)
        vm = evaluate(model, T_va)
        sched.step(vm["primary"])
        rec = {"epoch": epoch, "train_loss": tot / n, "val_loss": float(val_loss), "val_metric": vm["primary"],
               "lr": opt.param_groups[0]["lr"], "loss_parts": parts}
        history.append(rec)
        emit({"phase": "training", "epochs": P.epochs, "grad_norms": gnorms, **rec})
        if vm["primary"] > best + 1e-4:
            best, bad = vm["primary"], 0
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
        else:
            bad += 1
            if bad >= P.patience:
                emit({"phase": "training", "message": f"Early stopping en época {epoch}", "epoch": epoch, "epochs": P.epochs})
                break
    model.load_state_dict(best_state)

    emit({"phase": "validating", "message": "Calibración y evaluación"})
    temperature = 1.0
    if key == "completion_mlp":
        temperature = calibrate_temperature(model, T_va, "completion_logit", "y_completion")
    elif key == "risk_transformer":
        temperature = calibrate_temperature(model, T_va, "risk_logit", "y_risk")

    test_m = evaluate(model, T_te)
    val_m = evaluate(model, T_va)
    unseen = arr["unseen"][te]
    unseen_m = evaluate(model, {k: v[torch.as_tensor(unseen)] for k, v in T_te.items()}) if unseen.sum() > 20 else None

    base = run_baselines(arr, np.where(tr)[0], np.where(te)[0])
    base_primary = primary_value(key, {"completion": base["completion"], "risk": base["risk"], "mastery": base["mastery"], "rank": base["rank"]})
    beats = bool(test_m["primary"] > base_primary)

    # Drift de referencia (train vs cohorte de prueba): monitor de estabilidad de features.
    drift = drift_report(arr["x_tab"][tr], arr["x_tab"][te], TAB_FEATURES)
    max_psi = max((d["psi"] for d in drift), default=0.0)

    # Evaluación segmentada (equidad / estabilidad por grupo) -------------------
    meta_df = pd.read_csv(Path(manifest["storage_uri"]) / "enrollments.csv")
    seg_df = meta_df[te].reset_index(drop=True)
    segments = {}
    for col in ["course_level", "region"]:
        segments[col] = {}
        for val, g in seg_df.groupby(col):
            if len(g) < 25:
                continue
            sub = {k: v[torch.as_tensor(g.index.to_numpy())] for k, v in T_te.items()}
            segments[col][str(val)] = round(evaluate(model, sub)["primary"], 4)

    version = _next_version(key)
    out = settings.artifact_dir / key / version
    out.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), out / "model.pt")
    checksum = hashlib.sha256((out / "model.pt").read_bytes()).hexdigest()
    graph = describe(model, with_weights=False)
    meta = {
        "key": key, "version": version, "run_id": run_id, "title": model.title, "task": model.task,
        "primary_metric": model.primary_metric, "label": "DEMO",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset": {"version": manifest["version"], "checksum": manifest["checksum"], "label": manifest["label"]},
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "input_signature": {"x_tab": TAB_FEATURES, "x_seq": SEQ_FEATURES, "x_cat": "course_level[0..2]", "x_skill": "skill_idx[0..4]"},
        "init_kwargs": {k: v for k, v in kw.items()},
        "scalers": {"tab": tab_s.to_dict(), "seq": seq_s.to_dict()},
        "temperature": temperature,
        "params": P.__dict__, "params_total": model.param_count(),
        "history": history,
        "metrics": {"validation": val_m, "test": test_m, "test_unseen_students": unseen_m, "segments": segments,
                    "drift": {"reference": "train", "current": "test", "max_psi": round(max_psi, 4), "features": drift}},
        "baseline": base, "baseline_primary": base_primary, "primary": test_m["primary"],
        "beats_baseline": beats, "checksum": checksum,
        "environment": {"python": platform.python_version(), "torch": torch.__version__, "commit": os.getenv("GIT_COMMIT", "local")},
        "duration_s": round(time.time() - t0, 2),
        "layers": [{k: l[k] for k in ("id", "name", "op", "units", "shape")} for l in graph["layers"]],
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False, default=float))
    (out / "model_card.md").write_text(model_card(meta), encoding="utf-8")
    _mlflow_log(meta, out)
    emit({"phase": "completed", "message": "Entrenamiento completado", "version": version, "primary": test_m["primary"],
          "baseline_primary": base_primary, "beats_baseline": beats})
    return meta


def _mlflow_log(meta: dict, out: Path) -> None:
    if not settings.mlflow_uri:
        return
    try:
        import mlflow

        mlflow.set_tracking_uri(settings.mlflow_uri)
        mlflow.set_experiment(f"edumaster/{meta['key']}")
        with mlflow.start_run(run_name=f"{meta['key']}-{meta['version']}"):
            mlflow.log_params({k: v for k, v in meta["params"].items() if not isinstance(v, dict)})
            mlflow.log_param("dataset_version", meta["dataset"]["version"])
            mlflow.log_param("dataset_checksum", meta["dataset"]["checksum"])
            mlflow.log_metric("test_primary", meta["primary"])
            mlflow.log_metric("baseline_primary", meta["baseline_primary"])
            for h in meta["history"]:
                mlflow.log_metric("train_loss", h["train_loss"], step=h["epoch"])
                mlflow.log_metric("val_loss", h["val_loss"], step=h["epoch"])
                mlflow.log_metric("val_metric", h["val_metric"], step=h["epoch"])
            mlflow.log_artifacts(str(out))
    except Exception as exc:  # MLflow es opcional: no rompe el entrenamiento
        print(f"[mlflow] omitido: {exc}")


def model_card(m: dict) -> str:
    t = m["metrics"]["test"]
    lines = [
        f"# Model Card — {m['title']} v{m['version']}",
        "",
        "> **DEMO**: entrenado con dataset sintético. Las cifras NO son resultados educativos reales.",
        "",
        "| Campo | Valor |", "|---|---|",
        f"| Clave | `{m['key']}` |", f"| Tarea | {m['task']} |",
        f"| Dataset | {m['dataset']['version']} (`{m['dataset']['checksum'][:12]}…`) |",
        f"| Esquema de features | {m['feature_schema_version']} |",
        f"| Parámetros | {m['params_total']:,} |",
        f"| Métrica principal ({m['primary_metric']}) | {m['primary']:.4f} |",
        f"| Baseline | {m['baseline_primary']:.4f} |",
        f"| ¿Supera baseline? | {'Sí' if m['beats_baseline'] else 'No — no publicable sin justificación'} |",
        f"| Temperatura de calibración | {m['temperature']:.3f} |",
        f"| Checksum artefacto | `{m['checksum'][:16]}…` |",
        "", "## Arquitectura", "",
        "| Capa | Operación | Neuronas | Tensor |", "|---|---|---|---|",
        *[f"| {l['name']} | {l['op']} | {l['units']} | `{l['shape']}` |" for l in m["layers"]],
        "", "## Métricas de prueba (cohorte más reciente)", "", "```json", json.dumps(t, indent=1, default=float)[:2500], "```",
        "", "## Evaluación segmentada", "", "```json", json.dumps(m["metrics"]["segments"], indent=1), "```",
        "", "## Uso previsto y límites",
        "- Apoyo a docentes y coordinadores; **no** sanciona, excluye ni califica oficialmente.",
        "- Una probabilidad es una estimación, no certeza ni diagnóstico.",
        "- No usa variables sensibles ni proxies injustificados (sin género, edad, etnia, ubicación individual).",
        "- Requiere revisión humana y aprobación antes de producción; rollback disponible a la versión anterior.",
        f"- Población de entrenamiento: cohortes DEMO; niveles de dominio: {', '.join(MASTERY_LEVELS)}.",
    ]
    return "\n".join(lines)

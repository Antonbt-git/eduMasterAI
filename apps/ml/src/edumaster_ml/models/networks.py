"""Las 5 redes neuronales de EduMaster.ai (PyTorch).

Cada red expone:
  * forward(batch, acts=None)     -> dict de salidas (y opcionalmente activaciones por capa visual)
  * loss(batch)                   -> (pérdida total, partes)
  * visual_spec()                 -> topología REAL derivada de los módulos (capas, neuronas, dimensiones, aristas)

La topología que dibuja el frontend sale de aquí: no es un dibujo inventado.
"""
from __future__ import annotations

import math
from typing import Callable

import torch
import torch.nn as nn
import torch.nn.functional as F

from ..config import MASTERY_LEVELS, N_RESOURCES, SEQ_WEEKS_OBSERVED
from ..features.schema import N_COURSE_LEVELS, N_SKILLS, SEQ_FEATURES, TAB_FEATURES, TAB_LABELS_ES

N_TAB = len(TAB_FEATURES)
N_SEQ = len(SEQ_FEATURES)
SEQ_LABELS = ["Días activos", "Sesiones", "Actividades", "Puntaje", "Tardías", "Horas"]
RES_LABELS = [f"Recurso {i + 1}" for i in range(N_RESOURCES)]


def _layer(id, name, kind, op, units, shape, col, labels=None, module=None):
    return {"id": id, "name": name, "kind": kind, "op": op, "units": units, "shape": shape, "col": col,
            "labels": labels, "module": module}


def _edge(src, dst, weight: Callable[[], torch.Tensor] | None):
    return {"from": src, "to": dst, "weight": weight}


def _put(acts, key, t):
    if acts is not None:
        acts[key] = t.detach()


# ---------------------------------------------------------------------------
# Pérdidas auxiliares
# ---------------------------------------------------------------------------

def listnet_loss(scores: torch.Tensor, relevance: torch.Tensor) -> torch.Tensor:
    return -(F.softmax(relevance, -1) * F.log_softmax(scores, -1)).sum(-1).mean()


def bpr_loss(scores: torch.Tensor, relevance: torch.Tensor) -> torch.Tensor:
    pos = torch.argmax(relevance + 1e-3 * torch.rand_like(relevance), dim=-1)
    neg_mask = relevance < (relevance.gather(1, pos[:, None]) - 0.5)
    neg_logits = torch.where(neg_mask, torch.zeros_like(scores), torch.full_like(scores, -1e9))
    neg = torch.multinomial(F.softmax(neg_logits, -1), 1).squeeze(1)
    s_pos = scores.gather(1, pos[:, None]).squeeze(1)
    s_neg = scores.gather(1, neg[:, None]).squeeze(1)
    return F.softplus(-(s_pos - s_neg)).mean()


def coral_loss(logits: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
    k = logits.shape[1]
    levels = (torch.arange(k, device=y.device)[None, :] < y[:, None]).float()
    return F.binary_cross_entropy_with_logits(logits, levels)


class BaseNet(nn.Module):
    key: str = "base"
    title: str = ""
    description: str = ""
    task: str = ""
    primary_metric: str = ""

    def __init__(self, pos_weight: float = 1.0):
        super().__init__()
        self.register_buffer("pos_weight", torch.tensor(float(pos_weight)))
        self.register_buffer("temperature", torch.tensor(1.0))

    def visual_spec(self) -> dict:  # pragma: no cover - abstract
        raise NotImplementedError

    def param_count(self) -> int:
        return sum(p.numel() for p in self.parameters())


# ---------------------------------------------------------------------------
# 1. EduMaster Multi-Task Learning Network (documento maestro §9.1)
# ---------------------------------------------------------------------------
class EduMasterMTL(BaseNet):
    key = "edumaster_mtl"
    title = "EduMaster Multi-Task Network"
    description = "Rama densa tabular + rama temporal GRU, fusión con LayerNorm/Dropout y 4 cabezas: finalización, dominio, riesgo y ranking."
    task = "multitask"
    primary_metric = "composite"

    def __init__(self, pos_weight=1.0, risk_pos_weight=1.0, lambdas=(1.0, 0.7, 1.0, 0.5), dropout=0.2):
        super().__init__(pos_weight)
        self.register_buffer("risk_pos_weight", torch.tensor(float(risk_pos_weight)))
        self.lambdas = lambdas
        self.cat_emb = nn.Embedding(N_COURSE_LEVELS, 4)
        self.tab1 = nn.Linear(N_TAB + 4, 64)
        self.tab2 = nn.Linear(64, 32)
        self.gru = nn.GRU(N_SEQ, 32, batch_first=True)
        self.fuse = nn.Linear(64, 64)
        self.norm = nn.LayerNorm(64)
        self.drop = nn.Dropout(dropout)
        self.head_completion = nn.Linear(64, 1)
        self.head_mastery = nn.Linear(64, len(MASTERY_LEVELS))
        self.head_risk = nn.Linear(64, 1)
        self.head_rank = nn.Linear(64, N_RESOURCES)

    def forward(self, b, acts=None):
        _put(acts, "in_tab", b["x_tab"]); _put(acts, "in_seq", b["x_seq"][:, -1, :])
        t = torch.cat([b["x_tab"], self.cat_emb(b["x_cat"])], -1)
        h1 = F.relu(self.tab1(t)); _put(acts, "dense1", h1)
        h2 = F.relu(self.tab2(h1)); _put(acts, "dense2", h2)
        _, hn = self.gru(b["x_seq"]); g = hn[-1]; _put(acts, "gru", g)
        z = self.drop(F.relu(self.norm(self.fuse(torch.cat([h2, g], -1))))); _put(acts, "fusion", z)
        out = {
            "completion_logit": self.head_completion(z).squeeze(-1),
            "mastery_logits": self.head_mastery(z),
            "risk_logit": self.head_risk(z).squeeze(-1),
            "rank_scores": self.head_rank(z),
        }
        _put(acts, "out_completion", torch.sigmoid(out["completion_logit"])[:, None])
        _put(acts, "out_mastery", F.softmax(out["mastery_logits"], -1))
        _put(acts, "out_risk", torch.sigmoid(out["risk_logit"])[:, None])
        _put(acts, "out_rank", F.softmax(out["rank_scores"], -1))
        return out

    def loss(self, b):
        o = self(b)
        l1 = F.binary_cross_entropy_with_logits(o["completion_logit"], b["y_completion"], pos_weight=self.pos_weight)
        ce = F.cross_entropy(o["mastery_logits"], b["y_mastery"], reduction="none")
        m = b["y_mastery_mask"]
        l2 = (ce * m).sum() / m.sum().clamp(min=1)  # tarea sin etiqueta ⇒ enmascarada
        l3 = F.binary_cross_entropy_with_logits(o["risk_logit"], b["y_risk"], pos_weight=self.risk_pos_weight)
        l4 = listnet_loss(o["rank_scores"], b["y_rank"])
        la = self.lambdas
        total = la[0] * l1 + la[1] * l2 + la[2] * l3 + la[3] * l4
        return total, {"bce_completion": l1.item(), "ce_mastery": l2.item(), "bce_risk": l3.item(), "listnet_rank": l4.item()}

    def visual_spec(self):
        L = [
            _layer("in_tab", "Entrada tabular", "input", "Normalización", N_TAB, f"[B, {N_TAB}]", 0, [TAB_LABELS_ES[f] for f in TAB_FEATURES]),
            _layer("in_seq", "Secuencia de eventos", "input", "Ventana 8 semanas", N_SEQ, f"[B, {SEQ_WEEKS_OBSERVED}, {N_SEQ}]", 0, SEQ_LABELS),
            _layer("dense1", "Dense tabular", "hidden", "Linear + ReLU", 64, "[B, 64]", 1, module="tab1"),
            _layer("gru", "Rama temporal GRU", "temporal", "GRU (h=32)", 32, "[B, 32]", 1, module="gru"),
            _layer("dense2", "Dense tabular 2", "hidden", "Linear + ReLU", 32, "[B, 32]", 2, module="tab2"),
            _layer("fusion", "Fusión compartida", "fusion", "Concat → Linear → LayerNorm → Dropout", 64, "[B, 64]", 3, module="fuse"),
            _layer("out_completion", "A · Finalización", "output", "Sigmoid", 1, "[B, 1]", 4, ["P(finalizar)"], "head_completion"),
            _layer("out_mastery", "B · Dominio", "output", "Softmax ordinal", 5, "[B, 5]", 4, MASTERY_LEVELS, "head_mastery"),
            _layer("out_risk", "C · Riesgo", "output", "Sigmoid", 1, "[B, 1]", 4, ["P(desconexión)"], "head_risk"),
            _layer("out_rank", "D · Ranking", "output", "Scores de ranking", N_RESOURCES, f"[B, {N_RESOURCES}]", 4, RES_LABELS, "head_rank"),
        ]
        E = [
            _edge("in_tab", "dense1", lambda: self.tab1.weight[:, :N_TAB]),
            _edge("in_seq", "gru", lambda: self.gru.weight_ih_l0[32:64]),
            _edge("dense1", "dense2", lambda: self.tab2.weight),
            _edge("dense2", "fusion", lambda: self.fuse.weight[:, :32]),
            _edge("gru", "fusion", lambda: self.fuse.weight[:, 32:]),
            _edge("fusion", "out_completion", lambda: self.head_completion.weight),
            _edge("fusion", "out_mastery", lambda: self.head_mastery.weight),
            _edge("fusion", "out_risk", lambda: self.head_risk.weight),
            _edge("fusion", "out_rank", lambda: self.head_rank.weight),
        ]
        return {"layers": L, "edges": E}


# ---------------------------------------------------------------------------
# 2. Completion Net — MLP calibrado (Cabeza A especializada)
# ---------------------------------------------------------------------------
class CompletionNet(BaseNet):
    key = "completion_mlp"
    title = "Completion Predictor"
    description = "Perceptrón multicapa calibrado (temperature scaling) que estima la probabilidad de finalizar el curso en la ventana objetivo."
    task = "binary:completion"
    primary_metric = "roc_auc"

    def __init__(self, pos_weight=1.0, dropout=0.2):
        super().__init__(pos_weight)
        self.cat_emb = nn.Embedding(N_COURSE_LEVELS, 4)
        self.fc1 = nn.Linear(N_TAB + 4, 32)
        self.fc2 = nn.Linear(32, 16)
        self.out = nn.Linear(16, 1)
        self.drop = nn.Dropout(dropout)

    def forward(self, b, acts=None):
        _put(acts, "in", b["x_tab"])
        x = torch.cat([b["x_tab"], self.cat_emb(b["x_cat"])], -1)
        h1 = self.drop(F.relu(self.fc1(x))); _put(acts, "h1", h1)
        h2 = F.relu(self.fc2(h1)); _put(acts, "h2", h2)
        logit = self.out(h2).squeeze(-1) / self.temperature
        _put(acts, "out", torch.sigmoid(logit)[:, None])
        return {"completion_logit": logit}

    def loss(self, b):
        o = self(b)
        l = F.binary_cross_entropy_with_logits(o["completion_logit"], b["y_completion"], pos_weight=self.pos_weight)
        return l, {"bce": l.item()}

    def visual_spec(self):
        L = [
            _layer("in", "Variables de aprendizaje", "input", "Normalización + embedding nivel", N_TAB, f"[B, {N_TAB}+4]", 0, [TAB_LABELS_ES[f] for f in TAB_FEATURES]),
            _layer("h1", "Oculta 1", "hidden", "Linear + ReLU + Dropout", 32, "[B, 32]", 1, module="fc1"),
            _layer("h2", "Oculta 2", "hidden", "Linear + ReLU", 16, "[B, 16]", 2, module="fc2"),
            _layer("out", "Finalización", "output", "Sigmoid / T", 1, "[B, 1]", 3, ["P(finalizar)"], "out"),
        ]
        E = [
            _edge("in", "h1", lambda: self.fc1.weight[:, :N_TAB]),
            _edge("h1", "h2", lambda: self.fc2.weight),
            _edge("h2", "out", lambda: self.out.weight),
        ]
        return {"layers": L, "edges": E}


# ---------------------------------------------------------------------------
# 3. Skill Mastery — red ordinal CORAL
# ---------------------------------------------------------------------------
class MasteryOrdinalNet(BaseNet):
    key = "mastery_ordinal"
    title = "Skill Mastery Ordinal"
    description = "Red ordinal que estima el nivel de dominio (principiante → experto). Pérdida CE + EMD² que penaliza más los errores lejanos en la escala."
    task = "ordinal:mastery"
    primary_metric = "macro_f1"

    def __init__(self, pos_weight=1.0, emd_weight=0.5):
        super().__init__(pos_weight)
        self.emd_weight = emd_weight
        self.skill_emb = nn.Embedding(N_SKILLS, 4)
        self.fc1 = nn.Linear(N_TAB + 4 + N_SEQ, 48)
        self.fc2 = nn.Linear(48, 24)
        self.out = nn.Linear(24, len(MASTERY_LEVELS))

    def forward(self, b, acts=None):
        _put(acts, "in", b["x_tab"])
        seq_mean = b["x_seq"].mean(1)
        x = torch.cat([b["x_tab"], self.skill_emb(b["x_skill"]), seq_mean], -1)
        h1 = F.gelu(self.fc1(x)); _put(acts, "h1", h1)
        h2 = F.gelu(self.fc2(h1)); _put(acts, "h2", h2)
        logits = self.out(h2)
        p = F.softmax(logits, -1)
        _put(acts, "thr", 1 - torch.cumsum(p, -1)[:, :-1])  # P(nivel ≥ k)
        _put(acts, "out", p)
        return {"mastery_logits": logits, "mastery_probs": p}

    def loss(self, b):
        o = self(b)
        m = b["y_mastery_mask"]
        ce = F.cross_entropy(o["mastery_logits"], b["y_mastery"], reduction="none")
        target = F.one_hot(b["y_mastery"], o["mastery_probs"].shape[1]).float()
        emd = ((torch.cumsum(o["mastery_probs"], -1) - torch.cumsum(target, -1)) ** 2).sum(-1)
        per = ce + self.emd_weight * emd
        l = (per * m).sum() / m.sum().clamp(min=1)
        return l, {"ce+emd2": l.item()}

    def visual_spec(self):
        L = [
            _layer("in", "Evidencias y actividad", "input", "Tabular + embedding competencia + media temporal", N_TAB, f"[B, {N_TAB}+4+{N_SEQ}]", 0, [TAB_LABELS_ES[f] for f in TAB_FEATURES]),
            _layer("h1", "Oculta 1", "hidden", "Linear + GELU", 48, "[B, 48]", 1, module="fc1"),
            _layer("h2", "Oculta 2", "hidden", "Linear + GELU", 24, "[B, 24]", 2, module="fc2"),
            _layer("out", "Nivel de dominio", "output", "Softmax ordinal", 5, "[B, 5]", 3, MASTERY_LEVELS, "out"),
            _layer("thr", "Umbrales acumulados", "fusion", "P(nivel ≥ k)", 4, "[B, 4]", 4, ["≥ Elemental", "≥ Intermedio", "≥ Avanzado", "≥ Experto"]),
        ]
        E = [
            _edge("in", "h1", lambda: self.fc1.weight[:, :N_TAB]),
            _edge("h1", "h2", lambda: self.fc2.weight),
            _edge("h2", "out", lambda: self.out.weight),
            _edge("out", "thr", None),
        ]
        return {"layers": L, "edges": E}


# ---------------------------------------------------------------------------
# 4. Risk Transformer — encoder temporal para señal de desconexión
# ---------------------------------------------------------------------------
class RiskTransformer(BaseNet):
    key = "risk_transformer"
    title = "Disengagement Risk Transformer"
    description = "Transformer Encoder (2 bloques de self-attention) sobre la secuencia semanal de eventos + contexto tabular. Señal de apoyo humano, nunca sanción."
    task = "binary:risk"
    primary_metric = "pr_auc"

    def __init__(self, pos_weight=1.0, d_model=32, heads=4, layers=2, dropout=0.1):
        super().__init__(pos_weight)
        self.proj = nn.Linear(N_SEQ, d_model)
        self.pos = nn.Parameter(torch.randn(SEQ_WEEKS_OBSERVED, d_model) * 0.02)
        self.blocks = nn.ModuleList(
            [nn.TransformerEncoderLayer(d_model, heads, 64, dropout, batch_first=True, norm_first=True) for _ in range(layers)]
        )
        self.head1 = nn.Linear(d_model + N_TAB, 32)
        self.out = nn.Linear(32, 1)

    def forward(self, b, acts=None):
        _put(acts, "in_seq", b["x_seq"][:, -1, :]); _put(acts, "in_tab", b["x_tab"])
        h = self.proj(b["x_seq"]) + self.pos[None]
        _put(acts, "proj", h.mean(1))
        for i, blk in enumerate(self.blocks):
            h = blk(h)
            _put(acts, f"enc{i + 1}", h.mean(1))
        pooled = h.mean(1)
        z = F.relu(self.head1(torch.cat([pooled, b["x_tab"]], -1))); _put(acts, "head", z)
        logit = self.out(z).squeeze(-1) / self.temperature
        _put(acts, "out", torch.sigmoid(logit)[:, None])
        return {"risk_logit": logit}

    def loss(self, b):
        o = self(b)
        l = F.binary_cross_entropy_with_logits(o["risk_logit"], b["y_risk"], pos_weight=self.pos_weight)
        return l, {"bce": l.item()}

    def visual_spec(self):
        d = self.proj.out_features
        L = [
            _layer("in_seq", "Secuencia semanal", "input", "8 semanas × 6 señales", N_SEQ, f"[B, 8, {N_SEQ}]", 0, SEQ_LABELS),
            _layer("in_tab", "Contexto tabular", "input", "Normalización", N_TAB, f"[B, {N_TAB}]", 0, [TAB_LABELS_ES[f] for f in TAB_FEATURES]),
            _layer("proj", "Embedding temporal", "embedding", "Linear + posicional", d, f"[B, 8, {d}]", 1, module="proj"),
            _layer("enc1", "Self-Attention 1", "temporal", "MHA 4 cabezas + FFN", d, f"[B, 8, {d}]", 2, module="blocks.0"),
            _layer("enc2", "Self-Attention 2", "temporal", "MHA 4 cabezas + FFN", d, f"[B, 8, {d}]", 3, module="blocks.1"),
            _layer("head", "Cabeza densa", "fusion", "Pool + Concat + Linear + ReLU", 32, "[B, 32]", 4, module="head1"),
            _layer("out", "Riesgo de desconexión", "output", "Sigmoid / T", 1, "[B, 1]", 5, ["P(desconexión)"], "out"),
        ]
        E = [
            _edge("in_seq", "proj", lambda: self.proj.weight),
            _edge("proj", "enc1", lambda: self.blocks[0].self_attn.in_proj_weight[2 * d:3 * d]),
            _edge("enc1", "enc2", lambda: self.blocks[1].self_attn.in_proj_weight[2 * d:3 * d]),
            _edge("enc2", "head", lambda: self.head1.weight[:, :d]),
            _edge("in_tab", "head", lambda: self.head1.weight[:, d:]),
            _edge("head", "out", lambda: self.out.weight),
        ]
        return {"layers": L, "edges": E}


# ---------------------------------------------------------------------------
# 5. Neural Recommender — two-tower con pérdida BPR
# ---------------------------------------------------------------------------
class RecoRanker(BaseNet):
    key = "reco_ranker"
    title = "Neural Recommender (Two-Tower)"
    description = "Torre de estudiante + torre de recursos con embeddings; interacción u⊙v y ranking entrenado con BPR (NDCG@5)."
    task = "ranking:resources"
    primary_metric = "ndcg@5"

    def __init__(self, pos_weight=1.0, dim=16):
        super().__init__(pos_weight)
        self.skill_emb = nn.Embedding(N_SKILLS, 4)
        self.u1 = nn.Linear(N_TAB + 4, 32)
        self.u2 = nn.Linear(32, dim)
        self.item_emb = nn.Embedding(N_RESOURCES, dim)
        self.item_bias = nn.Embedding(N_RESOURCES, 1)
        self.inter = nn.Linear(dim, dim)
        self.score = nn.Linear(dim, 1)

    def forward(self, b, acts=None):
        _put(acts, "in_tab", b["x_tab"])
        x = torch.cat([b["x_tab"], self.skill_emb(b["x_skill"])], -1)
        h = F.relu(self.u1(x)); _put(acts, "user_h", h)
        u = self.u2(h); _put(acts, "user_emb", u)
        v = self.item_emb.weight  # [R, d]
        if acts is not None:
            acts["in_res"] = torch.ones(x.shape[0], N_RESOURCES)
            acts["item_emb"] = v.mean(0, keepdim=True).expand(x.shape[0], -1).detach()
        inter = F.relu(self.inter(u[:, None, :] * v[None, :, :]))  # [B, R, d]
        _put(acts, "inter", inter.mean(1))
        scores = self.score(inter).squeeze(-1) + self.item_bias.weight.T
        _put(acts, "out", F.softmax(scores, -1))
        return {"rank_scores": scores}

    def loss(self, b):
        o = self(b)
        l = bpr_loss(o["rank_scores"], b["y_rank"]) + 0.3 * listnet_loss(o["rank_scores"], b["y_rank"])
        return l, {"bpr+listnet": l.item()}

    def visual_spec(self):
        d = self.u2.out_features
        L = [
            _layer("in_tab", "Perfil del estudiante", "input", "Tabular + competencia", N_TAB, f"[B, {N_TAB}+4]", 0, [TAB_LABELS_ES[f] for f in TAB_FEATURES]),
            _layer("in_res", "Catálogo de recursos", "input", "IDs de recurso", N_RESOURCES, f"[R={N_RESOURCES}]", 0, RES_LABELS),
            _layer("user_h", "Torre estudiante", "hidden", "Linear + ReLU", 32, "[B, 32]", 1, module="u1"),
            _layer("item_emb", "Embedding de recursos", "embedding", "Embedding", d, f"[R, {d}]", 1, module="item_emb"),
            _layer("user_emb", "Embedding estudiante", "embedding", "Linear", d, f"[B, {d}]", 2, module="u2"),
            _layer("inter", "Interacción u⊙v", "fusion", "Hadamard + Linear + ReLU", d, f"[B, R, {d}]", 3, module="inter"),
            _layer("out", "Ranking de recursos", "output", "Score + sesgo", N_RESOURCES, f"[B, {N_RESOURCES}]", 4, RES_LABELS, "score"),
        ]
        E = [
            _edge("in_tab", "user_h", lambda: self.u1.weight[:, :N_TAB]),
            _edge("in_res", "item_emb", lambda: self.item_emb.weight.T),
            _edge("user_h", "user_emb", lambda: self.u2.weight),
            _edge("user_emb", "inter", lambda: self.inter.weight),
            _edge("item_emb", "inter", lambda: self.inter.weight),
            _edge("inter", "out", lambda: self.score.weight.expand(N_RESOURCES, -1)),
        ]
        return {"layers": L, "edges": E}


NETWORKS: dict[str, type[BaseNet]] = {
    cls.key: cls for cls in [EduMasterMTL, CompletionNet, MasteryOrdinalNet, RiskTransformer, RecoRanker]
}


def build(key: str, **kw) -> BaseNet:
    if key not in NETWORKS:
        raise KeyError(f"Red desconocida: {key}")
    return NETWORKS[key](**kw)


def _sample_idx(n: int, max_display: int) -> list[int]:
    if n <= max_display:
        return list(range(n))
    return sorted({round(i * (n - 1) / (max_display - 1)) for i in range(max_display)})


def describe(model: BaseNet, max_display: int = 8, with_weights: bool = True) -> dict:
    """Serializa la topología REAL para el visualizador (capas, dimensiones, aristas, pesos muestreados)."""
    spec = model.visual_spec()
    layers = []
    disp = {}
    for l in spec["layers"]:
        idx = _sample_idx(l["units"], max_display)
        disp[l["id"]] = idx
        params = 0
        if l.get("module"):
            mod = model.get_submodule(l["module"])
            params = sum(p.numel() for p in mod.parameters())
        layers.append({k: v for k, v in l.items() if k not in ("labels",)} | {
            "display_idx": idx,
            "labels": [l["labels"][i] for i in idx] if l.get("labels") else None,
            "params": params,
        })
    edges = []
    for e in spec["edges"]:
        w = None
        if with_weights and e["weight"] is not None:
            with torch.no_grad():
                W = e["weight"]().detach().float()
                fi, ti = disp[e["from"]], disp[e["to"]]
                ti = [i for i in ti if i < W.shape[0]]
                fi = [i for i in fi if i < W.shape[1]]
                sub = W[ti][:, fi]
                scale = sub.abs().max().clamp(min=1e-8)
                w = (sub / scale).round(decimals=3).tolist()
        edges.append({"from": e["from"], "to": e["to"], "weights": w})
    return {
        "key": model.key,
        "title": model.title,
        "description": model.description,
        "task": model.task,
        "primary_metric": model.primary_metric,
        "params_total": model.param_count(),
        "layers": layers,
        "edges": edges,
    }


def activations_for_display(model: BaseNet, acts: dict, max_display: int = 8) -> dict:
    out = {}
    for l in model.visual_spec()["layers"]:
        t = acts.get(l["id"])
        if t is None:
            continue
        v = t[0].float()
        idx = [i for i in _sample_idx(l["units"], max_display) if i < v.shape[0]]
        sel = v[idx]
        denom = sel.abs().max().clamp(min=1e-8) if l["kind"] != "output" else torch.tensor(1.0)
        out[l["id"]] = (sel.abs() / denom).clamp(0, 1).round(decimals=3).tolist()
    return out

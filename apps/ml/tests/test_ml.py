"""Pruebas ML: reproducibilidad, fuga de datos, formas, topología y gate de baseline."""
import os
import tempfile

os.environ.setdefault("ML_DATA_DIR", tempfile.mkdtemp())
os.environ.setdefault("ML_ARTIFACT_DIR", tempfile.mkdtemp())

import numpy as np
import pytest
import torch

from edumaster_ml.config import SEQ_WEEKS_OBSERVED
from edumaster_ml.datasets.pipeline import build_dataset, load_dataset
from edumaster_ml.models.networks import NETWORKS, build, describe
from edumaster_ml.training.trainer import prepare, to_tensors


@pytest.fixture(scope="module")
def ds():
    return load_dataset("demo-v1")


def test_dataset_reproducible_checksum(tmp_path):
    a = build_dataset("repro", seed=7, out_dir=tmp_path / "a")
    b = build_dataset("repro", seed=7, out_dir=tmp_path / "b")
    assert a["checksum"] == b["checksum"], "el pipeline debe reconstruir el mismo dataset desde su versión"


def test_quality_gates(ds):
    _, m = ds
    q = m["quality"]
    assert q["completeness_critical"] >= 0.98
    assert q["duplicates_after"] == 0
    assert q["duplicates_removed"] > 0 and q["quarantined_rows"] > 0
    assert m["label"] == "DEMO"


def test_no_temporal_leakage(ds):
    arr, _ = ds
    assert arr["x_seq"].shape[1] == SEQ_WEEKS_OBSERVED, "solo semanas observadas antes del corte"
    split = arr["split"]
    assert set(np.unique(split)) == {"train", "validation", "test"}


@pytest.mark.parametrize("key", list(NETWORKS))
def test_forward_loss_and_topology(ds, key):
    arr, _ = ds
    arr, _, _ = prepare(arr)
    t = to_tensors(arr, arr["split"] == "validation")
    b = {k: v[:16] for k, v in t.items()}
    m = build(key)
    loss, parts = m.loss(b)
    assert torch.isfinite(loss)
    loss.backward()
    acts = {}
    m.eval(); m(b, acts=acts)
    g = describe(m)
    ids = {l["id"] for l in g["layers"]}
    assert all(e["from"] in ids and e["to"] in ids for e in g["edges"])
    assert any(l["kind"] == "output" for l in g["layers"])
    assert g["params_total"] == sum(p.numel() for p in m.parameters())


def test_exactly_five_networks():
    assert len(NETWORKS) == 5

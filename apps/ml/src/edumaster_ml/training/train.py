"""CLI: python -m edumaster_ml.training.train --network edumaster_mtl --config configs/edumaster_mtl.yaml"""
from __future__ import annotations

import argparse
import json

import yaml

from ..models.networks import NETWORKS
from .trainer import train_network


def main() -> None:
    ap = argparse.ArgumentParser(description="Entrena una red de EduMaster.ai")
    ap.add_argument("--network", choices=[*NETWORKS, "all"], default="all")
    ap.add_argument("--config", default=None, help="YAML de hiperparámetros")
    args = ap.parse_args()
    params = yaml.safe_load(open(args.config)) if args.config else {}
    keys = list(NETWORKS) if args.network == "all" else [args.network]
    for k in keys:
        def show(e, k=k):
            if "epoch" in e and "train_loss" in e:
                print(f"[{k}] época {e['epoch']:>3} loss={e['train_loss']:.4f} val_loss={e['val_loss']:.4f} val={e['val_metric']:.4f}")
            elif e.get("message"):
                print(f"[{k}] {e['message']}")
        meta = train_network(k, params, progress=show)
        print(json.dumps({"key": k, "version": meta["version"], "primary": meta["primary"], "baseline": meta["baseline_primary"], "beats_baseline": meta["beats_baseline"]}))


if __name__ == "__main__":
    main()

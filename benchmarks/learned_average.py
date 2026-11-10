"""Average laplace++ checkpoints along one training path (#297).

With a constant learning rate, prequential training keeps drifting toward the
most recent series, so any single snapshot carries that noise: on monthly, the
12,000-series snapshot scored below the 9,000-series one. Averaging the
weights of several snapshots from the same run (stochastic weight averaging,
applied after the fact) cancels most of that drift. All snapshots must come
from one lineage (same architecture, sequential), which these do.

    LA_IN="a.pt b.pt c.pt" LA_OUT=avg.pt PYTHONPATH=src:benchmarks python benchmarks/learned_average.py
"""
from __future__ import annotations

import os
import sys

import torch


def main():
    paths = os.environ["LA_IN"].split()
    out = os.environ["LA_OUT"]
    cks = [torch.load(p, map_location="cpu", weights_only=False) for p in paths]
    sd0 = cks[0]["state_dict"]
    avg = {}
    for k, v in sd0.items():
        if torch.is_tensor(v) and v.is_floating_point():
            avg[k] = sum(c["state_dict"][k] for c in cks) / len(cks)
        else:
            avg[k] = v
    meta = {k: cks[-1].get(k) for k in ("k", "pi_lap", "corpus", "window", "lr")}
    torch.save({"state_dict": avg, **meta, "averaged_from": paths, "epochs": 1, "done": 0, "history": []}, out)
    print(f"[average] {len(paths)} checkpoints -> {out}")


if __name__ == "__main__":
    sys.exit(main())

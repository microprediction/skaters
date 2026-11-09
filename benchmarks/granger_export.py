"""Export a trained laplace++ checkpoint (skaters.torch.learned) as a granger
parameter file (skaters/granger_params/<frequency>.json) for the pure-Python,
Rust, JavaScript and R ports.

    GE_CKPT=benchmarks/learned_ckpt/monthly_k1_swa5.pt GE_FREQ=monthly \
      PYTHONPATH=src:benchmarks .venv-kumo/bin/python benchmarks/granger_export.py

The file holds the pool spec with every trained value substituted (the chain of
named transforms per candidate, fixed settings such as periods kept), the
ensemble's learning rate, forgetting rate, complexity penalty and prior log
weights, the terminal leaf's eta and scale rate, the gate's two layers, the
mixture prior, and the source checkpoint's sha256.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import os
import time

import torch

from skaters.torch.learned import LearnedLaplace
from skaters.torch.pool import pool_spec
import skaters.transform as T

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CKPT = os.environ["GE_CKPT"]
FREQ = os.environ.get("GE_FREQ", "monthly")
OUT = os.environ.get("GE_OUT", os.path.join(ROOT, "src", "skaters", "granger_params", f"{FREQ}.json"))


def _f(t):
    return float(t.detach()) if torch.is_tensor(t) else float(t)


def main():
    ck = torch.load(CKPT, map_location="cpu", weights_only=False)
    k = int(ck.get("k", 1))
    if k != 1:
        raise SystemExit("granger is exported at horizon 1 only")
    m = LearnedLaplace(k=1, pi_lap=float(ck.get("pi_lap", 0.25)))
    m.load_state_dict(ck["state_dict"])
    m.eval()
    trunk = m.trunks[0]
    cands = []
    for (chain, depth), mods in zip(pool_spec(1), trunk.candidate_modules):
        out = []
        for (name, kw), mod in zip(chain, mods):
            # every argument explicit (defaults included) so no port re-derives Python's defaults
            sig = inspect.signature(getattr(T, name))
            kw = {**{a: v.default for a, v in sig.parameters.items() if v.default is not inspect._empty}, **kw}
            for pname, p in mod.named_parameters(recurse=False):
                kw[pname] = _f(p)
            out.append([name, kw])
        cands.append({"chain": out, "depth": int(depth)})
    tl = trunk.tleaf_modules[0]
    g = m.gates[0]
    P = {
        "granger_format": 1,
        "frequency": FREQ,
        "k": 1,
        "pi_lap": float(ck.get("pi_lap", 0.25)),
        "trunk": {"learning_rate": _f(trunk.learning_rate), "complexity_penalty": _f(trunk.complexity_penalty),
                  "forget": _f(trunk.forget), "prior_log_weights": [_f(v) for v in trunk.prior_log_weights]},
        "tleaf": {"eta": _f(tl.eta), "scale_alpha": _f(tl.scale_alpha)},
        "candidates": cands,
        "gate": {"l1_weight": g.l1.weight.detach().tolist(), "l1_bias": g.l1.bias.detach().tolist(),
                 "l2_weight": g.l2.weight.detach().tolist(), "l2_bias": g.l2.bias.detach().tolist()},
        "source": {"checkpoint": os.path.basename(CKPT),
                   "sha256": hashlib.sha256(open(CKPT, "rb").read()).hexdigest(),
                   "trained_series": ck.get("n_series"), "exported": time.strftime("%Y-%m-%d")},
    }
    # the same file ships with the Python package, the Rust crate and the JS
    # package (R and Julia keep their own copies; see their repositories)
    outs = [OUT]
    if "GE_OUT" not in os.environ:
        outs += [os.path.join(ROOT, "rust", "params", f"{FREQ}.json"),
                 os.path.join(ROOT, "docs", "js", "skaters", "granger_params", f"{FREQ}.json")]
    for o in outs:
        os.makedirs(os.path.dirname(o), exist_ok=True)
        with open(o, "w") as fh:
            json.dump(P, fh, indent=1)
    n_vals = (len(P["trunk"]["prior_log_weights"]) + 3 + 2
              + sum(len(kw) for c in cands for _, kw in c["chain"])
              + sum(len(r) for r in P["gate"]["l1_weight"]) + len(P["gate"]["l1_bias"])
              + sum(len(r) for r in P["gate"]["l2_weight"]) + len(P["gate"]["l2_bias"]))
    print(f"[granger_export] {CKPT} -> {', '.join(os.path.relpath(o, ROOT) for o in outs)} ({len(cands)} candidates, {n_vals} numbers incl. fixed settings)")


if __name__ == "__main__":
    main()

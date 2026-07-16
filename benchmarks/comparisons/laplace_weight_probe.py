"""Did laplace's ensemble identify m=24 on M4-Hourly? Probe the final log_w.

    PYTHONPATH=src python benchmarks/comparisons/laplace_weight_probe.py

Runs laplace over M4-Hourly and daily series, extracts the terminal ensemble's
final log-weights, and reports the mass on the period-24 seasonal candidates.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import corpus
from skaters.api import laplace, _build_candidates


def labels_k1():
    L = []
    L.append("leaf")
    L += [f"ema({a})" for a in [0.01, 0.05, 0.1, 0.3]]
    L.append("diff")
    L += [f"drift({a},{s})" for a, s in [(0.05, 0.01), (0.01, 0.002), (0.002, 0.001), (0.0005, 0.0002)]]
    L += [f"theta({a})" for a in [0.05, 0.1, 0.3]]
    L += ["ar(1)", "ar(2)"]
    L += [f"holt({a},{b})" for a, b in [(0.1, 0.02), (0.1, 0.05), (0.3, 0.1)]]
    L += [f"seas({p})" for p in [7, 12, 24]]
    L += [f"anchor({p})" for p in [7, 12, 24]]
    L += [f"seas({p})+ema({a})" for p in [7, 12, 24] for a in [0.05, 0.1]]
    L += [f"diff+ema({a})" for a in [0.05, 0.1, 0.3]]
    L += [f"std+ema({a})" for a in [0.05, 0.1]]
    L += [f"frac({d})" for d in [0.2, 0.4]]
    L += [f"drift+ema({ad},{ae})" for ad, _ in [(0.002, 0.001), (0.0005, 0.0002)] for ae in [0.05, 0.1]]
    L += ["drift+holt", "garch+ema", "power+ema"]
    L += [f"fastslow({sa},{t})" for sa in [0.02, 0.05]
          for t in ["ema.3", "ema.5", "holt", "ar1", "drift", "diff"]]
    L += [f"yj({lam})+{tx}" for lam in [0.0, 0.5] for tx in ["diff", "ema.1"]]
    return L


def find_log_w(obj):
    if isinstance(obj, dict):
        if "log_w" in obj:
            return obj["log_w"]
        for v in obj.values():
            r = find_log_w(v)
            if r is not None:
                return r
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            r = find_log_w(v)
            if r is not None:
                return r
    return None


LAB = labels_k1()
cands, _, _ = _build_candidates(1)
assert len(cands) == len(LAB), (len(cands), len(LAB))
SEAS24 = [i for i, l in enumerate(LAB) if l.startswith("seas(24)")]
SEAS_ANY = [i for i, l in enumerate(LAB) if l.startswith("seas(")]


def probe(ch):
    f = laplace(1)
    state = None
    for y in ch[-1200:]:
        _, state = f(y, state)
    lw = find_log_w(state)
    assert lw is not None and len(lw) == len(LAB), (lw is None, len(lw or []))
    mx = max(lw)
    w = [math.exp(v - mx) for v in lw]
    tot = sum(w)
    w = [v / tot for v in w]
    top = max(range(len(w)), key=lambda i: w[i])
    return (sum(w[i] for i in SEAS24), sum(w[i] for i in SEAS_ANY), LAB[top], w[top])


def run_arm(arm, n_series):
    rows = []
    for sid, _, ch in corpus.iter_arm(arm):
        rows.append((sid, probe(ch)))
        if len(rows) >= n_series:
            break
    w24s = sorted(r[1][0] for r in rows)
    n = len(w24s)
    med = w24s[n // 2]
    print(f"[{arm}] {n} series: weight on seas(24)* median {med:.3f}  "
          f"q25 {w24s[n//4]:.3f}  q75 {w24s[3*n//4]:.3f}  "
          f">0.5 on {sum(1 for v in w24s if v > 0.5)}/{n}  "
          f">0.2 on {sum(1 for v in w24s if v > 0.2)}/{n}")
    tops = {}
    for _, (_, _, tl, _) in rows:
        tops[tl] = tops.get(tl, 0) + 1
    print(f"  top-weighted candidate counts: "
          f"{sorted(tops.items(), key=lambda kv: -kv[1])[:6]}")


run_arm("m4-hourly", 40)
run_arm("daily", 30)

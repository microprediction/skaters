"""Fresh monthly FRED training data for laplace++ (#297): the cached series no
corpus uses yet, leak-checked against the held-out monthly half.

The local FRED cache holds ~220k series; the canonical corpora use ~72k of them.
This keeps the unused MONTHLY series (median observation gap 28-31 days) with
at least FX_MINOBS observations, whose family is on the TRAIN side of the
family split, and then drops any candidate whose monthly changes correlate
above FX_MAX in absolute value with any held-out (valid-half) monthly series
on at least FX_OVERLAP common months. Correlations are exact Pearson on the
common months, computed for all pairs at once with masked matrix products
(each series z-scored first; Pearson is invariant to that).

Changes follow fred._to_changes (log-difference when strictly positive, else
first difference). The survivors are shuffled and written round-robin into
FX_SHARDS shard corpora, for sharded training runs whose weights are averaged.

    PYTHONPATH=src:benchmarks python benchmarks/fred_extra_corpus.py
    ... writes benchmarks/preds/_corpus_monthly-fx{0..N-1}.jsonl and
        benchmarks/fred_extra_corpus.tsv (every dropped candidate, partner, r)
"""
from __future__ import annotations

import datetime as dt
import json
import os
import random
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fred  # noqa: E402
import run_arm as ra  # noqa: E402
from learned_split import split_of  # noqa: E402

PREDS = os.path.join(HERE, "preds")
MINOBS = int(os.environ.get("FX_MINOBS", 61))
MAXR = float(os.environ.get("FX_MAX", 0.5))
OVERLAP = int(os.environ.get("FX_OVERLAP", 60))
SHARDS = int(os.environ.get("FX_SHARDS", 12))
CHUNK = 2000


def used_ids():
    out = set()
    for f in os.listdir(PREDS):
        if f.startswith("_corpus_") and f.endswith(".jsonl"):
            for line in open(os.path.join(PREDS, f)):
                out.add(json.loads(line)["sid"].split(":")[-1])
    return out


def monthly_changes(levels):
    """{month index: change}, or None unless the series is monthly."""
    if len(levels) < 3:
        return None
    d = [dt.date.fromisoformat(x) for x, _ in levels]
    gaps = sorted((b - a).days for a, b in zip(d[:-1], d[1:]))
    if not 28 <= gaps[len(gaps) // 2] <= 31:
        return None
    ch = fred._to_changes(levels)
    return {d[i + 1].year * 12 + d[i + 1].month - 1: c for i, c in enumerate(ch)
            if np.isfinite(c)}


def to_matrix(rows, m0, m1):
    """rows of {month: change} -> z-scored values (NaN-free) and 0/1 mask."""
    X = np.zeros((len(rows), m1 - m0), dtype=np.float64)
    M = np.zeros_like(X)
    for i, r in enumerate(rows):
        idx = np.fromiter((k - m0 for k in r), dtype=np.int64)
        v = np.fromiter(r.values(), dtype=np.float64)
        s = v.std()
        v = (v - v.mean()) / (s if s > 0 else 1.0)
        X[i, idx] = v
        M[i, idx] = 1.0
    return X, M


def main():
    used = used_ids()
    valid = []
    for sid, title, _ in ra.iter_series("monthly"):
        if split_of(sid) == "valid" and ra.regime(title) == "econ":
            r = monthly_changes(fred._load_levels(sid))
            if r and len(r) >= OVERLAP:
                valid.append((sid, r))
    cands = []
    for f in os.listdir(fred._CACHE):
        if not f.endswith(".csv"):
            continue
        sid = f[:-4]
        if sid in used or split_of(sid) != "train":
            continue
        lv = fred._load_levels(sid)
        if len(lv) < MINOBS:
            continue
        r = monthly_changes(lv)
        if r and len(r) >= MINOBS - 1:
            cands.append((sid, r))
    print(f"[fx] {len(cands)} unused train-family monthly candidates x {len(valid)} held-out monthly series", flush=True)

    allm = [k for _, r in valid + cands for k in r]
    m0, m1 = min(allm), max(allm) + 1
    V, MV = to_matrix([r for _, r in valid], m0, m1)
    V2 = V * V
    worst = np.zeros(len(cands)); partner = np.full(len(cands), -1)
    for a in range(0, len(cands), CHUNK):
        X, MX = to_matrix([r for _, r in cands[a:a + CHUNK]], m0, m1)
        N = MX @ MV.T
        Sx, Sy, Sxy = X @ MV.T, MX @ V.T, X @ V.T
        Sxx, Syy = (X * X) @ MV.T, MX @ V2.T
        with np.errstate(divide="ignore", invalid="ignore"):
            cov = Sxy - Sx * Sy / N
            den = np.sqrt((Sxx - Sx * Sx / N) * (Syy - Sy * Sy / N))
            R = np.where((N >= OVERLAP) & (den > 1e-12), cov / den, 0.0)
        j = np.abs(R).argmax(axis=1)
        worst[a:a + len(X)] = R[np.arange(len(X)), j]
        partner[a:a + len(X)] = j
        print(f"[fx] checked {min(a + CHUNK, len(cands))}/{len(cands)}", flush=True)

    keep = [c for c, w in zip(cands, worst) if abs(w) <= MAXR]
    with open(os.path.join(HERE, "fred_extra_corpus.tsv"), "w") as fh:
        fh.write("candidate\theld_out_partner\tr\n")
        for (sid, _), w, p in zip(cands, worst, partner):
            if abs(w) > MAXR:
                fh.write(f"{sid}\t{valid[p][0]}\t{w:+.3f}\n")
    random.Random(0).shuffle(keep)
    for s in range(SHARDS):
        out = os.path.join(PREDS, f"_corpus_monthly-fx{s}.jsonl")
        with open(out + ".tmp", "w") as fh:
            for sid, r in keep[s::SHARDS]:
                fh.write(json.dumps({"sid": f"fx:{sid}", "title": "",
                                     "ch": [r[k] for k in sorted(r)]}) + "\n")
        os.replace(out + ".tmp", out)
    print(f"[fx] kept {len(keep)}, dropped {len(cands) - len(keep)} (|r| > {MAXR} on >= {OVERLAP} months); "
          f"{SHARDS} shards of ~{len(keep) // SHARDS}", flush=True)


if __name__ == "__main__":
    main()

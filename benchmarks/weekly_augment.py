"""Extra weekly TRAINING data for laplace++ from the daily corpus, leak-checked.

FRED's weekly tag is exhausted: 3,631 series, all qualifying ones already in the
weekly corpus. The daily corpus holds ~10,900 series; resampled to weekly (the
last observation of each week ending Friday) they are more weekly training
series. The risk is leakage: many weekly FRED series are the weekly version of
a rate or index we also hold daily, under a different id, and some of those
weekly ids sit in the held-out half of the family split. So every candidate is
correlated, over overlapping weeks, against every held-out weekly series, and
dropped if any |correlation| exceeds 0.9 on at least 104 common weeks. Price
series are excluded as everywhere else. The derived ids are "d2w:<daily id>"
and never appear in validation.

    PYTHONPATH=src:benchmarks python benchmarks/weekly_augment.py
    ... writes benchmarks/preds/_corpus_weekly-aug.jsonl and a leak report
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fred  # noqa: E402
import fred_universe as fu  # noqa: E402
import run_arm as ra  # noqa: E402
from learned_split import split_of  # noqa: E402

PREDS = os.path.join(HERE, "preds")
OUT = os.path.join(PREDS, "_corpus_weekly-aug.jsonl")
CORR_MAX, MIN_OVERLAP, MIN_CHANGES = 0.9, 104, 300
PRICE = {"equity", "fx", "commodity"}


def week_end(d):
    d = dt.date.fromisoformat(d)
    return d + dt.timedelta(days=(4 - d.weekday()) % 7)      # the Friday of its week


def weekly_levels(levels):
    last = {}
    for d, v in levels:
        last[week_end(d)] = v                                 # last observation wins
    return sorted(last.items())


def weekly_changes(levels):
    """[(week, change)] with the same rule as fred._to_changes (log if positive)."""
    if len(levels) < 10:
        return []
    pos = all(v > 0 for _, v in levels)
    return [(b[0], (math.log(b[1]) - math.log(a[1])) if pos else (b[1] - a[1]))
            for a, b in zip(levels[:-1], levels[1:])]


def matrix(series, index):
    """Columns standardized over their own observed weeks, NaN filled with 0,
    plus the observed mask; the dot product of two columns over the shared mask
    divided by the overlap approximates their correlation on common weeks."""
    pos = {w: i for i, w in enumerate(index)}
    X = np.zeros((len(index), len(series)))
    M = np.zeros_like(X)
    for j, chs in enumerate(series):
        rows = [(pos[w], v) for w, v in chs if w in pos and math.isfinite(v)]
        if len(rows) < 3:
            continue
        idx = np.array([r[0] for r in rows]); val = np.array([r[1] for r in rows])
        sd = val.std()
        if sd <= 0:
            continue
        X[idx, j] = (val - val.mean()) / sd
        M[idx, j] = 1.0
    return X, M


def main():
    # held-out weekly series with their dates (from the level cache)
    valid = []
    for sid, title, ch in ra.iter_series("weekly"):
        if split_of(sid) == "valid":
            lv = fred._load_levels(sid) if os.path.exists(os.path.join(fred._CACHE, f"{sid}.csv")) else []
            if lv:
                valid.append((sid, weekly_changes(weekly_levels(lv))))
    print(f"[augment] held-out weekly series with dates: {len(valid)}", flush=True)
    # daily candidates, non-price
    cands = []
    for line in open(os.path.join(PREDS, "_corpus_daily.jsonl")):
        r = json.loads(line)
        if fu.asset_class(r["title"] or "") in PRICE:
            continue
        lv = fred._load_levels(r["sid"]) if os.path.exists(os.path.join(fred._CACHE, f"{r['sid']}.csv")) else []
        wch = weekly_changes(weekly_levels(lv)) if lv else []
        if len(wch) >= MIN_CHANGES:
            cands.append((r["sid"], r["title"], wch))
    print(f"[augment] daily non-price candidates with >= {MIN_CHANGES} weekly changes: {len(cands)}", flush=True)
    index = sorted({w for _, chs in valid for w, _ in chs} | {w for _, _, chs in cands for w, _ in chs})
    Xv, Mv = matrix([chs for _, chs in valid], index)
    Xc, Mc = matrix([chs for _, _, chs in cands], index)
    overlap = Mc.T @ Mv
    corr = (Xc.T @ Xv) / np.maximum(overlap, 1.0)
    bad = (np.abs(corr) > CORR_MAX) & (overlap >= MIN_OVERLAP)
    drop = bad.any(axis=1)
    report = []
    kept = 0
    with open(OUT + ".tmp", "w") as fh:
        for j, (sid, title, chs) in enumerate(cands):
            if drop[j]:
                k = int(np.argmax(np.where(bad[j], np.abs(corr[j]), 0)))
                report.append(f"{sid}\t{valid[k][0]}\t{corr[j, k]:+.3f}\t{int(overlap[j, k])}")
                continue
            fh.write(json.dumps({"sid": f"d2w:{sid}", "title": title, "ch": [float(v) for _, v in chs]}) + "\n")
            kept += 1
    os.replace(OUT + ".tmp", OUT)
    with open(os.path.join(HERE, "weekly_augment_dropped.tsv"), "w") as fh:
        fh.write("daily_id\theld_out_weekly_id\tcorr\toverlap_weeks\n" + "\n".join(report) + "\n")
    print(f"[augment] dropped {int(drop.sum())} (twin of a held-out weekly series), kept {kept} -> {OUT}")


if __name__ == "__main__":
    main()

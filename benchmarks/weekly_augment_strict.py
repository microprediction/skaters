"""Strict leak check for the daily->weekly training data (supersedes the 0.9 cutoff).

Weekly FRED series are usually weekly AVERAGES of a daily rate, while
weekly_augment.py samples the daily series at the END of each week. Changes of
a weekly average and of an end-of-week value correlate only ~0.65-0.69 even for
the same rate (DGS10 vs WGS10YR: 0.689 on 1,122 weeks), so a 0.9 cutoff on
exact correlations misses true twins. This check computes the exact Pearson
correlation on common weeks of every candidate against every held-out weekly
series, and also against the held-out series' 2-week moving sum (which absorbs
the averaging lag), and drops a candidate if either exceeds STRICT_MAX on at
least 104 common weeks.

    PYTHONPATH=src:benchmarks python benchmarks/weekly_augment_strict.py
    ... writes _corpus_weekly-augc.jsonl (clean), weekly_augment_strict.tsv
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fred  # noqa: E402
import fred_universe as fu  # noqa: E402
import run_arm as ra  # noqa: E402
from learned_split import split_of  # noqa: E402
from weekly_augment import MIN_CHANGES, MIN_OVERLAP, PREDS, PRICE, weekly_changes, weekly_levels  # noqa: E402

STRICT_MAX = float(os.environ.get("STRICT_MAX", 0.5))
OUT = os.path.join(PREDS, "_corpus_weekly-augc.jsonl")


def main():
    valid = []
    for sid, title, ch in ra.iter_series("weekly"):
        if split_of(sid) == "valid" and os.path.exists(os.path.join(fred._CACHE, f"{sid}.csv")):
            d = dict(weekly_changes(weekly_levels(fred._load_levels(sid))))
            ws = sorted(d)
            # 2-week moving sum, only over two consecutive weeks (a missing week is a gap)
            sm = {ws[i]: d[ws[i]] + d[ws[i - 1]] for i in range(1, len(ws))
                  if (dt.date.fromisoformat(str(ws[i])) - dt.date.fromisoformat(str(ws[i - 1]))).days == 7}
            valid.append((sid, d, sm))
    cands = []
    for line in open(os.path.join(PREDS, "_corpus_daily.jsonl")):
        r = json.loads(line)
        if fu.asset_class(r["title"] or "") in PRICE:
            continue
        if not os.path.exists(os.path.join(fred._CACHE, f"{r['sid']}.csv")):
            continue
        d = dict(weekly_changes(weekly_levels(fred._load_levels(r["sid"]))))
        if len(d) >= MIN_CHANGES:
            cands.append((r["sid"], r["title"], d))
    print(f"[strict] {len(cands)} candidates x {len(valid)} held-out weekly series, cutoff {STRICT_MAX}", flush=True)
    kept, rows = [], []
    for k, (did, title, cd) in enumerate(cands):
        worst, partner = 0.0, None
        for vid, vd, vsm in valid:
            for ref in (vd, vsm):
                common = cd.keys() & ref.keys()
                if len(common) < MIN_OVERLAP:
                    continue
                ws = sorted(common)
                a = np.array([cd[w] for w in ws]); b = np.array([ref[w] for w in ws])
                if a.std() <= 0 or b.std() <= 0:
                    continue
                c = float(np.corrcoef(a, b)[0, 1])
                if abs(c) > abs(worst):
                    worst, partner = c, vid
        rows.append(f"{did}\t{partner}\t{worst:+.3f}")
        if abs(worst) <= STRICT_MAX:
            kept.append((did, title, cd))
        if (k + 1) % 200 == 0:
            print(f"[strict] {k + 1}/{len(cands)}: kept {len(kept)}", flush=True)
    with open(OUT + ".tmp", "w") as fh:
        for did, title, cd in kept:
            fh.write(json.dumps({"sid": f"d2w:{did}", "title": title,
                                 "ch": [float(v) for _, v in sorted(cd.items())]}) + "\n")
    os.replace(OUT + ".tmp", OUT)
    with open(os.path.join(HERE, "weekly_augment_strict.tsv"), "w") as fh:
        fh.write("daily_id\tclosest_held_out_weekly_id\tmax_abs_corr\n" + "\n".join(rows) + "\n")
    print(f"[strict] kept {len(kept)} of {len(cands)} -> {OUT}")


if __name__ == "__main__":
    main()

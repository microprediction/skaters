"""Recover daily->weekly candidates the first leak check dropped too eagerly.

weekly_augment.py flags a candidate when an approximate correlation (columns
standardized over their own full history, then averaged over common weeks)
exceeds 0.9 against any held-out weekly series. That approximation can exceed 1
and is conservative. Here every candidate it dropped is re-checked against
EVERY held-out weekly series with the exact Pearson correlation on the common
weeks; a candidate is kept only if no exact |correlation| exceeds 0.9 on at
least 104 common weeks. Kept series go to a separate corpus, weekly-aug2, so
they are fresh training data for a run that already saw weekly-aug.

    PYTHONPATH=src:benchmarks python benchmarks/weekly_augment_recheck.py
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fred  # noqa: E402
import run_arm as ra  # noqa: E402
from learned_split import split_of  # noqa: E402
from weekly_augment import CORR_MAX, MIN_OVERLAP, PREDS, weekly_changes, weekly_levels  # noqa: E402

OUT = os.path.join(PREDS, "_corpus_weekly-aug2.jsonl")


def series_dict(levels):
    return dict(weekly_changes(weekly_levels(levels)))


def main():
    dropped = [l.split("\t")[0] for l in open(os.path.join(HERE, "weekly_augment_dropped.tsv")).read().splitlines()[1:] if l]
    titles = {}
    for line in open(os.path.join(PREDS, "_corpus_daily.jsonl")):
        r = json.loads(line)
        titles[r["sid"]] = r["title"]
    valid = []
    for sid, title, ch in ra.iter_series("weekly"):
        if split_of(sid) == "valid" and os.path.exists(os.path.join(fred._CACHE, f"{sid}.csv")):
            valid.append((sid, series_dict(fred._load_levels(sid))))
    kept, twins = [], []
    for k, did in enumerate(dropped):
        cd = series_dict(fred._load_levels(did))
        worst, partner = 0.0, None
        for vid, vd in valid:
            common = cd.keys() & vd.keys()
            if len(common) < MIN_OVERLAP:
                continue
            ws = sorted(common)
            a = np.array([cd[w] for w in ws]); b = np.array([vd[w] for w in ws])
            if a.std() <= 0 or b.std() <= 0:
                continue
            c = float(np.corrcoef(a, b)[0, 1])
            if abs(c) > abs(worst):
                worst, partner = c, vid
        if abs(worst) > CORR_MAX:
            twins.append(f"{did}\t{partner}\t{worst:+.3f}")
        else:
            kept.append((did, cd))
        if (k + 1) % 100 == 0:
            print(f"[recheck] {k + 1}/{len(dropped)}: kept {len(kept)}, true twins {len(twins)}", flush=True)
    with open(OUT + ".tmp", "w") as fh:
        for did, cd in kept:
            fh.write(json.dumps({"sid": f"d2w:{did}", "title": titles.get(did, ""),
                                 "ch": [float(v) for _, v in sorted(cd.items())]}) + "\n")
    os.replace(OUT + ".tmp", OUT)
    with open(os.path.join(HERE, "weekly_augment_twins.tsv"), "w") as fh:
        fh.write("daily_id\theld_out_weekly_id\texact_corr\n" + "\n".join(twins) + "\n")
    print(f"[recheck] of {len(dropped)} dropped: {len(twins)} true twins, {len(kept)} recovered -> {OUT}")


if __name__ == "__main__":
    main()

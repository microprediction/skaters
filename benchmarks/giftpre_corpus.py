"""Training corpora for laplace++ from the GIFT-Eval pretraining corpus (#297).

Salesforce/GiftEvalPretrain is built to share no data with the GIFT-Eval test
sets, so a model trained on it can be scored on GIFT-Eval cleanly. Here its
frequency-matched subsets become extra laplace++ TRAINING corpora (never
validated on). fred_md is excluded: it overlaps our FRED panel. Each series is
turned into changes by the same rule as fred._to_changes (log-difference when
strictly positive, else first difference), NaNs dropped. The very large Kaggle
web-traffic set is capped so it cannot swamp the economic training series.

    PYTHONPATH=src:benchmarks python benchmarks/giftpre_corpus.py
    ... writes benchmarks/preds/_corpus_{monthly,weekly,hourly}-gp.jsonl
"""
from __future__ import annotations

import json
import math
import os
import random

import datasets

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "data", "giftpre")
PREDS = os.path.join(HERE, "preds")
MIN_CHANGES = 48
CAP = {"kaggle_web_traffic_weekly": 3000}
GROUPS = {
    "monthly-gp": ["m1_monthly", "monash_m3_monthly", "tourism_monthly", "cif_2016_12"],
    "weekly-gp": ["nn5_weekly", "traffic_weekly", "kaggle_web_traffic_weekly"],
    "hourly-gp": ["traffic_hourly", "uber_tlc_hourly"],
}


def changes(vals):
    vals = [float(v) for v in vals if v is not None and math.isfinite(float(v))]
    if len(vals) < 10:
        return []
    if all(v > 0 for v in vals):
        return [math.log(b) - math.log(a) for a, b in zip(vals[:-1], vals[1:])]
    return [b - a for a, b in zip(vals[:-1], vals[1:])]


def main():
    for corpus, subs in GROUPS.items():
        out = os.path.join(PREDS, f"_corpus_{corpus}.jsonl")
        n = 0
        with open(out + ".tmp", "w") as fh:
            for sub in subs:
                ds = datasets.load_from_disk(os.path.join(SRC, sub))
                idx = list(range(len(ds)))
                if sub in CAP and len(idx) > CAP[sub]:
                    idx = sorted(random.Random(0).sample(idx, CAP[sub]))
                k = 0
                for i in idx:
                    r = ds[i]
                    tgt = r["target"]
                    if tgt and isinstance(tgt[0], (list, tuple)):     # multivariate: one series per variate
                        rows = [list(x) for x in zip(*tgt)] if len(tgt) > len(tgt[0]) else [list(x) for x in tgt]
                    else:
                        rows = [tgt]
                    for j, vals in enumerate(rows):
                        ch = changes(vals)
                        if len(ch) >= MIN_CHANGES:
                            fh.write(json.dumps({"sid": f"gp:{sub}:{r['item_id']}:{j}",
                                                 "title": f"giftpre {sub}", "ch": ch}) + "\n")
                            k += 1
                print(f"[giftpre] {corpus}: {sub} -> {k} series", flush=True)
                n += k
        os.replace(out + ".tmp", out)
        print(f"[giftpre] {corpus}: {n} series -> {out}", flush=True)


if __name__ == "__main__":
    main()

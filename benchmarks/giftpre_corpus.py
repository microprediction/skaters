"""Training corpora for laplace++ from the GIFT-Eval pretraining corpus (#297).

Salesforce/GiftEvalPretrain is built to share no data with the GIFT-Eval test
sets, so a model trained on it can be scored on GIFT-Eval cleanly. Here its
frequency-matched subsets become extra laplace++ TRAINING corpora (never
validated on). fred_md is excluded: it overlaps our FRED panel. Each series is
turned into changes by the same rule as fred._to_changes (log-difference when
strictly positive, else first difference), never across a missing value. The very large Kaggle
web-traffic set is capped so it cannot swamp the economic training series.

    PYTHONPATH=src:benchmarks python benchmarks/giftpre_corpus.py
    ... writes benchmarks/preds/_corpus_{monthly,weekly,hourly,daily}-gp.jsonl and _corpus_weekly-gp2.jsonl
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
CAP = {"kaggle_web_traffic_weekly": 3000, "m5": 2000, "wiki-rolling_nips": 3000, "weather": 3000,
       "subseasonal_precip": 2000}
GROUPS = {
    "monthly-gp": ["m1_monthly", "monash_m3_monthly", "tourism_monthly", "cif_2016_12"],
    "weekly-gp": ["nn5_weekly", "traffic_weekly", "kaggle_web_traffic_weekly"],
    "hourly-gp": ["traffic_hourly", "uber_tlc_hourly"],
    "daily-gp": ["m5", "wiki-rolling_nips", "weather", "subseasonal_precip", "favorita_transactions",
                 "nn5_daily_with_missing", "uber_tlc_daily", "covid_mobility", "bitcoin_with_missing",
                 "sunspot_with_missing", "vehicle_trips_with_missing"],
    "weekly-gp2": ["cdc_fluview_ilinet", "cdc_fluview_who_nrevss", "project_tycho"],
}
# GP_GROUPS=daily-gp,weekly-gp2 builds only those (default: all)
ONLY = [g for g in os.environ.get("GP_GROUPS", "").split(",") if g]


def changes(vals):
    """Changes between ADJACENT finite observations only: a missing value is a
    gap, never joined across (log-difference when every finite value is
    positive, else first difference)."""
    x = [float(v) if v is not None and math.isfinite(float(v)) else None for v in vals]
    fin = [v for v in x if v is not None]
    if len(fin) < 10:
        return []
    pos = all(v > 0 for v in fin)
    return [(math.log(b) - math.log(a)) if pos else (b - a)
            for a, b in zip(x[:-1], x[1:]) if a is not None and b is not None]


def main():
    os.makedirs(PREDS, exist_ok=True)
    for corpus, subs in GROUPS.items():
        if ONLY and corpus not in ONLY:
            continue
        out = os.path.join(PREDS, f"_corpus_{corpus}.jsonl")
        n = 0
        with open(out + ".tmp", "w") as fh:
            for sub in subs:
                ds = datasets.load_from_disk(os.path.join(SRC, sub))
                print(f"[giftpre] {sub}: {len(ds)} records, freq {ds[0].get('freq')}", flush=True)
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

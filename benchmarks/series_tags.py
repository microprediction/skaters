"""Tags for every series in the canonical corpora, from PRE-TEST history only.

The leaderboards can then be sliced by what kind of series it is. Each tag is
computed on the history the forecasters condition on before the scored window
(the last TEST changes never inform a tag), with the same characterization
the TabFM study pre-registered (tabfm_wide_study.characterize):

  martingality   lag-1 autocorrelation of changes: |rho1| < 0.05 is
                 "martingale", rho1 >= 0.05 "momentum", rho1 <= -0.05
                 "mean-reverting"
  repeats        share of adjacent equal changes (on a sticky series, runs
                 of zero change): < 5% "continuous", < 35% "mixed", else
                 "sticky"
  heavy tails    excess kurtosis of changes above 3
  vol clustering lag-1 autocorrelation of |changes| above 0.2
  seasonal       autocorrelation of changes at the frequency's natural period
                 (5 daily, 52 weekly, 12 monthly, 24 hourly) above 0.2

plus the descriptors the store already carries: frequency, regime (econ or
price), FRED family and title-keyword asset class.

    PYTHONPATH=src:benchmarks python benchmarks/series_tags.py
    ... writes benchmarks/series_tags.csv
"""
from __future__ import annotations

import csv
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import fred_universe as fu  # noqa: E402
import run_arm as ra  # noqa: E402
from tabfm_wide_study import characterize  # noqa: E402

CORPORA = ("daily", "weekly", "monthly", "m4-hourly")
PERIOD = {"daily": 5, "weekly": 52, "monthly": 12, "m4-hourly": 24}
TEST = ra.TEST
HIST = ra.aa.fs.HIST


def acf_at(a, lag):
    a = np.asarray(a, float)
    if len(a) <= lag + 2 or np.var(a) <= 0:
        return None
    x, y = a[:-lag], a[lag:]
    if np.var(x) <= 0 or np.var(y) <= 0:
        return None
    r = float(np.corrcoef(x, y)[0, 1])
    return r if math.isfinite(r) else None


def tags_for(corpus, ch):
    ch = [float(v) for v in ch[-HIST:]]
    pre = [v for v in ch[:-TEST] if math.isfinite(v)]
    rf, rho1, kurt, vcl = characterize(pre)
    seas = acf_at(pre, PERIOD[corpus])
    tags = []
    if rho1 is not None:
        tags.append("martingale" if abs(rho1) < 0.05 else "momentum" if rho1 >= 0.05 else "mean-reverting")
    tags.append("continuous" if rf < 0.05 else "mixed" if rf < 0.35 else "sticky")
    if kurt is not None and kurt > 3.0:
        tags.append("heavy tails")
    if vcl is not None and vcl > 0.2:
        tags.append("vol clustering")
    if seas is not None and seas > 0.2:
        tags.append("seasonal")
    return rf, rho1, kurt, vcl, seas, tags


def main():
    out = os.path.join(HERE, "series_tags.csv")
    n = 0
    with open(out, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["corpus", "series", "regime", "family", "asset_class",
                    "repeat_frac", "rho1", "excess_kurtosis", "vol_cluster", "seasonal_acf", "tags"])
        for corpus in CORPORA:
            for sid, title, ch in ra.iter_series(corpus):
                if len(ch[-HIST:]) < ra.MINLEN:
                    continue
                rf, rho1, kurt, vcl, seas, tags = tags_for(corpus, ch)
                f = lambda v: "" if v is None else f"{v:.4f}"
                w.writerow([corpus, sid, ra.regime(title), fu.family(sid), fu.asset_class(title),
                            f(rf), f(rho1), f(kurt), f(vcl), f(seas), ";".join(tags)])
                n += 1
            print(f"[series_tags] {corpus} done ({n} series so far)", flush=True)
    print(f"[series_tags] wrote {out}: {n} series")


if __name__ == "__main__":
    main()

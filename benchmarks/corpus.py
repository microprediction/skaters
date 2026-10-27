"""The benchmark corpus, in one place.

Every study draws its series from a named ARM defined here, so "which data was
this run on" always has a one-word answer. Arms are enumerated by fixed,
reproducible rules (FRED popularity ranking, or a public competition file) —
never hand-picked tickers. All arms forecast the one-step *change*
(fred._to_changes: first difference, log-difference for strictly-positive
levels).

  daily      FRED daily universe by popularity (fred_universe.enumerate_daily).
             Business-day observations: the week is m=5, the month m=21.
  weekly     FRED `weekly` tag by popularity, non-price, full history. m=52.
  monthly    FRED `monthly` tag by popularity, non-price, full history. m=12 —
             the annual cycle (NSA series carry real seasonality in changes).
  m4-hourly  The M4 competition hourly set (414 series, public CSV): the
             strongly-seasonal home turf of seasonal methods. m=24.

Frequency is verified per series from the cached dates (median day gap), not
trusted from the tag. Use iter_arm(name) -> yields (sid, title, changes).
"""
from __future__ import annotations
import csv
import io
import json
import os
import statistics
import urllib.request
from datetime import date

import fred

ARMS = {
    "daily":     dict(m=5,  gap=(0, 4),    min_changes=500, test=300),
    "weekly":    dict(m=52, gap=(5, 10),   min_changes=300, test=200),
    "monthly":   dict(m=12, gap=(25, 45),  min_changes=300, test=200),
    "m4-hourly": dict(m=24, gap=None,      min_changes=500, test=300),
    # Nulls with zero true forecastability (issue #250 review). Each copies the
    # length and title of a daily econ series, so any skill measured on them is
    # the baseline-estimation overhead at real lengths. perm-daily keeps each
    # series' marginal law and destroys its temporal order.
    "null-gauss":   dict(m=5, gap=None, min_changes=500, test=300),
    "null-t4":      dict(m=5, gap=None, min_changes=500, test=300),
    "null-laplace": dict(m=5, gap=None, min_changes=500, test=300),
    "perm-daily":   dict(m=5, gap=None, min_changes=500, test=300),
}
NULL_N = int(os.environ.get("NULL_N", 500))       # daily econ series each null copies

_M4_URL = ("https://raw.githubusercontent.com/Mcompetitions/M4-methods/"
           "master/Dataset/Train/Hourly-train.csv")
_M4_CACHE = os.path.join(fred._CACHE, "m4_hourly.csv")


def freq_gap(levels, k=13):
    """Median day-gap of the first k observations (frequency check)."""
    ds = [date.fromisoformat(d) for d, _ in levels[:k]]
    if len(ds) < 3:
        return None
    return statistics.median((b - a).days for a, b in zip(ds[:-1], ds[1:]))


def _iter_fred(arm, limit):
    lo, hi = ARMS[arm]["gap"]
    min_ch = ARMS[arm]["min_changes"]
    if arm == "daily":
        import fred_universe
        metas = fred_universe.enumerate_daily(limit)
    else:
        # tag-enumerated, non-price, FULL history (fetch_freq.py fetches these)
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        "comparisons"))
        import fetch_freq
        import fred_universe as fu
        metas = [s for s in fetch_freq.enumerate_tag(arm, limit)
                 if fu.asset_class(s.get("title", "")) not in fetch_freq.PRICE]
    n = 0
    for meta in metas:
        sid = meta["id"]
        path = os.path.join(fred._CACHE, f"{sid}.csv")
        levels = (fred._load_levels(sid) if os.path.exists(path) or arm == "daily"
                  else fred._fetch(sid, start="1900-01-01"))
        if levels and not os.path.exists(path) and len(levels) > 20:
            with open(path, "w") as f:
                for d, v in levels:
                    f.write(f"{d},{v}\n")
        if not levels:
            continue
        g = freq_gap(levels)
        if g is None or not (lo <= g <= hi):
            continue
        ch = fred._to_changes(levels)
        if len(ch) >= min_ch:
            n += 1
            yield sid, meta.get("title", ""), ch


def _iter_m4_hourly():
    min_ch = ARMS["m4-hourly"]["min_changes"]
    if not os.path.exists(_M4_CACHE):
        os.makedirs(fred._CACHE, exist_ok=True)
        with urllib.request.urlopen(_M4_URL, timeout=120) as r, \
                open(_M4_CACHE, "wb") as f:
            f.write(r.read())
    with open(_M4_CACHE, newline="") as f:
        for row in csv.reader(f):
            if not row or row[0] == "V1":
                continue
            sid = row[0].strip('"')
            vals = [float(v) for v in row[1:] if v not in ("", "NA")]
            levels = [(str(i), v) for i, v in enumerate(vals)]
            ch = fred._to_changes(levels)
            if len(ch) >= min_ch:
                yield sid, "M4 hourly", ch


def _daily_econ(n):
    """First n daily econ series (offline cache if present), for the null arms."""
    import fred_universe as fu
    cache = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "preds", "_corpus_daily.jsonl")
    if os.path.exists(cache):
        rows = (json.loads(line) for line in open(cache))
        src = ((r["sid"], r["title"], r["ch"]) for r in rows)
    else:
        src = _iter_fred("daily", 4000)
    k = 0
    for sid, title, ch in src:
        if fu.asset_class(title or "") in ("equity", "fx", "commodity"):
            continue
        yield sid, title, ch
        k += 1
        if k >= n:
            return


def _iter_null(arm):
    import random
    import zlib
    for sid, title, ch in _daily_econ(NULL_N):
        g = random.Random(zlib.crc32(f"{arm}:{sid}".encode()))
        n = len(ch)
        if arm == "perm-daily":
            x = list(ch)
            g.shuffle(x)
        elif arm == "null-gauss":
            x = [g.gauss(0.0, 1.0) for _ in range(n)]
        elif arm == "null-t4":
            x = [g.gauss(0.0, 1.0) / (g.gammavariate(2.0, 2.0) / 4.0) ** 0.5 for _ in range(n)]
        else:
            x = [g.expovariate(1.0) - g.expovariate(1.0) for _ in range(n)]
        yield f"{arm}:{sid}", title, x


def iter_arm(arm, limit=1000):
    """Yield (sid, title, changes) for a named corpus arm."""
    if arm not in ARMS:
        raise KeyError(f"unknown arm {arm!r}; have {sorted(ARMS)}")
    if arm in ("null-gauss", "null-t4", "null-laplace", "perm-daily"):
        yield from _iter_null(arm)
    elif arm == "m4-hourly":
        yield from _iter_m4_hourly()
    else:
        yield from _iter_fred(arm, limit)


if __name__ == "__main__":
    import sys
    arm = sys.argv[1] if len(sys.argv) > 1 else "monthly"
    n = 0
    for sid, title, ch in iter_arm(arm, limit=int(os.environ.get("CORPUS_LIMIT", 50))):
        n += 1
        print(f"{sid:24s} n_changes={len(ch):5d}  {title[:60]}")
    print(f"[{arm}] {n} qualifying series")

# laplace vs. GARCH-t

**Opponent.** GARCH(1,1) with Student-t innovations — the classical heavy-tail /
volatility-clustering SOTA. Two forms: Python `arch` (`GARCH-t`) and R `rugarch`
(`GARCH-t-R@{5,25,100}`, quantiles straight from the fitted Student-t). rugarch
needs `install.packages("rugarch")`.

**Why it matters.** This is the **honest caveat** in the README: on price/returns
GARCH-t wins, and you should use it. This matchup is where we *expect* to lose on
its home turf (and on CRPS especially), and the point is to say so plainly rather
than hide it. Run it split by universe:

```bash
# non-price economic series (laplace's turf)
STUDY_EXCLUDE_PRICE=1 PYTHONPATH=src python benchmarks/comparisons/run_comparison.py \
    laplace-vs-garch GARCH-t R@25
# price/returns (GARCH-t's turf)
STUDY_ONLY_PRICE=1 PYTHONPATH=src python benchmarks/comparisons/run_comparison.py \
    laplace-vs-garch GARCH-t R@25
```

**Result** _(N=119 R-covered across the mixed universe, 167 continuous; still growing
overnight. The price/non-price split below is the honest full story and is still pending.)_

laplace **win-rate**:

| method | CRPS all/cont | LL all/cont | N |
|---|---|---|---|
| GARCH-t-R@25 | 53/50% | **82/81%** | 119 |

A cautionary tale about small N: on the *first* 4 scored series (all rates/FX/VIX — GARCH's
home turf) GARCH-t-R was beating laplace on CRPS. Across the fuller mixed universe (N=119)
that reverses — laplace wins ~82% on log-likelihood and is a coin-flip on CRPS, because most
of the universe is *not* price/returns. That's exactly why this matchup must be read split by
universe, not pooled:

```bash
STUDY_EXCLUDE_PRICE=1 ...   # non-price economic series — laplace's turf
STUDY_ONLY_PRICE=1   ...   # price/returns — GARCH-t's turf (expect to lose here, and say so)
```

The split run is still pending; the pooled number above already makes the honest point that
GARCH-t only wins on the price minority.

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

**Result.** _Pending the price/non-price split run._ `GARCH-t-R` (rugarch) is installed and
verified working (Student-t quantile predictive), but the only series scored so far are the
first cached ones — rates/FX/VIX, i.e. GARCH's *home turf* — where it beats laplace on CRPS
on a tiny N=4. Publishing that would be dishonestly cherry-picked in GARCH's favour; the
matchup only means something split by universe (`STUDY_EXCLUDE_PRICE=1` vs `STUDY_ONLY_PRICE=1`),
so it's deliberately left blank until that run.

# Selection-temperature study (skaters#213 / #215)
skaters 0.16.0, commit `ea52aa2`

Best-fixed eta: **eta0.25x** (eta=0.2). Best forget: **0.99**.

## Result

### regime-changey
| comparison | median dLL | frac improving | median dPIT_L1 |
|---|---|---|---|
| adaptive-eta vs best-fixed-eta (forget=1.0) | -0.0001 | 48.5% (367 series) | -0.0003 |
| adaptive-eta+forget vs best-fixed-eta (forget=1.0) | +0.0001 | 50.7% (367 series) | -0.0008 |
| adaptive-eta+forget vs the FULLY fixed optimum (eta=best, forget=best) -- does adaptation add anything beyond just fixing forget correctly? | -0.0031 | 37.9% (367 series) | +0.0001 |

### stationary
| comparison | median dLL | frac improving | median dPIT_L1 |
|---|---|---|---|
| adaptive-eta vs best-fixed-eta (forget=1.0) | +0.0000 | 50.0% (632 series) | +0.0000 |
| adaptive-eta+forget vs best-fixed-eta (forget=1.0) | -0.0023 | 44.6% (632 series) | -0.0004 |
| adaptive-eta+forget vs the FULLY fixed optimum (eta=best, forget=best) -- does adaptation add anything beyond just fixing forget correctly? | +0.0005 | 51.4% (632 series) | +0.0001 |

## Verdict

**Outcome 3: `forget` already subsumes it.** Against the eta-only fixed baseline (forget pinned at 1.0), adaptive-eta is statistically a coin flip in both strata (48.5%/50.7% and 50.0%/44.6% of series improve; median dLL within 0.0001-0.0023 nats either way). That alone would read as a tie. But the third row is the real test: once `forget` is set to its own optimum (0.99, found by arm 2 with no adaptation at all), adding adaptive eta on top does not help and on the regime-changey stratum -- precisely where the hypothesis predicted its biggest edge -- it **loses** (median dLL -0.0031, only 37.9% of series improve). The two proposed levers are not complementary; `forget`'s geometric discounting already captures the regime-adaptation adaptive eta was built to add, and does it more simply.

No ship. `terminal_leaf_ensemble(adaptive_temperature=True)` stays as opt-in, off by default; `forget=0.99` remains the mechanism doing the actual work in production `laplace`. One incidental finding worth a separate look: `eta=0.2` (0.25x the shipped 0.8) was the best-fixed point in this sweep at forget=1.0 -- not re-tested at forget=0.99 against the shipped eta=0.8, so this is not by itself a case to change the default, just a flag that the eta/forget interaction wasn't swept as a full grid.

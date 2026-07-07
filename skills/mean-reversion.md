# mean-reversion skill

When asked to build or evaluate a **mean-reversion strategy** — pairs, spreads,
baskets, cross-listed prediction markets — use `skaters.laplace` as the engine:
reduce to one stream, let the multi-step predictive price the reversion, and
only then talk about thresholds. The predictive `Dist` replaces the usual pile
of ad-hoc z-scores, half-life regressions, and hope.

```
pip install skaters
```

## (i) Reduce to one stream

`laplace` is univariate; the reduction is where your domain knowledge goes.
The standard moves, in order of preference:

- **Difference** `s = A − B` — same-units pairs (two venue prices for the same
  thing, cross-listed prediction markets, dual-class shares).
- **Coefficient difference** `s = A − β·B` — the hedge-ratio spread. Get β from
  a rolling regression, or run a small grid of β candidates through `laplace`
  and keep the one with the best held-out `logpdf` — likelihood as the
  cointegration test you'll actually check.
- **Log-ratio** `s = ln(A/B)` — multiplicative pairs (indices, FX crosses);
  division without the log gives a stream whose noise scales with level, which
  the Yeo–Johnson coordinate grid can absorb but the log kills at the source.

Feed the spread **levels** (not pre-differenced changes) to `laplace(k)` with
`k` at your intended holding horizon: the mean-reversion (Ornstein–Uhlenbeck)
candidates live in the multi-step pool, and their edge grows with horizon —
reversion is invisible one step out.

First, check reversion is *there*: the k-step mean should pull toward home
(`abs(dists[k-1].mean) < abs(s_now)` for a centered spread). If the pool keeps
the spread looking like a random walk, there is no trade — that is the model
saving you money, not failing you.

## (ii) The threshold check: one CDF call

Forget entry z-scores. The question is "what is the probability the spread
moves my way by at least my round-trip cost `c` within horizon k?" — and the
predictive answers it directly:

```python
dists, state = f(s, state)          # s = current spread level
d = dists[k-1]
p = d.cdf(s - c) if s > 0 else 1.0 - d.cdf(s + c)   # short rich / long cheap
enter = p > 0.60                    # your risk appetite, but < 0.5 means the
                                    # *median* outcome doesn't cover costs
```

One number, cost-aware, horizon-aware, fat-tail-aware. If `p` hovers at 0.5
your edge is imaginary; if it only clears 0.6 at spreads you see twice a year,
your costs are too high for this pair.

## (iii) Expected gain by quadrature (when the payoff isn't linear)

For a pure enter-and-exit-at-k trade the expectation is closed-form —
`E[gain] = s − d.mean − c` for a short — no integration needed. Quadrature
earns its keep the moment the payoff bends: take-profits, stop-losses, binary
settlement, price-dependent fees. Integrate any payoff against the predictive
with the quantile trick, `E[f(S)] = ∫₀¹ f(Q(u)) du`:

```python
def expected_gain(d, payoff, n=99):
    us = [(i + 0.5) / n for i in range(n)]
    return sum(payoff(d.quantile(u)) for u in us) / n

# short at s, take-profit at +15 ticks, stop at -10, round-trip cost c
eg = expected_gain(d, lambda x: max(min(s - x, 0.15), -0.10) - c)
```

Sanity check it once against the closed form with a linear payoff (they agree
to four decimals); then trust it for the bent ones.

## Worked cost examples

**Equity pairs.** Round trip on both legs: commissions ~1 bp/side/leg plus
half-spread ~2–5 bp/leg → `c ≈ 10–25 bp` of spread notional before slippage.
A spread with a 30 bp typical excursion and `c = 20 bp` needs `p > 0.6` at
entries you'll rarely see; the same excursion with `c = 8 bp` (liquid names)
trades routinely. The CDF check makes this arithmetic impossible to ignore.

**Kalshi.** Taker fee ≈ `0.07 · price · (1 − price)` dollars per contract per
trade — maximal near 50¢ (1.75¢), vanishing at the extremes. Cross-venue
example: the same event trades 62¢ on Kalshi, 55¢ elsewhere, and your spread
model says the gap reverts. Fees: enter ≈ `0.07·0.62·0.38 ≈ 1.6¢`, exit near
55¢ ≈ `0.07·0.55·0.45 ≈ 1.7¢`, so `c ≈ 3.3¢` against a hoped-for 7¢ — the CDF
check needs `d.cdf(s − 0.033)` comfortably above one half. Alternative exit:
hold to settlement (no exit fee, binary payoff) — that is a *bent* payoff, so
price it by quadrature with `payoff(x) = 1[x settles your way] − entry − fee`,
using the model's own settlement-side probability, not your enthusiasm.

**Polymarket.** Currently no explicit trading fee: `c ≈` spread + gas, often
tighter than the equivalent Kalshi round trip near mid-prices — but the spread
IS the cost, so measure it from the book, not from the last print. (Fee
schedules change; re-check before believing this paragraph.)

## Caveats that pay for themselves

- **Regime check first**: if the spread's variance ratio says random walk
  (martingality high), the OU candidates will carry no weight and the k-step
  mean won't pull — believe them. Cointegration that broke is a trend you're
  fading.
- **Size from the quantiles, not the mean**: `d.quantile(0.05)` on your P&L
  payoff is the honest stop-sizing number; mixtures carry the fat tails that
  Gaussian half-life math throws away.
- **Costs are part of the hypothesis.** A mean-reversion signal that dies when
  you subtract `c` was never a signal; it was a market-making fee you proposed
  to pay someone else.

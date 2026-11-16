# When does a trader need a forecast more than one step ahead?

*Peter Cotton, November 2026. A note on multi-step prediction for a liquid security.*

## The question

A trader in a liquid security decides a position today and can revise it at the next tick. The decision that matters is today's. Does a forecast of the return two, ten or a hundred steps ahead change it, or is the multi-step forecast only relevant because trading is not free?

## The frictionless case: one step is enough

Write $x_t$ for the position chosen at $t$ with the information $\mathcal{F}_t$, $r_{t+1}$ for the next return, and $W_t$ for wealth. With no costs the wealth recursion is $W_{t+1} = W_t(1 + x_t r_{t+1})$ and the dynamic programme is

$$V_t(W_t, s_t) = \max_{x_t} \mathbb{E}\big[V_{t+1}(W_{t+1}, s_{t+1}) \,\big|\, \mathcal{F}_t\big],$$

where $s_t$ is whatever state drives the conditional law of returns.

For logarithmic utility the value function separates, $V_t = \log W_t + g_t(s_t)$, and the maximisation reduces to $\max_x \mathbb{E}[\log(1 + x r_{t+1}) \mid \mathcal{F}_t]$. The optimal position depends on the conditional law of the next return and on nothing further ahead. This is Mossin (1968), Samuelson (1969) and Merton (1969): the log investor is myopic. Kelly sizing is the same statement. Under that objective a perfect ten-step forecast adds nothing to today's trade that the one-step law did not already contain.

For other utilities the same holds when returns are independent across time (the investment opportunity set is constant). When returns are predictable, Merton (1971, 1973) adds an intertemporal hedging demand: the investor holds extra or less of the asset according to how its return covaries with changes in future opportunities, $\mathrm{Cov}(r_{t+1}, \partial V_{t+1}/\partial s_{t+1})$. That term is zero for log utility and for constant opportunities, and it is small for moderate risk aversion over short horizons. It is a genuine multi-step object: it needs the law of motion of the state, not just tomorrow's return. So the clean statement is: without frictions, today's decision needs the one-step conditional law, plus a hedging correction that vanishes for the log investor and is second order otherwise.

## Where the horizon comes back

Everything that puts $k > 1$ into today's decision is a reason the position cannot, or will not, be revised at every step.

**Transaction costs.** With quadratic trading costs and mean-reverting alphas, Gârleanu and Pedersen (2013) show the optimal trade moves the position part of the way toward an *aim* portfolio, and the aim is a weighted average of the current Markowitz portfolio and the expected future ones, $\mathrm{aim}_t \propto \sum_{h \ge 0} w_h\, \mathbb{E}_t[\text{Markowitz}_{t+h}]$ with weights that decay geometrically in $h$. Expected returns at every horizon enter, weighted by how long the position will have to be carried. An alpha that decays faster than the cost-implied trading speed is barely worth trading. This is the main channel, and it is exactly the user's intuition: the horizon that matters is set by the cost of moving.

**A holding period imposed from outside.** A term contract, a futures expiry, a lock-up, a mandate that rebalances monthly, or a liquidation of a position too large to unwind in one tick. The payoff then depends on the cumulative return over the holding period, so the object needed is the law of $\sum_{h=1}^{k} r_{t+h}$. That is a derived quantity: it follows from the one-step law iterated forward, and a one-step model that is right about volatility clustering and mean reversion produces it by iteration. A dedicated multi-step predictive is only worth having if it beats that iteration, which is a measurable question, not a philosophical one.

**Risk and regulation over a horizon.** A ten-day value at risk, a drawdown limit, a margin call that is settled over days: these are statements about multi-step distributions, and they constrain today's position. Again the multi-step law is the iterated one-step law unless the model does better.

**Derivatives.** An option price is a functional of the distribution of the price at expiry, and a path-dependent one of the whole path. A market maker in options is a multi-step forecaster by construction, and the one-step model enters only through what it implies about the path.

**Inattention and latency.** If the trader looks once a day, the decision interval is a day, and the relevant one step is the day. Costs of attention play the same role as costs of trading.

## What this says about the package

The decision horizon equals the interval between revisions. For a liquid security with no costs the interval is one tick, so one step ahead at the trading frequency is the whole problem, and `laplace(k=1)` is the object a trader scores. Multi-step forecasts earn their place through the reasons a position is carried: costs, mandates, derivatives, risk limits. In every one of those the multi-step law is either a derived quantity from the one-step model or an input weighted by a decay set by the friction. The right test of a $k > 1$ fan is therefore against the iterated one-step predictive on the cumulative return, at the horizons a cost model says are carried, which is a sharper and smaller benchmark than scoring every horizon equally.

## References

- Mossin, J. (1968). Optimal multiperiod portfolio policies. *Journal of Business* 41, 215–229.
- Samuelson, P. A. (1969). Lifetime portfolio selection by dynamic stochastic programming. *Review of Economics and Statistics* 51, 239–246.
- Merton, R. C. (1969, 1971, 1973). Lifetime portfolio selection under uncertainty; optimum consumption and portfolio rules in a continuous-time model; an intertemporal capital asset pricing model.
- Gârleanu, N. and Pedersen, L. H. (2013). Dynamic trading with predictable returns and transaction costs. *Journal of Finance* 68, 2309–2340.
- Kelly, J. L. (1956). A new interpretation of information rate. *Bell System Technical Journal* 35, 917–926.

# Why likelihood is the metric that matters

*Why `skaters` ranks forecasters by held-out log-likelihood, why CRPS is the wrong goal-post for most of what you will do with a forecast, and where CRPS is nonetheless the right tool.*

## The claim

A distributional forecast is a density — or a mixture, or a cloud of samples that stands in for one. To rank two of them you need a number that says which put more probability where the outcome actually landed. `skaters` uses one number for that: the held-out log-likelihood $\log q(y)$, averaged over out-of-sample points. Leaf selection, the terminal-leaf ensemble, and every benchmark in this repo are judged by it. This note is why.

## Locality: it scores the density where the outcome is

The log score reads exactly one thing off your forecast: the density it placed at the realized $y$. Nothing else about the distribution enters. That is its defining property — up to an affine change, the log score is the *only* smooth strictly proper **local** score (Bernardo, 1979). CRPS is not local: it integrates $\big(F(t) - \mathbf{1}\{t \ge y\}\big)^2$ over the whole line, so a forecaster is graded on probability placed far from the outcome, in regions no realized value ever visited.

Locality is not an aesthetic preference. The density at $y$ is the number your decisions actually consume. A Kelly bet, a likelihood ratio, a posterior update, an option price — each reads $q(y)$, not the shape of $q$ a mile away. A score that grades the whole curve is grading things you will never spend.

## It is what a market pays

Here is the sharper reason, the one the microprediction mechanisms make precise. A self-funding pool that splits its pot in proportion to the density each participant placed on the outcome pays each participant, per unit of staked wealth, exactly $q(y)$ relative to the field. A participant who compounds — a log-wealth (Kelly) bettor — therefore maximizes $\mathbb{E}[\log q(Y)]$, the log score. So the log score is not one proper score among many; it is the wealth a proper market hands you ([mechanisms.microprediction.org](https://mechanisms.microprediction.org)). CRPS has no such reading. There is no natural pot split that pays CRPS, and optimizing it compounds nobody's bankroll. A CRPS specialist is winning a goal-post that will not grow your wealth.

## It composes

Chained and boosted forecasts factor under the log score, and only under it. If a base forecast $p_1$ is refined by a residual stage with density $g$ for the residual z-score $z = \Phi^{-1}(F_1(y))$, the composed density is $p_1(y)\,g(z)/\varphi(z)$, so

$$\log p(y) = \log p_1(y) + \big(\log g(z) - \log\varphi(z)\big).$$

The chain's log score is the sum of the stages' log scores. That additivity is what makes a chain of residual markets a decentralized gradient-boosting machine, and what lets you attribute skill stage by stage ([Multi-Stage Solicitation](https://mechanisms.microprediction.org)). CRPS does not factor this way; a CRPS pipeline cannot be split into per-stage credit.

## It is information

The log score is the only proper score whose regret is a divergence you can read as information. Its regret against the truth is the Kullback–Leibler divergence, and the value a *conditioning* forecaster extracts from a covariate the crowd ignored is exactly the mutual information $I(R;X)$ between residual and input ([conformalprediction.net](https://conformalprediction.net)). This is why conformal prediction — which prices the residual flat across the input space — leaves $I(R;X)$ on the table: a log-scored (Kelly) market prices that gap and pays whoever closes it. There is no CRPS analogue; the mutual-information identity is a log-score identity.

## Where CRPS is the right tool

CRPS is a proper score, and it has two genuine virtues. Neither of them is "you don't have a density."

**Robustness.** The log score is unbounded below: a forecast that assigns near-zero density to a value that then occurs takes a near-infinite loss. That sensitivity is usually a signal, not a defect — it tells you the tails are wrong, and the fix is to model them, not to change the ruler. `skaters` does exactly this with its scale-mixture leaf: heavier tails *lift* the log-likelihood rather than being papered over. On price and returns a proper tail-and-volatility model like GARCH-t wins, and it wins under the log score too — because it is the right model there, not because CRPS is the right metric. Where CRPS earns its keep is when you genuinely cannot model the tails and still need a bounded score: monitoring, or an adversarial or unknown source, where a single deep-tail draw must not blow up the evaluation. CRPS is finite and lives in the units of the outcome, so it degrades gracefully when the model is wrong and you know it.

**Interpretability.** CRPS reports a distance in the outcome's own units — dollars, degrees, people — which a decision-maker can read directly. Log-likelihood is in nats.

What is *not* a reason to reach for CRPS is "I only have samples." A cloud of samples is a density waiting for a kernel. If you have no density at all then you do not have a probabilistic model, and no score repairs that. The move is to smooth the samples — with the jitter that keeps the smoothing honest ([the point-cloud paper](https://mechanisms.microprediction.org)) — and score the log-likelihood, not to retreat to a metric that pretends the question away.

## The verdict

Rank by held-out log-likelihood. It is local, it is the wealth a market pays, it composes, and it is information. Keep CRPS in the drawer for two jobs: a bounded score for when you cannot model the tails, and a unit-interpretable summary for a reader who asks for one. That is exactly what `skaters` does — everything is judged by log-likelihood, and `Dist.crps(y)` is there as a secondary proper score for when you want it.

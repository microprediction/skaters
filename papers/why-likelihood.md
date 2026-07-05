# Why likelihood is the metric that matters

*Why `skaters` ranks forecasters by held-out log-likelihood, why CRPS is the wrong goal-post for most of what you will do with a forecast.*

## The claim

A distributional forecast is a density — or a mixture, or a cloud of samples that stands in for one. To rank two of them you need a number that says which put more probability where the outcome actually landed. `skaters` uses one number for that: the held-out log-likelihood $\log q(y)$, averaged over out-of-sample points. Leaf selection, the terminal-leaf ensemble, and every benchmark in this repo are judged by it. This note is why.

## Locality: it scores the density where the outcome is

The log score reads exactly one thing off your forecast: the density it placed at the realized $y$. Nothing else about the distribution enters. That is its defining property — up to an affine change, the log score is the *only* smooth strictly proper **local** score (Bernardo, 1979). CRPS is not local: it integrates $\big(F(t) - \mathbf{1}\{t \ge y\}\big)^2$ over the whole line, so a forecaster is graded on probability placed far from the outcome, in regions no realized value ever visited.

Locality is not an aesthetic preference. The density at $y$ is the number your decisions actually consume. A Kelly bet, a likelihood ratio, a posterior update, an option price — each reads $q(y)$, not the shape of $q$ a mile away. A score that grades the whole curve is grading things you will never spend.

## It is what a market pays

Here is the sharper reason, and it is a foundational fact of quantitative finance rather than a metaphor: every financial market is the same object in disguise — a bet on an uncertain outcome, settled when the outcome is revealed, whose prices *are* a distribution. Arrow–Debreu state prices, normalized, are a density; the fundamental theorem of asset pricing says any price is an expectation under the market's implied law; and the investor who compounds — the growth-optimal, log-utility Kelly investor — maximizes $\mathbb{E}[\log q(Y)]$ by staking her true probabilities. A parimutuel that splits its pot in proportion to the density each participant placed on the outcome is only the bare version: per unit of staked wealth it pays exactly $q(y)$ relative to the field, so the log-wealth maximizer's best move is her honest density. An options book, a prediction market, and the nearest-the-pin pool are the same machine in different clothes ([mechanisms.microprediction.org](https://mechanisms.microprediction.org)), and the machine pays the log score. CRPS has no such reading: no natural market pays it, and optimizing it compounds nobody's bankroll. A CRPS specialist is winning a goal-post that will not grow your wealth.

## It composes

Chained and boosted forecasts factor under the log score, and only under it. If a base forecast $p_1$ is refined by a residual stage with density $g$ for the residual z-score $z = \Phi^{-1}(F_1(y))$, the composed density is $p_1(y)\,g(z)/\varphi(z)$, so

$$\log p(y) = \log p_1(y) + \big(\log g(z) - \log\varphi(z)\big).$$

The chain's log score is the sum of the stages' log scores. That additivity is what makes a chain of residual markets a decentralized gradient-boosting machine, and what lets you attribute skill stage by stage ([Multi-Stage Solicitation](https://mechanisms.microprediction.org/papers/multi-stage-solicitation.html)). CRPS does not factor this way; a CRPS pipeline cannot be split into per-stage credit.

## It is information

The log score is the only proper score whose regret is a divergence you can read as information. Its regret against the truth is the Kullback–Leibler divergence, and the value a *conditioning* forecaster extracts from a covariate the crowd ignored is exactly the mutual information $I(R;X)$ between residual and input ([Betting Against a Conformal Predictor](https://conformalprediction.net/papers/parimutuel/)). This is why conformal prediction — which prices the residual flat across the input space — leaves $I(R;X)$ on the table: a log-scored (Kelly) market prices that gap and pays whoever closes it. There is no CRPS analogue; the mutual-information identity is a log-score identity.

## Where CRPS is the right tool

CRPS is a proper score with two genuine virtues, but the pragmatic truth comes first. CRPS is often chosen because you *don't* have a density — and that, frankly, is a tell. It usually means you are leaning too heavily on a procedure that cannot produce one, conformal prediction being the standard example: it delivers marginal intervals, flat in the covariates, never a sharp conditional distribution, and it is glad of a score that will not expose the fact. What such a forecaster forfeits is exactly the conditional information a sharper, conditioning rival collects against it — the mutual information $I(R;X)$ between residual and input ([Betting Against a Conformal Predictor](https://conformalprediction.net/papers/parimutuel/)). So neither of CRPS's real virtues, below, is "you don't have a density"; that is a modeling failure wearing a metric's clothes.

**Robustness.** The log score is unbounded below: a forecast that assigns near-zero density to a value that then occurs takes a near-infinite loss. That sensitivity is usually a signal, not a defect — it tells you the tails are wrong, and the fix is to model them, not to change the ruler. `skaters` does exactly this with its scale-mixture leaf: heavier tails *lift* the log-likelihood rather than being papered over. On price and returns a proper tail-and-volatility model like GARCH-t wins, and it wins under the log score too — because it is the right model there, not because CRPS is the right metric. Where CRPS earns its keep is when you genuinely cannot model the tails and still need a bounded score: monitoring, or an adversarial or unknown source, where a single deep-tail draw must not blow up the evaluation. CRPS is finite and lives in the units of the outcome, so it degrades gracefully when the model is wrong and you know it.

**Interpretability.** CRPS reports a distance in the outcome's own units — dollars, degrees, people — which a decision-maker can read directly. Log-likelihood is in nats.

And samples are not the exception they seem: a cloud of samples is a density waiting for a kernel. Smooth it — with the jitter that keeps the smoothing honest ([the point-cloud paper](https://mechanisms.microprediction.org/papers/scoring-point-cloud-distributional-submissions.html)) — and score the log-likelihood. If you cannot form a density even then, you have no probabilistic model, and no score repairs that.

## The verdict

Rank by held-out log-likelihood. It is local, it is the wealth a market pays, it composes, and it is information. The short version on CRPS: it is for when you know the model is wrong and can't fix it — a bounded score under a misspecification you are stuck with, and a unit-interpretable summary when a reader wants one. That is exactly what `skaters` does: everything is judged by log-likelihood, with `Dist.crps(y)` in the drawer for those two jobs.

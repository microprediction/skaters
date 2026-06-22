# Denoising, one step at a time

*A short note on why `skaters` is secretly running the same identity that powers diffusion models, Kalman filters, and empirical Bayes — and why nobody noticed.*

## One identity, three disguises

Start with the most innocent question in statistics. You observe a noisy number
$y = \mu + \varepsilon$, $\varepsilon \sim N(0, \sigma^2)$, and you want the clean
$\mu$ behind it. **Tweedie's formula** answers it in one line, for *any* prior on
$\mu$:

$$\mathbb{E}[\mu \mid y] \;=\; y \;+\; \sigma^2\,\partial_y \log f(y),$$

where $f$ is the marginal density of the observations. The posterior mean is just
the observation, nudged by the **score of the marginal density**, scaled by the
noise variance. That's it. The prior enters only through $f$ — you never have to
name it.

The cute part is how many famous things are this one formula wearing a hat.

- **Empirical Bayes.** Robbins (1956) and Miyasawa (1961) used it to shrink
  thousands of noisy estimates toward each other without ever specifying a prior;
  Efron (2011) made it a centerpiece of large-scale inference. Estimate $f$ from
  the data, differentiate its log, done.
- **The Kalman filter.** Make the prior Gaussian, $\mu \sim N(m, P)$. Then $f$ is
  Gaussian too, its score is *linear* in $y$, and the formula collapses to
  $$\mathbb{E}[\mu \mid y] = m + \frac{P}{P+\sigma^2}\,(y - m).$$
  That fraction is the Kalman gain. The Kalman measurement update is Tweedie's
  formula with a Gaussian prior — nothing more.
- **Diffusion models.** Train a network to denoise images blurred with Gaussian
  noise and you have learned $\mathbb{E}[\text{clean} \mid \text{noisy}]$ — which,
  by the very same formula, *is* the score $\partial_y \log f$ up to scaling. This
  is the bridge (Vincent 2011; Song & Ermon 2019) that lets a denoiser be run
  backwards as a score-based sampler. Every "by Tweedie's formula…" in a diffusion
  paper is this identity.

Same equation. Empirical Bayes estimates the score, Kalman assumes it's linear,
diffusion learns it with a neural net.

## The variance version

Maurice Tweedie, generously, has *two* unrelated things named after him, and
`skaters` uses both. The second is the **exponential-dispersion / variance-function**
machinery, $\text{var}(Y\mid\mu) = \phi\,V(\mu)$. Apply the same posterior-mean
logic to the *variance* of a zero-mean Gaussian and you get

$$h_t \;=\; h_{t-1} \;+\; (1-\delta)\,(y_t^2 - h_{t-1}),$$

which is exactly a GARCH variance recursion. Hansen & Tong (2026) show this is the
**exact** Bayesian posterior-mean correction for the variance under a conjugate
prior and local precision discounting. GARCH, it turns out, was denoising the
variance all along.

## Where `skaters` comes in

Both of the package's named forecasters are doing per-step denoising:

- **`laplace`** carries a running level and corrects it toward each new
  observation — an EMA update, which is the constant-gain Kalman/Tweedie correction
  $\mu_t = \mu_{t-1} + \alpha\,(y_t - \mu_{t-1})$ with $\alpha = 1-\delta$.
- **`doob`** pins the mean and denoises the *variance*, averaging a family of clock
  candidates that are each the GARCH/Tweedie variance correction above.

So a forecast step in `skaters` is a single reverse-diffusion step in miniature:
take the noisy next observation, move it toward the latent level (or latent
variance) along the score, by an amount set by how much you trust the predictive.
Where a diffusion model runs hundreds of denoising steps over a fixed image,
`skaters` runs one denoising step per tick over an endless stream.

## Why nobody noticed

Tweedie's formula is famous — in statistics and, lately, loudly in machine
learning. But in the time-series econometrics world where GARCH and score-driven
(GAS) models live, it apparently never crossed over: Hansen & Tong searched the
curated GAS bibliography (453 papers, May 2026) and found **zero** prior uses of
the phrase. The recursions had been written down and used for forty years; the
one-line reason they work was sitting in a neighboring field the whole time.

That's the cute part. The thing `skaters` does every tick — denoise the next
observation toward its latent cause — is the oldest trick in empirical Bayes, the
engine of the Kalman filter, and the heartbeat of modern generative AI, all the
same identity, finally introduced to the time-series recursions that had been
quietly using it without a name.

---

**References.** Robbins (1956); Miyasawa (1961); Stein (1981); Efron, *Tweedie's
formula and selection bias*, JASA (2011); Vincent, *A connection between score
matching and denoising autoencoders* (2011); Song & Ermon (2019); Hansen & Tong,
*Tweedie's Formula and Score-Driven Updating*, [arXiv:2605.15902](https://arxiv.org/abs/2605.15902) (2026).

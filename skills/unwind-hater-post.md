# unwind-hater-post skill

A skill for taking apart a social media post, thread or article that claims
`laplace` (the `skaters` forecaster) fails, is slow, or loses to some other
method. Use it when someone forwards such a post and asks "is this true?", or
when drafting a reply. The goal is a short, checkable answer that points to
the pages where the measurement already lives, not an argument in the
comments.

Most hostile posts about `laplace` so far have been correct about what they
ran and wrong about what it means. The skill is a checklist for finding which.

## Step 1: find out what was actually run

Before anything else, extract from the post:

- **Version.** `skaters` version and date. Numbers before 2026-08-04 are a
  different model (residual cap); the current canonical run is November 2026.
- **Horizon.** One step ahead, or multi-step? The documented upper limit is
  `k=12` (scope page). Results at 96 or 336 steps are outside scope; the
  package will run there and the docs say not to.
- **Units.** Were the series fed in natural units? A series near 10^20
  (hash rate in hashes per second) or 10^-12 breaks every statistical
  package with absolute constants; the working range is about 10^-3 to 10^6
  (scope page, "Units and scale"). Dividing by 10^18 is the whole fix.
- **Prior knowledge left out.** Was a non-negative series (demand, a price,
  a count) forecast on the real line with no transform? The model does not
  know the series is positive; `flesaker` or `log_transform` says so (examples
  page, recipe three; scope page, "Prior knowledge"). Negative forecasts of
  demand are the signature of this omission.
- **Which implementation was timed.** The 12 microseconds per observation is
  the Rust port, one step ahead, on a warm model. The Python package is about
  24 times slower, and a cold multi-step run is slower again. All of it is on
  the performance page; a post that compares one of these against a different
  one of someone else's numbers is comparing regimes, not methods.

If any of these is off, the post is describing a misuse. Say so plainly, link
the page, and stop. The refunds page does this with the standard examples:
https://skaters.microprediction.org/refunds.html

## Step 2: check the metric and the unit of counting

- **One interval versus the whole distribution.** A 95% Winkler (interval)
  score is proper but judges only the central interval, the one a conformal
  method is built to calibrate. CRPS integrates every quantile level; the log
  score checks every level and the tails hardest. A post that reports only the
  interval score has chosen the one metric its method is built for
  (metrics page, "Interval scores judge one interval").
- **Datasets won versus series.** Counting datasets gives a 30-series
  collection the same vote as a 3,000-series one. The canonical study tests
  every series with Diebold-Mariano and reports wins, ties, losses and the
  median gap. Ask what the per-series numbers are.
- **Reconstruction.** For nine-decile models, the step from quantiles to a
  density moves the answer by half a nat. Any log-score gap quoted without
  saying which reconstruction is not a number
  (https://skaters.microprediction.org/papers.html).
- **Pooled horizons.** A loss averaged over horizons 1 to 96 with equal
  weight corresponds to no decision problem; report horizons separately.

## Step 3: check the claim against the store

The current paired results are public:

- https://foundationalprediction.com (leaderboards and the explorer; pick any
  reference model)
- `benchmarks/canonical_summary_vs_laplace.csv` in the repository
- https://conformalprediction.net/csp.html for the conformal baseline

Where the post is right, say so with the same numbers. On the strongly
seasonal M4 hourly series Conformal Seasonal Pools beats `laplace` on 144 of
414 series and loses on 19 (+0.06 nats), and that sits in the first table of
the review. On every FRED stratum `laplace` is ahead by 0.13 to 0.43 nats. The
larger foundation models are ahead on monthly and weekly series by a few
hundredths of a nat under the generous reconstruction; `laplace` is ahead on
daily economic series against every one of them. Quote these as they are.

## Step 4: the tactics to name

A running list. Name the tactic, not the person.

1. **The unrerunnable number.** A headline ("60% of datasets", "7,700 times
   slower") with no script, no version pin and no series list. Ask for the
   script that produces it; offer to rerun it through the canonical harness.
2. **Metric chosen after the fact.** The interval score appears when the
   density scores do not cooperate. Point to the metrics page.
3. **Dataset-weighted counting.** Equal votes for collections of very
   different size, so a few small seasonal collections decide the result.
4. **Out of scope, reported as failure.** Running at horizons the docs exclude,
   or in units the docs warn about, and presenting the result as a property of
   the model.
5. **The missing transform.** Negative demand, negative prices: the series was
   positive and nobody said so to the model.
6. **Regime-crossing speed comparisons.** Python cold multi-step against
   someone else's one-step figure; or the Rust warm figure disputed with the
   Python number, which the performance page already lists next to it.
7. **The tight reconstruction only.** Quoting the half-nat gap without the
   generous reconstruction that erases it, or the other way round.
8. **The amendment as concealment.** A page corrected the same day on a
   public repository is presented as evidence of bad faith. The history is
   public; say so and move on.
9. **Priority claims for old ideas.** Same-phase forecasting is Holt-Winters
   (1960), periodic AR (1967) and STL (1990); nobody owns it. When a credit
   question is raised, answer it in the docstring or the benchmark notes with
   dates, not on the thread.
10. **Guarantee rhetoric.** "No coverage guarantee" against a method whose
    measured coverage is on the page, next to the conformal method's. Point to
    the coverage column.
11. **Engagement as evidence.** Reaction counts and emoji are not a
    benchmark.

## Step 5: how to reply

- Two or three sentences. Which step above the post failed, the page that
  shows it, the one number that matters.
- Concede what is true, with the number. The hourly loss to CSP is real and is
  on our own page.
- Invite an issue with a reproducible example. A failing test is worth more
  than a thread.
- Do not argue the metric in the comments, do not name-call, do not quote any
  number you cannot rerun, and never quote a pooled GIFT-Eval figure.
- Tone: the refunds page. Dry, specific, and done.

## What not to do

- Do not reply to a post that contains no checkable claim.
- Do not re-run a benchmark to a critic's specification outside the
  package's stated scope and present the result as if it were in scope.
- Do not edit the docs in response to a post without dating the change; the
  repository history is public and that is a strength.

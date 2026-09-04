"""Terminal-leaf ensemble: mix for the mean, model the residual once.

Bayesian model averaging over a heterogeneous pool combines full predictive
distributions, which preserves the combined *mean* and *variance* but washes
out higher moments — so a heavy-tailed leaf used inside the pool collapses
back to Gaussian shape at the output (verified empirically).

This ensemble fixes that. It uses the sub-models only as **mean forecasters**:
it weights them by predictive likelihood (as in :func:`bayesian_ensemble`),
combines their means, and then models the distribution of the *combined
residual* with a single terminal leaf — **model first, conform last**. The
default terminal leaf is :func:`crps_leaf` (the residual is shaped to minimise
CRPS); pass ``leaf_fn=scale_mixture_leaf`` for the likelihood objective.
Because there is exactly one leaf at the end, its shape reaches the output
undiluted.

    y --[weighted mix of candidate means]--> mu_hat
    residual = y - mu_hat  -->  terminal leaf  -->  D
    predictive = D shifted by mu_hat

Everything still flows as :class:`Dist`; this is just *where* the residual
distribution is estimated — once, at the top, instead of once per candidate.
"""

from __future__ import annotations
import math
from collections import deque
from skaters.dist import Dist
from skaters.leaf import crps_leaf


_PIT_DISPERSION_TARGET = 1.0 / 12.0     # Var[U] for U ~ Uniform(0,1): E[(u-0.5)^2] at perfect calibration
_PIT_EWMA_DECAY = 0.98
_LOSS_FAST_DECAY = 0.90
_LOSS_SLOW_DECAY = 0.995
_TEMP_AMBIG_EPS = 0.15 * _PIT_DISPERSION_TARGET   # |e_t| below this defers to the loss-slope tiebreak


def terminal_leaf_ensemble(
    skaters: list,
    leaf_fn=crps_leaf,
    k: int = 1,
    learning_rate: float = 0.5,
    complexity_penalty: float = 0.0,
    depths: list[int] | None = None,
    prior_log_weights: list[float] | None = None,
    max_components: int = 20,
    forget: float = 1.0,
    adaptive_temperature: bool = False,
    temp_rho: float = 0.03,
    temp_band: float = 3.0,
):
    """Create a terminal-leaf ensemble.

    Args:
        skaters: sub-models used as mean forecasters.
        leaf_fn: factory for the terminal residual leaf (default :func:`crps_leaf`;
            pass ``scale_mixture_leaf`` for the likelihood objective).
        k: forecast horizon.
        learning_rate: eta for the likelihood-based mean weighting -- under
            random-utility maximization this is exactly a Gumbel-logit selection
            temperature (softmax(eta * score) is the choice probability when
            candidate scores carry i.i.d. Gumbel(0, 1/eta) noise): larger eta ->
            colder selection (commits to the best candidate faster), smaller eta
            -> hotter (hedges across the pool). Also the center of the adaptive
            band when ``adaptive_temperature`` is set.
        complexity_penalty: per-depth penalty (as in bayesian_ensemble).
        depths, prior_log_weights: optional, one per sub-model.
        max_components: prune the warm-up fallback mixture to this many.
        forget: geometric discount on accumulated log-evidence per step. 1.0 is
            exact cumulative updating (the ensemble converges to a fixed winner);
            values just below 1 (e.g. 0.99) keep it adaptive to regime change at
            negligible steady-state cost.
        adaptive_temperature: opt-in. Drives eta online from the ensemble's own
            realized one-step calibration instead of holding it fixed (see
            skaters#213/#215): a running EWMA of the issued predictive's PIT
            dispersion, ``e_t = EWMA((u_t - 0.5)^2) - 1/12`` (0 at perfect
            calibration; positive when misses land in the tails more than
            uniform predicts -> heat up / hedge; negative -> cool down / commit).
            When |e_t| is inside a small dead band (predictive dispersion looks
            fine), the direction instead follows the sign of a fast-vs-slow EWMA
            spread of the issued predictive's own logpdf (improving -> commit,
            degrading -> hedge). Off by default; when on, ``eta`` still starts
            at ``learning_rate`` and only drifts from there.
        temp_rho: log-space step size for the adaptive update. Fixed across all
            series -- not meant to be tuned per series.
        temp_band: adaptive eta is clipped to
            ``[learning_rate / temp_band, learning_rate * temp_band]`` so it
            cannot run away.
    """
    n = len(skaters)
    assert n > 0
    depths = depths if depths is not None else [0] * n
    prior = prior_log_weights if prior_log_weights is not None else [0.0] * n

    # One terminal leaf per horizon. These are closures, so they live HERE, in
    # the wrapper — never in the state dict. Skater state must stay pure data
    # (picklable for checkpoint/restore); functions are reconstructed with the
    # wrapper, exactly as multiscale keeps its sub-skaters outside state.
    tleafs = [leaf_fn(k=1) for _ in range(k)]

    def _skater(y: float, state: dict | None) -> tuple[list[Dist], dict]:
        if state is None:
            state = {
                "sub": [None] * n,
                "qdist": [deque() for _ in range(n)],          # h=1 Dist queue for weighting
                "log_w": [prior[i] for i in range(n)],
                "leaf_state": [None] * k,
                "leaf_pred": [None] * k,
                "mean_q": [deque() for _ in range(k)],          # pending combined means per horizon
                "adapt": {
                    "log_eta": math.log(learning_rate),
                    "pit_ewma": _PIT_DISPERSION_TARGET,
                    "loss_fast": None,
                    "loss_slow": None,
                    "pred_q": deque(),          # pending issued h=1 predictive, for next step's signal
                } if adaptive_temperature else None,
            }

        # Run all sub-models; collect their k Dists.
        all_dists = []
        for i, f in enumerate(skaters):
            di, state["sub"][i] = f(y, state["sub"][i])
            all_dists.append(di)

        # Adaptive selection temperature (skaters#213/#215): resolve the ISSUED
        # predictive from one step ago against this step's y, turn its PIT
        # dispersion (and, in the dead band, its own logpdf trend) into a
        # heat/cool signal, and use the resulting eta_t for THIS step's weight
        # update below. Strictly causal, same one-step lag as the qdist weighting.
        eta_t = learning_rate
        if adaptive_temperature:
            ad = state["adapt"]
            pq = ad["pred_q"]
            if pq:
                prev_pred = pq.popleft()
                lp_c = prev_pred.logpdf(y)
                if not (lp_c >= -20.0):
                    lp_c = -20.0
                elif lp_c > 20.0:
                    lp_c = 20.0
                u = prev_pred.cdf(y)
                if not (0.0 <= u <= 1.0):
                    u = 0.5                     # degenerate/NaN guard: no signal
                ad["pit_ewma"] = (_PIT_EWMA_DECAY * ad["pit_ewma"]
                                  + (1.0 - _PIT_EWMA_DECAY) * (u - 0.5) ** 2)
                if ad["loss_fast"] is None:
                    ad["loss_fast"] = ad["loss_slow"] = lp_c
                else:
                    ad["loss_fast"] = _LOSS_FAST_DECAY * ad["loss_fast"] + (1.0 - _LOSS_FAST_DECAY) * lp_c
                    ad["loss_slow"] = _LOSS_SLOW_DECAY * ad["loss_slow"] + (1.0 - _LOSS_SLOW_DECAY) * lp_c
                e_t = ad["pit_ewma"] - _PIT_DISPERSION_TARGET
                dloss_t = ad["loss_fast"] - ad["loss_slow"]
                if abs(e_t) > _TEMP_AMBIG_EPS:
                    direction = -1.0 if e_t > 0.0 else 1.0
                else:
                    direction = 1.0 if dloss_t > 0.0 else (-1.0 if dloss_t < 0.0 else 0.0)
                ad["log_eta"] += temp_rho * direction
                lo = math.log(learning_rate / temp_band)
                hi = math.log(learning_rate * temp_band)
                ad["log_eta"] = min(max(ad["log_eta"], lo), hi)
            eta_t = math.exp(ad["log_eta"])

        # Update model weights from the resolved one-step prediction. The `forget`
        # factor (< 1) geometrically discounts past log-evidence so the ensemble
        # stays adaptive to regime change and the weight gap cannot diverge; at
        # forget == 1.0 this is exact cumulative updating (the historical default).
        for i in range(n):
            q = state["qdist"][i]
            if q:
                # Bounded loss (mixability): clamp to a finite band so neither a
                # -inf (y far from every component) nor a +inf (an exact hit on a
                # Dirac atom, e.g. the sticky lattice path) can dominate or
                # NaN-poison log_w. The `not (lp >= -20.0)` arm also catches NaN.
                lp = q.popleft().logpdf(y)
                if lp > 20.0:
                    lp = 20.0
                elif not (lp >= -20.0):
                    lp = -20.0
                state["log_w"][i] = (forget * state["log_w"][i]
                                     + eta_t * lp - complexity_penalty * depths[i])
            q.append(all_dists[i][0])

        log_w = state["log_w"]
        max_lw = max(log_w)
        w = [math.exp(lw - max_lw) for lw in log_w]
        tot = sum(w)

        combined = []
        for h in range(k):
            mu_h = sum(w[i] * all_dists[i][h].mean for i in range(n)) / tot

            # Resolve the h-step-ahead combined-mean prediction made (h+1) steps
            # ago into a residual, and update this horizon's terminal leaf.
            mq = state["mean_q"][h]
            if len(mq) >= h + 1:
                r = y - mq.popleft()
                ld, state["leaf_state"][h] = tleafs[h](r, state["leaf_state"][h])
                state["leaf_pred"][h] = ld[0]

            if state["leaf_pred"][h] is not None:
                pred = state["leaf_pred"][h].shift(mu_h)
            else:
                # Warm-up: fall back to the candidate mixture until the leaf has data.
                pred = Dist.combine([all_dists[i][h] for i in range(n)], w)
                if len(pred) > max_components:
                    pred = pred.prune(max_components)
            combined.append(pred)
            mq.append(mu_h)

        if adaptive_temperature:
            state["adapt"]["pred_q"].append(combined[0])

        return combined, state

    _skater.__name__ = (f"terminal_leaf_ensemble(n={n}, k={k})" if not adaptive_temperature
                        else f"terminal_leaf_ensemble(n={n}, k={k}, adaptive_temp)")
    return _skater

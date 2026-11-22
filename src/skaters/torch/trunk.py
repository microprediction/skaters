"""The trunk in torch: :func:`skaters.terminal.terminal_leaf_ensemble` with
tensor weights and tensor means, so a log score at the output differentiates
through the mixing weights into every candidate's transform parameters.

Same arithmetic as the reference: each candidate's one-step predictive is
queued and scored against the next observation (log density clamped to
[-20, 20]); log-evidence accumulates with ``forget`` and ``learning_rate``
less a depth penalty; weights are the softmax of the accumulated evidence;
the combined mean per horizon is the weighted mean of candidate means; the
residual of the combined mean issued h+1 steps earlier updates a terminal
leaf (the reference ``crps_leaf``, a constant in the graph); the output is
that leaf's predictive shifted by the combined mean. During warm-up, before
the leaf has a residual, the candidate mixture is issued, as in the
reference.

Two things are deliberately not learnable in this pass: the terminal leaf
and the lattice/tail wrappers, which stay in the reference (``laplace`` is
``multiscale(_laplace_single_scale)`` plus ``_project`` and ``_gpdtails``;
this module is the ``terminal_leaf_ensemble`` inside, at one scale).
``learning_rate``, ``forget`` and ``complexity_penalty`` are parameters so
the mixing policy itself can be trained; ``prior_log_weights`` likewise.

``adaptive_temperature`` (with ``temp_rho`` and ``temp_band``) is the
reference's: eta moves in log space from the issued predictive's PIT
dispersion and log-score trend, inside a band around ``learning_rate``. The
direction of each move is decided on floats, as in the reference; eta itself
is a tensor in ``learning_rate``, so the gradient reaches it. The state is
the reference's layout (docs/STATE.md), ``adapt`` included.
"""

from __future__ import annotations

import math

import torch
from torch import nn

from skaters.leaf import crps_leaf
from skaters.terminal import (_PIT_DISPERSION_TARGET, _PIT_EWMA_DECAY, _LOSS_FAST_DECAY,
                              _LOSS_SLOW_DECAY, _TEMP_AMBIG_EPS)
from skaters.torch.dist import TorchDist, DTYPE, _t

_LOGPDF_LO, _LOGPDF_HI = -20.0, 20.0


class _LogW(list):
    """The per-candidate log weights, a plain list in the state (it is written
    to JSON as one), carrying ``decay = forget**t`` as an attribute so the
    prior's exact gradient survives the one-step truncation of the weight
    recursion. A list restored from JSON has no attribute: a restored state
    is a constant, so the carried weights then contribute no prior gradient."""
    __slots__ = ("decay",)


def _clamp_lp(lp):
    """Reference: lp > 20 -> 20; not (lp >= -20) (incl. NaN) -> -20."""
    if bool(lp > _LOGPDF_HI):
        return torch.as_tensor(_LOGPDF_HI, dtype=DTYPE)
    if not bool(lp >= _LOGPDF_LO):
        return torch.as_tensor(_LOGPDF_LO, dtype=DTYPE)
    return lp


class TerminalLeafEnsemble(nn.Module):
    """Likelihood-weighted mean trunk with a terminal reference leaf."""

    def __init__(self, skaters, k: int = 1, leaf_fn=crps_leaf, learning_rate: float = 0.5,
                 complexity_penalty: float = 0.0, depths=None, prior_log_weights=None,
                 max_components: int = 20, forget: float = 1.0, adaptive_temperature: bool = False,
                 temp_rho: float = 0.03, temp_band: float = 3.0):
        super().__init__()
        self.adaptive_temperature = bool(adaptive_temperature)
        self.temp_rho = float(temp_rho)
        self.temp_band = float(temp_band)
        n = len(skaters)
        assert n > 0
        self.skaters = list(skaters)
        # candidates are closures (conjugate chains); their transform modules
        # are registered separately so parameters()/state_dict()/.to() see them
        self.skater_modules = nn.ModuleList([s for s in skaters if isinstance(s, nn.Module)])
        self.candidate_modules = nn.ModuleList()
        self.detach_carry = True        # truncate backprop through the weight recursion at one step
        # #297: an optional per-step log-weight offset set by a learned gate
        # (skaters.torch.learned); None or zeros reproduce the reference exactly.
        # The offset multiplies the prequential weights at the combine step only;
        # the weight recursion itself is untouched.
        self.gate_offset = None
        self.last_log_w = None          # the prequential log weights after this step, detached
        self.k = k
        self.leaf_fn = leaf_fn
        self.n = n
        self.depths = list(depths) if depths is not None else [0] * n
        self.max_components = max_components
        self.learning_rate = nn.Parameter(torch.as_tensor(float(learning_rate), dtype=DTYPE))
        self.complexity_penalty = nn.Parameter(torch.as_tensor(float(complexity_penalty), dtype=DTYPE))
        self.forget = nn.Parameter(torch.as_tensor(float(forget), dtype=DTYPE))
        prior = prior_log_weights if prior_log_weights is not None else [0.0] * n
        self.prior_log_weights = nn.Parameter(torch.as_tensor([float(p) for p in prior], dtype=DTYPE))
        # one terminal leaf per horizon; closures live here, not in state.
        # A torch leaf (an nn.Module) is registered; a reference leaf is not.
        self.tleafs = [leaf_fn(k=1) for _ in range(k)]
        self.tleaf_modules = nn.ModuleList([t for t in self.tleafs if isinstance(t, nn.Module)])

    def forward(self, y, state=None):
        y = _t(y)
        n, k = self.n, self.k
        if state is None:
            state = {
                "sub": [None] * n,
                "qdist": [[] for _ in range(n)],
                "log_w": [self.prior_log_weights[i] for i in range(n)],
                "leaf_state": [None] * k,
                "leaf_pred": [None] * k,
                "mean_q": [[] for _ in range(k)],
                "adapt": {
                    "log_eta": torch.log(self.learning_rate),
                    "pit_ewma": torch.as_tensor(_PIT_DISPERSION_TARGET, dtype=DTYPE),
                    "loss_fast": None,
                    "loss_slow": None,
                    "pred_q": [],
                } if self.adaptive_temperature else None,
            }
            fresh = True
        else:
            fresh = False
        all_dists = []
        for i, f in enumerate(self.skaters):
            di, state["sub"][i] = f(y, state["sub"][i])
            all_dists.append(di)

        # adaptive selection temperature: the reference's signal on the issued
        # predictive, with eta a tensor in learning_rate (the band is too)
        eta_t = self.learning_rate
        if self.adaptive_temperature:
            ad = state.get("adapt")
            if ad is None:                       # a state written without adaptation
                ad = state["adapt"] = {"log_eta": torch.log(self.learning_rate),
                                       "pit_ewma": torch.as_tensor(_PIT_DISPERSION_TARGET, dtype=DTYPE),
                                       "loss_fast": None, "loss_slow": None, "pred_q": []}
            pq = ad["pred_q"]
            if pq:
                prev_pred = pq.pop(0)
                with torch.no_grad():
                    lp_c = _t(prev_pred.logpdf(y))
                    if not bool(lp_c >= -20.0):
                        lp_c = torch.as_tensor(-20.0, dtype=DTYPE)
                    elif bool(lp_c > 20.0):
                        lp_c = torch.as_tensor(20.0, dtype=DTYPE)
                    u = _t(prev_pred.cdf(y))
                    if not (0.0 <= float(u) <= 1.0):
                        u = torch.as_tensor(0.5, dtype=DTYPE)
                    ad["pit_ewma"] = (_PIT_EWMA_DECAY * _t(ad["pit_ewma"])
                                      + (1.0 - _PIT_EWMA_DECAY) * (u - 0.5) ** 2)
                    if ad["loss_fast"] is None:
                        ad["loss_fast"] = ad["loss_slow"] = lp_c
                    else:
                        ad["loss_fast"] = _LOSS_FAST_DECAY * _t(ad["loss_fast"]) + (1.0 - _LOSS_FAST_DECAY) * lp_c
                        ad["loss_slow"] = _LOSS_SLOW_DECAY * _t(ad["loss_slow"]) + (1.0 - _LOSS_SLOW_DECAY) * lp_c
                    e_t = float(ad["pit_ewma"]) - _PIT_DISPERSION_TARGET
                    dloss_t = float(ad["loss_fast"]) - float(ad["loss_slow"])
                if abs(e_t) > _TEMP_AMBIG_EPS:
                    direction = -1.0 if e_t > 0.0 else 1.0
                else:
                    direction = 1.0 if dloss_t > 0.0 else (-1.0 if dloss_t < 0.0 else 0.0)
                le = _t(ad["log_eta"]).detach() + self.temp_rho * direction
                lo = torch.log(self.learning_rate / self.temp_band)
                hi = torch.log(self.learning_rate * self.temp_band)
                # clamp with the band's gradient when a bound binds
                if bool(le < lo):
                    le = lo
                elif bool(le > hi):
                    le = hi
                else:
                    # inside the band log_eta is log(lr) plus a sum of constant steps
                    base = torch.log(self.learning_rate)
                    le = le + (base - base.detach())
                ad["log_eta"] = le
            eta_t = torch.exp(_t(ad["log_eta"]))

        # weight update from the resolved one-step predictive
        log_w = _LogW(state["log_w"])
        prev = state["log_w"]
        decay = getattr(prev, "decay", None)
        if decay is None:
            decay = torch.ones((), dtype=DTYPE) if fresh else torch.zeros((), dtype=DTYPE)
        updated = False
        for i in range(n):
            q = state["qdist"][i]
            if q:
                lp = _clamp_lp(q.pop(0).logpdf(y))
                carried = _t(log_w[i])
                if self.detach_carry:
                    # truncate the recursion's graph at one step, but keep the prior's
                    # exact gradient (d log_w_t / d prior = forget^t) through a value-zero term
                    pr = decay * self.prior_log_weights[i]
                    carried = carried.detach() + (pr - pr.detach())
                log_w[i] = (self.forget * carried + eta_t * lp
                            - self.complexity_penalty * self.depths[i])
                updated = True
            q.append(all_dists[i][0])
        log_w.decay = (self.forget * decay).detach() if updated else decay
        state["log_w"] = log_w
        lw = torch.stack([_t(v).reshape(()) for v in log_w])
        self.last_log_w = lw.detach()
        if self.gate_offset is not None:
            lw = lw + self.gate_offset
        max_lw = torch.max(lw)
        w = torch.exp(lw - max_lw)
        tot = torch.sum(w)

        ref_leaf = not isinstance(self.tleafs[0], nn.Module)
        combined = []
        for h in range(k):
            means = torch.stack([all_dists[i][h].mean.reshape(()) for i in range(n)])
            mu_h = torch.sum(w * means) / tot
            mq = state["mean_q"][h]
            if len(mq) >= h + 1:
                r = float(y.detach()) - float(_t(mq.pop(0)).detach())     # leaf sees a constant residual
                ls = state["leaf_state"][h]
                if ref_leaf and ls is not None:
                    from skaters.torch.state import floats
                    ls = floats(ls)                 # a reference leaf keeps floats
                ld, state["leaf_state"][h] = self.tleafs[h](r, ls)
                state["leaf_pred"][h] = ld[0]
            if state["leaf_pred"][h] is not None:
                pred = TorchDist.from_reference(state["leaf_pred"][h]).shift(mu_h)
            else:
                pred = TorchDist.combine([all_dists[i][h] for i in range(n)], w)
                if len(pred) > self.max_components:
                    pred = _prune(pred, self.max_components)
            combined.append(pred)
            mq.append(mu_h)
        if self.adaptive_temperature:
            state["adapt"]["pred_q"].append(combined[0])
        return combined, state


def _prune(d: TorchDist, max_components: int) -> TorchDist:
    """``TorchDist.prune``: the reference's merge path on detached floats, the
    merged moments as tensors, so the warm-up predictive keeps its gradient."""
    return d.prune(max_components)


def terminal_leaf_ensemble(skaters, leaf_fn=None, k: int = 1, learning_rate: float = 0.5,
                           complexity_penalty: float = 0.0, depths=None, prior_log_weights=None,
                           max_components: int = 20, forget: float = 1.0,
                           adaptive_temperature: bool = False, temp_rho: float = 0.03,
                           temp_band: float = 3.0) -> TerminalLeafEnsemble:
    """Factory with the reference's name and signature. The default terminal
    leaf is the torch ``crps_leaf``."""
    if leaf_fn is None:
        from skaters.torch.leaf import crps_leaf as torch_crps_leaf
        leaf_fn = torch_crps_leaf
    return TerminalLeafEnsemble(skaters, k=k, leaf_fn=leaf_fn, learning_rate=learning_rate,
                                complexity_penalty=complexity_penalty, depths=depths,
                                prior_log_weights=prior_log_weights, max_components=max_components,
                                forget=forget, adaptive_temperature=adaptive_temperature,
                                temp_rho=temp_rho, temp_band=temp_band)

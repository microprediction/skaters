"""Adaptive search over the transform tree, in torch: the twin of
:mod:`skaters.search`.

Same grammar, same expand/prune/merge schedule and the same #223
parent-relative child initialisation. Candidates are torch conjugation
chains built from a recipe (never stored as data: the pool holds the live
chain, its recipe and its transform modules, exactly as the reference pool
holds closures), the leaf is the reference leaf as a constant, and every
candidate's per-horizon ``log_w`` is a 0-d tensor so a log score at the
combined output differentiates through the softmax weights into the
transforms' parameters. Ordering decisions (which candidates to expand,
which to prune, which mixture components to merge) are taken on float
values; the arithmetic that reaches the output stays on tensors.
"""

from __future__ import annotations

import math
from collections import deque

import torch

from skaters.leaf import leaf as reference_leaf
from skaters.torch.conjugate import conjugate, reference_skater
from skaters.torch.dist import TorchDist, DTYPE, _t
from skaters.torch.periodicity import period_detector, top_periods
from skaters.torch.transform import from_reference


def _zero():
    return torch.zeros((), dtype=DTYPE)


def _psum(terms):
    """CPython's float ``sum()`` (Neumaier compensation) on 0-d tensors."""
    total = _zero()
    c = _zero()
    for x in terms:
        x = _t(x)
        t = total + x
        if bool(torch.abs(total) >= torch.abs(x)):
            c = c + ((total - t) + x)
        else:
            c = c + ((x - t) + total)
        total = t
    return total + c


# The grammar: (name, (registry name, kwargs), cost_per_obs), the reference's
# table expressed as module specs so a recipe rebuilds the same chain.
TRANSFORMS = [
    ("ema_t(0.05)", ("ema_transform", {"alpha": 0.05}), 1),
    ("ema_t(0.1)", ("ema_transform", {"alpha": 0.1}), 1),
    ("ema_t(0.3)", ("ema_transform", {"alpha": 0.3}), 1),
    ("diff", ("difference", {}), 1),
    ("std(0.05)", ("standardize", {"alpha": 0.05}), 1),
    ("frac(0.3)", ("fractional_difference", {"d": 0.3, "window": 30}), 3),
    ("garch", ("garch", {}), 1),
    ("pow(0.5)", ("power_transform", {"p": 0.5}), 1),
    ("ar(2)", ("ar", {"order": 2}), 2),
    ("ar(5)", ("ar", {"order": 5, "decay": 1}), 3),
    ("gar(16)", ("grouped_ar", {"max_lag": 16}), 2),
    ("theta(0.1)", ("theta", {"alpha": 0.1}), 1),
    ("theta(0.3)", ("theta", {"alpha": 0.3}), 1),
    ("drift", ("drift", {}), 1),
    ("drift(0.01)", ("drift", {"alpha": 0.01, "shrinkage": 0.002}), 1),
    ("holt(0.1,0.05)", ("holt_linear", {"alpha": 0.1, "beta": 0.05}), 1),
    ("holt(0.3,0.1)", ("holt_linear", {"alpha": 0.3, "beta": 0.1}), 1),
    ("seas(7)", ("seasonal_difference", {"period": 7}), 1),
    ("seas(12)", ("seasonal_difference", {"period": 12}), 1),
    ("seas(24)", ("seasonal_difference", {"period": 24}), 1),
]


def _prune_dist(d: TorchDist, max_components: int) -> TorchDist:
    """``Dist.prune`` on tensors: closest-pair moment-matching merges, pair
    selection on floats exactly as the reference (sorted by (mean, std,
    weight); first pair within ``1e-9 * span`` of the minimum distance)."""
    max_components = max(1, max_components)
    comps = list(zip(d.w, d.m, d.s))
    if len(comps) <= max_components:
        return d
    def _f(x):
        return float(x.detach()) if hasattr(x, "detach") else float(x)
    comps.sort(key=lambda c: (_f(c[1]), _f(c[2]), _f(c[0])))
    scale = (_f(comps[-1][1]) - _f(comps[0][1])) + 1e-12
    while len(comps) > max_components:
        best_dist = float("inf")
        for i in range(len(comps)):
            for j in range(i + 1, len(comps)):
                dd = abs(_f(comps[i][1]) - _f(comps[j][1]))
                if dd < best_dist:
                    best_dist = dd
        thresh = best_dist + 1e-9 * scale
        best_i = best_j = None
        for i in range(len(comps)):
            for j in range(i + 1, len(comps)):
                if abs(_f(comps[i][1]) - _f(comps[j][1])) <= thresh:
                    best_i, best_j = i, j
                    break
            if best_i is not None:
                break
        if best_i is None:
            best_i, best_j = 0, 1
        wi, mi, si = comps[best_i]
        wj, mj, sj = comps[best_j]
        w_new = wi + wj
        if bool(w_new < 1e-300):
            m_new = 0.5 * (mi + mj)
            s_new = torch.clamp(torch.maximum(si, sj), min=1e-12)
        else:
            m_new = (wi * mi + wj * mj) / w_new
            v_new = (wi * (si * si + (mi - m_new) ** 2) + wj * (sj * sj + (mj - m_new) ** 2)) / w_new
            s_new = torch.sqrt(torch.clamp(v_new, min=0.0))
        comps[best_i] = (w_new, m_new, s_new)
        comps.pop(best_j)
    return TorchDist([c[0] for c in comps], [c[1] for c in comps], [c[2] for c in comps])


def search(
    k: int = 1,
    learning_rate: float = 0.5,
    complexity_penalty: float = 0.02,
    max_pool: int = 30,
    expand_interval: int = 100,
    expand_top_n: int = 3,
    max_depth: int = 3,
    replay_buffer: int = 500,
    prune_threshold: float = -50.0,
    max_components: int = 20,
    cost_budget: float = float("inf"),
):
    """Adaptive-search skater; same arguments and defaults as the reference."""
    _pd_func = period_detector()

    def _search(y, state=None):
        y = _t(y)
        if state is None:
            state = {
                "pool": _init_pool(k, cost_budget=cost_budget),
                "n_obs": 0,
                "buffer": deque(maxlen=replay_buffer),
                "pd_state": None,
                "detected_periods": set(),
                "transforms": list(TRANSFORMS),
            }
        state["n_obs"] += 1
        state["buffer"].append(y)
        pool = state["pool"]

        for entry in pool:
            dists, entry["s"] = entry["f"](y, entry["s"])
            entry["dists"] = dists
            entry["age"] += 1

        for entry in pool:
            for h in range(k):
                q = entry["queues"][h]
                q.append(entry["dists"][h])
                if len(q) > h + 1:
                    past_dist = q.popleft()
                    if entry["warmed"]:
                        lp = past_dist.logpdf(y)
                        if bool(lp > 20.0):
                            lp = torch.as_tensor(20.0, dtype=DTYPE)
                        elif not bool(lp >= -20.0):
                            lp = torch.as_tensor(-20.0, dtype=DTYPE)
                        entry["log_w"][h] = (entry["log_w"][h] + learning_rate * lp
                                             - complexity_penalty * entry["depth"])

        scores, state["pd_state"] = _pd_func(y, state["pd_state"])

        if state["n_obs"] % expand_interval == 0 and state["n_obs"] > 10:
            detected = top_periods(scores, threshold=0.3, max_periods=3)
            for period in detected:
                if period not in state["detected_periods"]:
                    state["detected_periods"].add(period)
                    state["transforms"].append(
                        (f"seas({period})", ("seasonal_difference", {"period": period}), 2))
            new_children = _expand(pool, k, expand_top_n, max_depth,
                                   transforms=state["transforms"], cost_budget=cost_budget)
            for child in new_children:
                _warmup(child, state["buffer"], k)
            pool.extend(new_children)
            _prune(pool, prune_threshold, max_pool, k)

        combined = []
        for h in range(k):
            log_ws = [e["log_w"][h] for e in pool]
            max_lw = max(log_ws, key=lambda t: float(t.detach()))
            if math.isfinite(float(max_lw.detach())):
                weights = [torch.exp(lw - max_lw) for lw in log_ws]
            else:
                weights = [1.0] * len(pool)
            dist = TorchDist.combine([e["dists"][h] for e in pool], weights)
            if len(dist) > max_components:
                dist = _prune_dist(dist, max_components)
            combined.append(dist)
        return combined, state

    _search.__name__ = f"search(k={k})"
    return _search


def _make_entry(skater_fn, depth: int, recipe: list, k: int, cost: float = 0.0, mods=None) -> dict:
    return {
        "f": skater_fn,
        "s": None,
        "depth": depth,
        "recipe": recipe,
        "cost": cost,
        "age": 0,
        "warmed": False,
        "log_w": [_zero() for _ in range(k)],
        "queues": [deque() for _ in range(k)],
        "dists": None,
        "mods": mods or [],      # the chain's transform modules, outer first (parameters)
    }


def _warmup(entry: dict, buffer: deque, k: int):
    for y in buffer:
        dists, entry["s"] = entry["f"](y, entry["s"])
        entry["dists"] = dists
        entry["age"] += 1
    if entry["dists"] is not None:
        for h in range(k):
            entry["queues"][h].clear()
            entry["queues"][h].append(entry["dists"][h])
    entry["warmed"] = True


def _build_from_recipe(recipe: list, k: int, transforms=None):
    """Rebuild a torch chain from its recipe; returns ``(skater, modules)``."""
    if transforms is None:
        transforms = TRANSFORMS
    t_lookup = {name: spec for name, spec, *_ in transforms}
    f = reference_skater(reference_leaf(k=k))
    mods = []
    for t_name in recipe:
        reg, kw = t_lookup[t_name]
        m = from_reference(reg, **kw)
        mods.insert(0, m)
        f = conjugate(f, m, k=k)
    return f, mods


def _init_pool(k: int, cost_budget: float = float("inf")) -> list:
    pool = []
    entry = _make_entry(reference_skater(reference_leaf(k=k)), depth=0, recipe=[], k=k, cost=1.0)
    entry["warmed"] = True
    pool.append(entry)
    for t_name, _spec, t_cost in TRANSFORMS:
        candidate_cost = 1.0 + t_cost
        if candidate_cost > cost_budget:
            continue
        f, mods = _build_from_recipe([t_name], k)
        f.__name__ = f"{t_name}|leaf"
        entry = _make_entry(f, depth=1, recipe=[t_name], k=k, cost=candidate_cost, mods=mods)
        entry["warmed"] = True
        pool.append(entry)
    return pool


def _avg_log_w(e: dict, k: int):
    return _psum(e["log_w"]) / k


def _expand(pool: list, k: int, top_n: int, max_depth: int, transforms=None,
            cost_budget: float = float("inf")) -> list:
    if transforms is None:
        transforms = TRANSFORMS
    scored = [(float(_avg_log_w(e, k).detach()), i, e) for i, e in enumerate(pool)]
    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
    existing = {tuple(e["recipe"]) for e in pool}
    children = []
    for _, _, parent in scored[:top_n]:
        if parent["depth"] >= max_depth:
            continue
        for t_name, _spec, t_cost in transforms:
            child_cost = parent["cost"] + t_cost
            if child_cost > cost_budget:
                continue
            if parent["recipe"] and parent["recipe"][-1] == t_name:
                continue
            new_recipe = parent["recipe"] + [t_name]
            if tuple(new_recipe) in existing:
                continue
            existing.add(tuple(new_recipe))
            child_fn, mods = _build_from_recipe(new_recipe, k, transforms)
            child_fn.__name__ = "|".join(new_recipe) + "|leaf"
            child = _make_entry(child_fn, depth=len(new_recipe), recipe=new_recipe, k=k,
                                cost=child_cost, mods=mods)
            child["log_w"] = list(parent["log_w"])        # skaters#223: inherit the evidence
            children.append(child)
    return children


def _prune(pool: list, threshold: float, max_pool: int, k: int):
    if len(pool) <= 1:
        return
    best = max(float(_avg_log_w(e, k).detach()) for e in pool)
    i = 0
    while i < len(pool):
        avg_w = float(_avg_log_w(pool[i], k).detach())
        if avg_w < best + threshold and len(pool) > 1:
            pool.pop(i)
        else:
            i += 1
    while len(pool) > max_pool:
        worst_idx = min(range(len(pool)), key=lambda i: float(_avg_log_w(pool[i], k).detach()))
        pool.pop(worst_idx)

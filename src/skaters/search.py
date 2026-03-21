"""Adaptive search over the transform tree.

Instead of pre-enumerating a fixed candidate population, this module
grows the population online by expanding top performers with new
transforms and pruning losers.

The search proceeds like beam search over the transform grammar:

    Generation 0:  leaf                           (depth 0)
    Generation 1:  ema_t(α)|leaf, diff|leaf, ...  (depth 1)
    Generation 2:  diff|ema_t(α)|leaf, ...        (depth 2)
    ...

At each expansion step:
    1. Score all active candidates by cumulative log-likelihood
    2. Kill candidates below a weight threshold
    3. Take the top performers and conjugate them with each available
       transform to produce children
    4. Replay recent history through the children so they join warm
    5. Cap pool size by pruning the weakest

A rolling buffer of recent observations is maintained so that new
candidates can be replayed through history and start competing
immediately instead of wasting burn-in time.
"""

from __future__ import annotations
import math
from collections import deque
from skaters.dist import Dist
from skaters.leaf import leaf
from skaters.conjugate import conjugate
from skaters.transform import (
    difference, fractional_difference, standardize, ema_transform,
    garch, seasonal_difference, power_transform,
)
from skaters.periodicity import period_detector, top_periods


# The grammar: available transforms for expansion
# Each entry: (name, factory, cost_per_obs)
# Cost is empirically measured relative to leaf (~0.5μs/obs):
#   1 = ~1μs/obs (ema, diff, std, garch, pow, seas)
#   3 = ~3μs/obs (frac diff w=30)
TRANSFORMS = [
    ("ema_t(0.05)", lambda: ema_transform(0.05), 1),
    ("ema_t(0.1)", lambda: ema_transform(0.1), 1),
    ("ema_t(0.3)", lambda: ema_transform(0.3), 1),
    ("diff", lambda: difference(), 1),
    ("std(0.05)", lambda: standardize(0.05), 1),
    ("frac(0.3)", lambda: fractional_difference(0.3, 30), 3),
    ("garch", lambda: garch(), 1),
    ("pow(0.5)", lambda: power_transform(0.5), 1),
]


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
    """Create an adaptive-search skater.

    Args:
        k: forecast horizon
        learning_rate: η for Bayesian scoring
        complexity_penalty: per-step cost per unit of depth
        max_pool: maximum number of active candidates
        expand_interval: expand every N observations
        expand_top_n: how many top candidates to expand
        max_depth: maximum transform chain depth
        replay_buffer: number of recent observations to keep. New
            candidates are replayed through this buffer so they join
            the pool warm (with meaningful state) instead of cold.
        prune_threshold: kill candidates whose log-weight relative to
            the leader falls below this
        max_components: prune combined Dist to this many components
        cost_budget: maximum per-candidate cost (sum of transform costs).
            Candidates exceeding this budget are not created. Use
            float("inf") for no limit. Low values (e.g. 5) restrict
            to cheap transforms only.
    """

    _pd_func = period_detector()

    def _search(y: float, state: dict | None) -> tuple[list[Dist], dict]:
        if state is None:
            state = {
                "pool": _init_pool(k, cost_budget=cost_budget),
                "n_obs": 0,
                "buffer": deque(maxlen=replay_buffer),
                "pd_state": None,
                "detected_periods": set(),
                "transforms": list(TRANSFORMS),  # per-instance copy
            }

        state["n_obs"] += 1
        state["buffer"].append(y)

        pool = state["pool"]

        # 1. Run all active candidates
        for entry in pool:
            dists, entry["s"] = entry["f"](y, entry["s"])
            entry["dists"] = dists
            entry["age"] += 1

        # 2. Score: resolve queued predictions
        for entry in pool:
            for h in range(k):
                q = entry["queues"][h]
                if q:
                    past_dist = q.popleft()
                    if entry["warmed"]:
                        lp = max(past_dist.logpdf(y), -20.0)
                        entry["log_w"][h] += (
                            learning_rate * lp
                            - complexity_penalty * entry["depth"]
                        )

        # 3. Queue current predictions
        for entry in pool:
            for h in range(k):
                entry["queues"][h].append(entry["dists"][h])

        # 3b. Run period detector
        scores, state["pd_state"] = _pd_func(y, state["pd_state"])

        # 4. Periodically expand and prune
        if state["n_obs"] % expand_interval == 0 and state["n_obs"] > 10:
            # Inject seasonal transforms for newly detected periods
            detected = top_periods(scores, threshold=0.3, max_periods=3)
            for period in detected:
                if period not in state["detected_periods"]:
                    state["detected_periods"].add(period)
                    t_name = f"seas({period})"
                    state["transforms"].append(
                        (t_name, lambda p=period: seasonal_difference(p), 2)
                    )

            new_children = _expand(pool, k, expand_top_n, max_depth,
                                   transforms=state["transforms"],
                                   cost_budget=cost_budget)
            # Replay history through new children so they join warm
            for child in new_children:
                _warmup(child, state["buffer"], k)
            pool.extend(new_children)
            _prune(pool, prune_threshold, max_pool, k)

        # 5. Combine predictions via softmax weights
        combined = []
        for h in range(k):
            log_ws = [e["log_w"][h] for e in pool]
            max_lw = max(log_ws)
            if math.isfinite(max_lw):
                weights = [math.exp(lw - max_lw) for lw in log_ws]
            else:
                weights = [1.0] * len(pool)

            horizon_dists = [e["dists"][h] for e in pool]
            dist = Dist.combine(horizon_dists, weights)
            if len(dist) > max_components:
                dist = dist.prune(max_components)
            combined.append(dist)

        return combined, state

    _search.__name__ = f"search(k={k})"
    return _search


def _make_entry(skater_fn, depth: int, recipe: list[str], k: int, cost: float = 0.0) -> dict:
    """Create a pool entry for a candidate."""
    return {
        "f": skater_fn,
        "s": None,           # skater state
        "depth": depth,
        "recipe": recipe,    # list of transform names (for building children)
        "cost": cost,        # total cost per observation (sum of transform costs)
        "age": 0,
        "warmed": False,     # becomes True after warmup/initial burn-in
        "log_w": [0.0] * k,
        "queues": [deque() for _ in range(k)],
        "dists": None,
    }


def _warmup(entry: dict, buffer: deque, k: int):
    """Replay a history buffer through a candidate to warm up its state.

    Runs silently — no scoring, just state building. After warmup the
    candidate has meaningful internal state and its last prediction
    is queued for scoring on the next real observation.
    """
    for y in buffer:
        dists, entry["s"] = entry["f"](y, entry["s"])
        entry["dists"] = dists
        entry["age"] += 1

    # Queue the last prediction for scoring
    if entry["dists"] is not None:
        for h in range(k):
            entry["queues"][h].clear()
            entry["queues"][h].append(entry["dists"][h])

    entry["warmed"] = True


def _init_pool(k: int, cost_budget: float = float("inf")) -> list[dict]:
    """Seed the pool with depth-0 and depth-1 candidates within budget."""
    pool = []

    # Depth 0: just a leaf (cost = 1 for the leaf itself)
    entry = _make_entry(leaf(k=k), depth=0, recipe=[], k=k, cost=1.0)
    entry["warmed"] = True
    pool.append(entry)

    # Depth 1: each single transform applied to leaf
    for t_name, t_factory, t_cost in TRANSFORMS:
        candidate_cost = 1.0 + t_cost  # leaf + transform
        if candidate_cost > cost_budget:
            continue
        f = conjugate(leaf(k=k), t_factory(), k=k)
        f.__name__ = f"{t_name}|leaf"
        entry = _make_entry(f, depth=1, recipe=[t_name], k=k, cost=candidate_cost)
        entry["warmed"] = True
        pool.append(entry)

    return pool


def _expand(pool: list[dict], k: int, top_n: int, max_depth: int,
            transforms: list | None = None,
            cost_budget: float = float("inf")) -> list[dict]:
    """Take the top performers and create children.

    Returns the new children (not yet added to pool).
    """
    if transforms is None:
        transforms = TRANSFORMS

    # Build cost lookup
    cost_lookup = {name: cost for name, _, cost in transforms}

    scored = [(sum(e["log_w"]) / k, i, e) for i, e in enumerate(pool)]
    scored.sort(reverse=True)

    existing = {tuple(e["recipe"]) for e in pool}

    children = []
    for _, _, parent in scored[:top_n]:
        if parent["depth"] >= max_depth:
            continue

        for t_name, t_factory, t_cost in transforms:
            # Check cost budget
            child_cost = parent["cost"] + t_cost
            if child_cost > cost_budget:
                continue

            if parent["recipe"] and parent["recipe"][-1] == t_name:
                continue

            new_recipe = parent["recipe"] + [t_name]
            if tuple(new_recipe) in existing:
                continue
            existing.add(tuple(new_recipe))

            child_fn = _build_from_recipe(new_recipe, k, transforms)
            child_fn.__name__ = "|".join(new_recipe) + "|leaf"
            children.append(_make_entry(
                child_fn, depth=len(new_recipe), recipe=new_recipe, k=k,
                cost=child_cost,
            ))

    return children


def _build_from_recipe(recipe: list[str], k: int, transforms: list | None = None):
    """Reconstruct a skater from its transform recipe."""
    if transforms is None:
        transforms = TRANSFORMS
    t_lookup = {name: factory for name, factory, *_ in transforms}
    f = leaf(k=k)
    for t_name in recipe:
        f = conjugate(f, t_lookup[t_name](), k=k)
    return f


def _prune(pool: list[dict], threshold: float, max_pool: int, k: int):
    """Remove candidates that are hopelessly behind the leader."""
    if len(pool) <= 1:
        return

    best = max(sum(e["log_w"]) / k for e in pool)

    i = 0
    while i < len(pool):
        avg_w = sum(pool[i]["log_w"]) / k
        if avg_w < best + threshold and len(pool) > 1:
            pool.pop(i)
        else:
            i += 1

    while len(pool) > max_pool:
        worst_idx = min(range(len(pool)), key=lambda i: sum(pool[i]["log_w"]) / k)
        pool.pop(worst_idx)

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
from skaters.transform import difference, fractional_difference, standardize, ema_transform


# The grammar: available transforms for expansion
TRANSFORMS = [
    ("ema_t(0.05)", lambda: ema_transform(0.05)),
    ("ema_t(0.1)", lambda: ema_transform(0.1)),
    ("ema_t(0.3)", lambda: ema_transform(0.3)),
    ("diff", lambda: difference()),
    ("std(0.05)", lambda: standardize(0.05)),
    ("frac(0.3)", lambda: fractional_difference(0.3, 30)),
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
    """

    def _search(y: float, state: dict | None) -> tuple[list[Dist], dict]:
        if state is None:
            state = {
                "pool": _init_pool(k),
                "n_obs": 0,
                "buffer": deque(maxlen=replay_buffer),
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

        # 4. Periodically expand and prune
        if state["n_obs"] % expand_interval == 0 and state["n_obs"] > 10:
            new_children = _expand(pool, k, expand_top_n, max_depth)
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


def _make_entry(skater_fn, depth: int, recipe: list[str], k: int) -> dict:
    """Create a pool entry for a candidate."""
    return {
        "f": skater_fn,
        "s": None,           # skater state
        "depth": depth,
        "recipe": recipe,    # list of transform names (for building children)
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


def _init_pool(k: int) -> list[dict]:
    """Seed the pool with depth-0 and depth-1 candidates."""
    pool = []

    # Depth 0: just a leaf
    entry = _make_entry(leaf(k=k), depth=0, recipe=[], k=k)
    entry["warmed"] = True  # initial candidates score from the start
    pool.append(entry)

    # Depth 1: each single transform applied to leaf
    for t_name, t_factory in TRANSFORMS:
        f = conjugate(leaf(k=k), t_factory(), k=k)
        f.__name__ = f"{t_name}|leaf"
        entry = _make_entry(f, depth=1, recipe=[t_name], k=k)
        entry["warmed"] = True
        pool.append(entry)

    return pool


def _expand(pool: list[dict], k: int, top_n: int, max_depth: int) -> list[dict]:
    """Take the top performers and create children.

    Returns the new children (not yet added to pool).
    """
    scored = [(sum(e["log_w"]) / k, i, e) for i, e in enumerate(pool)]
    scored.sort(reverse=True)

    existing = {tuple(e["recipe"]) for e in pool}

    children = []
    for _, _, parent in scored[:top_n]:
        if parent["depth"] >= max_depth:
            continue

        for t_name, t_factory in TRANSFORMS:
            if parent["recipe"] and parent["recipe"][-1] == t_name:
                continue

            new_recipe = parent["recipe"] + [t_name]
            if tuple(new_recipe) in existing:
                continue
            existing.add(tuple(new_recipe))

            child_fn = _build_from_recipe(new_recipe, k)
            child_fn.__name__ = "|".join(new_recipe) + "|leaf"
            children.append(_make_entry(
                child_fn, depth=len(new_recipe), recipe=new_recipe, k=k
            ))

    return children


def _build_from_recipe(recipe: list[str], k: int):
    """Reconstruct a skater from its transform recipe."""
    t_lookup = {name: factory for name, factory in TRANSFORMS}
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

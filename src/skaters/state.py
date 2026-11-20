"""Checkpoint and restore for skater state: the fold contract.

A skater is a fold, so its state must be plain data that survives JSON
bit-exactly. A stream can then be stopped, stored, and resumed anywhere,
including in another port (JS, R, Julia), with the same numbers. Skater
state holds only None, bools, ints, finite floats, strings, lists, dicts
with string keys, and Dist objects (including the GPD-spliced predictive).
Closures are configuration and live in the skater, never in state.

    plain = state_to_json(state)            # Dist -> {"components": ...}
    text = json.dumps(plain)
    back = state_from_json(json.loads(text))  # {"components": ...} -> Dist, no renormalising

The canonical layout is documented in docs/STATE.md. This module mirrors
docs/js/skaters/state.mjs (stateToJSON, stateFromJSON, assertPlainState).

Both walkers raise ValueError, naming the offending path, on anything JSON
would damage or that another port could not read: non-finite floats, dict
keys that are not strings, deques, sets, and objects other than a Dist.
A tuple is written as a list, as JSON itself would; the canonical form of
every sequence is a list.
"""

from __future__ import annotations

import math

from skaters.dist import Dist

__all__ = ["state_to_json", "state_from_json", "assert_plain_state"]


def _is_dist(v) -> bool:
    if isinstance(v, Dist):
        return True
    from skaters.tails import SplicedDist          # local: avoid cycle
    return isinstance(v, SplicedDist)


def _offend(path: str, what: str):
    raise ValueError(f"skater state is not plain data at {path or '<root>'}: {what}")


def _walk(v, path: str, build: bool):
    if v is None or isinstance(v, (bool, str)):
        return v
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        if not math.isfinite(v):
            _offend(path, f"non-finite float {v!r} (JSON has no literal for it)")
        return v
    if _is_dist(v):
        if not build:
            return v
        d = v.to_dict()
        return _walk(d, path, True)
    if isinstance(v, (list, tuple)):
        if not build:
            for i, x in enumerate(v):
                _walk(x, f"{path}[{i}]", False)
            return v
        return [_walk(x, f"{path}[{i}]", True) for i, x in enumerate(v)]
    if isinstance(v, dict):
        out = {} if build else None
        for k, x in v.items():
            if not isinstance(k, str):
                _offend(path, f"a dict key {k!r} of type {type(k).__name__} (JSON keys are strings)")
            r = _walk(x, f"{path}.{k}", build)
            if build:
                out[k] = r
        return out if build else v
    if callable(v):
        _offend(path, "a function (closures belong in the skater, not in state)")
    _offend(path, f"an instance of {type(v).__name__} (not plain data)")


def assert_plain_state(state):
    """Raise ValueError if ``state`` holds anything that would not survive JSON."""
    _walk(state, "", False)
    return state


def state_to_json(state):
    """Plain-data image of ``state``: every Dist becomes its ``to_dict()`` form,
    tuples become lists. Raises ValueError, naming the path, on anything else
    non-plain. Also accepts a list of Dists (a skater output)."""
    return _walk(state, "", True)


def _is_dist_dict(v: dict) -> bool:
    if v.get("spliced") is True:
        return True
    return len(v) == 1 and isinstance(v.get("components"), list)


def state_from_json(obj):
    """Inverse of :func:`state_to_json`. A ``{"components": [[w, m, s], ...]}``
    dict becomes a Dist without renormalising, a ``{"spliced": true, ...}``
    dict becomes a SplicedDist; everything else is copied as is."""
    if isinstance(obj, list):
        return [state_from_json(x) for x in obj]
    if isinstance(obj, dict):
        if _is_dist_dict(obj):
            return Dist.from_dict(obj)
        return {k: state_from_json(x) for k, x in obj.items()}
    return obj


# ---------------------------------------------------------------------------
# Migration of pre-canonical Python checkpoints
# ---------------------------------------------------------------------------

def _unqueue(x):
    """Old Python checkpoints kept queues as ``collections.deque``. Return the
    same nesting with every deque replaced by a list, recursing through lists
    only (queue contents such as Dists are kept as they are). Used by the
    skaters on their first step after a restore."""
    from collections import deque
    if isinstance(x, deque):
        return [_unqueue(v) for v in x]
    if isinstance(x, list) and any(isinstance(v, (deque, list)) for v in x):
        return [_unqueue(v) for v in x]
    return x

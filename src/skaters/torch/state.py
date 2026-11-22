"""Checkpoint and restore for torch skater state, in the canonical layout.

The torch port keeps the reference's state layout (docs/STATE.md) key for
key: the same dicts, the same lists, the same nesting. What differs is only
the leaf values. Where the reference holds a float, the torch state holds a
0-d float64 tensor (so gradients can flow through it), and where the
reference holds a ``Dist`` or ``SplicedDist``, the torch state holds a
:class:`TorchDist` or :class:`TorchSplicedDist`. Integers, booleans, strings
and ``None`` are the same Python objects in both.

These two functions convert at the JSON boundary:

    plain = state_to_json(state)      # tensors -> numbers, dists -> dicts
    state = state_from_json(plain)    # numbers -> tensors, dicts -> dists

A state written here is read by :func:`skaters.state.state_from_json`, and a
state written there is read here, so a stream can move between the
reference and the torch port mid-flight. A restored state carries no graph:
every tensor is a fresh constant.

Restoring turns every JSON float into a tensor, including a few that the
torch modules keep as plain floats (the tail bookkeeping, the lattice table,
the parade's PIT and z). Those modules accept either and convert back on
their next step.
"""

from __future__ import annotations

import math

import torch

from skaters.torch.dist import TorchDist, DTYPE

__all__ = ["state_to_json", "state_from_json", "assert_plain_state", "floats"]


def _offend(path: str, what: str):
    raise ValueError(f"skater state is not plain data at {path or '<root>'}: {what}")


def _num(x: float, path: str):
    if not math.isfinite(x):
        _offend(path, f"non-finite value {x!r} (JSON has no literal for it)")
    return x


def _dist_dict(d, path: str) -> dict:
    """The canonical encoding of a torch or reference distribution, or None."""
    from skaters.torch.tails import TorchSplicedDist
    if isinstance(d, TorchDist):
        comps = [[_num(float(w), path), _num(float(m), path), _num(float(s), path)]
                 for w, m, s in zip(d.w.detach().tolist(), d.m.detach().tolist(),
                                    d.s.detach().tolist())]
        return {"components": comps}
    if isinstance(d, TorchSplicedDist):
        out = d.to_dict()
        return _walk(out, path)
    from skaters.dist import Dist
    from skaters.tails import SplicedDist
    if isinstance(d, (Dist, SplicedDist)):
        return _walk(d.to_dict(), path)
    return None


def _walk(v, path: str):
    if v is None or isinstance(v, (bool, str)):
        return v
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return _num(v, path)
    if isinstance(v, torch.Tensor):
        if v.ndim != 0:
            _offend(path, f"a tensor of shape {tuple(v.shape)} (state holds scalars and lists)")
        x = v.detach().item()
        if isinstance(x, bool):
            return x
        if isinstance(x, int):
            return x
        return _num(float(x), path)
    if isinstance(v, (list, tuple)):
        return [_walk(x, f"{path}[{i}]") for i, x in enumerate(v)]
    if isinstance(v, dict):
        out = {}
        for k, x in v.items():
            if not isinstance(k, str):
                _offend(path, f"a dict key {k!r} of type {type(k).__name__} (JSON keys are strings)")
            out[k] = _walk(x, f"{path}.{k}")
        return out
    d = _dist_dict(v, path)
    if d is not None:
        return d
    if callable(v):
        _offend(path, "a function (closures belong in the skater, not in state)")
    _offend(path, f"an instance of {type(v).__name__} (not plain data)")


def state_to_json(state):
    """Plain-data image of a torch skater state in the canonical layout:
    0-d tensors become numbers, TorchDist and TorchSplicedDist become their
    dict encodings, tuples become lists. Raises ValueError, naming the path,
    on a deque, a set, a non-string key, a non-finite number or anything
    else that is not plain data."""
    return _walk(state, "")


def assert_plain_state(state):
    """Raise ValueError if ``state`` would not survive :func:`state_to_json`."""
    _walk(state, "")
    return state


def _is_dist_dict(v: dict) -> bool:
    if v.get("spliced") is True:
        return True
    return len(v) == 1 and isinstance(v.get("components"), list)


def _dist_from(obj: dict):
    from skaters.dist import Dist
    from skaters.tails import SplicedDist
    from skaters.torch.tails import TorchSplicedDist
    ref = Dist.from_dict(obj)       # the reference's keep-or-normalise rule
    if isinstance(ref, SplicedDist):
        return TorchSplicedDist.from_reference(ref)
    return TorchDist.from_reference(ref)


def state_from_json(obj):
    """Inverse of :func:`state_to_json`, and the reader of a reference
    checkpoint: floats become 0-d float64 tensors, ints stay ints, a
    ``{"components": ...}`` dict becomes a TorchDist (weights kept bit for
    bit when they sum to one), a ``{"spliced": true, ...}`` dict a
    TorchSplicedDist."""
    if isinstance(obj, list):
        return [state_from_json(x) for x in obj]
    if isinstance(obj, dict):
        if _is_dist_dict(obj):
            return _dist_from(obj)
        return {k: state_from_json(x) for k, x in obj.items()}
    if isinstance(obj, float):
        return torch.as_tensor(obj, dtype=DTYPE)
    return obj


def floats(x):
    """The same nesting with every 0-d tensor replaced by its float, for the
    parts of torch state kept as plain floats (bookkeeping off the graph)."""
    if isinstance(x, torch.Tensor):
        return float(x.detach())
    if isinstance(x, list):
        return [floats(v) for v in x]
    if isinstance(x, dict):
        return {k: floats(v) for k, v in x.items()}
    return x

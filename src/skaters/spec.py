"""Symbolic specification for skater pipelines.

A spec is a plain dict that fully describes how to build a skater.
It can be serialized to JSON, hashed, compared, and materialized
into a live skater via `build(spec)`.

Every spec has an "op" key. The grammar:

    spec := {"op": "leaf", "k": int}
          | {"op": "ema", "alpha": float, "k": int}
          | {"op": "ensemble", "k": int, "skaters": [spec, ...]}
          | {"op": "conjugate", "skater": spec, "transform": transform_spec}

    transform_spec := {"op": "diff"}
                    | {"op": "frac", "d": float, "window": int}
                    | {"op": "std", "alpha": float}
                    | {"op": "ema_t", "alpha": float}

Canonical names:

    leaf
    ema_t(0.1)|leaf                      # conjugation: transform|skater
    diff|ema_t(0.1)|leaf                 # chains read left-to-right
    ensemble(ema(0.01),ema(0.1))         # ema is shorthand for ema_t|leaf
    diff|ensemble(ema(0.01),ema(0.1))
"""

from __future__ import annotations
import json

from skaters.leaf import leaf
from skaters.ema import ema
from skaters.ensemble import precision_weighted_ensemble
from skaters.conjugate import conjugate
from skaters.transform import difference, fractional_difference, standardize, ema_transform


# ---------------------------------------------------------------------------
# Build: spec -> live skater
# ---------------------------------------------------------------------------

def build(spec: dict):
    """Materialize a spec dict into a live skater callable."""
    op = spec["op"]

    if op == "leaf":
        f = leaf(k=spec["k"])

    elif op == "ema":
        f = ema(alpha=spec["alpha"], k=spec["k"])

    elif op == "ensemble":
        k = spec["k"]
        subs = [build(s) for s in spec["skaters"]]
        f = precision_weighted_ensemble(subs, k=k, floor=spec.get("floor", 1e-6))

    elif op == "conjugate":
        inner = build(spec["skater"])
        t = _build_transform(spec["transform"])
        k = _infer_k(spec["skater"])
        f = conjugate(inner, t, k=k)

    else:
        raise ValueError(f"Unknown op: {op}")

    f.__name__ = name(spec)
    return f


def _build_transform(spec: dict):
    """Build a (forward, inverse_k) transform pair from a spec."""
    op = spec["op"]
    if op == "diff":
        return difference()
    elif op == "frac":
        return fractional_difference(d=spec["d"], window=spec.get("window", 50))
    elif op == "std":
        return standardize(alpha=spec.get("alpha", 0.05))
    elif op == "ema_t":
        return ema_transform(alpha=spec["alpha"])
    else:
        raise ValueError(f"Unknown transform op: {op}")


def _infer_k(spec: dict) -> int:
    """Walk the spec tree to find k."""
    if "k" in spec:
        return spec["k"]
    if "skater" in spec:
        return _infer_k(spec["skater"])
    if "skaters" in spec:
        return _infer_k(spec["skaters"][0])
    raise ValueError(f"Cannot infer k from spec: {spec}")


# ---------------------------------------------------------------------------
# Name: spec -> canonical string
# ---------------------------------------------------------------------------

def name(spec: dict) -> str:
    """Derive a canonical, deterministic name from a spec."""
    op = spec["op"]

    if op == "leaf":
        return "leaf"

    elif op == "ema":
        return f"ema({_fmt(spec['alpha'])})"

    elif op == "ensemble":
        inner = ",".join(name(s) for s in spec["skaters"])
        return f"ensemble({inner})"

    elif op == "conjugate":
        t = _transform_name(spec["transform"])
        s = name(spec["skater"])
        return f"{t}|{s}"

    else:
        raise ValueError(f"Unknown op: {op}")


def _transform_name(spec: dict) -> str:
    op = spec["op"]
    if op == "diff":
        return "diff"
    elif op == "frac":
        w = spec.get("window", 50)
        if w == 50:
            return f"frac({_fmt(spec['d'])})"
        return f"frac({_fmt(spec['d'])},w={w})"
    elif op == "std":
        return f"std({_fmt(spec.get('alpha', 0.05))})"
    elif op == "ema_t":
        return f"ema_t({_fmt(spec['alpha'])})"
    else:
        raise ValueError(f"Unknown transform op: {op}")


def _fmt(x: float) -> str:
    """Format a float compactly."""
    if x == int(x):
        return str(int(x))
    return f"{x:.6g}"


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def to_json(spec: dict) -> str:
    """Serialize a spec to JSON."""
    return json.dumps(spec, separators=(",", ":"))


def from_json(s: str) -> dict:
    """Deserialize a spec from JSON."""
    return json.loads(s)


# ---------------------------------------------------------------------------
# Spec constructors (convenience)
# ---------------------------------------------------------------------------

def leaf_spec(k: int = 1) -> dict:
    return {"op": "leaf", "k": k}


def ema_spec(alpha: float = 0.05, k: int = 1) -> dict:
    return {"op": "ema", "alpha": alpha, "k": k}


def ensemble_spec(*skater_specs: dict, k: int = 1) -> dict:
    return {"op": "ensemble", "k": k, "skaters": list(skater_specs)}


def conjugate_spec(skater_spec: dict, transform_spec: dict) -> dict:
    return {"op": "conjugate", "skater": skater_spec, "transform": transform_spec}


def diff_spec() -> dict:
    return {"op": "diff"}


def frac_spec(d: float = 0.4, window: int = 50) -> dict:
    return {"op": "frac", "d": d, "window": window}


def std_spec(alpha: float = 0.05) -> dict:
    return {"op": "std", "alpha": alpha}


def ema_t_spec(alpha: float = 0.05) -> dict:
    return {"op": "ema_t", "alpha": alpha}

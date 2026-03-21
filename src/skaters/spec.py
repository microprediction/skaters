"""Symbolic specification for skater pipelines.

A spec is a plain dict that fully describes how to build a skater.
It can be serialized to JSON, hashed, compared, and materialized
into a live skater via `build(spec)`.

Every spec has an "op" key. The grammar:

    spec := {"op": "ema", "alpha": float, "k": int}
          | {"op": "ensemble", "k": int, "skaters": [spec, ...]}
          | {"op": "conjugate", "skater": spec, "transform": transform_spec}
          | {"op": "envelope", "skater": spec, "k": int, "decay": float|null}
          | {"op": "calibrated", "skater": spec, "k": int, "target": float}

    transform_spec := {"op": "diff"}
                    | {"op": "frac", "d": float, "window": int}
                    | {"op": "std", "alpha": float}

Canonical names are derived from specs deterministically:

    ema(0.1)
    diff|ema(0.1)                        # conjugation: transform|skater
    std(0.05)|diff|ema(0.1)              # chains read left-to-right
    ensemble(ema(0.01),ema(0.1),ema(0.3))
    diff|ensemble(ema(0.01),ema(0.1))
    calibrated[diff|ensemble(ema(0.01),ema(0.1))]
    envelope[ema(0.1),decay=0.95]
"""

from __future__ import annotations
import json

from skaters.ema import ema
from skaters.ensemble import precision_weighted_ensemble
from skaters.conjugate import conjugate
from skaters.transform import difference, fractional_difference, standardize
from skaters.envelope import envelope
from skaters.calibrated import calibrated_envelope


# ---------------------------------------------------------------------------
# Build: spec -> live skater
# ---------------------------------------------------------------------------

def build(spec: dict):
    """Materialize a spec dict into a live skater callable.

    The returned skater's __name__ is set to the canonical name.
    """
    op = spec["op"]

    if op == "ema":
        f = ema(alpha=spec["alpha"], k=spec["k"])

    elif op == "ensemble":
        k = spec["k"]
        subs = [build(s) for s in spec["skaters"]]
        f = precision_weighted_ensemble(subs, k=k, floor=spec.get("floor", 1e-6))

    elif op == "conjugate":
        inner = build(spec["skater"])
        t = _build_transform(spec["transform"])
        k = spec["skater"]["k"] if "k" in spec["skater"] else _infer_k(spec["skater"])
        f = conjugate(inner, t, k=k)

    elif op == "envelope":
        inner = build(spec["skater"])
        k = spec["k"]
        f = envelope(inner, k=k, decay=spec.get("decay"))

    elif op == "calibrated":
        inner = build(spec["skater"])
        k = spec["k"]
        f = calibrated_envelope(inner, k=k, target=spec.get("target", 0.6827))

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

    if op == "ema":
        return f"ema({_fmt(spec['alpha'])})"

    elif op == "ensemble":
        inner = ",".join(name(s) for s in spec["skaters"])
        return f"ensemble({inner})"

    elif op == "conjugate":
        t = _transform_name(spec["transform"])
        s = name(spec["skater"])
        return f"{t}|{s}"

    elif op == "envelope":
        s = name(spec["skater"])
        decay = spec.get("decay")
        if decay is not None:
            return f"envelope[{s},decay={_fmt(decay)}]"
        return f"envelope[{s}]"

    elif op == "calibrated":
        s = name(spec["skater"])
        target = spec.get("target", 0.6827)
        if abs(target - 0.6827) < 1e-4:
            return f"calibrated[{s}]"
        return f"calibrated[{s},target={_fmt(target)}]"

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
    else:
        raise ValueError(f"Unknown transform op: {op}")


def _fmt(x: float) -> str:
    """Format a float compactly."""
    if x == int(x):
        return str(int(x))
    s = f"{x:.6g}"
    return s


# ---------------------------------------------------------------------------
# Parse: canonical name -> spec (roundtrip)
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

def ema_spec(alpha: float = 0.05, k: int = 1) -> dict:
    return {"op": "ema", "alpha": alpha, "k": k}


def ensemble_spec(*skater_specs: dict, k: int = 1) -> dict:
    return {"op": "ensemble", "k": k, "skaters": list(skater_specs)}


def conjugate_spec(skater_spec: dict, transform_spec: dict) -> dict:
    return {"op": "conjugate", "skater": skater_spec, "transform": transform_spec}


def envelope_spec(skater_spec: dict, k: int = 1, decay: float | None = None) -> dict:
    return {"op": "envelope", "skater": skater_spec, "k": k, "decay": decay}


def calibrated_spec(skater_spec: dict, k: int = 1, target: float = 0.6827) -> dict:
    return {"op": "calibrated", "skater": skater_spec, "k": k, "target": target}


def diff_spec() -> dict:
    return {"op": "diff"}


def frac_spec(d: float = 0.4, window: int = 50) -> dict:
    return {"op": "frac", "d": d, "window": window}


def std_spec(alpha: float = 0.05) -> dict:
    return {"op": "std", "alpha": alpha}

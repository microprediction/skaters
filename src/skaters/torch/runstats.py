"""Online running statistics on 0-d tensors: the twin of :mod:`skaters.runstats`
(Welford's mean/variance), same arithmetic order."""

from __future__ import annotations

import torch

from skaters.torch.dist import DTYPE, _t

_INF = torch.as_tensor(float("inf"), dtype=DTYPE)


def running_var_init() -> dict:
    return {"n": 0, "mean": torch.zeros((), dtype=DTYPE), "m2": torch.zeros((), dtype=DTYPE)}


def running_var_update(state: dict, x) -> dict:
    x = _t(x)
    n = state["n"] + 1
    delta = x - state["mean"]
    mean = state["mean"] + delta / n
    delta2 = x - mean
    m2 = state["m2"] + delta * delta2
    return {"n": n, "mean": mean, "m2": m2}


def running_var_get(state: dict):
    if state["n"] < 2:
        return state["mean"], _INF
    return state["mean"], state["m2"] / (state["n"] - 1)


def running_std_get(state: dict):
    _, var = running_var_get(state)
    return torch.sqrt(var) if bool(torch.isfinite(var)) else _INF


def running_mse_get(state: dict):
    if state["n"] < 1:
        return _INF
    mean, var = running_var_get(state)
    if not bool(torch.isfinite(var)):
        return _INF
    return mean * mean + var

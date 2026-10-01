"""Spatiotemporal mesh study: do neighbour messages help a grid of skaters?

The question
------------
Video (or any static-camera raster) is a grid of scalar streams. A skater is a
scalar online filter, so one skater per pixel is the obvious temporal model. The
claim under test is that a pixel's next value is better predicted when its
neighbours' predictions are injected as artificial observations, i.e. a
Gaussian-belief-propagation / approximate-Kalman message on a 4-neighbour mesh.

Two things must both hold for the mesh to be worth building out:

  1. messages must improve the predictive log-score over the temporal-only
     baseline, and
  2. the fused predictive distribution must stay calibrated. Neighbour messages
     are correlated (loopy graph), so injecting them as independent observations
     double-counts information and the fused variance collapses. This is the
     failure mode to watch. If (1) holds but (2) fails, the real problem is
     online recalibration of the fused distribution, not the mesh itself, and
     that is the more interesting result.

What the script does
--------------------
  * builds a T x H x W grayscale stack (synthetic by default; --npy loads a real
    static-camera clip as float array shaped (T, H, W), values in [0, 1]),
  * runs one temporal skater per pixel (the temporal factor of the mesh),
  * at each frame fuses each node's own 1-step prediction with its 4 neighbours'
    predictions by Gaussian precision fusion (the GBP message), scaled by a
    coupling strength kappa,
  * scores baseline (kappa=0) against the mesh over a scan of kappa,
  * reports mean predictive log-score and a PIT calibration statistic for each,
  * optionally applies online std recalibration (--recal) to show the lever that
     fixes the double-counting failure.

This is deliberately univariate-per-pixel and CPU-only. It is a probe, not a
video predictor. 64x64 is the intended scale; larger needs the descriptor/patch
layer that this script does not build.

Run
---
    python benchmarks/mesh_video_study.py                 # synthetic, ema factor
    python benchmarks/mesh_video_study.py --recal         # + online recalibration
    python benchmarks/mesh_video_study.py --npy clip.npy  # real (T,H,W) in [0,1]
    python benchmarks/mesh_video_study.py --temporal laplace   # slower, stronger

Records the skaters version + commit it ran against (study convention).
"""

from __future__ import annotations
import argparse
import math
import subprocess
import numpy as np

import skaters
from skaters import laplace, ema
from skaters.dist import Dist


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def synthetic_stack(T: int, H: int, W: int, seed: int = 0) -> np.ndarray:
    """A static-camera regime with bounded motion: a slowly drifting textured
    background plus a soft blob that moves on a smooth path. This has genuine
    spatial coherence (neighbours are informative) AND temporal structure
    (each pixel is predictable from its own past), which is exactly the regime
    where the mesh should help if it helps anywhere. Values in [0, 1].
    """
    rng = np.random.default_rng(seed)
    ys, xs = np.mgrid[0:H, 0:W].astype(float)

    # low-frequency background that drifts slowly (temporal predictability)
    base = 0.5 + 0.15 * np.sin(xs / 7.0) * np.cos(ys / 9.0)
    stack = np.empty((T, H, W), dtype=float)
    phase = 0.0
    for t in range(T):
        phase += 0.05
        bg = base + 0.05 * np.sin(xs / 7.0 + phase)
        # soft blob on a smooth Lissajous path (bounded motion)
        cx = W * (0.5 + 0.35 * math.sin(0.11 * t))
        cy = H * (0.5 + 0.35 * math.sin(0.17 * t + 1.0))
        blob = 0.4 * np.exp(-((xs - cx) ** 2 + (ys - cy) ** 2) / (2 * (0.08 * W) ** 2))
        frame = bg + blob + 0.01 * rng.standard_normal((H, W))  # small sensor noise
        stack[t] = np.clip(frame, 0.0, 1.0)
    return stack


# ---------------------------------------------------------------------------
# Temporal factor (one skater per pixel)
# ---------------------------------------------------------------------------

def make_factor(name: str):
    if name == "ema":
        return lambda: ema(alpha=0.2, k=1)
    if name == "laplace":
        return lambda: laplace(k=1)
    raise ValueError(f"--temporal must be 'ema' or 'laplace', got {name!r}")


# ---------------------------------------------------------------------------
# Gaussian message fusion (the GBP / approx-Kalman step)
# ---------------------------------------------------------------------------

def fuse(mu0: float, var0: float,
         neigh: list[tuple[float, float]],
         kappa: float,
         var_floor: float = 1e-8) -> tuple[float, float]:
    """Precision fusion of a node's own 1-step prediction (mu0, var0) with its
    neighbours' predictions, each down-weighted by coupling kappa in [0, 1].

    kappa = 0 recovers the temporal-only baseline exactly.
    kappa = 1 treats every neighbour message as a full independent observation
    (maximally overconfident: this is the double-counting failure mode).

    A neighbour predicting the value at THIS node is the mesh's spatial-smoothness
    assumption. It is only correct where the scene is locally smooth, which is
    the whole reason this is a probe for the bounded-motion regime.
    """
    prec = 1.0 / max(var0, var_floor)
    num = prec * mu0
    for mu_n, var_n in neigh:
        p = kappa / max(var_n, var_floor)
        prec += p
        num += p * mu_n
    var = 1.0 / prec
    return num * var, var


# ---------------------------------------------------------------------------
# Study
# ---------------------------------------------------------------------------

def run(stack: np.ndarray, factor_name: str, kappas: list[float], recal: bool):
    T, H, W = stack.shape
    make = make_factor(factor_name)

    # one skater state per pixel; one temporal skater instance reused per pixel
    factors = [[make() for _ in range(W)] for _ in range(H)]
    states = [[None for _ in range(W)] for _ in range(H)]

    # per-kappa accumulators: sum of log-scores, count, and PIT values for calibration
    logscore = {kap: 0.0 for kap in kappas}
    n_scored = {kap: 0 for kap in kappas}
    pits = {kap: [] for kap in kappas}

    # per-kappa online recalibration state: EWMA of squared z-scores (target 1.0)
    recal_ms = {kap: 1.0 for kap in kappas}
    recal_alpha = 0.02

    NEI = [(-1, 0), (1, 0), (0, -1), (0, 1)]

    for t in range(T):
        # 1) advance every pixel's temporal factor, collect its 1-step prediction
        mu = np.empty((H, W)); var = np.empty((H, W))
        for i in range(H):
            for j in range(W):
                dists, states[i][j] = factors[i][j](float(stack[t, i, j]), states[i][j])
                d = dists[0]
                mu[i, j] = d.mean
                var[i, j] = max(d.std ** 2, 1e-8)

        # 2) for t >= 1 we have a genuine 1-step-ahead target: stack[t] itself was
        #    predicted by the state BEFORE this tick. To keep the loop simple we
        #    score the prediction made at t-1 against the value at t using the
        #    predictions cached from the previous frame.
        if t >= 1:
            for kap in kappas:
                for i in range(H):
                    for j in range(W):
                        neigh = []
                        if kap > 0.0:
                            for di, dj in NEI:
                                ii, jj = i + di, j + dj
                                if 0 <= ii < H and 0 <= jj < W:
                                    neigh.append((prev_mu[ii, jj], prev_var[ii, jj]))
                        fm, fv = fuse(prev_mu[i, j], prev_var[i, j], neigh, kap)
                        fs = math.sqrt(fv)
                        if recal:
                            fs *= math.sqrt(recal_ms[kap])
                        y = float(stack[t, i, j])
                        dist = Dist.gaussian(fm, fs)
                        logscore[kap] += dist.logpdf(y)
                        n_scored[kap] += 1
                        pits[kap].append(dist.cdf(y))
                        if recal:
                            z2 = ((y - fm) / max(fs, 1e-8)) ** 2
                            recal_ms[kap] += recal_alpha * (z2 - recal_ms[kap])

        prev_mu, prev_var = mu, var

    return logscore, n_scored, pits


def pit_calibration(pit: list[float], bins: int = 10) -> float:
    """L1 deviation of the PIT histogram from uniform. 0 = perfectly calibrated;
    larger = worse. A collapsed (overconfident) predictive piles PIT mass at 0
    and 1, so this rises sharply under double-counting.
    """
    if not pit:
        return float("nan")
    h, _ = np.histogram(pit, bins=bins, range=(0.0, 1.0))
    p = h / h.sum()
    return float(np.abs(p - 1.0 / bins).sum())


def version_stamp() -> str:
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        commit = "unknown"
    return f"skaters {skaters.__version__} @ {commit}"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--npy", type=str, default=None,
                    help="path to a (T,H,W) float array in [0,1]; else synthetic")
    ap.add_argument("--T", type=int, default=60)
    ap.add_argument("--H", type=int, default=64)
    ap.add_argument("--W", type=int, default=64)
    ap.add_argument("--temporal", type=str, default="ema", choices=["ema", "laplace"])
    ap.add_argument("--kappa", type=float, nargs="+",
                    default=[0.0, 0.1, 0.25, 0.5, 1.0])
    ap.add_argument("--recal", action="store_true",
                    help="apply online std recalibration to the fused predictive")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    if args.npy:
        stack = np.load(args.npy).astype(float)
        assert stack.ndim == 3, "expected (T, H, W)"
    else:
        stack = synthetic_stack(args.T, args.H, args.W, seed=args.seed)

    print(version_stamp())
    print(f"stack {stack.shape}  temporal={args.temporal}  recal={args.recal}")
    print(f"{'kappa':>6}  {'mean logscore':>14}  {'PIT L1 (cal)':>13}")
    print("-" * 40)

    logscore, n_scored, pits = run(stack, args.temporal, args.kappa, args.recal)
    base = None
    for kap in args.kappa:
        mls = logscore[kap] / max(n_scored[kap], 1)
        cal = pit_calibration(pits[kap])
        if base is None:
            base = mls
        delta = mls - base
        flag = ""
        if kap > 0 and delta > 0:
            flag = "  logscore up"
        if kap > 0 and cal > pit_calibration(pits[args.kappa[0]]) * 1.5:
            flag += "  CALIBRATION DEGRADED"
        print(f"{kap:>6.2f}  {mls:>14.4f}  {cal:>13.4f}{flag}")

    print()
    print("read: kappa=0 is temporal-only. A useful mesh raises mean logscore")
    print("AND keeps PIT L1 near the kappa=0 value. If logscore rises but PIT L1")
    print("blows up, the messages are double-counting; try --recal, and if that")
    print("recovers calibration the finding is 'loopy fusion needs online recal'.")


if __name__ == "__main__":
    main()

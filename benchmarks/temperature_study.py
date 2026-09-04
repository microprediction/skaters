"""Study: does a calibration-adaptive selection temperature beat the best fixed
eta? Protocol for skaters#213, executable spec in skaters#215.

`laplace`'s ensemble weight is softmax(log_w) with
log_w[i] += eta * lp - lambda * depth[i] (a `forget`-discounted running sum),
i.e. Gumbel-logit selection with `eta` (`learning_rate`) as a fixed inverse
temperature (skaters.terminal.terminal_leaf_ensemble). This script builds
laplace's exact candidate pool and wrapper stack (multiscale -> gpdtails ->
parade, same as skaters.api.laplace) and varies only the selection
temperature, in four arms:

  1. fixed-eta sweep   {1.0x, 0.25x, 0.5x, 2x, 4x} * default, forget=1.0
  2. forget sweep      best-fixed eta, forget in {1.0, 0.999, 0.99, 0.97}
  3. adaptive-eta       terminal_leaf_ensemble(adaptive_temperature=True),
                        centered on best-fixed eta, forget=1.0
  4. adaptive-eta+forget  arm 3 with the best forget from arm 2

Each series is stratified stationary / regime-changey by the ratio of the
largest to smallest per-quartile variance of its scored window (>6.0 ->
regime-changey; threshold calibrated from a pilot ratio scan, frozen before
any arm ran -- see STRATUM_RATIO). Per (series, arm):
mean one-step logpdf/CRPS (via bench_core, the one scorer) and PIT L1 (10-bin
deviation from uniform, read from `parade`'s own state["pit"][0] -- the
calibration machinery this study reuses rather than reimplementing).

Resumable: writes to one CSV, keyed by (series, arm); a rerun skips what is
already there. The two data-dependent choices (best-fixed eta, best forget)
are cached to a small JSON sidecar so a resumed run cannot silently re-derive
a different winner from partial data.

    PYTHONPATH=src:benchmarks .venv-sota/bin/python benchmarks/temperature_study.py
    PYTHONPATH=src:benchmarks .venv-sota/bin/python benchmarks/temperature_study.py summarize
"""
from __future__ import annotations
import csv
import json
import math
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import fred
import bench_core as bc
from study import _scope_tag

_HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("TEMP_OUT", os.path.join(_HERE, "comparisons", "_temperature_study.csv"))
CHOICES = os.environ.get("TEMP_CHOICES", os.path.join(_HERE, "comparisons", "_temperature_study_choices.json"))
README = os.path.join(_HERE, "TEMPERATURE_STUDY.md")

N_SERIES = int(os.environ.get("TEMP_N", 1000))
MIN_CHANGES = int(os.environ.get("TEMP_MIN_CHANGES", 800))
MAX_CHANGES = int(os.environ.get("TEMP_MAX_CHANGES", 2000))
TEST = int(os.environ.get("TEMP_TEST", 1000))       # scored window, "lastN"
WORKERS = int(os.environ.get("TEMP_WORKERS", min(16, os.cpu_count() or 4)))

ETA_DEFAULT = 0.8            # skaters.api.laplace's own learning_rate
COMPLEXITY_PENALTY = 0.005   # matches laplace's own
FORGET_GRID = [1.0, 0.999, 0.99, 0.97]
STRATUM_RATIO = 6.0          # per-quartile variance ratio threshold, frozen pre-run. Calibrated
                              # from a pilot scan (100 qualifying series, this protocol's TEST/BURN
                              # window): median ratio ~6.6, 87% already above 2.0 (FRED change series
                              # are heavy-tailed enough that a low threshold classifies nearly
                              # everything "regime-changey"). 6.0 gives an approximately balanced
                              # split; set from the ratio distribution alone, before any arm was run.


def _build_arm(eta, forget, adaptive=False):
    """laplace's exact stack (multiscale -> gpdtails -> parade over
    terminal_leaf_ensemble(_build_candidates)), varying only the selection
    temperature. Mirrors skaters.api.laplace / _laplace_single_scale."""
    from skaters.api import _build_candidates, _objective_leaf
    from skaters.terminal import terminal_leaf_ensemble
    from skaters.multiscale import multiscale
    from skaters.sticky import sticky as _project
    from skaters.tails import gpdtails as _gpdtails
    from skaters.parade import parade as _parade

    def _single_scale(k):
        candidates, depths, _ = _build_candidates(k)
        f = terminal_leaf_ensemble(
            candidates, k=k, leaf_fn=_objective_leaf("crps", 0.03),
            learning_rate=eta, complexity_penalty=COMPLEXITY_PENALTY,
            depths=depths, max_components=20, forget=forget,
            adaptive_temperature=adaptive,
        )
        return _project(f, k=k)

    def factory():
        f = multiscale(_single_scale, k=1)
        f = _gpdtails(f, k=1)
        f = _parade(f, k=1)
        return f
    return factory


def _stratum(y_scored):
    """stationary | regime-changey, from the ratio of the largest to smallest
    per-quartile variance of the scored window. Frozen rule, set before any
    arm was run."""
    n = len(y_scored)
    if n < 40:
        return "stationary"
    q = n // 4
    variances = [float(np.var(y_scored[i * q:(i + 1) * q])) for i in range(4)]
    variances = [v for v in variances if v > 0]
    if len(variances) < 4:
        return "stationary"
    ratio = max(variances) / min(variances)
    return "regime-changey" if ratio > STRATUM_RATIO else "stationary"


def _score_arm(factory, changes, start):
    """(mean_logpdf, mean_crps, pit_l1, n) for one arm on one series, scored
    from `start` on. PIT comes from parade's own state["pit"][0] -- the
    calibration diagnostic laplace already carries, not a re-derivation."""
    f = factory(); state = None; pend = None
    lp = cr = 0.0; n = 0
    us = []
    seen = set(); scorable = False
    for i, y in enumerate(changes):
        if pend is not None and i >= start and scorable:
            a, b = bc.score_dist(pend[0], y); lp += a; cr += b; n += 1
        if not scorable:
            seen.add(y)
            if len(seen) >= 2:
                scorable = True; seen = None
        pend, state = f(y, state)
        if pend is not None and i >= start and scorable:
            u = state["pit"][0] if isinstance(state, dict) and state.get("pit") else None
            if u is not None and math.isfinite(u):
                us.append(min(max(u, 0.0), 1.0))
    if not n:
        return None
    pit_l1 = None
    if len(us) >= 10:
        hist, _ = np.histogram(us, bins=10, range=(0.0, 1.0))
        frac = hist / len(us)
        pit_l1 = float(np.mean(np.abs(frac - 0.1)))
    return lp / n, cr / n, pit_l1, n


def score_series(payload):
    """One series, every requested arm. payload = (sid, [(name, eta, forget,
    adaptive), ...]). Returns (sid, stratum, rows); one bad arm never kills
    the series (matches study.py's score_series)."""
    sid, configs = payload
    lv = fred._load_levels(sid)
    ch = fred._to_changes(lv) if lv else []
    if len(ch) < MIN_CHANGES:
        return sid, None, []
    if len(ch) > MAX_CHANGES:
        ch = ch[-MAX_CHANGES:]
    if _scope_tag(ch):
        return sid, None, []
    start = max(bc.BURN, len(ch) - TEST)
    stratum = _stratum(ch[start:])
    rows = []
    for name, eta, forget, adaptive in configs:
        try:
            r = _score_arm(_build_arm(eta, forget, adaptive), ch, start)
        except Exception as e:                       # noqa: BLE001
            print(f"  ERR {sid}/{name}: {e}", flush=True); continue
        if r is None:
            continue
        lp, cr, pit_l1, n = r
        rows.append([sid, stratum, name, f"{lp:.6f}", f"{cr:.6f}",
                     "" if pit_l1 is None else f"{pit_l1:.6f}", n])
    return sid, stratum, rows


# ---- universe -----------------------------------------------------------------

def _universe(n):
    """Scan the cached universe (id order, deterministic) for the first `n`
    series that qualify -- MIN_CHANGES and in-scope. A raw id-list slice is
    NOT a fair sample: alphabetically-early cache entries cluster short
    series (e.g. short EU monthly codes), so slicing before qualifying can
    silently starve the study of series it never even looked at."""
    ids = sorted(f[:-4] for f in os.listdir(fred._CACHE) if f.endswith(".csv"))
    out = []
    for sid in ids:
        lv = fred._load_levels(sid)
        ch = fred._to_changes(lv) if lv else []
        if len(ch) >= MIN_CHANGES and not _scope_tag(ch):
            out.append(sid)
            if len(out) >= n:
                break
    return out


# ---- resumable CSV --------------------------------------------------------------

def _done_pairs():
    done = set()
    if os.path.exists(OUT):
        with open(OUT) as fh:
            r = csv.reader(fh); next(r, None)
            for row in r:
                if len(row) >= 3:
                    done.add((row[0], row[2]))
    return done


def _run_phase(configs, sids, tag):
    """Run `configs` over `sids`, skipping (sid, name) pairs already in OUT.
    Appends as it goes; crash-safe, resumable."""
    done = _done_pairs()
    new = not os.path.exists(OUT)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    t0 = time.time(); finished = 0
    with open(OUT, "a", newline="") as fh, ProcessPoolExecutor(max_workers=WORKERS) as pool:
        w = csv.writer(fh)
        if new:
            w.writerow(["series", "stratum", "arm", "mean_logpdf", "mean_crps", "pit_l1", "n"])
            fh.flush()
        futs = {}
        for sid in sids:
            todo = [c for c in configs if (sid, c[0]) not in done]
            if not todo:
                continue
            futs[pool.submit(score_series, (sid, todo))] = sid
        print(f"[{tag}] {len(futs)} series to score ({len(configs)} configs each)", flush=True)
        for fut in as_completed(futs):
            sid = futs[fut]
            try:
                _, _, rows = fut.result()
            except Exception as e:                    # noqa: BLE001
                print(f"  ERR {sid}: {e}", flush=True); continue
            for row in rows:
                w.writerow(row)
            fh.flush(); finished += 1
            if finished % 100 == 0:
                rate = finished / max(time.time() - t0, 1e-9)
                print(f"  [{tag}] {finished}/{len(futs)} series -- {rate*60:.0f}/min", flush=True)
    print(f"[{tag}] done in {time.time()-t0:.0f}s", flush=True)


def _load_results():
    rows = []
    with open(OUT) as fh:
        r = csv.DictReader(fh)
        for row in r:
            rows.append(row)
    return rows


def _agg_mean_lp(rows, arm):
    vals = [float(r["mean_logpdf"]) for r in rows if r["arm"] == arm]
    return float(np.mean(vals)) if vals else float("nan"), len(vals)


def _load_choices():
    if os.path.exists(CHOICES):
        return json.load(open(CHOICES))
    return {}


def _save_choices(d):
    os.makedirs(os.path.dirname(CHOICES), exist_ok=True)
    json.dump(d, open(CHOICES, "w"), indent=2)


# ---- pipeline -------------------------------------------------------------------

def main():
    sids = _universe(N_SERIES)

    eta_grid = {
        "eta1.0x": ETA_DEFAULT, "eta0.25x": 0.25 * ETA_DEFAULT, "eta0.5x": 0.5 * ETA_DEFAULT,
        "eta2x": 2.0 * ETA_DEFAULT, "eta4x": 4.0 * ETA_DEFAULT,
    }

    # ---- arm 1: fixed-eta sweep, forget=1.0 ----
    phase_a = [(name, eta, 1.0, False) for name, eta in eta_grid.items()]
    _run_phase(phase_a, sids, "arm1-eta-sweep")

    choices = _load_choices()
    if "best_eta_name" not in choices:
        rows = _load_results()
        scored = {name: _agg_mean_lp(rows, name) for name in eta_grid}
        for name, (mlp, n) in scored.items():
            print(f"  {name} (eta={eta_grid[name]:.3f}): mean_logpdf={mlp:.4f} n={n}", flush=True)
        best_name = max(scored, key=lambda nm: scored[nm][0])
        choices["best_eta_name"] = best_name
        choices["best_eta"] = eta_grid[best_name]
        _save_choices(choices)
    best_eta = choices["best_eta"]
    print(f"[arm1] best-fixed eta = {best_eta:.3f} ({choices['best_eta_name']})", flush=True)

    # ---- arm 2: forget sweep at best-fixed eta. All 4 points run at best_eta
    # (including forget=1.0) since arm 1's forget=1.0 point used ETA_DEFAULT,
    # not necessarily best_eta -- they only coincide when best_eta == eta1.0x.
    phase_b = [(f"forget{fg}", best_eta, fg, False) for fg in FORGET_GRID]
    _run_phase(phase_b, sids, "arm2-forget-sweep")

    if "best_forget" not in choices:
        rows = _load_results()
        names = [f"forget{fg}" for fg in FORGET_GRID]
        scored = {fg: _agg_mean_lp(rows, f"forget{fg}") for fg in FORGET_GRID}
        for fg, (mlp, n) in scored.items():
            print(f"  forget={fg}: mean_logpdf={mlp:.4f} n={n}", flush=True)
        best_forget = max(scored, key=lambda fg: scored[fg][0])
        choices["best_forget"] = best_forget
        _save_choices(choices)
    best_forget = choices["best_forget"]
    print(f"[arm2] best forget = {best_forget}", flush=True)

    # ---- arm 3: adaptive-eta, forget=1.0, centered on best-fixed eta ----
    phase_c = [("adaptive", best_eta, 1.0, True)]
    _run_phase(phase_c, sids, "arm3-adaptive")

    # ---- arm 4: adaptive-eta + best forget ----
    phase_d = [("adaptive+forget", best_eta, best_forget, True)]
    _run_phase(phase_d, sids, "arm4-adaptive-forget")

    print("[temperature-study] all phases done. Run with `summarize` to produce the bout README.", flush=True)


# ---- summary / bout README --------------------------------------------------------

def _paired_deltas(rows, baseline_name, arm_name, stratum=None):
    by_series = {}
    for r in rows:
        if stratum and r["stratum"] != stratum:
            continue
        by_series.setdefault(r["series"], {})[r["arm"]] = r
    deltas_lp, deltas_pit = [], []
    for sid, d in by_series.items():
        if baseline_name in d and arm_name in d:
            deltas_lp.append(float(d[arm_name]["mean_logpdf"]) - float(d[baseline_name]["mean_logpdf"]))
            if d[arm_name]["pit_l1"] and d[baseline_name]["pit_l1"]:
                deltas_pit.append(float(d[arm_name]["pit_l1"]) - float(d[baseline_name]["pit_l1"]))
    return deltas_lp, deltas_pit


def _git_stamp():
    try:
        commit = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=_HERE).decode().strip()
    except Exception:
        commit = "unknown"
    ver = "unknown"
    try:
        for line in open(os.path.join(os.path.dirname(_HERE), "pyproject.toml")):
            if line.strip().startswith("version"):
                ver = line.split("=", 1)[1].strip().strip('"')
                break
    except Exception:
        pass
    return commit, ver


def summarize():
    rows = _load_results()
    choices = _load_choices()
    best_eta_name = choices.get("best_eta_name", "?")
    best_eta = choices.get("best_eta")
    best_forget = choices.get("best_forget")
    commit, ver = _git_stamp()

    lines = [f"# Selection-temperature study (skaters#213 / #215)\n",
             f"skaters {ver}, commit `{commit}`\n",
             f"\nBest-fixed eta: **{best_eta_name}** (eta={best_eta}). Best forget: **{best_forget}**.\n",
             "\n## Result\n"]

    for stratum in ("regime-changey", "stationary"):
        lines.append(f"\n### {stratum}\n")
        lines.append("| arm | vs best-fixed: median dLL | frac improving | median dPIT_L1 |\n")
        lines.append("|---|---|---|---|\n")
        for arm_name, label in [("adaptive", "adaptive-eta"),
                                 ("adaptive+forget", "adaptive-eta + best forget")]:
            dlp, dpit = _paired_deltas(rows, best_eta_name, arm_name, stratum)
            if not dlp:
                lines.append(f"| {label} | (no paired series) | | |\n")
                continue
            med_lp = float(np.median(dlp))
            frac = float(np.mean([d > 0 for d in dlp]))
            med_pit = float(np.median(dpit)) if dpit else float("nan")
            lines.append(f"| {label} | {med_lp:+.4f} | {frac:.1%} ({len(dlp)} series) | {med_pit:+.4f} |\n")

    lines.append("\n## Verdict\n\n(fill in: adaptive wins / ties / forget subsumes it, per the decision rule in #215)\n")
    with open(README, "w") as fh:
        fh.writelines(lines)
    print(f"wrote {README}")
    print("".join(lines))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "summarize":
        summarize()
    else:
        main()

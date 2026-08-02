"""Multi-horizon round-robin study: the week study repeated at k = 1, 2, 4, 8, 16.

Direct h-step forecasting. For horizon h every arm predicts the change h steps
ahead of a context that ends h observations before the target, and is scored
against the SAME last-TEST targets as k=1, so the horizons are directly
comparable and laplace(h) is the apples-to-apples baseline at each h
(arm_adapters is horizon-aware; ARM_H selects h). Isolated from the running k=1
study: its own preds tree (preds_h/h<k>/), its own STOP file, its own summaries
(canonical_summary_*_h<k>.csv). Reuses the k=1 corpus caches under preds/.

    benchmarks/launch_horizon_study.sh              # unattended, sleep-proof
    WEEK_H_LIST="1 2 4" WEEK_MODELS=laplace,TiRex,TiRex&lap ... horizon_study.py

Stop cleanly: touch benchmarks/preds_h/STOP.  Resumes on relaunch (run_arm skips
covered (series, method) cells per horizon).
"""
from __future__ import annotations
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import week_study as ws                       # reuse the venv map and base env

_HERE, _ROOT = ws._HERE, ws._ROOT
PREDS_H = os.path.join(_HERE, "preds_h")
STOP = os.path.join(PREDS_H, "STOP")

HORIZONS = [int(x) for x in os.environ.get("WEEK_H_LIST", "1 2 4 8 16").split()]
CORPORA = os.environ.get("WEEK_CORPORA", "daily weekly monthly m4-hourly").split()
CTX = os.environ.get("WEEK_CTX", "128")
TEST = os.environ.get("WEEK_TEST", "64")
DEVICE = os.environ.get("WEEK_DEVICE", "cpu")
PAR = int(os.environ.get("WEEK_PAR", "4"))
DURATION_DAYS = float(os.environ.get("WEEK_DAYS", "7"))
MAX_ROUNDS = int(os.environ.get("WEEK_MAX_ROUNDS", "0"))
BATCH = int(os.environ.get("WEEK_BATCH", "120"))         # per-round series cap step
JOB_TIMEOUT = int(os.environ.get("WEEK_JOB_TIMEOUT", str(6 * 3600)))
# The headline arms by default (all Tier C / slow); override with WEEK_MODELS.
DEFAULT_ROSTER = ("laplace,Chronos,TiRex,TimesFM,"
                  "Chronos&lap,TiRex&lap,TimesFM&lap")


def roster():
    only = {m for m in os.environ.get("WEEK_MODELS", DEFAULT_ROSTER).split(",") if m}
    out = {}
    for name, (venv, tier, extra) in ws.MODELS.items():
        if name not in only:
            continue
        if not os.path.isdir(os.path.join(_ROOT, venv)):
            continue
        if name == "TabPFN" and not os.environ.get("TABPFN_TOKEN"):
            continue
        out[name] = (venv, tier, extra)
    return out


def job(name, venv, extra, corpus, cap, h, preds_dir):
    out = os.path.join(preds_dir, f"{name}__{corpus}.csv")
    env = dict(os.environ)
    env.update(ws._BASE_ENV)
    env.update(extra)
    env.update({
        "PYTHONPATH": f"{os.path.join(_ROOT, 'src')}:{_HERE}",
        "ARM_METHODS": name, "ARM_CORPUS": corpus, "PRED_OUT": out,
        "ARM_MAX": str(cap), "ARM_H": str(h),
        "FM_CTX": CTX, "FM_TEST": TEST, "FM_DEVICE": DEVICE,
    })
    if name == "TabPFN" and os.environ.get("TABPFN_TOKEN"):
        env["TABPFN_TOKEN"] = os.environ["TABPFN_TOKEN"]
    py = os.path.join(_ROOT, venv, "bin", "python")
    t0 = time.time()
    try:
        r = subprocess.run([py, "-u", os.path.join(_HERE, "run_arm.py")],
                           env=env, timeout=JOB_TIMEOUT,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        tail = r.stdout.decode(errors="replace").strip().splitlines()[-1:] or [""]
        return f"h{h} {name}/{corpus} cap={cap} rc={r.returncode} {time.time()-t0:.0f}s | {tail[0]}"
    except subprocess.TimeoutExpired:
        return f"h{h} {name}/{corpus} cap={cap} TIMEOUT after {JOB_TIMEOUT}s"
    except Exception as e:                                    # noqa: BLE001
        return f"h{h} {name}/{corpus} cap={cap} ERROR {e}"


def summarize(h, preds_dir):
    py = os.path.join(_ROOT, ".venv-sota", "bin", "python")
    env = dict(os.environ)
    env["PYTHONPATH"] = f"{os.path.join(_ROOT, 'src')}:{_HERE}"
    env["CANON_PREDS"] = preds_dir
    env["CANON_SUFFIX"] = f"_h{h}"
    subprocess.run([py, os.path.join(_HERE, "summarize_canonical.py")], env=env, cwd=_ROOT)
    for f in (f"canonical_summary_vs_laplace_h{h}.csv",
              f"canonical_summary_coverage_h{h}.csv"):
        subprocess.run(["git", "add", os.path.join("benchmarks", f)], cwd=_ROOT)
    subprocess.run(["git", "commit", "-q", "-m",
                    f"horizon-study: derived summaries h={h}"], cwd=_ROOT)


def main():
    models = roster()
    for h in HORIZONS:
        os.makedirs(os.path.join(PREDS_H, f"h{h}"), exist_ok=True)
    print(f"[hstudy] horizons={HORIZONS} models={list(models)} corpora={CORPORA} "
          f"CTX={CTX} TEST={TEST} device={DEVICE} par={PAR} days={DURATION_DAYS}", flush=True)
    t_end = time.time() + DURATION_DAYS * 86400
    rnd = 0
    while time.time() < t_end and not os.path.exists(STOP):
        if MAX_ROUNDS and rnd >= MAX_ROUNDS:
            break
        rnd += 1
        cap = rnd * BATCH
        jobs = []
        for h in HORIZONS:
            preds_dir = os.path.join(PREDS_H, f"h{h}")
            for name, (venv, _tier, extra) in models.items():
                for corpus in CORPORA:
                    jobs.append((name, venv, extra, corpus, cap, h, preds_dir))
        print(f"\n[hstudy] === round {rnd} : {len(jobs)} jobs (cap={cap}) ===", flush=True)
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=PAR) as ex:
            futs = [ex.submit(job, *j) for j in jobs]
            for f in as_completed(futs):
                print("   " + f.result(), flush=True)
                if os.path.exists(STOP):
                    print("[hstudy] STOP file seen; finishing round", flush=True)
        print(f"[hstudy] round {rnd} done in {time.time()-t0:.0f}s", flush=True)
        for h in HORIZONS:
            try:
                summarize(h, os.path.join(PREDS_H, f"h{h}"))
            except Exception as e:                            # noqa: BLE001
                print(f"[hstudy] summarize h{h} failed: {e}", flush=True)
    print(f"[hstudy] exiting after {rnd} rounds "
          f"({'STOP' if os.path.exists(STOP) else 'duration'})", flush=True)


if __name__ == "__main__":
    main()

"""Week-long round-robin study driver (see preregistrations/2026-07-22-week-long-study.md).

Breadth-first, not depth-first: every ROUND advances every (model x corpus) cell
by a small equal increment, so the derived star maps / win-draw-loss matrix are
broad after round 1 and CONVERGE as rounds accrue, rather than one region
appearing at a time. Anytime property: useful and broad if stopped at any moment.

Each model runs in its OWN venv (deps conflict). The driver shells out to
run_arm.py per (model, corpus), which appends per-step rows to the ONE canonical
predictions.py store and skips already-covered (series, method) cells, so growing
the per-round cap deepens every cell uniformly and a restart resumes wherever
coverage is thinnest. No round redoes work.

Every COMMIT_EVERY rounds it regenerates the small derived summaries
(summarize_canonical.py) and commits them locally (never pushes). The large
per-step store under preds/ is gitignored and regenerable.

    # 7-day unattended run, CPU, bounded parallelism:
    caffeinate -i nohup .venv-sota/bin/python benchmarks/week_study.py \
        > benchmarks/_week.log 2>&1 &

Stop cleanly by creating benchmarks/preds/STOP. Env knobs below.
"""
from __future__ import annotations
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
PREDS = os.path.join(_HERE, "preds")
STOP = os.path.join(PREDS, "STOP")

# ---- protocol (uniform across arms so scores are comparable) -------------------
CTX = os.environ.get("WEEK_CTX", "128")
TEST = os.environ.get("WEEK_TEST", "64")
DEVICE = os.environ.get("WEEK_DEVICE", "cpu")     # cpu is stable for a week; mps faster
CORPORA = os.environ.get("WEEK_CORPORA", "daily weekly monthly m4-hourly").split()

DURATION_DAYS = float(os.environ.get("WEEK_DAYS", "7"))
MAX_ROUNDS = int(os.environ.get("WEEK_MAX_ROUNDS", "0"))   # 0 = unbounded
PAR = int(os.environ.get("WEEK_PAR", "4"))        # parallel (model,corpus) jobs
COMMIT_EVERY = int(os.environ.get("WEEK_COMMIT_EVERY", "1"))
BATCH_A = int(os.environ.get("WEEK_BATCH_A", "300"))   # Tier A series added / round
BATCH_C = int(os.environ.get("WEEK_BATCH_C", "40"))    # Tier C (slow) series / round
JOB_TIMEOUT = int(os.environ.get("WEEK_JOB_TIMEOUT", str(6 * 3600)))

_THREADS = os.environ.get("WEEK_THREADS", "4")    # per-job thread cap (avoid oversubscription)
_BASE_ENV = {"CUDA_VISIBLE_DEVICES": "", "PYTORCH_ENABLE_MPS_FALLBACK": "1",
             "TIREX_NO_CUDA": "1", "TOKENIZERS_PARALLELISM": "false",
             "OMP_NUM_THREADS": _THREADS, "MKL_NUM_THREADS": _THREADS,
             "OPENBLAS_NUM_THREADS": _THREADS, "VECLIB_MAXIMUM_THREADS": _THREADS}

# ---- models: name -> (venv, tier, extra_env). Tier A = fast/big batch. ----------
# TabPFN is included only when TABPFN_TOKEN is set (one-time license acceptance).
MODELS = {
    "laplace":     (".venv-sota",      "A", {}),
    "Sundial":     (".venv-sundial",   "C", {}),
    "TiRex":       (".venv-tirex",     "C", {}),
    "flowstate":   (".venv-flowstate", "C", {}),
    "Chronos":     (".venv-chronos",   "C", {}),
    "TimesFM":     (".venv-timesfm",   "C", {}),
    "TabPFN":      (".venv-tabpfn",    "C", {}),
    # laplace-calibrated sandwiches (quantile-averaged with laplace, own venv):
    "TimesFM+lap": (".venv-timesfm",   "C", {}),
    "TiRex+lap":   (".venv-tirex",     "C", {}),
    "Chronos+lap": (".venv-chronos",   "C", {}),
    # adaptive residual sandwiches (FM location + laplace conditional scale):
    "TimesFM~lap": (".venv-timesfm",   "C", {}),
    "TiRex~lap":   (".venv-tirex",     "C", {}),
    "Chronos~lap": (".venv-chronos",   "C", {}),
}


def enabled_models():
    only = {m for m in os.environ.get("WEEK_MODELS", "").split(",") if m}
    out = {}
    for name, (venv, tier, extra) in MODELS.items():
        if only and name not in only:
            continue
        if not os.path.isdir(os.path.join(_ROOT, venv)):
            continue
        if name == "TabPFN" and not os.environ.get("TABPFN_TOKEN"):
            continue            # gated: skip until the token is provided
        out[name] = (venv, tier, extra)
    return out


def job(name, venv, tier, extra, corpus, cap):
    """Run one (model, corpus) increment as a subprocess in the model's venv."""
    out = os.path.join(PREDS, f"{name}__{corpus}.csv")
    env = dict(os.environ)
    env.update(_BASE_ENV)
    env.update(extra)
    env.update({
        "PYTHONPATH": f"{os.path.join(_ROOT, 'src')}:{_HERE}",
        "ARM_METHODS": name, "ARM_CORPUS": corpus, "PRED_OUT": out,
        "ARM_MAX": str(cap), "FM_CTX": CTX, "FM_TEST": TEST, "FM_DEVICE": DEVICE,
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
        return f"{name}/{corpus} cap={cap} rc={r.returncode} {time.time()-t0:.0f}s | {tail[0]}"
    except subprocess.TimeoutExpired:
        return f"{name}/{corpus} cap={cap} TIMEOUT after {JOB_TIMEOUT}s"
    except Exception as e:                                    # noqa: BLE001
        return f"{name}/{corpus} cap={cap} ERROR {e}"


def commit_summaries(rnd):
    """Regenerate the small derived summaries and commit locally (never push)."""
    py = os.path.join(_ROOT, ".venv-sota", "bin", "python")
    env = dict(os.environ)
    env["PYTHONPATH"] = f"{os.path.join(_ROOT, 'src')}:{_HERE}"
    subprocess.run([py, os.path.join(_HERE, "summarize_canonical.py")],
                   env=env, cwd=_ROOT)
    subprocess.run(["git", "add", "benchmarks/canonical_summary_vs_laplace.csv",
                    "benchmarks/canonical_summary_coverage.csv"], cwd=_ROOT)
    subprocess.run(["git", "commit", "-q", "-m",
                    f"week-study: derived summaries after round {rnd}"], cwd=_ROOT)


def main():
    os.makedirs(PREDS, exist_ok=True)
    models = enabled_models()
    print(f"[week] models={list(models)} corpora={CORPORA} CTX={CTX} TEST={TEST} "
          f"device={DEVICE} par={PAR} days={DURATION_DAYS}", flush=True)
    t_end = time.time() + DURATION_DAYS * 86400
    rnd = 0
    while time.time() < t_end and not os.path.exists(STOP):
        if MAX_ROUNDS and rnd >= MAX_ROUNDS:
            break
        rnd += 1
        jobs = []
        for name, (venv, tier, extra) in models.items():
            cap = rnd * (BATCH_A if tier == "A" else BATCH_C)
            for corpus in CORPORA:
                jobs.append((name, venv, tier, extra, corpus, cap))
        print(f"\n[week] === round {rnd} : {len(jobs)} jobs ===", flush=True)
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=PAR) as ex:
            futs = [ex.submit(job, *j) for j in jobs]
            for f in as_completed(futs):
                print("   " + f.result(), flush=True)
                if os.path.exists(STOP):
                    print("[week] STOP file seen; finishing round", flush=True)
        print(f"[week] round {rnd} done in {time.time()-t0:.0f}s", flush=True)
        if rnd % COMMIT_EVERY == 0:
            try:
                commit_summaries(rnd)
            except Exception as e:                            # noqa: BLE001
                print(f"[week] summarize/commit failed: {e}", flush=True)
    print(f"[week] exiting after {rnd} rounds "
          f"({'STOP' if os.path.exists(STOP) else 'duration'})", flush=True)


if __name__ == "__main__":
    main()

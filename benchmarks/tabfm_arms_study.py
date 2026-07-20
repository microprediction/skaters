"""Run TabFM (clf8) on the seasonal/waveform radar arms.

The pre-registered TabFM wide study (tabfm_wide_study.py) covers only the
non-price DAILY universe, so TabFM shows as a single point on the challengers
radar. This scores the clf8 arm (the one the radar plots) plus laplace on the
weekly, monthly and M4-hourly corpora over the same TEST/CTX window, so the
radar can draw TabFM's full shape. Output: results_tabfm_arms.csv, crash-safe
(resume by series+arm+method). All scoring is reused from tabfm_wide_study.

    TB_DEVICE=mps PYTHONPATH=src:benchmarks python benchmarks/tabfm_arms_study.py
    TB_MAX=2 ...   # cap series per arm (smoke test)

Sharding for a MPS + CPU fleet: each worker takes a disjoint set of residue
classes and writes its own file, so there is no shared-file race. The radar
generator globs results_tabfm_arms*.csv and merges. Example fleet:

    # GPU worker (does ~5x a CPU worker, so give it more residues)
    TB_DEVICE=mps  TB_NSHARD=12 TB_SHARDS=0,1,2,3,4 TB_OUT=results_tabfm_arms.mps.csv ...
    # CPU worker j
    TB_DEVICE=cpu  TB_NSHARD=12 TB_SHARDS=5          TB_OUT=results_tabfm_arms.c5.csv  ...
"""
import csv
import gc
import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tabfm_wide_study as tw
import corpus

_HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(_HERE, os.environ.get("TB_OUT", "results_tabfm_arms.csv"))
ARMS = os.environ.get("TB_ARMS_CORPUS", "weekly monthly m4-hourly").split()
TB_MAX = int(os.environ.get("TB_MAX", 0))
NSHARD = int(os.environ.get("TB_NSHARD", 1))
SHARDS = {int(s) for s in os.environ.get("TB_SHARDS", "0").split(",") if s != ""}
MINLEN = tw.CTX + tw.TEST + 12          # context + rolling test window + lag headroom


def done_keys(path):
    if not os.path.exists(path):
        return set()
    return {(r["series"], r["arm"], r["method"]) for r in csv.DictReader(open(path))}


def main():
    from tabfm import TabFMClassifier as Clf, tabfm_v1_0_0_pytorch as V
    t0 = time.time()
    model = V.load(model_type="classification", checkpoint_path=tw.WEIGHTS,
                   device=None if tw.DEVICE == "cpu" else tw.DEVICE)
    tw._mps_shim()
    print(f"[load] classification checkpoint {time.time()-t0:.0f}s device={tw.DEVICE} "
          f"TEST={tw.TEST} CTX={tw.CTX} minlen={MINLEN}", flush=True)

    done = done_keys(OUT)
    mode = "a" if os.path.exists(OUT) else "w"
    fh = open(OUT, mode, newline="")
    w = csv.writer(fh)
    if mode == "w":
        w.writerow(["series", "method", "logpdf", "crps", "n", "arm"])

    for arm in ARMS:
        series = list(corpus.iter_arm(arm))
        if TB_MAX:
            series = series[:TB_MAX]
        # keep only this worker's residue classes (disjoint across the fleet)
        series = [(j, x) for j, x in enumerate(series) if j % NSHARD in SHARDS]
        scored = skipped = 0
        for j, (sid, title, ch) in series:
            ch = ch[-tw.HIST:]
            need_lap = (sid, arm, "laplace") not in done
            need_clf = (sid, arm, "clf8") not in done
            if not (need_lap or need_clf):
                continue
            if len(ch) < MINLEN:
                skipped += 1
                continue
            t = time.time()
            y = ch[len(ch) - tw.TEST:]
            if need_lap:
                lp, cr = tw.laplace_scores(ch)
                w.writerow([sid, "laplace", f"{lp:.6f}", f"{cr:.6f}", tw.TEST, arm])
            if need_clf:
                dists = tw.clf_arm_dists(ch, 8, [tw.decile_edges], model, Clf, 1)
                aa, bb = tw.score_steps(dists, y)
                w.writerow([sid, "clf8", f"{aa:.6f}", f"{bb:.6f}", tw.TEST, arm])
            fh.flush()
            scored += 1
            print(f"  {arm} {j+1}/{len(series)} {sid} ({time.time()-t:.0f}s)", flush=True)
        print(f"[{arm}] scored {scored}, skipped {skipped} (too short)", flush=True)

    fh.close()
    del model
    gc.collect()
    print("[done]", flush=True)


if __name__ == "__main__":
    main()

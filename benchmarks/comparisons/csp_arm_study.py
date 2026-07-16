"""laplace vs the official CSP package on one corpus arm.

    PYTHONPATH=src python benchmarks/comparisons/csp_arm_study.py <arm>

Arms come from benchmarks/corpus.py (weekly m=52, monthly m=12, m4-hourly m=24;
the daily arm runs through run_comparison.py as before). The CSP season period
is recentred on the arm's m, so the variant star tests the arm's own cycle.
Results append to comparisons/laplace-vs-csp/results_<arm>.csv (crash-safe
resume); the win-rate table prints at the end.
"""
import csv
import math
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

_HERE = os.path.dirname(os.path.abspath(__file__))
_BENCH = os.path.dirname(_HERE)
sys.path.insert(0, _BENCH)

import corpus

ARM = sys.argv[1] if len(sys.argv) > 1 else "monthly"
CFG = corpus.ARMS[ARM]
os.environ["BENCH_CSP_M"] = str(CFG["m"])          # before opponents import, incl. workers
BURN = 150 if ARM in ("weekly", "monthly") else 300
MAX_CH = 6000
MAX_QUALIFY = int(os.environ.get("STUDY_MAX_QUALIFY", 250))
LIMIT = int(os.environ.get("CORPUS_LIMIT", 2000))
WORKERS = int(os.environ.get("STUDY_WORKERS", min(8, (os.cpu_count() or 4))))
OPPS = [s for s in os.environ.get("STUDY_OPPS", "laplace,CSP").split(",") if s]
RESULTS = os.path.join(_HERE, "laplace-vs-csp", f"results_{ARM.replace('-', '_')}.csv")


def _covered(opp_name, methods, opp_methods=None):
    """Is this opponent already fully present in a series' scored methods?"""
    if opp_name == "CSP":
        return any(m.startswith("CSPr-") for m in methods)
    need = (opp_methods or {}).get(opp_name) or [opp_name]
    return all(m in methods for m in need)


def score_one(payload):
    sid, ch, todo = payload
    import opponents as opp                         # after BENCH_CSP_M is set
    if len(ch) > MAX_CH:
        ch = ch[-MAX_CH:]
    start = max(BURN, len(ch) - CFG["test"])
    rows = []
    for name in todo:
        op = opp.REGISTRY[name]
        try:
            for method, lp, cr, n in op.predict(ch, start, 25):
                rows.append([sid, method, f"{cr:.6f}",
                             ("" if lp is None else f"{lp:.6f}"), n])
        except Exception as e:  # noqa: BLE001
            print(f"  ERR {sid}/{name}: {e}", flush=True)
    return sid, rows


def main():
    done = {}
    if os.path.exists(RESULTS):
        with open(RESULTS) as f:
            r = csv.reader(f); next(r, None)
            for row in r:
                if row:
                    done.setdefault(row[0], set()).add(row[1])
    new = not os.path.exists(RESULTS)
    try:
        import subprocess
        from skaters import __version__ as _v
        _sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, cwd=_BENCH).stdout.strip()
        print(f"[{ARM}] skaters {_v} @ {_sha}", flush=True)
    except Exception:  # noqa: BLE001 — stamping is best-effort
        pass
    print(f"[{ARM}] m={CFG['m']} test={CFG['test']} burn={BURN} opps={OPPS} "
          f"max_qualify={MAX_QUALIFY} resume={len(done)} -> {RESULTS}", flush=True)
    import opponents as opp_mod                     # BENCH_CSP_M already set
    opp_methods = {o.name: o.methods for o in opp_mod.ALL}
    t0 = time.time(); n_sub = n_seen = n_fin = 0
    with open(RESULTS, "a", newline="") as fh, \
            ProcessPoolExecutor(max_workers=WORKERS) as pool:
        w = csv.writer(fh)
        if new:
            w.writerow(["series", "method", "crps", "logpdf", "n"]); fh.flush()
        futs = []
        for sid, title, ch in corpus.iter_arm(ARM, limit=LIMIT):
            n_seen += 1
            if n_seen > MAX_QUALIFY:
                break
            todo = [o for o in OPPS
                    if not _covered(o, done.get(sid, set()), opp_methods)]
            if not todo:
                continue
            futs.append(pool.submit(score_one, (sid, ch, todo)))
            n_sub += 1
        for fut in as_completed(futs):
            _, rows = fut.result()
            for row in rows:
                w.writerow(row)
            fh.flush(); n_fin += 1
            if n_fin % 20 == 0:
                print(f"  scored {n_fin}/{n_sub}  "
                      f"({n_fin / max(time.time() - t0, 1e-9) * 60:.0f}/min)", flush=True)
    print(f"[{ARM}] scored {n_fin} new series", flush=True)
    summarize()


def summarize():
    by = {}
    with open(RESULTS) as f:
        for row in csv.DictReader(f):
            try:
                lp = float(row["logpdf"]) if row["logpdf"] else float("nan")
                cr = float(row["crps"])
            except ValueError:
                continue
            by.setdefault(row["series"], {})[row["method"]] = (lp, cr)
    methods = sorted({m for d in by.values() for m in d} - {"laplace"})
    print(f"\n=== [{ARM}] {len(by)} series — laplace win-rate vs each ===")
    print(f"  {'method':22s}{'CRPS':>8s}{'LL':>8s}{'N':>6s}")
    for m in methods:
        pairs = [(by[s]["laplace"], by[s][m]) for s in by
                 if "laplace" in by[s] and m in by[s]]
        cw = [1.0 if a[1] < b[1] else 0.0 for a, b in pairs
              if not (math.isnan(a[1]) or math.isnan(b[1]))]
        lw = [1.0 if a[0] > b[0] else 0.0 for a, b in pairs
              if not (math.isnan(a[0]) or math.isnan(b[0]))]
        print(f"  {m:22s}{100 * sum(cw) / len(cw):>7.0f}%"
              f"{100 * sum(lw) / len(lw):>7.0f}%{len(pairs):>6d}" if cw else
              f"  {m:22s}{'—':>8s}{'—':>8s}{0:>6d}")


if __name__ == "__main__":
    if "summarize" in sys.argv:
        summarize()
    else:
        main()

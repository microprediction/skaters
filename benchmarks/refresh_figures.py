"""Regenerate every study-derived artefact from the current results CSV, so the
paper figures, the site figures, the robustness explorer, and the headline
numbers can all be refreshed with ONE command any time the study advances.

    PYTHONPATH=src python benchmarks/refresh_figures.py [results.csv]

Defaults to the non-price sweep CSV. Everything downstream reads the same CSV, so
the frontier plot, the win-rate tables, and the explorer never drift apart.

Outputs:
  docs/assets/frontier.svg, .png     accuracy/speed frontier (paper + landing page)
  docs/robustness.html               interactive robustness explorer (standalone)
  papers/_benchmark_numbers.txt      current win-rate tables (paste into the paper / README)

Idempotent: re-run whenever the sweep has scored more series. Needs matplotlib
(for the frontier) in the active environment; the other outputs need none.
"""
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_PY = sys.executable
DEFAULT_CSV = os.path.join(_HERE, "comparisons", "_shared_R25_nonprice.csv")


# Homebrew's Python 3.12 pyexpat.so is linked against Homebrew's libexpat (newer
# symbols than /usr/lib), so matplotlib's xml import can fail with a missing
# symbol. Point the dynamic loader at Homebrew's expat when it exists.
_EXPAT = "/opt/homebrew/opt/expat/lib"


def _run(desc, argv, env, capture_to=None):
    print(f"\n=== {desc} ===", flush=True)
    env2 = dict(os.environ, **env, PYTHONPATH=os.path.join(_ROOT, "src"))
    if os.path.isdir(_EXPAT):
        prev = env2.get("DYLD_LIBRARY_PATH", "")
        env2["DYLD_LIBRARY_PATH"] = _EXPAT + (":" + prev if prev else "")
    r = subprocess.run(argv, cwd=_ROOT, env=env2,
                       stdout=(subprocess.PIPE if capture_to else None),
                       stderr=(subprocess.STDOUT if capture_to else None), text=True)
    if capture_to and r.stdout is not None:
        with open(capture_to, "w") as f:
            f.write(r.stdout)
        print(r.stdout)
        print(f"  -> wrote {os.path.relpath(capture_to, _ROOT)}")
    print("  status:", "ok" if r.returncode == 0 else f"FAILED ({r.returncode})", flush=True)
    return r.returncode


def main(argv):
    csv = os.path.abspath(argv[0]) if argv else DEFAULT_CSV
    if not os.path.exists(csv):
        print(f"results CSV not found: {csv}"); return 1
    n = sum(1 for _ in open(csv)) - 1
    print(f"refreshing all artefacts from {os.path.relpath(csv, _ROOT)}  ({n} rows)")
    env = {"STUDY_RESULTS": csv, "STUDY_EXCLUDE_PRICE": "1"}
    rc = 0

    # 1. accuracy/speed frontier (paper + site) — needs matplotlib
    rc |= _run("frontier plot -> docs/assets/frontier.{svg,png}",
               [_PY, "benchmarks/make_frontier.py"], env)

    # 2. robustness explorer -> docs/robustness.html (standalone, no deps)
    rc |= _run("robustness explorer -> docs/robustness.html",
               [_PY, "benchmarks/comparisons/make_robustness_page.py", csv,
                os.path.join(_ROOT, "docs", "robustness.html"), "--standalone"], env)

    # 3. headline win-rate tables -> papers/_benchmark_numbers.txt (paste source)
    _run("win-rate tables -> papers/_benchmark_numbers.txt",
         [_PY, "benchmarks/horserace_summary.py"], env,
         capture_to=os.path.join(_ROOT, "papers", "_benchmark_numbers.txt"))

    print("\nDONE." if rc == 0 else "\nDONE (with a failure above).")
    return 1 if rc else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

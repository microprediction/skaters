"""Run laplace vs. a single opponent set, into that comparison's own folder.

    PYTHONPATH=src python benchmarks/comparisons/run_comparison.py <slug> <opp> [<opp> ...]

`<slug>` is the folder under comparisons/ (e.g. laplace-vs-adam); the remaining
args are opponent *names* from the registry (e.g. R@25, statsforecast@25, CSP,
GARCH-t). laplace is always included. Results go to comparisons/<slug>/results.csv
and the same one-harness summary is printed (paste it into that folder's README).

Nothing new is scored: it's the `sota` study with STUDY_ONLY restricting the
opponent set and STUDY_RESULTS pointing at the folder — the one honest harness,
one slice at a time.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_BENCH = os.path.dirname(_HERE)
sys.path.insert(0, _BENCH)


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    slug, opps = argv[0], argv[1:]
    folder = os.path.join(_HERE, slug)
    os.makedirs(folder, exist_ok=True)
    os.environ["STUDY_ONLY"] = ",".join(["laplace"] + opps)
    os.environ["STUDY_RESULTS"] = os.path.join(folder, "results.csv")
    print(f"[comparison] {slug}: laplace vs {opps}")
    print(f"[comparison] results -> {os.environ['STUDY_RESULTS']}\n")
    import study
    study.run("sota")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

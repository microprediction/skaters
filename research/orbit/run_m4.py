"""Run ordinary orbit-transform candidates through the canonical M4 pipeline."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
METHODS = ("orbit-leaf", "laplace(+orbit)", "CSP", "laplace")


def validate_targets(output):
    """Refuse unpaired, incomplete, or duplicated canonical cells."""
    targets = {}
    seen = set()
    cells = {}
    for path in sorted(output.glob("*__m4-hourly.csv")):
        with path.open() as handle:
            for row in csv.DictReader(handle):
                target = (row["series"], int(row["step"]))
                key = target + (row["method"],)
                if key in seen:
                    raise ValueError(f"duplicate canonical row {key}")
                seen.add(key)
                y = row["y"]
                if targets.setdefault(target, y) != y:
                    raise ValueError(f"unpaired targets at {target}")
                cells.setdefault((row["series"], row["method"]), set()).add(target[1])
    series = {sid for sid, _ in cells}
    if not series or any(cells.get((sid, method)) != set(range(64))
                         for sid in series for method in METHODS):
        raise ValueError("each series must have 64 targets for all four methods")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--horizon", type=int, default=1)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--baseline-cache", type=Path,
                        help="reuse canonical CSP/laplace rows from an identical-protocol run")
    args = parser.parse_args()
    if args.horizon < 1 or args.workers < 1:
        parser.error("horizon and workers must be positive")
    output = ROOT / "benchmarks" / "preds" / f"orbit-h{args.horizon}"
    output.mkdir(parents=True, exist_ok=True)
    methods = list(METHODS)
    if args.baseline_cache:
        paths = sorted(args.baseline_cache.glob("*__m4-hourly.csv"))
        if not paths:
            parser.error("baseline cache has no canonical M4 Hourly files")
        dest = output / "cached-baselines__m4-hourly.csv"
        with dest.open("w", newline="") as handle:
            writer = None
            for path in paths:
                with path.open() as source:
                    reader = csv.DictReader(source)
                    if writer is None:
                        writer = csv.DictWriter(handle, fieldnames=reader.fieldnames)
                        writer.writeheader()
                    for row in reader:
                        if row["method"] in ("CSP", "laplace"):
                            writer.writerow(row)
        methods = [m for m in methods if m not in ("CSP", "laplace")]
    common = dict(os.environ, ARM_METHODS=",".join(methods), ARM_CORPUS="m4-hourly",
                  ARM_H=str(args.horizon), ARM_NSHARD=str(args.workers), ARM_MAX="0",
                  ARM_REGIME="", ARM_SPLIT="", ARM_PREMAX="0", CSP_M="24",
                  FM_TEST="64", FM_CTX="128", CSP_NSAMPLES="256", CSP_FIT_WIN="750")
    common["PYTHONPATH"] = os.pathsep.join((str(ROOT), str(ROOT / "src"),
                                           str(ROOT / "benchmarks"), os.environ.get("PYTHONPATH", "")))

    def run_shard(shard):
        env = dict(common, ARM_SHARDS=str(shard),
                   PRED_OUT=str(output / f"shard{shard}__m4-hourly.csv"))
        log = output / f"shard{shard}.log"
        with log.open("w") as handle:
            result = subprocess.run([sys.executable, "benchmarks/run_arm.py"], cwd=ROOT,
                                    env=env, stdout=handle, stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError(f"shard {shard} failed, see {log}")
        print(f"shard {shard} complete", flush=True)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(run_shard, range(args.workers)))
    validate_targets(output)
    for baseline in ("CSP", "laplace"):
        suffix = f"_orbit_h{args.horizon}"
        env = dict(common, CANON_PREDS=str(output), CANON_BASELINE=baseline,
                   CANON_SUFFIX=suffix, CANON_PER_SERIES="0")
        subprocess.run([sys.executable, "benchmarks/summarize_canonical.py"], cwd=ROOT,
                       env=env, check=True)
        suffix += "_vs_CSP" if baseline == "CSP" else ""
        for kind, label in (("vs_laplace", "scores"), ("coverage", "coverage")):
            summary = ROOT / "benchmarks" / f"canonical_summary_{kind}{suffix}.csv"
            if baseline == "CSP" or label == "scores":
                destination = Path(__file__).parent / f"results_{label}_h{args.horizon}_vs_{baseline}.csv"
                destination.write_text(summary.read_text())
            summary.unlink()


if __name__ == "__main__":
    main()

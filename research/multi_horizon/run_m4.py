"""Run fixed research arms and CSP through the canonical M4 Hourly pipeline."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
METHODS = "MHSeasonal-naive,MHSeasonal-ema,MHSeasonal-laplace,CSP,laplace"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--horizon", type=int, default=1)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--methods", default=METHODS)
    args = parser.parse_args()
    if args.horizon < 1 or args.workers < 1:
        parser.error("horizon and workers must be positive")
    output = ROOT / "benchmarks" / "preds" / f"mh-seasonal-h{args.horizon}"
    output.mkdir(parents=True, exist_ok=True)
    common = dict(os.environ, ARM_METHODS=args.methods, ARM_CORPUS="m4-hourly",
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
    env = dict(common, CANON_PREDS=str(output), CANON_BASELINE="CSP",
               CANON_SUFFIX=f"_mhseasonal_h{args.horizon}", CANON_PER_SERIES="0")
    subprocess.run([sys.executable, "benchmarks/summarize_canonical.py"], cwd=ROOT,
                   env=env, check=True)
    for kind, label in (("vs_laplace", "scores"), ("coverage", "coverage")):
        summary = ROOT / "benchmarks" / f"canonical_summary_{kind}_mhseasonal_h{args.horizon}_vs_CSP.csv"
        destination = Path(__file__).parent / f"results_{label}_h{args.horizon}_vs_CSP.csv"
        destination.write_text(summary.read_text())
        summary.unlink()


if __name__ == "__main__":
    main()

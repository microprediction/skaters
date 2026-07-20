#!/usr/bin/env bash
# PyMC-Forecast (solo) on the seasonal/waveform arms, thread-capped CPU pool.
# 12 workers x 1 BLAS thread = 12 cores, under half of this 28-core box.
# Each worker: disjoint residue shard, own output file, own pytensor compiledir.
# Kill: pkill -f pymc_arms_study
set -u
cd "$(dirname "$0")/.."
export PYTHONPATH=src:benchmarks
PY="$HOME/.venvs/skaters-pymc/bin/python"
NSHARD=12
METHOD=${PF_METHOD:-raw}       # raw = standalone challenger (radar); solo = collaboration

pids=()
for r in $(seq 0 $((NSHARD - 1))); do
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
  PYTENSOR_FLAGS="base_compiledir=$HOME/.pytensor/pf_worker_$r" \
  PF_METHOD=$METHOD PF_NSHARD=$NSHARD PF_SHARDS=$r PF_OUT="results_pymc_${METHOD}_arms.$r.csv" \
    "$PY" -u benchmarks/pymc_arms_study.py > "benchmarks/_pymc_${METHOD}_$r.log" 2>&1 &
  pids+=($!)
done
echo "[pf-fleet] launched ${#pids[@]} workers (12 x 1 thread), pids: ${pids[*]}"
wait
echo "[pf-fleet] all workers exited"

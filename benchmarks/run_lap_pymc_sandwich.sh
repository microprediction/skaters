#!/usr/bin/env bash
# laplace@PyMC (laplace base, PyMC regression on laplace's normal scores,
# inverted through laplace), the frontier figure's "PyMC-laplace sandwich"
# through run_arm.py, on the three FRED economic strata, first 500 series of
# each (the monthly cap matches the stored raw PyMC run). Eight shards per
# corpus, corpora in sequence, resumable by (series, method).
#
#   caffeinate -i -s nohup benchmarks/run_lap_pymc_sandwich.sh > benchmarks/_lap_pymc_fleet.log 2>&1 &
set -u
cd "$(dirname "$0")/.."
export PYTHONPATH=src:benchmarks
PY="$HOME/.venvs/skaters-pymc/bin/python"
THREADS=${SAND_THREADS:-3}
NSHARD=${PYMC_NSHARD:-8}
CORPORA=${LAP_PYMC_CORPORA:-"monthly weekly daily"}

status=0
for corpus in $CORPORA; do
  pids=()
  for r in $(seq 0 $((NSHARD - 1))); do
    OMP_NUM_THREADS=$THREADS MKL_NUM_THREADS=$THREADS VECLIB_MAXIMUM_THREADS=$THREADS \
    ARM_METHODS="laplace@PyMC" ARM_CORPUS=$corpus ARM_MAX=500 ARM_REGIME=econ \
    ARM_NSHARD=$NSHARD ARM_SHARDS=$r \
    PRED_OUT="benchmarks/preds/laplace@PyMC__${corpus}.s${r}.csv" \
      "$PY" -u benchmarks/run_arm.py > "benchmarks/_lap_pymc_${corpus}.s${r}.log" 2>&1 &
    pids+=($!)
  done
  echo "[lap@pymc] $corpus: launched ${#pids[@]} workers"
  for pid in "${pids[@]}"; do
    wait "$pid" || { echo "[lap@pymc] $corpus worker $pid failed" >&2; status=1; }
  done
  echo "[lap@pymc] $corpus done"
done
[ $status -eq 0 ] && echo "[lap@pymc] all corpora exited"
exit $status

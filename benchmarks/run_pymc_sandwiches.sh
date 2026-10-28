#!/usr/bin/env bash
# The four sandwich arms (+lap, ~lap, @lap, &lap) on the PyMC-forecast base,
# through run_arm.py, on the same series as the stored raw PyMC run
# (monthly, ARM_MAX=500: 471 of the first 500 series are long enough for the
# scored window; the warm-up-extended window that ~lap/@lap need fits 354 of
# them). The base is memoized (arm_adapters._memoized) so one ADVI fit
# sequence serves +lap/&lap and one serves ~lap/@lap per series. Eight
# shards, resumable by (series, method).
#
#   caffeinate -i -s nohup benchmarks/run_pymc_sandwiches.sh > benchmarks/_pymc_sand_fleet.log 2>&1 &
set -u
cd "$(dirname "$0")/.."
export PYTHONPATH=src:benchmarks
PY="$HOME/.venvs/skaters-pymc/bin/python"
THREADS=${SAND_THREADS:-3}
NSHARD=${PYMC_NSHARD:-8}
ARMS="PyMC+lap,PyMC~lap,PyMC@lap,PyMC&lap"

pids=()
for r in $(seq 0 $((NSHARD - 1))); do
  OMP_NUM_THREADS=$THREADS MKL_NUM_THREADS=$THREADS VECLIB_MAXIMUM_THREADS=$THREADS \
  ARM_METHODS="$ARMS" ARM_CORPUS=monthly ARM_MAX=500 ARM_NSHARD=$NSHARD ARM_SHARDS=$r \
  PRED_OUT="benchmarks/preds/PyMC-sandwiches__monthly.s${r}.csv" \
    "$PY" -u benchmarks/run_arm.py > "benchmarks/_pymc_sand.s${r}.log" 2>&1 &
  pids+=($!)
done
echo "[pymc-sand] launched ${#pids[@]} workers, pids: ${pids[*]}"
status=0
for pid in "${pids[@]}"; do
  wait "$pid" || { echo "[pymc-sand] worker $pid failed" >&2; status=1; }
done
[ $status -eq 0 ] && echo "[pymc-sand] all workers exited"
exit $status

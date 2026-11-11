#!/usr/bin/env bash
# Untested pool transforms through run_arm.py: laplace(+lou), (+gar), (+ou),
# (+ma), (+huber), (+ptrend), (+setar) and laplace(markov), each laplace with
# extra candidate chains (arm_adapters._pool_extras, benchmarks/pool_transforms.py)
# and everything else identical, so each pairs with the laplace run on the same
# windows. Corpora in sequence, eight shards each, resumable by (series,
# method). Monthly capped at 5,600 like laplace's run.
#
#   caffeinate -i -s nohup benchmarks/run_pool_transforms.sh > benchmarks/_pool_fleet.log 2>&1 &
set -u
cd "$(dirname "$0")/.."
export PYTHONPATH=src:benchmarks
PY=".venv-sota/bin/python"
CORPORA=${PT_CORPORA:-"weekly m4-hourly monthly daily"}
NSHARD=${PT_NSHARD:-8}
ARMS=$($PY -c "import arm_adapters as a; print(','.join(f'laplace({x})' for x in a.POOL_EXTRAS))")
status=0
for c in $CORPORA; do
  max=0; [ "$c" = monthly ] && max=5600
  pids=()
  for r in $(seq 0 $((NSHARD - 1))); do
    OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
    ARM_METHODS="$ARMS" ARM_CORPUS=$c ARM_MAX=$max ARM_NSHARD=$NSHARD ARM_SHARDS=$r \
    PRED_OUT="benchmarks/preds/pool__${c}.s${r}.csv" \
      "$PY" -u benchmarks/run_arm.py > "benchmarks/_pool_${c}.s${r}.log" 2>&1 &
    pids+=($!)
  done
  echo "[pool] $(date '+%T') $c: ${#pids[@]} workers"
  for p in "${pids[@]}"; do wait "$p" || { echo "[pool] worker $p failed"; status=1; }; done
  echo "[pool] $(date '+%T') $c done"
done
exit $status

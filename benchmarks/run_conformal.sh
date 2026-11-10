#!/usr/bin/env bash
# Conformal methods for time series through run_arm.py (benchmarks/conformal_arms.py):
# wrappers on laplace and AutoARIMA (id, roll, nexcp, aci, pid) and Vovk's
# histogram predictive system. Corpora in sequence, eight shards each,
# resumable by (series, method). Monthly capped at 5,600 like laplace's run.
#
#   caffeinate -i -s nohup benchmarks/run_conformal.sh > benchmarks/_conformal_fleet.log 2>&1 &
set -u
cd "$(dirname "$0")/.."
export PYTHONPATH=src:benchmarks
PY=".venv-sota/bin/python"
CORPORA=${CF_CORPORA:-"weekly m4-hourly monthly daily"}
NSHARD=${CF_NSHARD:-8}
ARMS=$($PY -c "import conformal_arms as c; print(','.join(c.registry(1)))")
status=0
for c in $CORPORA; do
  max=0; [ "$c" = monthly ] && max=5600
  pids=()
  for r in $(seq 0 $((NSHARD - 1))); do
    OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
    ARM_METHODS="$ARMS" ARM_CORPUS=$c ARM_MAX=$max ARM_NSHARD=$NSHARD ARM_SHARDS=$r \
    PRED_OUT="benchmarks/preds/conformal__${c}.s${r}.csv" \
      "$PY" -u benchmarks/run_arm.py > "benchmarks/_conformal_${c}.s${r}.log" 2>&1 &
    pids+=($!)
  done
  echo "[conformal] $(date '+%T') $c: ${#pids[@]} workers"
  for p in "${pids[@]}"; do wait "$p" || { echo "[conformal] worker $p failed"; status=1; }; done
  echo "[conformal] $(date '+%T') $c done"
done
exit $status

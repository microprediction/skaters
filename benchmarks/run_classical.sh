#!/usr/bin/env bash
# The classical baselines through run_arm.py, refit at every step
# (AutoARIMA: order once on pre-test history, coefficients every step;
# AutoETS and AutoTheta: full refit every step; GARCH-t: refit every step).
# Corpora in sequence, eight shards each, resumable by (series, method).
#
#   caffeinate -i -s nohup benchmarks/run_classical.sh > benchmarks/_classical_fleet.log 2>&1 &
#
# CL_CORPORA (default "weekly monthly m4-hourly daily"), CL_MAX_<corpus> caps
# (default: weekly and hourly all, monthly and daily 1500), CL_NSHARD (8).
set -u
cd "$(dirname "$0")/.."
export PYTHONPATH=src:benchmarks
PY=".venv-sota/bin/python"
CORPORA=${CL_CORPORA:-"weekly monthly m4-hourly daily"}
NSHARD=${CL_NSHARD:-8}
ARMS="AutoETS,AutoTheta,GARCH-t,AutoARIMA"
cap() { local v="CL_MAX_$1"; v=${v//-/_}; case $1 in monthly|daily) echo "${!v:-1500}";; *) echo "${!v:-0}";; esac; }

status=0
for c in $CORPORA; do
  pids=()
  for r in $(seq 0 $((NSHARD - 1))); do
    OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
    ARM_METHODS="$ARMS" ARM_CORPUS=$c ARM_MAX=$(cap "$c") ARM_NSHARD=$NSHARD ARM_SHARDS=$r \
    PRED_OUT="benchmarks/preds/classical__${c}.s${r}.csv" \
      "$PY" -u benchmarks/run_arm.py > "benchmarks/_classical_${c}.s${r}.log" 2>&1 &
    pids+=($!)
  done
  echo "[classical] $(date '+%T') $c: ${#pids[@]} workers"
  for pid in "${pids[@]}"; do wait "$pid" || { echo "[classical] $c worker $pid failed" >&2; status=1; }; done
  echo "[classical] $(date '+%T') $c done"
done
exit $status

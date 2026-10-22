#!/usr/bin/env bash
# t0-gamma arms (#287) through the canonical runner: one worker per arm, each
# walking the four corpora, writing benchmarks/preds/<arm>__<corpus>.csv.
# Resumable (run_arm.py skips written (series, method) rows). Monthly is capped
# at 5,600 series, the same bound as the Timestral and TimesFM3(wide) runs.
#
#   caffeinate -i -s nohup benchmarks/run_t0_study.sh > benchmarks/_t0_fleet.log 2>&1 &
set -u
cd "$(dirname "$0")/.."
export PYTHONPATH=src:benchmarks
PY=.venv-t0/bin/python
ARMS=${T0_ARMS:-"t0-gamma(q21) t0-gamma t0-gamma(q21+sym)"}
CORPORA=${T0_CORPORA:-"m4-hourly weekly daily monthly"}
THREADS=${T0_THREADS:-8}

pids=()
for arm in $ARMS; do
  (
    for corpus in $CORPORA; do
      max=0; [ "$corpus" = monthly ] && max=5600
      OMP_NUM_THREADS=$THREADS MKL_NUM_THREADS=$THREADS VECLIB_MAXIMUM_THREADS=$THREADS \
      FM_DEVICE=cpu ARM_METHODS="$arm" ARM_CORPUS=$corpus ARM_MAX=$max \
      PRED_OUT="benchmarks/preds/${arm}__${corpus}.csv" \
        $PY -u benchmarks/run_arm.py || exit 1
    done
  ) > "benchmarks/_t0_${arm}.log" 2>&1 &
  pids+=($!)
done

echo "[t0] launched ${#pids[@]} workers, pids: ${pids[*]}"
status=0
for pid in "${pids[@]}"; do
  wait "$pid" || { echo "[t0] worker $pid failed" >&2; status=1; }
done
if [ $status -eq 0 ]; then echo "[t0] all workers exited"; fi
exit $status

#!/usr/bin/env bash
# TimeH2O arms (#298) through the canonical runner: one worker per checkpoint
# running its tight and generous reconstructions together (one forward pass,
# memoised), all four corpora, monthly capped at 5,600 like the Timestral,
# t0-gamma and TimesFM3(wide) runs. Resumable. Needs a Hugging Face token with
# the h2oai/timeh2o-v1 and h2oai/timeh2o-v1-tiny licences accepted.
#
#   caffeinate -i -s nohup benchmarks/run_timeh2o_study.sh > benchmarks/_timeh2o_fleet.log 2>&1 &
set -u
cd "$(dirname "$0")/.."
export PYTHONPATH=src:benchmarks
PY=.venv-timeh2o/bin/python
THREADS=${TIMEH2O_THREADS:-6}
CORPORA=${TIMEH2O_CORPORA:-"m4-hourly weekly daily monthly"}

pids=()
for size in v1 v1-tiny; do
  arms="TimeH2O-${size},TimeH2O-${size}(wide)"
  (
    for corpus in $CORPORA; do
      max=0; [ "$corpus" = monthly ] && max=5600
      OMP_NUM_THREADS=$THREADS MKL_NUM_THREADS=$THREADS VECLIB_MAXIMUM_THREADS=$THREADS \
      FM_DEVICE=cpu ARM_METHODS="$arms" ARM_CORPUS=$corpus ARM_MAX=$max \
      PRED_OUT="benchmarks/preds/TimeH2O-${size}__${corpus}.csv" \
        $PY -u benchmarks/run_arm.py || exit 1
    done
  ) > "benchmarks/_timeh2o_${size}.log" 2>&1 &
  pids+=($!)
done

echo "[timeh2o] launched ${#pids[@]} workers, pids: ${pids[*]}"
status=0
for pid in "${pids[@]}"; do
  wait "$pid" || { echo "[timeh2o] worker $pid failed" >&2; status=1; }
done
if [ $status -eq 0 ]; then echo "[timeh2o] all workers exited"; fi
exit $status

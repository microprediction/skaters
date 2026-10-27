#!/usr/bin/env bash
# Timestral arms (#282) through the canonical runner: one worker per arm, each
# walking the four corpora in order, writing the per-arm store files
# benchmarks/preds/<arm>__<corpus>.csv that summarize_canonical.py reads.
# Resumable: run_arm.py skips any (series, method) already in its PRED_OUT.
# Monthly is capped at 5,600 series, the same bound as the TimesFM3(wide) run,
# so the arm pairs with the 5,576 monthly series laplace has in the store.
#
#   caffeinate -i nohup benchmarks/run_timestral_study.sh > benchmarks/_timestral_fleet.log 2>&1 &
#   pkill -f "ARM_METHODS=Timestral"     # stop
set -u
cd "$(dirname "$0")/.."
export PYTHONPATH=src:benchmarks
PY=.venv-timestral/bin/python
ARMS=${TIMESTRAL_ARMS:-"Timestral-5M Timestral-28M Timestral-123M Timestral-209M Timestral-5M(q21) Timestral-28M(q21) Timestral-123M(q21) Timestral-209M(q21)"}
CORPORA=${TIMESTRAL_CORPORA:-"m4-hourly weekly daily monthly"}
THREADS=${TIMESTRAL_THREADS:-4}

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
  ) > "benchmarks/_timestral_${arm}.log" 2>&1 &
  pids+=($!)
done

echo "[timestral] launched ${#pids[@]} workers, pids: ${pids[*]}"
status=0
for pid in "${pids[@]}"; do
  wait "$pid" || { echo "[timestral] worker $pid failed" >&2; status=1; }
done
if [ $status -eq 0 ]; then echo "[timestral] all workers exited"; fi
exit $status

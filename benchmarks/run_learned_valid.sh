#!/usr/bin/env bash
# Score the learned model (#297) on the VALIDATION half of the family split,
# through run_arm.py: the guaranteed mixture ("learned") and the trained expert
# alone ("learned-expert"), paired against the laplace rows already in the
# store. Eight shards, resumable. The checkpoint comes from learned_train.py.
#
#   LEARNED_CKPT=benchmarks/learned_ckpt/weekly_k1.pt LV_CORPUS=weekly LV_MAX=300 \
#     caffeinate -i -s nohup benchmarks/run_learned_valid.sh > benchmarks/_learned_valid_fleet.log 2>&1 &
set -u
cd "$(dirname "$0")/.."
export PYTHONPATH=src:benchmarks
PY=".venv-kumo/bin/python"
CORPUS=${LV_CORPUS:-weekly}
MAX=${LV_MAX:-300}
NSHARD=${LV_NSHARD:-8}
THREADS=${LV_THREADS:-2}
: "${LEARNED_CKPT:?set LEARNED_CKPT to the checkpoint}"
TAG=$(basename "$LEARNED_CKPT" .pt)

pids=()
for r in $(seq 0 $((NSHARD - 1))); do
  OMP_NUM_THREADS=$THREADS MKL_NUM_THREADS=$THREADS \
  ARM_METHODS="learned,learned-expert" ARM_CORPUS=$CORPUS ARM_REGIME=econ ARM_SPLIT=valid \
  ARM_MAX=$MAX ARM_NSHARD=$NSHARD ARM_SHARDS=$r \
  PRED_OUT="benchmarks/preds/learned-${TAG}__${CORPUS}.s${r}.csv" \
    "$PY" -u benchmarks/run_arm.py > "benchmarks/_learned_valid_${TAG}.s${r}.log" 2>&1 &
  pids+=($!)
done
echo "[learned-valid] $CORPUS: launched ${#pids[@]} workers for $TAG"
status=0
for pid in "${pids[@]}"; do
  wait "$pid" || { echo "[learned-valid] worker $pid failed" >&2; status=1; }
done
[ $status -eq 0 ] && echo "[learned-valid] all workers exited"
exit $status

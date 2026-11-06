#!/usr/bin/env bash
# laplace++ monthly on fresh FRED data (#297): one training run per shard of
# fred_extra_corpus.py's leak-checked corpus, all from the same start, then the
# shards' running averages are averaged (a weight soup) and scored on the
# held-out monthly half exactly like the earlier monthly runs.
#
#   FX_INIT=benchmarks/learned_ckpt/monthly_k1_swa5.pt \
#     caffeinate -i -s nohup benchmarks/run_monthly_fx.sh > benchmarks/_monthly_fx.log 2>&1 &
#
# Resumable: rerunning continues each shard from its checkpoint.
set -u
cd "$(dirname "$0")/.."
export PYTHONPATH=src:benchmarks
PY=".venv-kumo/bin/python"
CK=benchmarks/learned_ckpt
SHARDS=${FX_SHARDS:-12}
INIT=${FX_INIT:?set FX_INIT to the starting checkpoint}
TAG=${FX_TAG:-fx}

pids=()
for i in $(seq 0 $((SHARDS - 1))); do
  OUT=$CK/monthly_${TAG}${i}.pt
  OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  LT_BASE=0 LT_CORPUS=monthly LT_EXTRA=monthly-fx$i LT_EXTRA_MINLEN=60 LT_MAX=0 LT_K=1 LT_EPOCHS=1 \
  LT_WINDOW=64 LT_LR=${FX_LR:-3e-4} LT_PI=0.25 LT_CKPT_EVERY=25 LT_SWA_EVERY=300 LT_SWA_START=300 \
  LT_INIT=$INIT LT_RESUME=$OUT LT_OUT=$OUT \
    "$PY" -u benchmarks/learned_train.py > benchmarks/_learned_train_monthly_${TAG}${i}.log 2>&1 &
  pids+=($!)
done
echo "[fx] $(date '+%F %T') launched ${#pids[@]} shard runs from $INIT"
status=0
for pid in "${pids[@]}"; do wait "$pid" || { echo "[fx] shard run $pid failed"; status=1; }; done
[ $status -eq 0 ] || exit $status

IN=$(for i in $(seq 0 $((SHARDS - 1))); do printf '%s ' "$CK/monthly_${TAG}${i}_swa.pt"; done)
LA_IN="$IN" LA_OUT=$CK/monthly_${TAG}soup.pt "$PY" benchmarks/learned_average.py || exit 1
echo "[fx] $(date '+%F %T') soup of $SHARDS shards -> $CK/monthly_${TAG}soup.pt"
LEARNED_CKPT=$CK/monthly_${TAG}soup.pt LV_CORPUS=monthly LV_MAX=0 LV_PREMAX=5600 LV_NSHARD=8 LV_THREADS=2 \
  LV_RUN=${TAG}soup benchmarks/run_learned_valid.sh || exit 1
echo "[fx] $(date '+%F %T') ${TAG}soup scored"

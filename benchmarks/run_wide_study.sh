#!/usr/bin/env bash
# Generous-reconstruction arms (#269, #261): the same zero-shot quantile
# forecasts as the tight arms, reconstructed by nozzles.nozzle_wide. One
# worker per model in its own venv, each walking the four corpora, bounded to
# the series count its tight arm already covers so every row pairs.
# Resumable (run_arm.py skips written (series, method) rows).
#
#   caffeinate -i -s nohup benchmarks/run_wide_study.sh > benchmarks/_wide_fleet.log 2>&1 &
set -u
cd "$(dirname "$0")/.."
export PYTHONPATH=src:benchmarks
THREADS=${WIDE_THREADS:-6}
CORPORA=${WIDE_CORPORA:-"m4-hourly weekly daily monthly"}

# model  venv  per-corpus caps (m4-hourly weekly daily monthly), from the tight arm's coverage
declare -a JOBS=(
  "Chronos   .venv-chronos   0 2930 2930 2930"
  "TiRex     .venv-tirex     0 2920 2920 2920"
  "TimesFM   .venv-timesfm   0 2920 2920 2920"
  "flowstate .venv-flowstate 0 2930 2930 2930"
)

pids=()
for job in "${JOBS[@]}"; do
  read -r model venv cap_m4 cap_w cap_d cap_mo <<<"$job"
  arm="${model}(wide)"
  (
    for corpus in $CORPORA; do
      case $corpus in m4-hourly) max=$cap_m4;; weekly) max=$cap_w;; daily) max=$cap_d;; monthly) max=$cap_mo;; esac
      OMP_NUM_THREADS=$THREADS MKL_NUM_THREADS=$THREADS VECLIB_MAXIMUM_THREADS=$THREADS \
      FM_DEVICE=cpu ARM_METHODS="$arm" ARM_CORPUS=$corpus ARM_MAX=$max \
      PRED_OUT="benchmarks/preds/${arm}__${corpus}.csv" \
        $venv/bin/python -u benchmarks/run_arm.py || exit 1
    done
  ) > "benchmarks/_wide_${model}.log" 2>&1 &
  pids+=($!)
done

echo "[wide] launched ${#pids[@]} workers, pids: ${pids[*]}"
status=0
for pid in "${pids[@]}"; do
  wait "$pid" || { echo "[wide] worker $pid failed" >&2; status=1; }
done
if [ $status -eq 0 ]; then echo "[wide] all workers exited"; fi
exit $status

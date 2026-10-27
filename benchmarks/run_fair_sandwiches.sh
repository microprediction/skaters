#!/usr/bin/env bash
# The four sandwich arms (+lap, ~lap, @lap, &lap) on every fair base: the
# native-21-level Timestral-209M and t0-gamma arms and the generous (wide)
# reconstructions of TimesFM3, TimesFM 2.5, TiRex and Chronos. One worker per
# base runs its four arms together so the base forecasts are computed once
# per window (arm_adapters._memoized); TiRex is sharded five ways on CPU.
# Caps match the base runs so every row pairs. Resumable.
#
#   caffeinate -i -s nohup benchmarks/run_fair_sandwiches.sh > benchmarks/_sand_fleet.log 2>&1 &
set -u
cd "$(dirname "$0")/.."
export PYTHONPATH=src:benchmarks
THREADS=${SAND_THREADS:-3}
CORPORA=${SAND_CORPORA:-"m4-hourly weekly daily monthly"}

arms_for() { local b=$1; echo "${b}+lap,${b}~lap,${b}@lap,${b}&lap"; }

pids=()
launch() {  # base venv cap_monthly cap_other nshard shard
  local base=$1 venv=$2 capm=$3 capo=$4 nshard=$5 shard=$6
  local tag; tag=$(echo "$base" | tr -d '()')
  (
    for corpus in $CORPORA; do
      case $corpus in monthly) max=$capm;; m4-hourly) max=0;; *) max=$capo;; esac
      OMP_NUM_THREADS=$THREADS MKL_NUM_THREADS=$THREADS VECLIB_MAXIMUM_THREADS=$THREADS \
      FM_DEVICE=cpu ARM_METHODS="$(arms_for "$base")" ARM_CORPUS=$corpus ARM_MAX=$max \
      ARM_NSHARD=$nshard ARM_SHARDS=$shard \
      PRED_OUT="benchmarks/preds/${tag}-sandwiches__${corpus}.s${shard}.csv" \
        $venv/bin/python -u benchmarks/run_arm.py || exit 1
    done
  ) > "benchmarks/_sand_${tag}.s${shard}.log" 2>&1 &
  pids+=($!)
}

launch "Timestral-209M(q21)" .venv-timestral 5600 0    1 0
launch "t0-gamma(q21)"       .venv-t0       5600 0    1 0
launch "TimesFM3(wide)"      .venv-timesfm3 5600 0    1 0
launch "TimesFM(wide)"       .venv-timesfm  2920 2920 1 0
launch "Chronos(wide)"       .venv-chronos  2930 2930 1 0
for r in 0 1 2 3 4; do launch "TiRex(wide)" .venv-tirex 2920 2920 5 $r; done

echo "[sand] launched ${#pids[@]} workers, pids: ${pids[*]}"
status=0
for pid in "${pids[@]}"; do
  wait "$pid" || { echo "[sand] worker $pid failed" >&2; status=1; }
done
if [ $status -eq 0 ]; then echo "[sand] all workers exited"; fi
exit $status

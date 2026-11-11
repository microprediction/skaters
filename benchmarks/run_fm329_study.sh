#!/usr/bin/env bash
# Foundation-model arms from #329 through the canonical runner: one worker per
# model group, each in its own venv (benchmarks/<slug>_requirements.lock), all
# four corpora, monthly capped at 5,600 like the Timestral, t0-gamma and
# TimeH2O runs. Resumable by (series, method).
#
#   caffeinate -i -s nohup benchmarks/run_fm329_study.sh > benchmarks/_fm329_fleet.log 2>&1 &
#
# FM329_GROUPS picks groups by name (default all); VENV_ROOT is where the
# .venv-* directories live (default the repository root).
set -u
cd "$(dirname "$0")/.."
export PYTHONPATH=src:benchmarks
VENV_ROOT=${VENV_ROOT:-.}
THREADS=${FM329_THREADS:-2}
CORPORA=${FM329_CORPORA:-"m4-hourly weekly daily monthly"}

# group | venv | arms
GROUPS_ALL="
Chronos-2|.venv-chronos|Chronos-2
TiRex-2|.venv-tirex2|TiRex-2,TiRex-2(wide)
TTM-R3|.venv-ttm3|TTM-R3,TTM-R3(wide)
Moirai-2.0-small|.venv-moirai2|Moirai-2.0-small,Moirai-2.0-small(wide)
TinyCast|.venv-tinycast|TinyCast,TinyCast(flip),TinyCast(wide)
Toto2-small|.venv-toto2|Toto2-4m,Toto2-4m(wide),Toto2-22m,Toto2-22m(wide),Toto2-313m,Toto2-313m(wide)
Toto2-1B|.venv-toto2|Toto2-1B,Toto2-1B(wide)
Toto2-2.5B|.venv-toto2|Toto2-2.5B,Toto2-2.5B(wide)
"
WANT=${FM329_GROUPS:-all}

pids=()
while IFS='|' read -r group venv arms; do
  [ -z "$group" ] && continue
  if [ "$WANT" != all ] && [[ ",$WANT," != *",$group,"* ]]; then continue; fi
  (
    for corpus in $CORPORA; do
      max=0; [ "$corpus" = monthly ] && max=5600
      OMP_NUM_THREADS=$THREADS MKL_NUM_THREADS=$THREADS VECLIB_MAXIMUM_THREADS=$THREADS \
      FM_DEVICE=cpu ARM_METHODS="$arms" ARM_CORPUS=$corpus ARM_MAX=$max \
      PRED_OUT="benchmarks/preds/${group}__${corpus}.csv" \
        "$VENV_ROOT/$venv/bin/python" -u benchmarks/run_arm.py || exit 1
    done
  ) > "benchmarks/_fm329_${group}.log" 2>&1 &
  pids+=($!)
  echo "[fm329] $(date '+%T') $group: $arms"
done <<< "$GROUPS_ALL"

status=0
for pid in "${pids[@]}"; do
  wait "$pid" || { echo "[fm329] worker $pid failed" >&2; status=1; }
done
[ $status -eq 0 ] && echo "[fm329] $(date '+%T') all workers exited"
exit $status

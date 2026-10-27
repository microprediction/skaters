#!/usr/bin/env bash
# Kumo Tabular arms (#294) through the canonical runner, CPU only (the MPS
# path returned a different median on the same block). The two regressor
# level sets share one forward pass per series when run in the same worker,
# so each worker scores "<size>-reg(q21),<size>-reg(q99)" together. Workers
# are disjoint residue shards writing their own files (run_arm.py applies
# ARM_MAX before sharding, so shards partition the same series the other
# arms cover). Monthly capped at 5,600 like the Timestral and t0 runs.
#
#   caffeinate -i -s nohup benchmarks/run_kumo_study.sh > benchmarks/_kumo_fleet.log 2>&1 &
set -u
cd "$(dirname "$0")/.."
export PYTHONPATH=src:benchmarks
PY=.venv-kumo/bin/python
THREADS=${KUMO_THREADS:-3}
CORPORA=${KUMO_CORPORA:-"m4-hourly weekly daily monthly"}
NSHARD=${KUMO_NSHARD:-8}

pids=()
launch() {  # methods nshard shard tag
  local methods=$1 nshard=$2 shard=$3 tag=$4
  (
    for corpus in $CORPORA; do
      max=0; [ "$corpus" = monthly ] && max=5600
      OMP_NUM_THREADS=$THREADS MKL_NUM_THREADS=$THREADS VECLIB_MAXIMUM_THREADS=$THREADS \
      FM_DEVICE=cpu ARM_METHODS="$methods" ARM_CORPUS=$corpus ARM_MAX=$max \
      ARM_NSHARD=$nshard ARM_SHARDS=$shard \
      PRED_OUT="benchmarks/preds/${tag}__${corpus}.s${shard}.csv" \
        $PY -u benchmarks/run_arm.py || exit 1
    done
  ) > "benchmarks/_kumo_${tag}.s${shard}.log" 2>&1 &
  pids+=($!)
}

for r in 0 1 2 3 4 5; do launch "Kumo-large-reg(q21),Kumo-large-reg(q99)" 6 $r "Kumo-large-reg"; done
for r in 0 1; do launch "Kumo-small-reg(q21),Kumo-small-reg(q99)" 2 $r "Kumo-small-reg"; done
for r in 0 1; do launch "Kumo-small-clf8" 2 $r "Kumo-small-clf8"; done

echo "[kumo] launched ${#pids[@]} workers, pids: ${pids[*]}"
status=0
for pid in "${pids[@]}"; do
  wait "$pid" || { echo "[kumo] worker $pid failed" >&2; status=1; }
done
if [ $status -eq 0 ]; then echo "[kumo] all workers exited"; fi
exit $status

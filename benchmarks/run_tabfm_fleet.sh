#!/usr/bin/env bash
# TabFM arms fleet: one MPS worker + N_CPU CPU workers, disjoint residue shards,
# each its own output file (no shared-file race). Kill with: pkill -f tabfm_arms_study
set -u
cd "$(dirname "$0")/.."
export PYTHONPATH=src:benchmarks
PY=.venv-fm/bin/python
NSHARD=20
N_CPU=7                       # residues 13..19; MPS takes residues 0..12
CPU_THREADS=4                 # 7 x 4 = 28 logical cores

# MPS runs ~12x a single CPU worker on this model, so it takes 13 of 20
# residues and the 7 CPU workers take 1 each; both then finish ~together.
pids=()

# MPS worker. Resumes the already-computed rows in results_tabfm_arms.mps.csv.
TB_DEVICE=mps TB_NSHARD=$NSHARD TB_SHARDS=0,1,2,3,4,5,6,7,8,9,10,11,12 \
  TB_OUT=results_tabfm_arms.mps.csv \
  $PY -u benchmarks/tabfm_arms_study.py > benchmarks/_tabfm_mps.log 2>&1 &
pids+=($!)

# CPU workers: one residue each.
for r in $(seq 13 $((13 + N_CPU - 1))); do
  OMP_NUM_THREADS=$CPU_THREADS MKL_NUM_THREADS=$CPU_THREADS VECLIB_MAXIMUM_THREADS=$CPU_THREADS \
  TB_DEVICE=cpu TB_NSHARD=$NSHARD TB_SHARDS=$r \
    TB_OUT=results_tabfm_arms.c$r.csv \
    $PY -u benchmarks/tabfm_arms_study.py > benchmarks/_tabfm_c$r.log 2>&1 &
  pids+=($!)
done

echo "[fleet] launched ${#pids[@]} workers (1 mps + $N_CPU cpu), pids: ${pids[*]}"
status=0
for pid in "${pids[@]}"; do
  wait "$pid" || { echo "[fleet] worker $pid failed" >&2; status=1; }
done
if [ $status -eq 0 ]; then echo "[fleet] all workers exited"; fi
exit $status

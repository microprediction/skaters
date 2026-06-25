#!/usr/bin/env bash
# Overnight comprehensive horse race: laplace (current main: ema-calibration fix +
# forget=0.99) vs every baseline, across the FULL cached FRED universe.
#
# study.py's run() resumes from the CSV (skips already-scored series/method pairs)
# and re-seeds per-opponent budgets, but a hard worker crash (arch/statsforecast
# can segfault -> BrokenProcessPool) poisons the rest of a single run. So we wrap
# it in a relaunch loop: each pass resumes where the CSV left off; we stop when a
# pass adds no new rows (converged) or after MAX_PASSES.
#
#   bash benchmarks/overnight_horserace.sh
set -u
cd "$(dirname "$0")/.."

export PYTHONPATH=src
export STUDY_CACHED_ONLY=1                 # no network fetches — use the 2600 cached series
export STUDY_MAX_QUALIFY=3000              # let the whole qualifying cache in
export STUDY_N_CANDIDATES=3000
export STUDY_RESULTS=benchmarks/results_overnight.csv   # fresh file — do NOT clobber committed CSV
export STUDY_WORKERS=8
# The slow refitting baselines are capped so they don't gate throughput; the
# scientifically central race (laplace vs GARCH-t) runs wide across the cache.
export BENCH_SF_MAX=600                    # AutoARIMA / AutoETS (statsforecast)
export BENCH_SM_MAX=600                    # SARIMAX / ETS-sm (statsmodels)
export BENCH_GARCH_MAX=3000               # GARCH-t goes wide — the key opponent
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1

LOG=benchmarks/overnight_horserace.log
MAX_PASSES=40
echo "=== overnight horse race started $(date) ===" >> "$LOG"

rows_count() { [ -f "$STUDY_RESULTS" ] && wc -l < "$STUDY_RESULTS" | tr -d ' ' || echo 0; }

for pass in $(seq 1 $MAX_PASSES); do
  before=$(rows_count)
  echo "--- pass $pass start $(date) (rows so far: $before) ---" >> "$LOG"
  python benchmarks/study.py sota >> "$LOG" 2>&1
  status=$?
  after=$(rows_count)
  echo "--- pass $pass end $(date) status=$status rows: $before -> $after ---" >> "$LOG"
  # converged: a clean finish (status 0) that added no new rows
  if [ "$status" -eq 0 ] && [ "$after" -le "$before" ]; then
    echo "=== converged at pass $pass $(date) ===" >> "$LOG"
    break
  fi
  sleep 5
done

echo "=== horse race done $(date); summary follows ===" >> "$LOG"
python benchmarks/study.py sota summarize >> "$LOG" 2>&1 || true
echo "=== run benchmarks/horserace_summary.py for the price/non-price + family split ===" >> "$LOG"

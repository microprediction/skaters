#!/usr/bin/env bash
# Definitive NON-PRICE study: laplace (current main) vs every baseline across the
# full general / economic universe — all cached rates/credit/other series
# (equity/fx/commodity excluded; those are GARCH-t's turf, reported separately).
#
# This is the canonical study for the paper's "general time-series" claim. The
# slow refitting baselines (AutoARIMA/SARIMAX) are capped at 900 (they report N);
# laplace, GARCH-t (for the explicit price caveat comparison), conformal and the
# fast baselines run across all ~1249 non-price series. Relaunch loop resumes
# from the CSV so a hard worker crash can't lose progress.
#
#   bash benchmarks/nonprice_study.sh
set -u
cd "$(dirname "$0")/.."

export PYTHONPATH=src
export STUDY_CACHED_ONLY=1
export STUDY_EXCLUDE_PRICE=1               # general / non-price economic universe
export STUDY_MAX_QUALIFY=3000
export STUDY_N_CANDIDATES=3000
export STUDY_RESULTS=benchmarks/results_nonprice.csv
export STUDY_WORKERS=8
export BENCH_SF_MAX=900                     # AutoARIMA / AutoETS
export BENCH_SM_MAX=900                     # SARIMAX / ETS-sm
export BENCH_GARCH_MAX=3000                # GARCH-t across all non-price (for the caveat)
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1

LOG=benchmarks/nonprice_study.log
MAX_PASSES=40
echo "=== non-price study started $(date) ===" >> "$LOG"
rows() { [ -f "$STUDY_RESULTS" ] && wc -l < "$STUDY_RESULTS" | tr -d ' ' || echo 0; }

for pass in $(seq 1 $MAX_PASSES); do
  before=$(rows)
  echo "--- pass $pass start $(date) (rows: $before) ---" >> "$LOG"
  python benchmarks/study.py sota >> "$LOG" 2>&1
  status=$?
  after=$(rows)
  echo "--- pass $pass end $(date) status=$status rows: $before -> $after ---" >> "$LOG"
  if [ "$status" -eq 0 ] && [ "$after" -le "$before" ]; then
    echo "=== converged at pass $pass $(date) ===" >> "$LOG"; break
  fi
  sleep 5
done

echo "=== non-price study done $(date) ===" >> "$LOG"
STUDY_RESULTS=benchmarks/results_nonprice.csv python benchmarks/study.py sota summarize >> "$LOG" 2>&1 || true

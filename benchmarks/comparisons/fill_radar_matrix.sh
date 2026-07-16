#!/usr/bin/env bash
# Fill the challengers-radar matrix: run the registered opponents on every
# corpus arm, then regenerate the radar data. Built for a big machine; every
# arm study is crash-safe (resume by series+method), so rerun until clean.
#
# Needs:
#   - FRED_API_KEY in skaters/.env (or the environment)
#   - R with: install.packages(c("forecast","smooth","rugarch","bsts","NNS"))
#   - pip install statsforecast arch scipy
#     pip install git+https://github.com/valeman/csp-forecaster.git
#
#   PY=python bash benchmarks/comparisons/fill_radar_matrix.sh
#
# Knobs: OPPS (comma list of registry names), ARMS, STUDY_WORKERS.
# TBATS-R-ms (seasonal.periods 24,168) is meaningful on m4-hourly only and is
# added there automatically. Copy the results_*.csv back afterwards (they are
# gitignored) and rerun make_challenges_radar.py locally.
set -u
cd "$(dirname "$0")/../.."
PY=${PY:-python}
export PYTHONPATH=src
export STUDY_WORKERS=${STUDY_WORKERS:-$($PY -c 'import os; print(max((os.cpu_count() or 8)-2, 4))')}
OPPS=${OPPS:-"laplace,CSP,NNS-R,TBATS-R,R@25,statsforecast@25,GARCH-t,dantzig"}
ARMS=${ARMS:-"weekly monthly m4-hourly daily"}
export BENCH_TBATS_MS=${BENCH_TBATS_MS:-24,168}

run_arm () {
  local arm=$1 opps=$2 extra=""
  [ "$arm" = "daily" ] && extra="env CORPUS_LIMIT=700 STUDY_MAX_QUALIFY=500"
  [ "$arm" = "m4-hourly" ] && extra="env STUDY_MAX_QUALIFY=414"
  for attempt in 1 2 3; do
    STUDY_OPPS="$opps" $extra $PY benchmarks/comparisons/csp_arm_study.py "$arm" && return 0
    echo "[fill] $arm attempt $attempt exited nonzero; resuming" >&2
  done
  return 1
}

for arm in $ARMS; do
  opps="$OPPS"
  [ "$arm" = "m4-hourly" ] && opps="$OPPS,TBATS-R-ms"
  run_arm "$arm" "$opps" || echo "[fill] $arm gave up after 3 attempts" >&2
done
$PY benchmarks/comparisons/make_challenges_radar.py
echo "[fill] done — rsync benchmarks/comparisons/laplace-vs-csp/results_*.csv back and regenerate the radar"

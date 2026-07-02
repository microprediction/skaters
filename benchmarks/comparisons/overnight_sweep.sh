#!/bin/bash
# Long-running benchmark sweep with auto-resume. Appends to STUDY_RESULTS, which
# is resumable (per series+method), so a kill/restart never loses or re-scores
# work. Every knob below is overridable via the environment before launching.
#
# Requires the FRED cache in benchmarks/data/ (rsync it between machines) OR a
# FRED_API_KEY to fetch (drop STUDY_CACHED_ONLY then). R opponents need
# install.packages(c("forecast","smooth","rugarch","bsts")); absent ones drop out.
#
# Launch (macOS, prevent sleep):
#   caffeinate -is bash benchmarks/comparisons/overnight_sweep.sh &
# Launch (Linux):
#   nohup bash benchmarks/comparisons/overnight_sweep.sh &
set -u
cd "$(dirname "$0")/../.." || exit 1              # repo root

: "${STUDY_CACHED_ONLY:=1}"                        # 0 + FRED_API_KEY to fetch instead
: "${STUDY_MAX_QUALIFY:=2600}"
: "${BENCH_R_REFITS:=25}"                          # single cadence: nnetar/adam per-step cost doesn't amortize
: "${BENCH_SF_REFITS:=25}"
: "${BENCH_R_MAX:=2600}"; : "${BENCH_SF_MAX:=2600}"; : "${BENCH_GARCH_MAX:=2600}"
: "${BENCH_R_SKIP:=bsts-R}"                        # bsts refits MCMC every step — too slow for volume
: "${STUDY_ONLY:=laplace,R@25,statsforecast@25,CSP,GARCH-t}"
: "${STUDY_RESULTS:=benchmarks/comparisons/_shared_R25.csv}"
: "${OVERNIGHT_LOG:=benchmarks/comparisons/_overnight.log}"
: "${MAX_RESUMES:=200}"
export STUDY_CACHED_ONLY STUDY_MAX_QUALIFY BENCH_R_REFITS BENCH_SF_REFITS \
       BENCH_R_MAX BENCH_SF_MAX BENCH_GARCH_MAX BENCH_R_SKIP STUDY_ONLY STUDY_RESULTS

echo "[sweep] start $(date) -> $STUDY_RESULTS  opponents=$STUDY_ONLY" | tee -a "$OVERNIGHT_LOG"
n=0
until PYTHONPATH=src python benchmarks/study.py sota >>"$OVERNIGHT_LOG" 2>&1; do
  n=$((n + 1)); echo "[sweep] non-zero exit; resume $n at $(date)" | tee -a "$OVERNIGHT_LOG"
  [ "$n" -ge "$MAX_RESUMES" ] && { echo "[sweep] giving up after $n" | tee -a "$OVERNIGHT_LOG"; break; }
  sleep 15
done
echo "[sweep] finished $(date) after $n resumes" | tee -a "$OVERNIGHT_LOG"

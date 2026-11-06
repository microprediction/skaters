#!/usr/bin/env bash
# Night of 2026-11-03: laplace++ (#297) continued, chained.
#   1. wait for the e2 wrapper (weekly training + its full-half validation)
#   2. weekly: score the 1,000-series snapshot (run e2s1000), and a consolidation
#      pass at lr 1e-4 from the e2 checkpoint (snapshots every 500) -> run e3
#   3. monthly: wait for the 3,000->6,000-series continuation -> run e3
#   4. wait for the classical and TimeH2O fleets, then the pairs summary over the
#      roster and the site rebuild + push
# Every step resumes; re-running the script skips what is done.
#
#   caffeinate -i -s nohup benchmarks/run_learned_night2.sh > benchmarks/_learned_night2.log 2>&1 &
set -u
cd "$(dirname "$0")/.."
export PYTHONPATH=src:benchmarks
PY=".venv-kumo/bin/python"
CK=benchmarks/learned_ckpt
log() { echo "[night2] $(date '+%F %T') $*"; }
wait_for() { while pgrep -f "$1" >/dev/null; do sleep 60; done; }

log "waiting for the e2 wrapper"
wait_for run_learned_overnight.sh
log "e2 wrapper done"

# 2a. the weekly 1,000-series snapshot on the full validation half
if [ -f $CK/weekly_k1_e1s1000.pt ]; then
  log "scoring weekly snapshot s1000"
  LEARNED_CKPT=$CK/weekly_k1_e1s1000.pt LV_CORPUS=weekly LV_MAX=0 LV_NSHARD=6 LV_THREADS=2 LV_RUN=e2s1000 \
    benchmarks/run_learned_valid.sh >> benchmarks/_learned_valid_fleet.log 2>&1 &
  SNAP_PID=$!
fi

# 2b. weekly consolidation pass from the e2 checkpoint
[ -f $CK/weekly_k1_e2final.pt ] || cp $CK/weekly_k1.pt $CK/weekly_k1_e2final.pt
resume=$CK/weekly_k1_e3.pt; [ -f "$resume" ] || resume=$CK/weekly_k1.pt
log "weekly consolidation pass (lr 1e-4) from $resume"
OMP_NUM_THREADS=6 MKL_NUM_THREADS=6 LT_CORPUS=weekly LT_MAX=1500 LT_K=1 LT_EPOCHS=2 LT_WINDOW=64 LT_LR=1e-4 \
LT_PI=0.25 LT_CKPT_EVERY=25 LT_SNAP_EVERY=500 LT_RESUME=$resume LT_OUT=$CK/weekly_k1_e3.pt \
  "$PY" -u benchmarks/learned_train.py > benchmarks/_learned_train_weekly_e3.log 2>&1
log "weekly consolidation done; scoring run e3 on the full weekly half"
LEARNED_CKPT=$CK/weekly_k1_e3.pt LV_CORPUS=weekly LV_MAX=0 LV_NSHARD=6 LV_THREADS=2 LV_RUN=e3 \
  benchmarks/run_learned_valid.sh >> benchmarks/_learned_valid_fleet.log 2>&1
[ -n "${SNAP_PID:-}" ] && wait "$SNAP_PID"

# 3. monthly continuation (started separately) -> run e3
log "waiting for the monthly continuation"
while ! grep -q "epoch 1:" benchmarks/_learned_train_monthly_e3.log 2>/dev/null; do sleep 60; done
if [ -f $CK/monthly_k1_e3.pt ]; then
  log "scoring monthly run e3"
  LEARNED_CKPT=$CK/monthly_k1_e3.pt LV_CORPUS=monthly LV_MAX=5600 LV_NSHARD=8 LV_THREADS=2 LV_RUN=e3 \
    benchmarks/run_learned_valid.sh >> benchmarks/_learned_valid_fleet.log 2>&1
fi

# 4. classical and TimeH2O, then the pairs and the site
log "waiting for the classical and TimeH2O fleets"
wait_for run_classical.sh
wait_for run_timeh2o_study.sh
M="laplace,learned(e3),learned(e2),learned(e2s1000),learned(e2s500),Timestral-209M(q21),t0-gamma(q21),TimesFM3(wide),TimesFM(wide),TiRex(wide),Chronos(wide),TimeH2O-v1(wide),AutoARIMA,AutoETS,AutoTheta,GARCH-t"
log "pairs summary over the roster"
CANON_PER_SERIES=1 CANON_PER_SERIES_MODELS="$M" CANON_PAIRS="$M" \
  .venv-gifteval/bin/python -u benchmarks/summarize_canonical.py > benchmarks/_summ_pairs.log 2>&1
log "site rebuild"
( cd ../foundationalprediction && SKATERS_DIR=../skaters python3 build.py \
  && git add -A && git commit -q -m "Nightly rebuild: laplace++ runs, classical models, TimeH2O" \
  && git push -q origin main ) >> benchmarks/_learned_night2.log 2>&1
log "done"

#!/usr/bin/env bash
# Launch the multi-horizon study (k = 1,2,4,8,16), unattended and sleep-proof.
# Runs alongside or after the k=1 week study; fully isolated (own preds_h tree,
# own STOP, own summaries). Heavy: it is the roster x corpora x |horizons|, so
# prefer running it once the k=1 study has finished, or lower WEEK_PAR.
#
#   benchmarks/launch_horizon_study.sh
#   WEEK_H_LIST="1 2 4" WEEK_MODELS=laplace,TiRex,TiRex&lap benchmarks/launch_horizon_study.sh
#
# Stop cleanly:  touch benchmarks/preds_h/STOP
# Watch:         tail -f benchmarks/_horizon.log
# Resume:        re-run this script (run_arm skips covered cells per horizon).
set -u
cd "$(dirname "$0")/.."

: "${WEEK_MODELS:=laplace,Chronos,TiRex,TimesFM,Chronos&lap,TiRex&lap,TimesFM&lap}"
: "${WEEK_H_LIST:=1 2 4 8 16}"
: "${WEEK_CORPORA:=daily weekly monthly m4-hourly}"
: "${WEEK_CTX:=128}"
: "${WEEK_TEST:=64}"
: "${WEEK_DEVICE:=cpu}"
: "${WEEK_PAR:=6}"
: "${WEEK_DAYS:=7}"
: "${WEEK_BATCH:=120}"
export WEEK_MODELS WEEK_H_LIST WEEK_CORPORA WEEK_CTX WEEK_TEST WEEK_DEVICE \
       WEEK_PAR WEEK_DAYS WEEK_BATCH

mkdir -p benchmarks/preds_h
rm -f benchmarks/preds_h/STOP
echo "[launch] horizons=$WEEK_H_LIST roster=$WEEK_MODELS par=$WEEK_PAR days=$WEEK_DAYS"
nohup .venv-sota/bin/python benchmarks/horizon_study.py \
      > benchmarks/_horizon.log 2>&1 &
PID=$!
nohup caffeinate -i -w $PID > /dev/null 2>&1 &   # hold sleep until the driver exits
echo "[launch] horizon_study pid $PID ; log: benchmarks/_horizon.log"

#!/usr/bin/env bash
# Launch the week-long round-robin study, unattended, sleep-proof.
#
#   benchmarks/launch_week_study.sh            # 7 days, default roster
#   WEEK_MODELS=laplace,TiRex ... launch_week_study.sh   # override roster
#
# Stop cleanly:  touch benchmarks/preds/STOP
# Watch:         tail -f benchmarks/_week.log ; python -m ... /workflows
# Resume:        just re-run this script — run_arm skips covered cells.
#
# TabPFN joins automatically if TABPFN_TOKEN is exported (one-time license
# acceptance at ux.priorlabs.ai). Attribution carried in the study writeup:
# "Built with PriorLabs-TabPFN"; TiRex under the NXAI Community License;
# flowstate ibm-research research checkpoint (arXiv:2508.05287), research use.
set -u
cd "$(dirname "$0")/.."

: "${WEEK_MODELS:=laplace,Sundial,TiRex,flowstate,Chronos,TimesFM}"
: "${WEEK_CORPORA:=daily weekly monthly m4-hourly}"
: "${WEEK_CTX:=128}"
: "${WEEK_TEST:=64}"
: "${WEEK_DEVICE:=cpu}"
: "${WEEK_PAR:=6}"
: "${WEEK_DAYS:=7}"
: "${WEEK_BATCH_A:=300}"
: "${WEEK_BATCH_C:=40}"
export WEEK_MODELS WEEK_CORPORA WEEK_CTX WEEK_TEST WEEK_DEVICE WEEK_PAR WEEK_DAYS \
       WEEK_BATCH_A WEEK_BATCH_C

rm -f benchmarks/preds/STOP
echo "[launch] roster=$WEEK_MODELS device=$WEEK_DEVICE par=$WEEK_PAR days=$WEEK_DAYS"
caffeinate -i -w $$ &                    # keep the Mac awake while this shell lives
nohup .venv-sota/bin/python benchmarks/week_study.py \
      > benchmarks/_week.log 2>&1 &
echo "[launch] week_study pid $! ; log: benchmarks/_week.log"

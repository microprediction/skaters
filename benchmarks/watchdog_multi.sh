#!/usr/bin/env bash
# Relaunch the MULTI-HORIZON week study if its driver died (crash, reboot, power
# cut). Runs from cron (periodic + @reboot). Stands down if preds_multi/STOP
# exists. Remove with:  crontab -l | grep -v watchdog_multi | crontab -
set -u
cd "$(dirname "$0")/.."

[ -f benchmarks/preds_multi/STOP ] && exit 0
pgrep -f "week_study.py" > /dev/null && exit 0   # already running; don't double-launch

echo "[watchdog-multi] $(date) driver down; relaunching (par=6, horizons 1 2 3 5 8 13)" \
  >> benchmarks/_watchdog_multi.log
WEEK_HS="1 2 3 5 8 13" WEEK_PREDS=preds_multi WEEK_DAYS=3650 \
  WEEK_COMMIT_EVERY=1000000000 WEEK_DEVICE=cpu WEEK_PAR=6 \
  nohup .venv-sota/bin/python benchmarks/week_study.py >> benchmarks/_week_multi.log 2>&1 &
PID=$!
nohup caffeinate -i -w "$PID" > /dev/null 2>&1 &
echo "[watchdog-multi] relaunched pid $PID" >> benchmarks/_watchdog_multi.log

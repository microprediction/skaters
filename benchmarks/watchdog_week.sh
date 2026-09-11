#!/usr/bin/env bash
# Relaunch the week study if its driver died (crash, reboot, power cut).
# Installed in cron; stands down after WEEK_END or if preds/STOP exists.
# Remove with: crontab -l | grep -v watchdog_week | crontab -
set -u
cd "$(dirname "$0")/.."

WEEK_END=1785356400   # 2026-07-29 16:20 ET: the driver's own 7-day clock ends 16:13
ROSTER='laplace,Sundial,TiRex,flowstate,Chronos,TimesFM,TimesFM@lap,TiRex@lap,Chronos@lap,TimesFM&lap,TiRex&lap,Chronos&lap'

[ -f benchmarks/preds/STOP ] && exit 0
[ "$(date +%s)" -ge "$WEEK_END" ] && exit 0
pgrep -f "week_study.py" > /dev/null && exit 0

# remaining budget in days (fractional), so a relaunch never runs past WEEK_END
DAYS=$(awk -v e="$WEEK_END" -v n="$(date +%s)" 'BEGIN{printf "%.2f", (e-n)/86400}')
echo "[watchdog] $(date) driver down; relaunching with $DAYS days left" \
  >> benchmarks/_watchdog.log
WEEK_MODELS="$ROSTER" WEEK_DAYS="$DAYS" benchmarks/launch_week_study.sh \
  >> benchmarks/_watchdog.log 2>&1

#!/usr/bin/env bash
# Overnight training of the learned model (#297): one trainer per corpus in
# parallel (weekly, monthly, daily economic series, train half of the family
# split, k=1), each resumable from its last checkpoint, then the validation
# fleet for each corpus (run_learned_valid.sh: the mixture and the trained
# expert on the validation half, paired against laplace in the store), then
# the canonical summaries. Kept awake with caffeinate. Re-running the script
# resumes each trainer where it stopped and skips validation rows already in
# the store.
#
#   caffeinate -i -s nohup benchmarks/run_learned_overnight.sh > benchmarks/_learned_overnight.log 2>&1 &
#
# Knobs: ON_CORPORA (default "weekly monthly daily"), ON_MAX (train series per
# corpus, default 1500), ON_EPOCHS (default 1), ON_VALID_MAX (default 400; 0 =
# the whole validation half), ON_THREADS (torch threads per trainer, default
# 4), ON_PI (laplace's prior share, default 0.5), ON_TAG (run tag for the
# validation arms). Any of MAX, EPOCHS, VALID_MAX takes a per-corpus override
# ON_<name>_<corpus>, e.g. ON_MAX_monthly=3000; so does LR (ON_LR, ON_LR_<corpus>).
set -u
cd "$(dirname "$0")/.."
export PYTHONPATH=src:benchmarks
PY=".venv-kumo/bin/python"
CORPORA=${ON_CORPORA:-"weekly monthly daily"}
MAX=${ON_MAX:-1500}
EPOCHS=${ON_EPOCHS:-1}
VALID_MAX=${ON_VALID_MAX:-400}
THREADS=${ON_THREADS:-4}
PI=${ON_PI:-0.5}            # laplace's prior share in the mixture (the bound is h*log(1/PI))
RUN=${ON_TAG:-}             # names this run's validation arms: learned(<tag>) / learned-expert(<tag>)
mkdir -p benchmarks/learned_ckpt

over() {   # over <name> <corpus> <default>: per-corpus override ON_<name>_<corpus>
  local v="ON_$1_$2"; echo "${!v:-$3}"
}

train_one() {   # corpus
  local c=$1 ck="benchmarks/learned_ckpt/${c}_k1.pt" resume=""
  [ -f "$ck" ] && resume="$ck"
  OMP_NUM_THREADS=$THREADS MKL_NUM_THREADS=$THREADS \
  LT_CORPUS=$c LT_MAX=$(over MAX "$c" "$MAX") LT_K=1 LT_EPOCHS=$(over EPOCHS "$c" "$EPOCHS") \
  LT_WINDOW=64 LT_LR=$(over LR "$c" "${ON_LR:-1e-3}") LT_PI=$PI \
  LT_CKPT_EVERY=25 LT_SNAP_EVERY=${ON_SNAP:-0} LT_RESUME="$resume" LT_OUT="$ck" \
    "$PY" -u benchmarks/learned_train.py > "benchmarks/_learned_train_${c}_k1.log" 2>&1
}

echo "[overnight] $(date '+%F %T') training: $CORPORA (max $MAX series each, $EPOCHS epoch)"
pids=(); names=()
for c in $CORPORA; do
  train_one "$c" & pids+=($!); names+=("$c")
done
status=0
for i in "${!pids[@]}"; do
  if wait "${pids[$i]}"; then echo "[overnight] $(date '+%T') ${names[$i]} trained"
  else echo "[overnight] $(date '+%T') ${names[$i]} trainer FAILED" >&2; status=1; fi
done

for c in $CORPORA; do
  ck="benchmarks/learned_ckpt/${c}_k1.pt"
  [ -f "$ck" ] || { echo "[overnight] no checkpoint for $c, skipping validation" >&2; continue; }
  vmax=$(over VALID_MAX "$c" "$VALID_MAX")
  echo "[overnight] $(date '+%T') validating $c on ${vmax:-all} series (run tag '${RUN}')"
  LEARNED_CKPT="$ck" LV_CORPUS=$c LV_MAX=$vmax LV_NSHARD=8 LV_THREADS=2 LV_RUN="$RUN" \
    benchmarks/run_learned_valid.sh >> benchmarks/_learned_valid_fleet.log 2>&1 || status=1
done

echo "[overnight] $(date '+%T') summarizing"
"$PY" benchmarks/summarize_canonical.py > benchmarks/_learned_summarize.log 2>&1 || status=1
"$PY" - <<'EOF'
import csv
vs = list(csv.DictReader(open("benchmarks/canonical_summary_vs_laplace.csv")))
print(f"{'arm':16s} {'stratum':14s} {'n':>5s} {'W':>5s} {'D':>5s} {'L':>5s} {'medLL':>7s} {'q25':>7s} {'q75':>7s} {'crpsR':>6s}")
for r in vs:
    if r["model"].startswith(("learned", "learned-expert")):
        print(f"{r['model']:16s} {r['study']:14s} {r['n_series']:>5s} {r['win']:>5s} {r['draw']:>5s} {r['loss']:>5s} "
              f"{float(r['med_dLL']):7.3f} {float(r['q25_dLL']):7.3f} {float(r['q75_dLL']):7.3f} {float(r['med_crps_ratio']):6.3f}")
EOF
echo "[overnight] $(date '+%F %T') done (status $status)"
exit $status

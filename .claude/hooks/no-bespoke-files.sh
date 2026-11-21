#!/usr/bin/env bash
# PreToolUse/Write guard: refuse NEW code files that would become a bespoke
# study, simulation, scorer or results pipeline.
#
# The user has said this more than twenty times: results come from ONE pipeline
# (week_study -> run_arm -> summarize_canonical -> site build.py). A one-off
# script "just to prototype" is exactly the thing that keeps happening, so a new
# code file is denied when it lands somewhere a study would live, or its name or
# content says it is one. Editing an EXISTING file is never blocked here.
# If the pipeline cannot do something: stop and tell the user what is missing.
set -uo pipefail

input="$(cat)"
path="$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null)" || exit 0
[ -n "$path" ] || exit 0
[ -e "$path" ] && exit 0                      # existing file: an edit, not a new pipeline

case "$path" in
  *.py|*.sh|*.R|*.r|*.jl|*.ipynb|*.js|*.mjs|*.ts) ;;
  *) exit 0 ;;
esac
case "$path" in
  */.claude/hooks/*|*/tests/*|*/test_*.py) exit 0 ;;    # guards and unit tests are fine
esac

content="$(printf '%s' "$input" | jq -r '.tool_input.content // empty' 2>/dev/null)"
base="$(basename "$path")"
why=""

# 1. Location: scratch/tmp code, or a new file inside a benchmark tree.
case "$path" in
  /tmp/*|/private/tmp/*|*/scratchpad/*) why="a new code file in a scratch/tmp directory" ;;
  */benchmarks/*|*/surrogate/*|*/bench/*) why="a new code file inside a benchmark tree" ;;
esac
# 2. Name says study/simulation/scoring.
if [ -z "$why" ] && printf '%s' "$base" | grep -qiE 'study|score|scoring|bench|eval|sim|prototype|proto|pilot|leaderboard|backtest|weights|horserace|runner|launch'; then
  why="its name ($base) says it is a study, scorer or simulation"
fi
# 3. Content does simulation or reads/writes results.
if [ -z "$why" ] && printf '%s' "$content" | grep -qE 'default_rng|np\.random|random\.seed|preds/|preds_|canonical_[a-z_]*\.csv|roll_dist_scores|dm_contest|logpdf|crps|value iteration|simulate'; then
  why="its content simulates or reads/derives forecast results"
fi
[ -n "$why" ] || exit 0

reason="Blocked: $why.

NO BESPOKE STUDIES, SIMULATIONS, PROTOTYPES OR RESULTS PIPELINES. Not in the
scratchpad, not 'just to check'. The user has said this twenty-plus times.

Use the pipeline:  week_study.py -> run_arm.py -> summarize_canonical.py
(CANON_* env options, CANON_PER_SERIES=1 for re-aggregation) -> site build.py.
New model = arm_adapters.py REGISTRY entry. Extend an EXISTING file if an
option is missing.

If the pipeline cannot do it: STOP and tell the user what is missing. Do not
work around this guard."
jq -n --arg r "$reason" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
exit 0

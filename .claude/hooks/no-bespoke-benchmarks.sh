#!/usr/bin/env bash
# PreToolUse/Bash guard: refuse ad-hoc scoring runs.
#
# This repository has one benchmark pipeline. Results that are not produced by
# it are not comparable with results that are, and a bespoke scorer is free to
# drift from the definitions the rest of the repo uses. Every time a study has
# been written as a one-off script or a heredoc it has had to be rerun.
#
# Blocks a command that EXECUTES python which imports the scoring helpers or
# writes a results CSV, unless it invokes a sanctioned entry point. Reading the
# source (grep, sed, cat) never trips it, because it runs no python.
set -uo pipefail

cmd="$(jq -r '.tool_input.command // empty' 2>/dev/null)" || exit 0
[ -n "$cmd" ] || exit 0

# Never inspect commands whose job is text, not execution. A git commit message
# or a doc that quotes the pipeline would otherwise match its own description.
# First line only: a heredoc body would otherwise contribute its own words.
lead="$(printf '%s' "$cmd" | head -1 | sed -E 's/^[[:space:]]*//; s/^([A-Za-z_][A-Za-z0-9_]*=[^[:space:]]*[[:space:]]+)*//; s/^(cd[[:space:]]+[^&;|]*[[:space:]]*(&&|;)[[:space:]]*)*//' | awk 'NR==1{print $1}')"
case "$(basename "${lead:-x}")" in
  git|jq|echo|cat|printf|sed|awk|grep|rg|less|head|tail|wc|diff|nano|vim|code) exit 0 ;;
esac

# Only ever interested in commands that actually run python.
printf '%s' "$cmd" | grep -qE '(^|[^[:alnum:]_/])(python3?|[A-Za-z0-9_./-]*/bin/python3?)([[:space:]]|$)' || exit 0

# Sanctioned entry points: the pipeline, and the paper's own constant scripts.
if printf '%s' "$cmd" | grep -qE 'benchmarks/(run_arm|study|summarize_canonical|horserace_summary|bench|foundation_study|nozzle_study|refresh_figures)\.py|papers/[A-Za-z0-9_-]+/(constants|verify_paper)\.py|-m[[:space:]]+pytest|tests/'; then
  exit 0
fi

# Signals of a scoring run, as CODE rather than prose: an import statement, a
# call to the shared scorer, or a redirect into a results file. Prose that names
# these modules ("importing bench_core") is documentation and must pass.
if printf '%s' "$cmd" | grep -qE '(^|[^[:alnum:]_])(import[[:space:]]+(bench_core|opponents|arm_adapters|horserace_summary)|from[[:space:]]+(bench_core|opponents|arm_adapters|horserace_summary)[[:space:]]+import|roll_dist_scores[[:space:]]*\(|score_dist[[:space:]]*\(|_statsforecast_predict[[:space:]]*\()' \
   || printf '%s' "$cmd" | grep -qE '>[[:space:]]*[^[:space:]|]*results_[A-Za-z0-9_]*\.csv'; then
  reason='Blocked: this looks like a benchmark or scoring run outside the canonical pipeline.

This repo has one pipeline and results from anywhere else are not comparable:
  score an arm   PYTHONPATH=src:benchmarks ARM_METHODS=<Name> ARM_CORPUS=<corpus> \
PRED_OUT=benchmarks/preds/<Name>__<corpus>.csv python benchmarks/run_arm.py
  register first benchmarks/arm_adapters.py REGISTRY (sandwich variants come free)
  derive         python benchmarks/summarize_canonical.py
  classic arms   benchmarks/horserace_summary.py owns the continuity and family filters

If an arm is slow, give it a series budget (ARM_MAX) and report N. Do not write a
one-off scorer, and do not re-derive win rates in a heredoc.

If this command is genuinely not a scoring run, run it yourself with a leading !
or add it to permissions.allow.'
  jq -n --arg r "$reason" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
  exit 0
fi
exit 0

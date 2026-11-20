#!/usr/bin/env bash
# Self-test for the two no-bespoke guards: bash .claude/hooks/test_guards.sh
cd "$(dirname "$0")"
S=/private/tmp/claude-501/x/scratchpad
fail=0
t(){ out=$(printf '%s' "$2" | ./$1 | jq -r ".hookSpecificOutput.permissionDecision"); out=${out:-allow}
     [ "$out" = "$3" ] && r=ok || { r=FAIL; fail=1; }
     printf '%-4s %-6s %s\n' "$r" "$out" "$4"; }
t no-bespoke-files.sh "{\"tool_input\":{\"file_path\":\"$S/linear_weights.py\",\"content\":\"import numpy\"}}" deny "Write scratchpad linear_weights.py"
t no-bespoke-files.sh '{"tool_input":{"file_path":"/Users/petercotton/github/skaters-meme/benchmarks/new_thing.py","content":"x=1"}}' deny "Write new benchmarks/new_thing.py"
t no-bespoke-files.sh '{"tool_input":{"file_path":"/Users/petercotton/github/foundationalprediction/lead_sim.py","content":"x=1"}}' deny "Write new lead_sim.py"
t no-bespoke-files.sh '{"tool_input":{"file_path":"/Users/petercotton/github/foundationalprediction/x.py","content":"rng=np.random.default_rng(0)"}}' deny "Write new file using default_rng"
t no-bespoke-files.sh '{"tool_input":{"file_path":"/Users/petercotton/github/skaters-meme/benchmarks/summarize_canonical.py","content":"..."}}' allow "Write EXISTING summarize_canonical.py"
t no-bespoke-files.sh "{\"tool_input\":{\"file_path\":\"$S/page.html\",\"content\":\"<p>\"}}" allow "Write scratchpad html"
t no-bespoke-benchmarks.sh "{\"tool_input\":{\"command\":\"python3 $S/linear_weights.py\"}}" deny "run scratchpad script"
t no-bespoke-benchmarks.sh "{\"tool_input\":{\"command\":\"cat > $S/a.py <<'EOF'\\nx=1\\nEOF\"}}" deny "cat > scratchpad .py"
t no-bespoke-benchmarks.sh '{"tool_input":{"command":"python3 - <<EOF\nimport numpy as np\nrng=np.random.default_rng(0)\nEOF"}}' deny "inline simulation heredoc"
t no-bespoke-benchmarks.sh '{"tool_input":{"command":"python3 - <<EOF\nimport csv\nfor r in csv.DictReader(open(\"benchmarks/canonical_per_series.csv\")): pass\nEOF"}}' deny "inline re-derive from canonical csv"
t no-bespoke-benchmarks.sh '{"tool_input":{"command":"cd ~/github/skaters-meme && CANON_PREDS=benchmarks/preds_leads/h1 .venv-sota/bin/python benchmarks/summarize_canonical.py"}}' allow "summarize_canonical"
t no-bespoke-benchmarks.sh '{"tool_input":{"command":"cd ~/github/foundationalprediction && python3 build.py"}}' allow "site build.py"
t no-bespoke-benchmarks.sh '{"tool_input":{"command":"python3 - <<EOF\nimport json\nprint(1)\nEOF"}}' allow "harmless json heredoc"
exit $fail

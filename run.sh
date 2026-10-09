#!/usr/bin/env bash
# usage: bash run.sh <A|B|C|D> <rep>
# Runs one migration attempt on a fresh copy of base/ outside any git repo.
set -euo pipefail
COND="$1"; REP="$2"
LAB="$(cd "$(dirname "$0")" && pwd)"
RUNS="${RUNS_DIR:?set RUNS_DIR to a folder outside any repository}"
ID="${COND}${REP}"
DIR="$RUNS/$ID"
EVID="$LAB/../evidence/runs/$ID"
rm -rf "$DIR"; mkdir -p "$DIR" "$EVID"
cp -r "$LAB/base/." "$DIR/"
cp "$LAB/targets.txt" "$LAB/TASK.md" "$DIR/"

SOLO="Do all of the work yourself in this session."
ORCH="You are the orchestrator. First write _migration/SPEC.md with the conventions every file must follow. Then use the migrator subagent for all edits to the nine target files (one file or a small group per call; you may run several). Do not edit the nine target files yourself. When the workers finish, review their changes against SPEC.md and send fixes back to a migrator if needed. Then write the report."

agents_json() {
  cat <<EOF
{"migrator":{"description":"Edits the assigned script files to follow _migration/SPEC.md.","prompt":"You migrate hardcoded machine paths in the files you are assigned, following _migration/SPEC.md exactly. Read SPEC.md and TASK.md first. Edit only the files you are assigned. You cannot run code. Reply with a few lines on what you changed and anything that did not fit the spec.","model":"$1","tools":["Read","Edit","Grep","Glob"]}}
EOF
}

COMMON=(-p --output-format stream-json --verbose --permission-mode acceptEdits
        --strict-mcp-config --max-budget-usd 5)
case "$COND" in
  A) ARGS=(--model claude-opus-5-5 --allowedTools Read Edit Write Grep Glob --disallowedTools Agent Task Bash Skill WebFetch WebSearch); FLOW="$SOLO";;
  C) ARGS=(--model claude-sonnet-5-5 --allowedTools Read Edit Write Grep Glob --disallowedTools Agent Task Bash Skill WebFetch WebSearch); FLOW="$SOLO";;
  B) ARGS=(--model claude-opus-5-5 --agents "$(agents_json sonnet)" --allowedTools Read Edit Write Grep Glob Agent --disallowedTools Bash Skill WebFetch WebSearch); FLOW="$ORCH";;
  D) ARGS=(--model claude-opus-5-5 --agents "$(agents_json haiku)" --allowedTools Read Edit Write Grep Glob Agent --disallowedTools Bash Skill WebFetch WebSearch); FLOW="$ORCH";;
  E) ARGS=(--model claude-opus-5-5 --agents "$(agents_json claude-sonnet-5-5)" --allowedTools Read Edit Write Grep Glob Agent --disallowedTools Bash Skill WebFetch WebSearch); FLOW="$ORCH";;
  F) ARGS=(--model claude-opus-5-5 --agents "$(agents_json claude-haiku-5-5)" --allowedTools Read Edit Write Grep Glob Agent --disallowedTools Bash Skill WebFetch WebSearch); FLOW="$ORCH";;
  *) echo "unknown condition $COND"; exit 2;;
esac

PROMPT="Read TASK.md in the current directory and complete it. $FLOW"
START=$(date +%s)
( cd "$DIR" && printf '%s' "$PROMPT" | claude "${COMMON[@]}" "${ARGS[@]}" ) > "$EVID/stream.jsonl" 2> "$EVID/stderr.txt" || echo "claude exit $?" >> "$EVID/stderr.txt"
END=$(date +%s)
echo "{\"id\":\"$ID\",\"cond\":\"$COND\",\"rep\":$REP,\"wall_s\":$((END-START))}" > "$EVID/meta.json"

# keep the outputs, not the whole tree
mkdir -p "$EVID/out"
while read -r f; do mkdir -p "$EVID/out/$(dirname "$f")"; cp "$DIR/$f" "$EVID/out/$f" 2>/dev/null || true; done < "$LAB/targets.txt"
[ -d "$DIR/_migration" ] && cp -r "$DIR/_migration" "$EVID/out/"
PYTHONIOENCODING=utf-8 python "$LAB/gate.py" "$DIR" --json "$EVID/gate.json" > "$EVID/gate.txt" || true
tail -1 "$EVID/gate.txt"

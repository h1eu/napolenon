#!/usr/bin/env bash
# Hook PostToolUse (Edit|Write): format rồi analyze file vừa sửa theo .claude/instructions/toolchain.json.
# Output: JSON hookSpecificOutput.additionalContext (stdout exit-0 thường không tới Claude; additionalContext thì có).
# Luôn exit 0. Không có toolchain.json hoặc đuôi lạ → im lặng.
set -u
ROOT="${CLAUDE_PROJECT_DIR:-$(pwd)}"
TC="$ROOT/.claude/instructions/toolchain.json"
[ -f "$TC" ] || exit 0

INPUT="$(cat 2>/dev/null || true)"
FILE="$(printf '%s' "$INPUT" | python3 -c 'import json,sys
try:
    d=json.load(sys.stdin); print(d.get("tool_input",{}).get("file_path",""))
except Exception: print("")' 2>/dev/null)"
[ -n "$FILE" ] || exit 0

EXT=".${FILE##*.}"
CMDS="$(python3 - "$TC" "$EXT" "$FILE" <<'EOF' 2>/dev/null
import json, shlex, sys
tc, ext, f = sys.argv[1:4]
by = json.load(open(tc)).get("by_ext", {}).get(ext)
if by:
    for k in ("format", "analyze"):
        if by.get(k):
            print(by[k].replace("{file}", shlex.quote(f)))
EOF
)"
[ -n "$CMDS" ] || exit 0

ALL=""
while IFS= read -r cmd; do
  [ -n "$cmd" ] || continue
  OUT="$(cd "$ROOT" && bash -c "$cmd" </dev/null 2>&1)"; RC=$?
  [ -n "$OUT" ] && ALL="$ALL$OUT"$'\n'
  [ "$RC" -ne 0 ] && ALL="$ALL""napoleon: lệnh thoát $RC: $cmd"$'\n'
done <<< "$CMDS"

[ -n "$ALL" ] || exit 0
printf '%s' "$ALL" | python3 -c 'import json,sys
print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": sys.stdin.read().rstrip()}}, ensure_ascii=False))' 2>/dev/null
exit 0

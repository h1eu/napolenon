#!/usr/bin/env bash
# Test 3 hook script + settings.json
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TOOLS="$ROOT/.claude/tools"
FAIL=0
fail() { FAIL=$((FAIL+1)); echo "  FAIL: $1"; }
tmp() { mktemp -d 2>/dev/null || mktemp -d -t nap; }
hook_in() { printf '{"tool_name":"Edit","tool_input":{"file_path":"%s"}}' "$1"; }

echo "test_check_no_toolchain_silent"
T=$(tmp)
OUT=$(hook_in "$T/a.dart" | CLAUDE_PROJECT_DIR="$T" bash "$TOOLS/check.sh"); RC=$?
[ "$RC" -eq 0 ] || fail "exit $RC"
[ -z "$OUT" ] || fail "stdout phải rỗng, nhận: $OUT"

# stdout của check.sh phải là JSON hookSpecificOutput.additionalContext → lấy nội dung text ra
ctx() { python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["hookSpecificOutput"]["additionalContext"]); assert d["hookSpecificOutput"]["hookEventName"]=="PostToolUse"' 2>/dev/null; }

echo "test_check_runs_format_and_analyze_as_json"
T=$(tmp); mkdir -p "$T/.claude/instructions"; cp "$ROOT/tests/fixtures/toolchain.json" "$T/.claude/instructions/"
touch "$T/a.dart"
OUT=$(hook_in "$T/a.dart" | CLAUDE_PROJECT_DIR="$T" bash "$TOOLS/check.sh"); RC=$?
[ "$RC" -eq 0 ] || fail "exit $RC"
CTX=$(echo "$OUT" | ctx) || fail "stdout không phải JSON additionalContext: $OUT"
echo "$CTX" | grep -q "FMT $T/a.dart" || fail "không chạy format: $CTX"
echo "$CTX" | grep -q "ANA $T/a.dart" || fail "không chạy analyze: $CTX"

echo "test_check_format_fails_still_exit0"
touch "$T/B.kt"
OUT=$(hook_in "$T/B.kt" | CLAUDE_PROJECT_DIR="$T" bash "$TOOLS/check.sh"); RC=$?
[ "$RC" -eq 0 ] || fail "exit $RC"
echo "$OUT" | ctx | grep -q "LOI" || fail "không in lỗi format: $OUT"

echo "test_check_path_with_spaces"
mkdir -p "$T/my dir"; touch "$T/my dir/a b.dart"
OUT=$(hook_in "$T/my dir/a b.dart" | CLAUDE_PROJECT_DIR="$T" bash "$TOOLS/check.sh")
echo "$OUT" | ctx | grep -qF "FMT $T/my dir/a b.dart" || fail "đường dẫn có khoảng trắng bị vỡ: $OUT"

echo "test_check_stdin_reading_formatter"
T2=$(tmp); mkdir -p "$T2/.claude/instructions"
echo '{"by_ext":{".dart":{"format":"cat >/dev/null; echo FMT","analyze":"echo ANA"}}}' > "$T2/.claude/instructions/toolchain.json"
OUT=$(hook_in "$T2/a.dart" | CLAUDE_PROJECT_DIR="$T2" bash "$TOOLS/check.sh")
echo "$OUT" | ctx | grep -q "ANA" || fail "formatter đọc stdin nuốt lệnh sau: $OUT"

echo "test_check_unknown_ext_silent"
OUT=$(hook_in "$T/x.xyz" | CLAUDE_PROJECT_DIR="$T" bash "$TOOLS/check.sh")
[ -z "$OUT" ] || fail "stdout phải rỗng: $OUT"

echo "test_sync_without_codegraph"
T=$(tmp); (cd "$T" && git init -q && echo x > f && git add f && git -c user.email=a@b -c user.name=t commit -qm i && echo y > f)
OUT=$(cd "$T" && PATH=/usr/bin:/bin CLAUDE_PROJECT_DIR="$T" bash "$TOOLS/codegraph-sync.sh"); RC=$?
[ "$RC" -eq 0 ] || fail "exit $RC"
[ -z "$OUT" ] || fail "stdout phải rỗng: $OUT"

echo "test_session_start_without_state"
T=$(tmp)
OUT=$(CLAUDE_PROJECT_DIR="$T" bash "$TOOLS/session-start.sh"); RC=$?
[ "$RC" -eq 0 ] || fail "exit $RC"
[ -z "$OUT" ] || fail "stdout phải rỗng: $OUT"

echo "test_session_start_with_state"
T=$(tmp); mkdir -p "$T/.claude"; cp -R "$TOOLS" "$T/.claude/tools"
python3 "$TOOLS/state.py" --root "$T" init >/dev/null
python3 "$TOOLS/state.py" --root "$T" feature add login >/dev/null
OUT=$(CLAUDE_PROJECT_DIR="$T" bash "$TOOLS/session-start.sh"); RC=$?
[ "$RC" -eq 0 ] || fail "exit $RC"
echo "$OUT" | grep -q "login" || fail "không in feature: $OUT"
[ "$(echo "$OUT" | wc -l | tr -d ' ')" -le 5 ] || fail "quá 5 dòng"

# ---- guard.py (PreToolUse: chặn ghi file nguồn bằng Bash, chặn sửa tay state.json) ----
G="$TOOLS/guard.py"
T=$(tmp); mkdir -p "$T/lib"
json_cmd() { python3 -c 'import json,sys; print(json.dumps({"command": sys.argv[1]}))' "$1"; }
pre() { printf '{"tool_name":"%s","tool_input":%s}' "$1" "$2" | CLAUDE_PROJECT_DIR="$T" python3 "$G"; }
decision() { python3 -c 'import json,sys
d = sys.stdin.read().strip()
print(json.loads(d)["hookSpecificOutput"]["permissionDecision"] if d else "allow")' 2>/dev/null; }

echo "test_guard_blocks_bash_write_to_source"
while IFS= read -r CMD; do
  [ -n "$CMD" ] || continue
  OUT=$(pre Bash "$(json_cmd "$CMD")")
  [ "$(echo "$OUT" | decision)" = "deny" ] || fail "không chặn: $CMD → $OUT"
done <<'CASES'
cat > lib/a.dart <<EOF
sed -i "" s/a/b/ lib/a.dart
echo x | tee lib/a.dart
cp /other/x.dart lib/a.dart
CASES

echo "test_guard_blocks_python_write_in_heredoc"
OUT=$(pre Bash "$(printf '{"command": "python3 - <<PY\\nopen(\\"lib/a.dart\\", \\"w\\").write(1)\\nPY"}')")
[ "$(echo "$OUT" | decision)" = "deny" ] || fail "không chặn python ghi file nguồn: $OUT"

echo "test_guard_allows_normal_commands"
while IFS= read -r CMD; do
  [ -n "$CMD" ] || continue
  OUT=$(pre Bash "$(json_cmd "$CMD")")
  [ "$(echo "$OUT" | decision)" = "allow" ] || fail "chặn nhầm: $CMD → $OUT"
done <<'CASES'
flutter test 2>&1 | tail -5
dart format lib/
git show HEAD:lib/a.dart > /tmp/old.dart
echo "cat > lib/a.dart" >> docs/note.md
python3 .claude/tools/conform.py
CASES

echo "test_guard_escape_hatch"
OUT=$(printf '{"tool_name":"Bash","tool_input":%s}' "$(json_cmd 'cat > lib/a.dart <<EOF')" \
  | CLAUDE_PROJECT_DIR="$T" NAPOLEON_ALLOW_BASH_WRITES=1 python3 "$G")
[ -z "$OUT" ] || fail "cờ NAPOLEON_ALLOW_BASH_WRITES không mở lối: $OUT"

echo "test_guard_blocks_manual_state_edit"
OUT=$(pre Write '{"file_path":"docs/napoleon/state.json"}')
[ "$(echo "$OUT" | decision)" = "deny" ] || fail "không chặn sửa tay state.json: $OUT"
echo "$OUT" | grep -q "state.py" || fail "thông báo không chỉ sang state.py"
OUT=$(pre Edit '{"file_path":"lib/a.dart"}')
[ "$(echo "$OUT" | decision)" = "allow" ] || fail "chặn nhầm Edit file nguồn: $OUT"

echo "test_guard_post_nudges_codegraph_only_for_symbol_search"
OUT=$(printf '{"tool_name":"Bash","tool_input":%s}' "$(json_cmd 'grep -rn CompareTray lib')" | python3 "$G" --post)
echo "$OUT" | grep -q "codegraph" || fail "không nhắc codegraph: $OUT"
OUT=$(printf '{"tool_name":"Bash","tool_input":%s}' "$(json_cmd 'flutter test | grep -c passed')" | python3 "$G" --post)
[ -z "$OUT" ] || fail "nhắc nhầm khi lọc output lệnh: $OUT"

echo "test_guard_bad_stdin_is_silent"
OUT=$(echo 'không phải json' | python3 "$G"); RC=$?
{ [ "$RC" -eq 0 ] && [ -z "$OUT" ]; } || fail "stdin hỏng phải im lặng, exit 0 (rc=$RC, out=$OUT)"

echo "test_session_start_warns_when_stack_stale"
T=$(tmp); mkdir -p "$T/.claude"; cp -R "$TOOLS" "$T/.claude/tools"
python3 "$TOOLS/state.py" --root "$T" init >/dev/null
printf 'name: a\ndependencies:\n  dio: ^5.0.0\n' > "$T/pubspec.yaml"
python3 "$TOOLS/stack.py" --root "$T" --no-probe >/dev/null
OUT=$(CLAUDE_PROJECT_DIR="$T" bash "$TOOLS/session-start.sh")
echo "$OUT" | grep -q "stack.md cũ" && fail "báo cũ khi chưa đổi gì: $OUT"
printf 'name: a\ndependencies:\n  dio: ^5.9.0\n' > "$T/pubspec.yaml"
OUT=$(CLAUDE_PROJECT_DIR="$T" bash "$TOOLS/session-start.sh")
echo "$OUT" | grep -q "stack.md cũ" || fail "không báo stack.md cũ: $OUT"
[ "$(echo "$OUT" | wc -l | tr -d ' ')" -le 5 ] || fail "quá 5 dòng"

echo "test_settings_json_valid"
python3 - "$ROOT/.claude/settings.json" <<'EOF' || fail "settings.json không hợp lệ"
import json, sys
s = json.load(open(sys.argv[1]))
h = s["hooks"]
assert {"PreToolUse", "PostToolUse", "Stop", "SessionStart"} <= set(h), h.keys()
assert h["PostToolUse"][0]["matcher"] == "Edit|Write"
assert "check.sh" in h["PostToolUse"][0]["hooks"][0]["command"]
assert "guard.py" in h["PreToolUse"][0]["hooks"][0]["command"]
assert "Bash" in h["PreToolUse"][0]["matcher"] and "Write" in h["PreToolUse"][0]["matcher"]
assert any("guard.py --post" in x["hooks"][0]["command"] for x in h["PostToolUse"])
assert "codegraph-sync.sh" in h["Stop"][0]["hooks"][0]["command"]
assert "session-start.sh" in h["SessionStart"][0]["hooks"][0]["command"]
EOF

echo "hooks: $FAIL lỗi"
[ "$FAIL" -eq 0 ]

#!/usr/bin/env bash
# Test install.sh — bash thuần, không dependency.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INSTALL="$ROOT/install.sh"
FAIL=0
PASS=0

ok()   { PASS=$((PASS+1)); }
fail() { FAIL=$((FAIL+1)); echo "  FAIL: $1"; }
assert_file()     { [ -f "$1" ] || fail "thiếu file $1"; }
assert_contains() { grep -q -- "$2" "$1" 2>/dev/null || fail "$1 không chứa '$2'"; }
assert_eq()       { [ "$1" = "$2" ] || fail "mong '$2' nhận '$1'"; }
tmp() { mktemp -d 2>/dev/null || mktemp -d -t nap; }

echo "test_fresh_install"
T=$(tmp)
bash "$INSTALL" "$T" >/dev/null
assert_file "$T/.claude/CLAUDE.md"
assert_file "$T/.mcp.json"
assert_contains "$T/.gitignore" ".codegraph/"
assert_contains "$T/.gitignore" "reports/"
for d in prd api design; do [ -f "$T/docs/sources/$d/.gitkeep" ] || fail "thiếu docs/sources/$d/.gitkeep"; done
ok

echo "test_sources_existing_files_untouched"
T=$(tmp); mkdir -p "$T/docs/sources/prd"; echo PRD > "$T/docs/sources/prd/a.md"
bash "$INSTALL" "$T" >/dev/null
assert_eq "$(cat "$T/docs/sources/prd/a.md")" "PRD"
assert_file "$T/docs/sources/api/.gitkeep"
ok

echo "test_no_overwrite"
T=$(tmp); mkdir -p "$T/.claude"; echo USER > "$T/.claude/CLAUDE.md"
OUT=$(bash "$INSTALL" "$T")
assert_eq "$(cat "$T/.claude/CLAUDE.md")" "USER"
echo "$OUT" | grep -q "bỏ qua.*CLAUDE.md" || fail "stdout không báo bỏ qua CLAUDE.md"
ok

echo "test_update_overwrites_bundle_keeps_user_files"
T=$(tmp); mkdir -p "$T/.claude/rules"
echo B > "$T/.claude/rules/b.md"
echo USER > "$T/.claude/CLAUDE.md"
bash "$INSTALL" "$T" --update >/dev/null
[ "$(cat "$T/.claude/CLAUDE.md")" != "USER" ] || fail "--update không đè CLAUDE.md"
assert_eq "$(cat "$T/.claude/rules/b.md")" "B"
ok

echo "test_update_keeps_settings_json"
T=$(tmp); mkdir -p "$T/.claude"
echo '{"permissions":{"allow":["Bash(ls)"]}}' > "$T/.claude/settings.json"
OUT=$(bash "$INSTALL" "$T" --update)
assert_eq "$(cat "$T/.claude/settings.json")" '{"permissions":{"allow":["Bash(ls)"]}}'
echo "$OUT" | grep -q "hooks" || fail "không hướng dẫn gộp hooks"
ok

echo "test_fresh_install_existing_settings_hint"
T=$(tmp); mkdir -p "$T/.claude"; echo '{}' > "$T/.claude/settings.json"
OUT=$(bash "$INSTALL" "$T")
assert_eq "$(cat "$T/.claude/settings.json")" '{}'
echo "$OUT" | grep -q "hooks" || fail "không hướng dẫn gộp hooks"
ok

echo "test_flag_first_order"
T=$(tmp)
bash "$INSTALL" --update "$T" >/dev/null 2>&1; RC=$?
assert_eq "$RC" "0"
assert_file "$T/.claude/CLAUDE.md"
ok

echo "test_existing_mcp_json_kept"
T=$(tmp); echo '{"x":1}' > "$T/.mcp.json"
OUT=$(bash "$INSTALL" "$T")
assert_eq "$(cat "$T/.mcp.json")" '{"x":1}'
echo "$OUT" | grep -q "context7" || fail "không hướng dẫn gộp context7"
echo "$OUT" | grep -q "codegraph" || fail "không hướng dẫn gộp codegraph"
ok

echo "test_missing_codegraph_warns"
T=$(tmp)
OUT=$(PATH=/usr/bin:/bin bash "$INSTALL" "$T"); RC=$?
assert_eq "$RC" "0"
echo "$OUT" | grep -q "install.sh | sh" || fail "không gợi ý lệnh cài codegraph"
ok

echo "install: $PASS nhóm, $FAIL lỗi"
[ "$FAIL" -eq 0 ]

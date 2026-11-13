#!/usr/bin/env bash
# Hook SessionStart: in ≤ 5 dòng trạng thái từ state.json (+ một dòng nếu stack.md cũ). Không có state → im lặng. Luôn exit 0.
set -u
ROOT="${CLAUDE_PROJECT_DIR:-$(pwd)}"
[ -f "$ROOT/docs/napoleon/state.json" ] || exit 0
{
  python3 "$ROOT/.claude/tools/state.py" --root "$ROOT" show --brief 2>/dev/null | head -n 4
  [ -f "$ROOT/docs/napoleon/stack.md" ] && python3 "$ROOT/.claude/tools/stack.py" --root "$ROOT" --check 2>/dev/null
} | head -n 5
exit 0

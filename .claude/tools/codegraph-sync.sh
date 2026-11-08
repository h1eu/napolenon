#!/usr/bin/env bash
# Hook Stop: có file thay đổi và có codegraph → codegraph sync. Luôn exit 0, im lặng.
set -u
ROOT="${CLAUDE_PROJECT_DIR:-$(pwd)}"
command -v codegraph >/dev/null 2>&1 || exit 0
cd "$ROOT" 2>/dev/null || exit 0
[ -d .codegraph ] || exit 0
if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
  codegraph sync >/dev/null 2>&1 || true
fi
exit 0

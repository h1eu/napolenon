#!/usr/bin/env bash
# Cài napoleon vào một dự án: install.sh <đường-dẫn-dự-án> [--update]   (thứ tự tuỳ ý)
#  - Không ghi đè file đã có (in "bỏ qua: ...").
#  - --update: ghi đè file thuộc bộ napoleon (commands, skills lõi, agents lõi, tools, templates, CLAUDE.md).
#  - Không bao giờ đè: .claude/settings.json, .mcp.json (in hướng dẫn gộp), .claude/instructions/, .claude/rules/, docs/napoleon/.
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"
TARGET=""; UPDATE=0
for arg in "$@"; do
  case "$arg" in
    --update) UPDATE=1 ;;
    --*) echo "cờ không biết: $arg" >&2; exit 1 ;;
    *) TARGET="$arg" ;;
  esac
done
[ -n "$TARGET" ] || { echo "cách dùng: install.sh <đường-dẫn-dự-án> [--update]" >&2; exit 1; }
mkdir -p "$TARGET"
TARGET="$(cd "$TARGET" && pwd)"

copied=0; skipped=0

# 1. Copy .claude/ (trừ instructions/, rules/ chỉ copy .gitkeep; settings.json xử lý riêng)
while IFS= read -r -d '' f; do
  rel="${f#"$SRC/"}"
  case "$rel" in
    .claude/instructions/*|.claude/rules/*) [ "$(basename "$f")" = ".gitkeep" ] || continue ;;
    .claude/settings.json) continue ;;
  esac
  dst="$TARGET/$rel"
  if [ -e "$dst" ] && [ "$UPDATE" -eq 0 ]; then
    echo "bỏ qua: $rel"; skipped=$((skipped+1)); continue
  fi
  mkdir -p "$(dirname "$dst")"
  cp "$f" "$dst"; copied=$((copied+1))
done < <(find "$SRC/.claude" -type f -not -path "*/__pycache__/*" -not -name "*.pyc" -not -name ".DS_Store" -print0)

# 2. settings.json: không bao giờ đè
if [ -e "$TARGET/.claude/settings.json" ]; then
  echo "bỏ qua: .claude/settings.json đã có. Hãy gộp khoá 'hooks' từ $SRC/.claude/settings.json vào file của bạn."
else
  cp "$SRC/.claude/settings.json" "$TARGET/.claude/settings.json"; copied=$((copied+1))
fi

# 3. .mcp.json: không bao giờ đè
if [ -e "$TARGET/.mcp.json" ]; then
  echo "bỏ qua: .mcp.json đã có. Hãy gộp hai khoá 'codegraph' và 'context7' từ $SRC/.mcp.json vào mcpServers."
else
  cp "$SRC/.mcp.json" "$TARGET/.mcp.json"; copied=$((copied+1))
fi

# 4. docs/sources/ — tài liệu người dùng đưa; chỉ tạo thư mục, không đụng file có sẵn
for d in prd api design; do
  mkdir -p "$TARGET/docs/sources/$d"
  [ -e "$TARGET/docs/sources/$d/.gitkeep" ] || touch "$TARGET/docs/sources/$d/.gitkeep"
done

# 5. .gitignore
GI="$TARGET/.gitignore"; touch "$GI"
for line in ".codegraph/" "reports/"; do
  grep -qxF "$line" "$GI" || echo "$line" >> "$GI"
done

# 6. Kiểm tra công cụ
command -v python3 >/dev/null 2>&1 || echo "thiếu python3: cài qua https://www.python.org/downloads/ hoặc 'brew install python'"
command -v codegraph >/dev/null 2>&1 || echo "thiếu codegraph: curl -fsSL https://raw.githubusercontent.com/colbymchenry/codegraph/main/install.sh | sh  (rồi chạy 'codegraph install')"

echo "napoleon: đã copy $copied file, bỏ qua $skipped vào $TARGET"
echo "tiếp theo: mở Claude Code trong dự án → /map-codebase (dự án có sẵn) hoặc /start-build (dự án mới)"

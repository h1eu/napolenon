"""Glob và khoá 'exclude' của rules.json, dùng chung cho conform/audit/affected/hook."""
import fnmatch
import json
import sys
from pathlib import Path

RULES_REL = Path(".claude/instructions/rules.json")


def match(rel, pattern):
    """fnmatch; thêm: '**/' cũng khớp 0 thư mục (fnmatch gốc đòi ≥ 1)."""
    if fnmatch.fnmatchcase(rel, pattern):
        return True
    if "**/" in pattern:
        return match(rel, pattern.replace("**/", "", 1))
    return False


def excluded_globs(root):
    """List glob file sinh (*.g.dart, l10n/gen/**). rules.json thiếu hoặc hỏng → []."""
    p = Path(root) / RULES_REL
    if not p.exists():
        return []
    try:
        ex = json.loads(p.read_text(encoding="utf-8")).get("exclude", [])
    except (ValueError, AttributeError) as e:
        print(f"bỏ qua exclude, {RULES_REL} không đọc được ({e.__class__.__name__})", file=sys.stderr)
        return []
    if not isinstance(ex, list):
        print(f"bỏ qua exclude, {RULES_REL} → exclude phải là list glob", file=sys.stderr)
        return []
    return ex


def is_excluded(rel, globs):
    return any(match(rel, g) for g in globs)

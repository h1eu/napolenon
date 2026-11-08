#!/usr/bin/env python3
"""Soi code theo rules.json. In: path:line: rule-id: message. Exit 1 nếu có vi phạm, 2 nếu thiếu rules.

  conform.py [--root DIR] [--rules PATH] [--json]

Loại rule:
  forbidden-import {in, forbid[]}    naming {in, class_regex}
  location {pattern, must_be_under}  max-lines {in, max}
  max-comment-ratio {in, max_ratio, min_lines=20}  — tỉ lệ dòng comment / dòng không trống
Glob dùng fnmatch trên đường dẫn tương đối root; '*' và '**' đều khớp qua '/'.
"""
import argparse
import fnmatch
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from imports import LANG_BY_EXT, find_imports  # noqa: E402

RULES_REL = Path(".claude/instructions/rules.json")
SKIP_DIRS = {".git", ".codegraph", "build", "node_modules", ".dart_tool", ".gradle", ".idea"}
CLASS_RE = re.compile(r"^\s*(?:\w+\s+)*class\s+(\w+)", re.M)


def match(rel, pattern):
    """fnmatch; thêm: '**/' cũng khớp 0 thư mục (fnmatch gốc đòi ≥ 1)."""
    if fnmatch.fnmatchcase(rel, pattern):
        return True
    if "**/" in pattern:
        return fnmatch.fnmatchcase(rel, pattern.replace("**/", "", 1)) or match(rel, pattern.replace("**/", "", 1))
    return False


LINE_COMMENT = {"dart": "//", "kotlin": "//", "swift": "//", "ts": "//", "py": "#"}


def comment_ratio(text, lang):
    """(số dòng comment, số dòng không trống). Đếm // # và khối /* */."""
    prefix = LINE_COMMENT.get(lang, "//")
    total = comments = 0
    in_block = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        total += 1
        if in_block:
            comments += 1
            if "*/" in line:
                in_block = False
            continue
        if line.startswith(prefix) or (lang != "py" and line.startswith("*")):
            comments += 1
        elif lang != "py" and line.startswith("/*"):
            comments += 1
            in_block = "*/" not in line
    return comments, total


def source_files(root):
    for p in root.rglob("*"):
        if p.is_file() and p.suffix in LANG_BY_EXT and not (set(p.relative_to(root).parts[:-1]) & SKIP_DIRS):
            yield p


def check_file(root, path, rules):
    rel = path.relative_to(root).as_posix()
    out = []
    text = None
    for r in rules:
        kind = r["type"]
        if kind == "location":
            under = r["must_be_under"].rstrip("/") + "/"
            if match(rel, r["pattern"]) and not rel.startswith(under):
                out.append((rel, 1, r["id"], f"phải nằm dưới {under}"))
            continue
        if not match(rel, r["in"]):
            continue
        if text is None:
            text = path.read_text(encoding="utf-8", errors="replace")
        if kind == "forbidden-import":
            for i, imp in find_imports(text, LANG_BY_EXT[path.suffix]):
                if any(match(imp, f) for f in r["forbid"]):
                    out.append((rel, i, r["id"], f"import cấm: {imp}"))
        elif kind == "naming":
            rx = re.compile(r["class_regex"])
            for m in CLASS_RE.finditer(text):
                if not rx.match(m.group(1)):
                    line = text.count("\n", 0, m.start()) + 1
                    out.append((rel, line, r["id"], f"class {m.group(1)} không khớp {r['class_regex']}"))
        elif kind == "max-lines":
            n = text.count("\n") + (0 if text.endswith("\n") or not text else 1)
            if n > r["max"]:
                out.append((rel, r["max"] + 1, r["id"], f"{n} dòng > {r['max']}"))
        elif kind == "max-comment-ratio":
            c, n = comment_ratio(text, LANG_BY_EXT[path.suffix])
            if n >= r.get("min_lines", 20) and n and c / n > r["max_ratio"]:
                out.append((rel, 1, r["id"], f"comment {c}/{n} dòng = {c * 100 // n}% > {int(r['max_ratio'] * 100)}%"))
    return out


def relevant(rel, rules):
    for r in rules:
        pat = r.get("in") or r.get("pattern")
        if pat and match(rel, pat):
            return True
    return False


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", default=".")
    p.add_argument("--rules")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    root = Path(a.root).resolve()
    rules_path = Path(a.rules) if a.rules else root / RULES_REL
    if not rules_path.exists():
        print(f"không có {rules_path}", file=sys.stderr)
        sys.exit(2)
    try:
        rules = json.loads(rules_path.read_text(encoding="utf-8"))["rules"]
        for r in rules:
            r["id"]; r["type"]
            r["pattern"] if r["type"] == "location" else r["in"]
    except (KeyError, TypeError, ValueError) as e:
        print(f"rules.json không hợp lệ ({e.__class__.__name__}: {e}); cần {{\"rules\": [{{id,type,in|pattern,...}}]}}", file=sys.stderr)
        sys.exit(2)

    scanned = 0
    violations = []
    for f in sorted(source_files(root)):
        if not relevant(f.relative_to(root).as_posix(), rules):
            continue
        scanned += 1
        violations.extend(check_file(root, f, rules))

    if a.json:
        print(json.dumps([{"path": p_, "line": l, "rule": r, "message": m} for p_, l, r, m in violations],
                         ensure_ascii=False, indent=2))
    else:
        for p_, l, r, m in violations:
            print(f"{p_}:{l}: {r}: {m}")
        print(f"{scanned} file quét, {len(violations)} vi phạm")
    sys.exit(1 if violations else 0)


if __name__ == "__main__":
    main()

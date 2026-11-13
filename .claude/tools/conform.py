#!/usr/bin/env python3
"""Soi code theo rules.json. In: path:line: rule-id: message. Exit 1 nếu có vi phạm, 2 nếu thiếu rules.

  conform.py [--root DIR] [--rules PATH] [--json] [--files a,b]
  conform.py --coverage [--conventions PATH]     # quy ước nào chưa có rule, rule nào chết

Loại rule:
  forbidden-import {in, forbid[]}    naming {in, class_regex}
  location {pattern, must_be_under}  max-lines {in, max}
  max-comment-ratio {in, max_ratio, min_lines=20}  — tỉ lệ dòng comment / dòng không trống
  forbidden-pattern {in, regex, allow[]?, message?, skip_strings?} — regex từng dòng code (luôn bỏ dòng comment;
                     skip_strings=true thì bỏ cả nội dung chuỗi); allow = glob được miễn
  max-function-lines {in, max}       max-params {in, max, constructors=true} — hàm có tên, xem funcs.py;
                                     constructors=false bỏ qua constructor (data class nhiều field)
  no-sibling-import {base, allow[]?} — file dưới base/<a>/ không import base/<b>/ (allow = tên thư mục dùng chung)
Khoá 'exclude' (list glob) ở cấp cao nhất: file khớp bị bỏ qua mọi rule (code sinh: *.g.dart, *.freezed.dart).
Glob dùng fnmatch trên đường dẫn tương đối root; '*' và '**' đều khớp qua '/'.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from funcs import find_functions, strip_code  # noqa: E402
from globs import RULES_REL, is_excluded, match  # noqa: E402,F401
from imports import LANG_BY_EXT, find_imports  # noqa: E402

CONVENTIONS_REL = Path(".claude/instructions/conventions.md")
NO_IN = {"location": "pattern", "no-sibling-import": "base"}       # loại rule không dùng khoá 'in'
REQUIRED = {"forbidden-import": ["forbid"], "naming": ["class_regex"], "location": ["must_be_under"],
            "max-lines": ["max"], "max-comment-ratio": ["max_ratio"], "forbidden-pattern": ["regex"],
            "max-function-lines": ["max"], "max-params": ["max"], "no-sibling-import": []}
SKIP_DIRS = {".git", ".codegraph", "build", "node_modules", ".dart_tool", ".gradle", ".idea"}
CLASS_RE = re.compile(r"^\s*(?:\w+\s+)*class\s+(\w+)", re.M)


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


def package_name(root):
    pub = root / "pubspec.yaml"
    if pub.exists():
        m = re.search(r"^name:\s*(\S+)", pub.read_text(encoding="utf-8", errors="replace"), re.M)
        if m:
            return m.group(1)
    return None


def sibling_of(rel, imp, base, pkg):
    """Tên thư mục con của base mà import trỏ tới, hoặc None nếu import không vào base."""
    base = base.strip("/")
    cands = [imp]
    if imp.startswith("package:"):
        name, _, rest = imp[len("package:"):].partition("/")
        cands = [f"lib/{rest}"] if pkg and name == pkg else []
    elif imp.startswith("."):
        parts = []
        for part in (Path(rel).parent / imp).parts:
            if part == "..":
                parts and parts.pop()
            elif part != ".":
                parts.append(part)
        cands = ["/".join(parts)]
    for c in cands:
        if c.startswith(base + "/"):
            return c[len(base) + 1:].split("/")[0]
        m = re.search(r"(?:^|\.)" + re.escape(base.replace("/", ".").split(".")[-1]) + r"\.(\w+)", c)
        if m and "/" not in c:                 # import dạng a.b.features.login.X (Kotlin, Python)
            return m.group(1)
    return None


def check_functions(rel, text, lang, rules, out):
    fn_rules = [r for r in rules if r["type"] in ("max-function-lines", "max-params") and match(rel, r["in"])]
    if not fn_rules:
        return
    for fn in find_functions(text, lang):
        for r in fn_rules:
            if r["type"] == "max-function-lines" and fn["lines"] > r["max"]:
                out.append((rel, fn["line"], r["id"], f"hàm {fn['name']} {fn['lines']} dòng > {r['max']}"))
            elif r["type"] == "max-params" and fn["params"] > r["max"] and (r.get("constructors", True) or not fn["ctor"]):
                out.append((rel, fn["line"], r["id"], f"hàm {fn['name']} {fn['params']} tham số > {r['max']}"))


def check_file(root, path, rules, pkg=None):
    rel = path.relative_to(root).as_posix()
    lang = LANG_BY_EXT[path.suffix]
    out = []
    text = None
    for r in rules:
        kind = r["type"]
        if kind == "location":
            under = r["must_be_under"].rstrip("/") + "/"
            if match(rel, r["pattern"]) and not rel.startswith(under):
                out.append((rel, 1, r["id"], f"phải nằm dưới {under}"))
            continue
        if kind == "no-sibling-import":
            base = r["base"].strip("/")
            if not rel.startswith(base + "/") or "/" not in rel[len(base) + 1:]:
                continue
            own = rel[len(base) + 1:].split("/")[0]
            if text is None:
                text = path.read_text(encoding="utf-8", errors="replace")
            for i, imp in find_imports(text, lang):
                sib = sibling_of(rel, imp, base, pkg)
                if sib and sib != own and sib not in r.get("allow", []) and own not in r.get("allow", []):
                    out.append((rel, i, r["id"], f"{base}/{own} import {base}/{sib}: {imp}"))
            continue
        if not match(rel, r["in"]):
            continue
        if text is None:
            text = path.read_text(encoding="utf-8", errors="replace")
        if kind == "forbidden-pattern":
            if any(match(rel, g) for g in r.get("allow", [])):
                continue
            rx = re.compile(r["regex"])
            code = strip_code(text, lang).splitlines() if r.get("skip_strings") else None
            for i, line in enumerate(text.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith(LINE_COMMENT.get(lang, "//")) or stripped.startswith("*"):
                    continue
                if rx.search(code[i - 1] if code else line):
                    out.append((rel, i, r["id"], r.get("message") or f"khớp mẫu cấm: {r['regex']}"))
        elif kind == "forbidden-import":
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
    if text is not None:
        check_functions(rel, text, lang, rules, out)
    elif any(r["type"] in ("max-function-lines", "max-params") and match(rel, r["in"]) for r in rules):
        check_functions(rel, path.read_text(encoding="utf-8", errors="replace"), lang, rules, out)
    return out


def rule_glob(r):
    if r["type"] == "no-sibling-import":
        return r["base"].strip("/") + "/**"
    return r.get("in") or r.get("pattern")


def relevant(rel, rules, exclude=()):
    if is_excluded(rel, exclude):
        return False
    return any(match(rel, rule_glob(r)) for r in rules)


def load_rules(rules_path):
    """(rules, exclude). Thoát 2 nếu thiếu hoặc sai cấu trúc."""
    if not rules_path.exists():
        print(f"không có {rules_path}", file=sys.stderr)
        sys.exit(2)
    try:
        doc = json.loads(rules_path.read_text(encoding="utf-8"))
        rules = doc["rules"]
        exclude = doc.get("exclude", [])
        if not isinstance(exclude, list):
            raise TypeError("exclude phải là list glob")
        for r in rules:
            r["id"]
            if r["type"] not in REQUIRED:
                raise ValueError(f"rule {r['id']}: loại '{r['type']}' không có; có: {sorted(REQUIRED)}")
            for k in [NO_IN.get(r["type"], "in")] + REQUIRED[r["type"]]:
                r[k]
            if r["type"] == "forbidden-pattern":
                re.compile(r["regex"])
            if r["type"] == "naming":
                re.compile(r["class_regex"])
    except (KeyError, TypeError, ValueError, re.error) as e:
        print(f"rules.json không hợp lệ ({e.__class__.__name__}: {e}); cần {{\"rules\": [{{id,type,in|pattern,...}}]}}", file=sys.stderr)
        sys.exit(2)
    return rules, exclude


TAG_RE = re.compile(r"\[rule:\s*([^\]]+)\]")
MANUAL_TAG = "[tay]"
MANUAL_HEADING = "Không kiểm tự động"


def coverage(root, rules, exclude, conv_path):
    """(lỗi, cảnh báo). Lỗi: quy ước chưa gắn nhãn, nhãn trỏ rule không có. Cảnh báo: rule không khớp file nào,
    rule không quy ước nào nhắc."""
    errors, warns = [], []
    ids = {r["id"] for r in rules}
    cited = set()
    if not conv_path.exists():
        errors.append(f"không có {conv_path}")
    else:
        manual = False
        for n, line in enumerate(conv_path.read_text(encoding="utf-8").splitlines(), 1):
            if line.startswith("#"):
                manual = MANUAL_HEADING in line
                continue
            body = line.strip()
            if not body.startswith("- ") or body[2:].lstrip().startswith("<"):
                continue                        # không phải quy ước, hoặc placeholder của template
            tags = [t.strip() for m in TAG_RE.finditer(body) for t in m.group(1).split(",")]
            for t in tags:
                cited.add(t)
                if t not in ids:
                    errors.append(f"{conv_path.name}:{n}: nhãn [rule: {t}] nhưng rules.json không có rule này")
            if not tags and not manual and MANUAL_TAG not in body:
                errors.append(f"{conv_path.name}:{n}: quy ước chưa gắn [rule: <id>] hoặc {MANUAL_TAG}: {body[2:60]}")
    files = [f.relative_to(root).as_posix() for f in source_files(root)]
    files = [f for f in files if not is_excluded(f, exclude)]
    for r in rules:
        if files and not any(match(f, rule_glob(r)) for f in files):
            warns.append(f"rule {r['id']}: glob '{rule_glob(r)}' không khớp file nào")
        if r["id"] not in cited:
            warns.append(f"rule {r['id']}: không quy ước nào trong {conv_path.name} nhắc tới")
    return errors, warns


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", default=".")
    p.add_argument("--rules")
    p.add_argument("--json", action="store_true")
    p.add_argument("--files", help="chỉ soi các file này (cách nhau dấu phẩy, tương đối root)")
    p.add_argument("--coverage", action="store_true")
    p.add_argument("--conventions")
    a = p.parse_args(argv)
    root = Path(a.root).resolve()
    rules, exclude = load_rules(Path(a.rules) if a.rules else root / RULES_REL)

    if a.coverage:
        errors, warns = coverage(root, rules, exclude, Path(a.conventions) if a.conventions else root / CONVENTIONS_REL)
        for w in warns:
            print(f"cảnh báo: {w}")
        for e in errors:
            print(e)
        print(f"{len(rules)} rule, {len(errors)} lỗi, {len(warns)} cảnh báo")
        sys.exit(1 if errors else 0)

    only = {x.strip() for x in a.files.split(",") if x.strip()} if a.files else None
    pkg = package_name(root)
    scanned = 0
    violations = []
    for f in sorted(source_files(root)):
        rel = f.relative_to(root).as_posix()
        if (only is not None and rel not in only) or not relevant(rel, rules, exclude):
            continue
        scanned += 1
        violations.extend(check_file(root, f, rules, pkg))

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

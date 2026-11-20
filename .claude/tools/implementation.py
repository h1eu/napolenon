#!/usr/bin/env python3
"""Sinh docs/napoleon/implementation.md từ dữ liệu repo: cái gì đã làm, ở đâu, test nào chứng minh.

  implementation.py [--root DIR] [--out PATH]

Chỉ đọc state.json và git; không có dấu thời gian, cùng dữ liệu → cùng byte.
Thiếu nguồn → "—". Muốn thêm cột/số → sửa file này, không gõ tay vào báo cáo.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

TOOLS = str(Path(__file__).resolve().parent)
sys.path.insert(0, TOOLS)

import report  # noqa: E402

STATE_REL = Path("docs/napoleon/state.json")
OUT_REL = Path("docs/napoleon/implementation.md")
HEADER = "<!-- napoleon:generated — không sửa tay, chạy implementation.py -->"
DASH = "—"


def cell(x):
    if x is None or x == "" or x == []:
        return DASH
    return str(x).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def table(headers, rows):
    lines = ["| " + " | ".join(cell(h) for h in headers) + " |",
             "|" + "|".join("---" for _ in headers) + "|"]
    lines += ["| " + " | ".join(cell(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


def section(title, body, src):
    return f"## {title}\n\n{body}\n\nnguồn: {src}\n"


def tid(feature, t):
    return f"{feature}#{t.get('id')}"


def load_state(root):
    p = root / STATE_REL
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _git(root, *args):
    try:
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None


def has_git(root):
    r = _git(root, "rev-parse", "--git-dir")
    return r is not None and r.returncode == 0


def is_ancestor(root, commit, head):
    r = _git(root, "merge-base", "--is-ancestor", commit, head)
    return r is not None and r.returncode == 0


def rev_list(root, *args):
    r = _git(root, "rev-list", *args)
    return r.stdout.split() if r is not None and r.returncode == 0 else []


def task_commit(root, t):
    if t.get("status") != "done" or not t.get("commit"):
        return DASH
    if not has_git(root):
        return DASH
    if not is_ancestor(root, t["commit"], "HEAD"):
        return "— (lịch sử đã viết lại)"
    after = rev_list(root, "--reverse", "--first-parent", f"{t['commit']}..HEAD")
    if not after:
        return "commit kế tiếp"
    base = t.get("base") or ""
    mid = len(rev_list(root, "--first-parent", f"{base}..{t['commit']}")) if base and base != t["commit"] else 0
    return after[0][:7] + (f" (+{mid})" if mid else "")


def _verify_text(f):
    v = f.get("verify") or []
    if not v:
        return DASH
    last = v[-1]
    s = f"lần {len(v)} {last.get('result', '')}".strip()
    issues = last.get("issues") or []
    return s + (f" ({', '.join(issues)})" if issues else "")


def _test_text(t):
    test = t.get("test") or {}
    result = test.get("result")
    if not result:
        return DASH
    n = len(test.get("files") or [])
    return f"{result} · {n} file" if n else result


def _status_text(t):
    st = t.get("status") or "todo"
    return f"blocked: {t.get('blocker')}" if st == "blocked" and t.get("blocker") else st


def overview(features):
    rows = []
    for name, f in features.items():
        tasks = f.get("tasks") or []
        done = sum(1 for t in tasks if t.get("status") == "done")
        waiting = sum(1 for h in f.get("human") or [] if not h.get("done"))
        rows.append([name, f.get("step"), f"{done}/{len(tasks)}", _verify_text(f), waiting or None])
    return section("Tổng quan", table(["Feature", "Bước", "Task xong", "Verify", "Người chờ"], rows),
                   "docs/napoleon/state.json")


def tasks_section(root, features):
    parts = []
    for name, f in features.items():
        rows = [[tid(name, t), t.get("title"), _status_text(t), ", ".join(t.get("routes") or []),
                 len(t.get("changed") or []) or None, _test_text(t), task_commit(root, t)]
                for t in f.get("tasks") or []]
        if rows:
            parts.append(f"### {name}\n\n" + table(["ID", "Việc", "Trạng thái", "Route", "File đổi", "Test", "Commit"], rows))
    return section("Task", "\n\n".join(parts) or "chưa có task", "docs/napoleon/state.json, git")


def changes_section(features):
    rows = []
    for name, f in features.items():
        for t in sorted(f.get("tasks") or [], key=lambda x: x.get("id") or 0):
            if t.get("status") != "done":
                continue
            for c in sorted(t.get("changed") or [], key=lambda x: x.get("path", "")):
                rows.append([tid(name, t), c.get("path"), c.get("kind")])
    body = table(["ID", "File", "Kiểu"], rows) if rows else "chưa có task done"
    return section("Thay đổi theo task", body, "docs/napoleon/state.json")


def plan_tests(root, feature):
    p = root / "docs/napoleon/features" / feature / "plan.md"
    if not p.exists():
        return {}
    out = {}
    cur = None
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"###\s+Task\s+(\d+)\b", line)
        if m:
            cur = int(m.group(1))
            continue
        if line.startswith("#"):
            cur = None
        m = re.match(r"\s*-\s*Test chứng minh:\s*(.*\S)", line)
        if m and cur is not None:
            out.setdefault(cur, m.group(1))
    return out


def _ran_text(test):
    if not test:
        return DASH
    if test.get("mode") == "all":
        return "toàn bộ"
    return ", ".join(test.get("files") or [])


def _result_text(test):
    result = test.get("result")
    if not result:
        return DASH
    return f"{result}: {test['tail']}" if test.get("tail") else result


def _verify_line(root, name, f, counts):
    parts = []
    v = f.get("verify") or []
    if v:
        items = []
        for i, e in enumerate(v, 1):
            s = f"lần {i} {e.get('result', '')}".strip()
            issues = e.get("issues") or []
            items.append(s + (f" ({', '.join(issues)})" if issues else ""))
        parts.append(", ".join(items))
    if name in counts:
        done, total, human = counts[name]
        parts.append(f"máy+verifier {done}/{total}")
        parts.append(f"người chờ {human}")
    return f"{name} — verify " + " · ".join(parts) if parts else None


def render_tests(root, state):
    features = state.get("features") or {}
    counts = report.verify_counts(root)
    rows, lines = [], []
    for name, f in features.items():
        plan = plan_tests(root, name)
        for t in sorted(f.get("tasks") or [], key=lambda x: x.get("id") or 0):
            test, checks = t.get("test") or {}, t.get("checks") or {}
            if not test and not checks:
                continue
            cmd = test.get("command")
            rows.append([tid(name, t), plan.get(t.get("id")), _ran_text(test), f"`{cmd}`" if cmd else None,
                         _result_text(test), checks.get("conform")])
        line = _verify_line(root, name, f, counts)
        if line:
            lines.append(line)
    body = table(["ID", "Test chứng minh (plan)", "Test đã chạy", "Lệnh", "Kết quả", "Conform"], rows) \
        if rows else "chưa có task nào chạy test"
    if lines:
        body += "\n\n" + "\n\n".join(lines)
    return section("Test và bằng chứng", body, "plan.md, verify.md, docs/napoleon/state.json")


def md_table(text, heading):
    lines = text.splitlines()
    start = 0
    if heading is not None:
        want = heading.lstrip("#").strip()
        for i, l in enumerate(lines):
            if l.startswith("#") and l.lstrip("#").strip() == want:
                start = i + 1
                break
        else:
            return []
    rows, started = [], False
    for l in lines[start:]:
        s = l.strip()
        if s.startswith("|"):
            started = True
            rows.append([c.strip() for c in s.strip("|").split("|")])
        elif started:
            break
        elif heading is not None and s.startswith("#"):
            return []
    out = []
    for r in rows[1:]:
        if all(re.fullmatch(r":?-{3,}:?", c) for c in r if c) and any(r):
            continue
        if r and r[0].replace("`", "").startswith("<"):
            continue
        out.append(r)
    return out


class Code:
    def __init__(self, root):
        import audit
        chunks = []
        for f in audit.source_files(root):
            try:
                chunks.append((root / f).read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
        self.text = "\n".join(chunks)

    def has(self, text):
        return bool(text.strip()) and text in self.text

    def has_word(self, name):
        if not name.strip():
            return False
        return re.search(r"(?<![\w$])" + re.escape(name) + r"(?![\w$])", self.text) is not None

    def findall(self, pattern):
        return set(pattern.findall(self.text))


def _route_pattern(root):
    p = root / ".claude/instructions/toolchain.json"
    try:
        v = json.loads(p.read_text(encoding="utf-8")).get("route_pattern")
    except (OSError, ValueError, AttributeError):
        return None
    return v if isinstance(v, str) and v else None


def _code_routes_lines(root, code, declared):
    raw = _route_pattern(root)
    if not raw:
        return ["chưa bật dò route trong code (đặt route_pattern trong .claude/instructions/toolchain.json)"]
    try:
        pat = re.compile(raw)
    except re.error as e:
        return [f"route_pattern không hợp lệ: {e}"]
    if pat.groups != 1:
        return [f"route_pattern không hợp lệ: cần đúng 1 nhóm bắt, có {pat.groups}"]
    found = sorted(r for r in code.findall(pat) if r not in declared)
    return [f"- route {r} có trong code, chưa khai trong routes.md" for r in found]


def render_routes(root, state, code):
    src = ".claude/instructions/routes.md, docs/napoleon/state.json, file nguồn"
    p = root / ".claude/instructions/routes.md"
    if not p.exists():
        return section("Route và màn", "chưa có .claude/instructions/routes.md — tạo từ .claude/templates/routes.md", src)
    declared = md_table(p.read_text(encoding="utf-8", errors="replace"), None)
    features = state.get("features") or {}
    by_route, uses = {}, []
    for name, f in features.items():
        for t in sorted(f.get("tasks") or [], key=lambda x: x.get("id") or 0):
            for r in t.get("routes") or []:
                by_route.setdefault(r, []).append((tid(name, t), t.get("status")))
                uses.append((tid(name, t), r))
    rows = []
    for r in declared:
        r = (r + [""] * 4)[:4]
        route, screen = r[0].strip("`"), r[1].strip("`")
        ts = by_route.get(route, [])
        status = "chưa có task" if not ts else "xong" if all(s == "done" for _, s in ts) else "đang làm"
        missing = [w for w, ok in (("route", code.has(route)), ("màn", code.has_word(screen))) if not ok]
        rows.append([route, screen, r[2], ", ".join(i for i, _ in ts), status, r[3],
                     "có" if not missing else "thiếu " + ", ".join(missing)])
    known = {r[0].strip("`") for r in declared}
    body = table(["Route", "Màn", "Feature", "Task", "Trạng thái", "Design", "Trong code"], rows)
    notes = [f"- task {i} khai route {r} không có trong routes.md" for i, r in uses if r not in known]
    notes += _code_routes_lines(root, code, known)
    return section("Route và màn", body + "\n\n" + "\n".join(notes), src)


ARCH_REL = ".claude/instructions/architecture.md"
ARCH_MISSING = f"chưa có {ARCH_REL}"


def _arch_text(root):
    p = root / ARCH_REL
    return p.read_text(encoding="utf-8", errors="replace") if p.exists() else None


def render_truth(root, code):
    src = f"{ARCH_REL}, file nguồn"
    arch = _arch_text(root)
    if arch is None:
        return section("Nguồn sự thật", ARCH_MISSING, src) + "\n" + section("Logic tái dùng", ARCH_MISSING, src)
    truth_rows = []
    for r in md_table(arch, "## Nguồn sự thật dùng chung"):
        r = (r + [""] * 4)[:4]
        m = re.search(r"[A-Z]\w+", r[1])
        truth_rows.append(r + ["có" if m and code.has_word(m.group(0)) else "thiếu"])
    truth = table(["Trạng thái", "Owner (class, path)", "Phát ra qua", "Ai được ghi", "Trong code"], truth_rows) \
        if truth_rows else "chưa khai"
    mgr_rows = []
    for r in md_table(arch, "## Logic tái dùng (manager)"):
        r = (r + [""] * 4)[:4]
        name = r[0].strip("`")
        if not code.has_word(name):
            status = "thiếu"
        else:
            test = r[3].replace("`", "").strip()
            status = "có · test có" if test and (root / test).is_file() else "có · thiếu test"
        mgr_rows.append(r + [status])
    mgr = table(["Class", "Việc duy nhất", "Nằm ở", "Test", "Trong code"], mgr_rows) if mgr_rows else "chưa khai"
    return section("Nguồn sự thật", truth, src) + "\n" + section("Logic tái dùng", mgr, src)


def render_decisions(root, state):
    adrs = []
    d = root / ".claude/instructions/decisions"
    for p in sorted(d.glob("*.md")) if d.is_dir() else []:
        first = next((l for l in p.read_text(encoding="utf-8", errors="replace").splitlines()
                      if l.startswith("# ")), "")
        m = re.search(r"ADR-\d+", first)
        if m:
            title = first.split(":", 1)[1].strip() if ":" in first else ""
            adrs.append((m.group(0), title))
    adrs.sort(key=lambda a: (int(a[0][4:]), a[0]))
    opens = [f for f in state.get("followups") or [] if f.get("status") == "open"]
    rows, used = [], set()
    for code_, title in adrs:
        mine = [f for f in opens if code_ in re.findall(r"ADR-\d+", f.get("source") or "")]
        used.update(f.get("id") for f in mine)
        rows.append([code_, title, "; ".join(f"#{f.get('id')} {f.get('text')}" for f in mine)])
    for f in opens:
        if f.get("id") not in used:
            rows.append([None, None, f"#{f.get('id')} {f.get('text')}"])
    body = table(["ADR", "Tiêu đề", "Followup mở"], rows) if rows else "không có"
    return section("Quyết định và việc hẹn lại", body, ".claude/instructions/decisions/, docs/napoleon/state.json")


def build(root):
    state = load_state(root)
    if state is None:
        return None
    features = state.get("features") or {}
    code = Code(root)
    parts = [overview(features), tasks_section(root, features), changes_section(features),
             render_tests(root, state), render_routes(root, state, code), render_truth(root, code),
             render_decisions(root, state)]
    return HEADER + "\n\n# Implementation\n\n" + "\n".join(parts)


def write(root, out=None):
    text = build(root)
    if text is None:
        return False
    out = Path(out) if out else root / OUT_REL
    if out.exists() and out.read_text(encoding="utf-8") == text:
        return False
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return True


def main(argv=None):
    ap = argparse.ArgumentParser(description="Sinh docs/napoleon/implementation.md")
    ap.add_argument("--root", default=".")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve()
    if not (root / STATE_REL).exists():
        print("chưa có state.json — chưa sinh báo cáo")
        return 0
    wrote = write(root, a.out)
    print(f"{'đã ghi' if wrote else 'không đổi'}: {a.out or OUT_REL}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

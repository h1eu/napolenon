#!/usr/bin/env python3
"""Sinh reports/roadmap.html từ dữ liệu repo. Không có số nào gõ tay.

  report.py [--root DIR] [--out PATH]

Nguồn: docs/napoleon/state.json, git log, .codegraph/codegraph.db, features/*/verify.md, audit.py.
Thiếu nguồn → "không có dữ liệu". Agent không sửa HTML tay; muốn thêm số → sửa file này.
"""
import argparse
import html
import json
import re
import sqlite3
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit  # noqa: E402
from cgdb import DB_REL, open_db  # noqa: E402

STATE_REL = Path("docs/napoleon/state.json")
FEATURES_REL = Path("docs/napoleon/features")
NO_DATA = "không có dữ liệu"

CSS = """
body{font:15px/1.5 -apple-system,Segoe UI,Helvetica,Arial,sans-serif;max-width:960px;margin:32px auto;padding:0 16px;color:#222;background:#fff}
h1{font-size:22px;margin:0 0 4px}h2{font-size:17px;margin:28px 0 8px}
section{border:1px solid #e3e3e3;border-radius:8px;padding:12px 16px;margin:12px 0}
table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:4px 8px;border-bottom:1px solid #eee}
.stat{display:inline-block;min-width:120px;margin:4px 12px 4px 0}.stat b{font-size:22px;display:block}
.src{color:#777;font-size:12px}.muted{color:#999}.bar{height:8px;background:#e8e8e8;border-radius:4px;overflow:hidden}
.bar i{display:block;height:100%;background:#4a7}.badge{padding:1px 6px;border-radius:4px;background:#eef;font-size:12px}
@media(prefers-color-scheme:dark){body{background:#151515;color:#ddd}section{border-color:#333}td,th{border-color:#2a2a2a}.bar{background:#2a2a2a}.badge{background:#243}}
"""


def esc(x):
    return html.escape(str(x))


# ---------- nguồn ----------

def load_state(root):
    p = root / STATE_REL
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def git_log(root):
    try:
        r = subprocess.run(["git", "-C", str(root), "log", "--date=short", "--pretty=%ad%x09%s"],
                           capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    rows = []
    for line in r.stdout.splitlines():
        d, _, s = line.partition("\t")
        rows.append((d, s))
    return rows


CG_TABLES = ("files", "nodes", "edges")


def codegraph_stats(root, recognized):
    """Đếm files/nodes/edges — chỉ khi audit.py đã nhận dạng được schema (recognized)."""
    if not (root / DB_REL).exists() or not recognized:
        return None
    try:
        with open_db(root) as con:
            if con is None:
                return None
            tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            counts = {t: con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in CG_TABLES if t in tables}
        return counts or None
    except sqlite3.Error:
        return None


HUMAN_HEADING = re.compile(r"^##\s+Người\s*$")
BOX = re.compile(r"^\s*- \[( |x|X)\]")


def verify_counts(root):
    """feature → (máy đạt, máy tổng, người chờ). Mục Người tách riêng: người tự kiểm sau, không kéo tỉ lệ xuống."""
    out = {}
    base = root / FEATURES_REL
    if not base.exists():
        return out
    for v in sorted(base.glob("*/verify.md")):
        done = total = human = 0
        in_human = False
        for line in v.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("## "):
                in_human = bool(HUMAN_HEADING.match(line))
                continue
            m = BOX.match(line)
            if not m:
                continue
            if in_human:
                human += m.group(1) == " "
            else:
                total += 1
                done += m.group(1) != " "
        out[v.parent.name] = (done, total, human)
    return out


# ---------- render ----------

def section(sid, title, body, src):
    return f'<section id="{sid}"><h2>{esc(title)}</h2>{body}<small class="src">nguồn: {esc(src)}</small></section>'


def stat(key, label, value):
    return f'<div class="stat"><b data-stat="{key}">{esc(value)}</b>{esc(label)}</div>'


def render_features(state):
    if not state:
        return f'<p class="muted">{NO_DATA}</p>'
    feats = state["features"]
    steps = Counter(f["step"] for f in feats.values())
    rows = []
    for name, f in feats.items():
        n = len(f["tasks"]); d = sum(1 for t in f["tasks"] if t["status"] == "done")
        pct = int(d * 100 / n) if n else 0
        rows.append(f"<tr><td>{esc(name)}</td><td><span class='badge'>{esc(f['step'])}</span></td>"
                    f"<td>{d}/{n}</td><td style='width:40%'><div class='bar'><i style='width:{pct}%'></i></div></td></tr>")
    table = "<table><tr><th>Feature</th><th>Bước</th><th>Task xong</th><th></th></tr>" + "".join(rows) + "</table>" if rows else f'<p class="muted">chưa có feature</p>'
    head = stat("features", "feature", len(feats)) + stat("features-done", "đã done", steps.get("done", 0))
    return head + table


def render_tasks(state):
    if not state:
        return f'<p class="muted">{NO_DATA}</p>'
    c = Counter(t["status"] for f in state["features"].values() for t in f["tasks"])
    total = sum(c.values())
    return (stat("tasks-total", "task", total) + stat("tasks-done", "done", c.get("done", 0))
            + stat("tasks-progress", "đang làm", c.get("in_progress", 0)) + stat("tasks-blocked", "blocked", c.get("blocked", 0)))


def render_commits(log, state):
    if log is None:
        return f'<p class="muted">{NO_DATA}</p>'
    by_day = Counter(d for d, _ in log)
    per_feature = {}
    if state:
        for name in state["features"]:
            rx = re.compile(r"(?<![a-z0-9-])" + re.escape(name) + r"(?![a-z0-9-])", re.I)
            per_feature[name] = sum(1 for _, s in log if rx.search(s))
    body = stat("commits", "commit", len(log)) + stat("commit-days", "ngày có commit", len(by_day))
    if per_feature:
        body += "<table><tr><th>Feature</th><th>Commit nhắc tới</th></tr>" + "".join(
            f"<tr><td>{esc(k)}</td><td>{v}</td></tr>" for k, v in per_feature.items()) + "</table>"
    recent = sorted(by_day.items())[-14:]
    if recent:
        mx = max(v for _, v in recent) or 1
        body += "<table>" + "".join(
            f"<tr><td style='width:110px'>{esc(d)}</td><td><div class='bar'><i style='width:{int(v*100/mx)}%'></i></div></td><td>{v}</td></tr>"
            for d, v in recent) + "</table>"
    return body


def render_codegraph(counts):
    if not counts:
        return f'<p class="muted">{NO_DATA} — chạy: codegraph init</p>'
    return "".join(stat(f"cg-{k}", k, counts[k]) for k in CG_TABLES if k in counts)


def render_verify(vc, state):
    if not vc:
        return f'<p class="muted">{NO_DATA}</p>'
    rounds = {k: len(f.get("verify", [])) for k, f in (state or {}).get("features", {}).items()}
    body = stat("verify-human", "mục Người chờ bạn", sum(h for _, _, h in vc.values()))
    rows = "".join(
        f"<tr><td>{esc(k)}</td><td data-stat='verify-{esc(k)}'>{d}/{n}</td>"
        f"<td data-stat='human-{esc(k)}'>{h or ''}</td><td>{rounds.get(k) or ''}</td></tr>"
        for k, (d, n, h) in vc.items())
    return body + ("<table><tr><th>Feature</th><th>Máy + verifier</th><th>Người chờ</th><th>Lần verify</th></tr>"
                   + rows + "</table>")


def render_followups(state):
    fu = (state or {}).get("followups", [])
    if not fu:
        return f'<p class="muted">không có followup</p>'
    op = [x for x in fu if x["status"] == "open"]
    body = stat("followups-open", "đang mở", len(op)) + stat("followups", "tổng", len(fu))
    return body + "<table><tr><th>#</th><th>Feature</th><th>Việc</th><th>Nguồn</th></tr>" + "".join(
        f"<tr><td>{x['id']}</td><td>{esc(x['feature'])}</td><td>{esc(x['text'])}</td><td>{esc(x['source'])}</td></tr>"
        for x in op) + "</table>"


def render_audit(a):
    if not a:
        return f'<p class="muted">{NO_DATA}</p>'
    body = (stat("audit-files", "file", a["files"]) + stat("audit-cycles", "cycles", len(a["cycles"]))
            + stat("audit-violations", "vi phạm ranh giới", len(a["boundary_violations"]))
            + stat("audit-orphans", "file mồ côi", len(a["orphans"])))
    if a["cycles"]:
        body += "<ul>" + "".join(f"<li>{esc(' ↔ '.join(c))}</li>" for c in a["cycles"][:10]) + "</ul>"
    if a["boundary_violations"]:
        body += "<ul>" + "".join(f"<li>{esc(v['from'])} → {esc(v['to'])}</li>" for v in a["boundary_violations"][:10]) + "</ul>"
    return body


def build(root):
    root = Path(root).resolve()
    state = load_state(root)
    log = git_log(root)
    vc = verify_counts(root)
    try:
        a = audit.collect(root, "auto", 2)
    except Exception:  # audit lỗi không được làm hỏng cả báo cáo; mục Audit ghi "không có dữ liệu"
        a = None
    cg = codegraph_stats(root, recognized=bool(a and a["source"] == "codegraph"))
    gen = datetime.now().strftime("%Y-%m-%d %H:%M")
    parts = [
        "<!doctype html><html lang='vi'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>",
        f"<title>Roadmap</title><style>{CSS}</style></head><body>",
        f"<h1>Roadmap</h1><p class='muted'>sinh lúc {gen} bởi report.py — mọi số đều từ dữ liệu repo</p>",
        section("features", "Feature", render_features(state), "docs/napoleon/state.json"),
        section("tasks", "Task", render_tasks(state), "docs/napoleon/state.json"),
        section("commits", "Commit", render_commits(log, state), "git log"),
        section("codegraph", "Codegraph", render_codegraph(cg), ".codegraph/codegraph.db"),
        section("verify", "Verify", render_verify(vc, state), "docs/napoleon/features/*/verify.md + state.json"),
        section("followups", "Việc hẹn lại", render_followups(state), "docs/napoleon/state.json"),
        section("audit", "Audit", render_audit(a), f"audit.py (source: {a['source'] if a else '—'})"),
        "</body></html>",
    ]
    return "\n".join(parts)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", default=".")
    p.add_argument("--out", default="reports/roadmap.html")
    a = p.parse_args(argv)
    root = Path(a.root).resolve()
    out = Path(a.out)
    if not out.is_absolute():
        out = root / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build(root), encoding="utf-8")
    print(f"đã ghi {out}")


if __name__ == "__main__":
    main()

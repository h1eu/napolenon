#!/usr/bin/env python3
"""Trạng thái feature/task của dự án. Chỉ sửa state.json qua tool này.

  state.py [--root DIR] init
  state.py [--root DIR] show [--brief] [--json]
  state.py [--root DIR] feature add <tên> | step <tên> <bước> | show <tên>
  state.py [--root DIR] task add <feature> "<title>" [--files a,b] | start|done <feature> <id>
  state.py [--root DIR] task block <feature> <id> "<lý do>"
  state.py [--root DIR] session note <feature> "<ghi chú>"
  state.py [--root DIR] sources mark | show        # mốc đồng bộ docs/sources/ (dùng bởi sources.py)
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

STATE_REL = Path("docs/napoleon/state.json")
JOURNAL_REL = Path("docs/napoleon/journal.md")
SOURCES_REL = Path("docs/sources")
SOURCES_SKIP = {".gitkeep", ".DS_Store"}
STEPS = ["spec", "plan", "build", "verify", "done"]
TASK_STATUS = ["todo", "in_progress", "done", "blocked"]
NAME_RE = re.compile(r"^[a-z0-9-]+$")


def now():
    return datetime.now().replace(microsecond=0).isoformat()


def die(msg):
    print(msg, file=sys.stderr)
    sys.exit(1)


def load_state(root):
    p = Path(root) / STATE_REL
    if not p.exists():
        die("chưa có state.json — chạy: state.py init")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except ValueError as e:
        die(f"state.json hỏng ({e}) — sửa tay hoặc xoá rồi init lại")


def save_state(root, state):
    p = Path(root) / STATE_REL
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, p)


def append_journal(root, feature, note):
    p = Path(root) / JOURNAL_REL
    p.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    with p.open("a", encoding="utf-8") as f:
        f.write(f"## {stamp} — {feature}\n{note}\n\n")


def empty_state():
    return {"version": 1, "features": {}, "last_session": {"feature": "", "note": "", "at": ""},
            "sources": empty_sources()}


def empty_sources():
    return {"commit": "", "manifest": {}, "at": ""}


def sources_manifest(root):
    """path tương đối → sha256, cho mọi file trong docs/sources/."""
    base = Path(root) / SOURCES_REL
    out = {}
    if not base.is_dir():
        return out
    for f in sorted(base.rglob("*")):
        if not f.is_file() or f.name in SOURCES_SKIP:
            continue
        out[f.relative_to(root).as_posix()] = hashlib.sha256(f.read_bytes()).hexdigest()
    return out


def git_head(root):
    try:
        r = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def get_feature(state, name):
    if name not in state["features"]:
        die(f"không có feature '{name}'")
    return state["features"][name]


def get_task(feature, task_id):
    for t in feature["tasks"]:
        if t["id"] == task_id:
            return t
    die(f"không có task id {task_id}")


# ---- lệnh ----

def cmd_init(root, _):
    if (Path(root) / STATE_REL).exists():
        die("state.json đã tồn tại")
    save_state(root, empty_state())
    print(f"đã tạo {STATE_REL}")


def brief_lines(state):
    lines = []
    ls = state["last_session"]
    if ls["feature"]:
        lines.append(f"phiên trước: {ls['feature']} — {ls['note']}")
    for name, f in state["features"].items():
        if f["step"] == "done":
            continue
        cur = [t for t in f["tasks"] if t["status"] in ("in_progress", "blocked")]
        todo = sum(1 for t in f["tasks"] if t["status"] == "todo")
        s = f"{name}: bước {f['step']}, {todo} task chờ"
        if cur:
            t = cur[0]
            s += f", đang: #{t['id']} {t['title']}" + (f" [BLOCK: {t['blocker']}]" if t["status"] == "blocked" else "")
        lines.append(s)
    if not lines:
        lines.append("chưa có feature nào")
    return lines[:5]


def cmd_show(root, a):
    state = load_state(root)
    if a.json:
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return
    if a.brief:
        print("\n".join(brief_lines(state)))
        return
    for name, f in state["features"].items():
        print(f"{name} [{f['step']}] cập nhật {f['updated']}")
        for t in f["tasks"]:
            extra = f" ({t['blocker']})" if t["status"] == "blocked" else ""
            print(f"  #{t['id']} {t['status']:<11} {t['title']}{extra}")
    ls = state["last_session"]
    if ls["feature"]:
        print(f"phiên trước ({ls['at']}): {ls['feature']} — {ls['note']}")


def cmd_feature(root, a):
    state = load_state(root)
    if a.action == "add":
        if not NAME_RE.match(a.name):
            die("tên feature chỉ gồm [a-z0-9-]")
        if a.name in state["features"]:
            die(f"feature '{a.name}' đã có")
        state["features"][a.name] = {"step": "spec", "tasks": [], "updated": now()}
    elif a.action == "step":
        if a.step not in STEPS:
            die(f"bước phải là một trong {STEPS}")
        f = get_feature(state, a.name)
        f["step"] = a.step
        f["updated"] = now()
    elif a.action == "show":
        print(json.dumps(get_feature(state, a.name), ensure_ascii=False, indent=2))
        return
    save_state(root, state)


def cmd_task(root, a):
    state = load_state(root)
    f = get_feature(state, a.feature)
    if a.action == "add":
        tid = max([t["id"] for t in f["tasks"]], default=0) + 1
        files = [x.strip() for x in (a.files or "").split(",") if x.strip()]
        f["tasks"].append({"id": tid, "title": a.title, "status": "todo", "files": files, "blocker": ""})
        print(tid)
    else:
        t = get_task(f, a.id)
        if a.action == "start":
            t["status"], t["blocker"] = "in_progress", ""
        elif a.action == "done":
            t["status"], t["blocker"] = "done", ""
        elif a.action == "block":
            t["status"], t["blocker"] = "blocked", a.reason
    f["updated"] = now()
    save_state(root, state)


def cmd_session(root, a):
    state = load_state(root)
    get_feature(state, a.feature)
    state["last_session"] = {"feature": a.feature, "note": a.note, "at": now()}
    save_state(root, state)
    append_journal(root, a.feature, a.note)


def cmd_sources(root, a):
    state = load_state(root)
    src = state.get("sources") or empty_sources()
    if a.action == "show":
        print(json.dumps(src, ensure_ascii=False, indent=2))
        return
    manifest = sources_manifest(root)
    state["sources"] = {"commit": git_head(root), "manifest": manifest, "at": now()}
    save_state(root, state)
    print(f"đã đánh mốc {len(manifest)} file trong {SOURCES_REL}")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", default=".")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init").set_defaults(fn=cmd_init)

    s = sub.add_parser("show")
    s.add_argument("--brief", action="store_true")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_show)

    fe = sub.add_parser("feature").add_subparsers(dest="action", required=True)
    x = fe.add_parser("add"); x.add_argument("name")
    x = fe.add_parser("step"); x.add_argument("name"); x.add_argument("step")
    x = fe.add_parser("show"); x.add_argument("name")

    ta = sub.add_parser("task").add_subparsers(dest="action", required=True)
    x = ta.add_parser("add"); x.add_argument("feature"); x.add_argument("title"); x.add_argument("--files")
    for act in ("start", "done"):
        x = ta.add_parser(act); x.add_argument("feature"); x.add_argument("id", type=int)
    x = ta.add_parser("block"); x.add_argument("feature"); x.add_argument("id", type=int); x.add_argument("reason")

    se = sub.add_parser("session").add_subparsers(dest="action", required=True)
    x = se.add_parser("note"); x.add_argument("feature"); x.add_argument("note")

    so = sub.add_parser("sources").add_subparsers(dest="action", required=True)
    so.add_parser("mark"); so.add_parser("show")

    a = p.parse_args(argv)
    fn = {"init": cmd_init, "show": cmd_show, "feature": cmd_feature, "task": cmd_task, "session": cmd_session,
          "sources": cmd_sources}[a.cmd]
    fn(a.root, a)


if __name__ == "__main__":
    main()

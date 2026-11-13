#!/usr/bin/env python3
"""Trạng thái feature/task của dự án. Chỉ sửa state.json qua tool này.

  state.py [--root DIR] init
  state.py [--root DIR] show [--brief] [--json]
  state.py [--root DIR] feature add <tên> | step <tên> <bước> | show <tên>
  state.py [--root DIR] task add <feature> "<title>" [--files a,b] | start <feature> <id>
  state.py [--root DIR] task done <feature> <id> [--skip-tests] [--skip-conform] [--timeout S]
  state.py [--root DIR] task block <feature> <id> "<lý do>"
  state.py [--root DIR] verify <feature> pass|fail [--issue tag ...] [--note "..."]
  state.py [--root DIR] human <feature> list | tick <n> | tick-all
  state.py [--root DIR] followup add <feature> "<việc>" [--source ADR-012] | list [--all] | done <id>
  state.py [--root DIR] session note <feature> "<ghi chú>"
  state.py [--root DIR] sources mark | show        # mốc đồng bộ docs/sources/ (dùng bởi sources.py)

Cổng bằng code (không qua được bằng lời):
  task done   → conform.py trên file của task + test theo diff (affected.py). Trượt → không đánh done.
  feature step <tên> done → verify.md phải hết ô trống ngoài mục "## Người"; ô ở mục Người → human pending.
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

TOOLS = Path(__file__).resolve().parent
STATE_REL = Path("docs/napoleon/state.json")
JOURNAL_REL = Path("docs/napoleon/journal.md")
FEATURES_REL = Path("docs/napoleon/features")
SOURCES_REL = Path("docs/sources")
SOURCES_SKIP = {".gitkeep", ".DS_Store"}
STEPS = ["spec", "plan", "build", "verify", "done"]
TASK_STATUS = ["todo", "in_progress", "done", "blocked"]
NAME_RE = re.compile(r"^[a-z0-9-]+$")
HUMAN_HEADING = re.compile(r"^##\s+Người\s*$", re.M)
BOX_RE = re.compile(r"^\s*- \[( |x|X)\]\s*(.*)$")
VERSION = 2
REPEAT_AT = 2                                  # một loại lỗi lặp tới mức này → bắt chặn bằng máy


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
        state = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as e:
        die(f"state.json hỏng ({e}) — sửa tay hoặc xoá rồi init lại")
    return migrate(state)


def migrate(state):
    """state cũ (version 1) đọc được: thêm khoá mới với giá trị rỗng."""
    state.setdefault("version", VERSION)
    state.setdefault("features", {})
    state.setdefault("followups", [])
    for f in state["features"].values():
        f.setdefault("verify", [])
        f.setdefault("human", [])
        for t in f.get("tasks", []):
            t.setdefault("commit", "")
            t.setdefault("checks", {})
    state["version"] = VERSION
    return state


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
    return {"version": VERSION, "features": {}, "followups": [],
            "last_session": {"feature": "", "note": "", "at": ""}, "sources": empty_sources()}


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


def git(root, *args, timeout=20):
    try:
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None


def git_head(root):
    r = git(root, "rev-parse", "HEAD", timeout=10)
    return r.stdout.strip() if r and r.returncode == 0 else ""


def get_feature(state, name):
    if name not in state["features"]:
        die(f"không có feature '{name}'")
    return state["features"][name]


def get_task(feature, task_id):
    for t in feature["tasks"]:
        if t["id"] == task_id:
            return t
    die(f"không có task id {task_id}")


# ---- cổng ----

def run_tool(root, tool, *args, timeout=600):
    """(rc, output). rc = -1 nếu không chạy được."""
    try:
        r = subprocess.run([sys.executable, str(TOOLS / tool), "--root", str(root), *args],
                           capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        return -1, f"{tool} không chạy được ({e.__class__.__name__})"
    return r.returncode, (r.stdout + r.stderr).strip()


def gate_conform(root, files):
    """(ok, dòng kết quả). Thiếu rules.json → bỏ qua, không chặn."""
    args = ["--files", ",".join(files)] if files else []
    rc, out = run_tool(root, "conform.py", *args, timeout=300)
    last = out.splitlines()[-1] if out else ""
    if rc == 2:
        return True, f"bỏ qua (rules.json: {last})"
    if rc == -1:
        return True, f"bỏ qua ({last})"
    return rc == 0, last or f"exit {rc}"


def gate_tests(root, base, timeout):
    """(ok, dòng kết quả). Lệnh test lấy từ affected.py → toolchain.json."""
    rc, out = run_tool(root, "affected.py", "--base", base or "HEAD", "--json", timeout=120)
    if rc != 0:
        return True, f"bỏ qua (affected.py: {out.splitlines()[-1] if out else rc})"
    try:
        d = json.loads(out)
    except ValueError:
        return True, "bỏ qua (affected.py trả dữ liệu lạ)"
    if not d["command"]:
        return True, f"không có test để chạy ({d['reason']})"
    try:
        r = subprocess.run(d["command"], shell=True, cwd=str(root), capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, f"{d['command']} — không xong ({e.__class__.__name__})"
    tail = [ln for ln in (r.stdout + r.stderr).strip().splitlines() if ln.strip()]
    return r.returncode == 0, f"{d['reason']} → {'pass' if r.returncode == 0 else 'FAIL'}: {tail[-1][:160] if tail else ''}"


def verify_boxes(root, name):
    """(chưa tick ngoài mục Người, chưa tick trong mục Người) hoặc None nếu không có verify.md."""
    p = Path(root) / FEATURES_REL / name / "verify.md"
    if not p.exists():
        return None
    machine, human = [], []
    in_human = False
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("## "):
            in_human = bool(HUMAN_HEADING.match(line))
            continue
        m = BOX_RE.match(line)
        if m and m.group(1) == " ":
            (human if in_human else machine).append(m.group(2).strip())
    return machine, human


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
    open_fu = [x for x in state.get("followups", []) if x["status"] == "open"]
    if open_fu:
        lines.append(f"followup chờ: {len(open_fu)} — state.py followup list")
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
        human = sum(1 for h in f["human"] if not h["done"])
        extra = f", {human} mục Người chờ" if human else ""
        print(f"{name} [{f['step']}] cập nhật {f['updated']}{extra}")
        for t in f["tasks"]:
            note = f" ({t['blocker']})" if t["status"] == "blocked" else ""
            print(f"  #{t['id']} {t['status']:<11} {t['title']}{note}")
    for x in state.get("followups", []):
        if x["status"] == "open":
            print(f"followup #{x['id']} [{x['feature']}] {x['text']}" + (f" ({x['source']})" if x["source"] else ""))
    ls = state["last_session"]
    if ls["feature"]:
        print(f"phiên trước ({ls['at']}): {ls['feature']} — {ls['note']}")


def sync_human(root, state, name):
    """Đồng bộ mục Người trong verify.md vào state (giữ tick đã có)."""
    boxes = verify_boxes(root, name)
    f = state["features"][name]
    if boxes is None:
        return f["human"]
    done = {h["text"]: h["done"] for h in f["human"]}
    p = Path(root) / FEATURES_REL / name / "verify.md"
    items, in_human = [], False
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("## "):
            in_human = bool(HUMAN_HEADING.match(line))
            continue
        m = BOX_RE.match(line)
        if m and in_human:
            text = m.group(2).strip()
            items.append({"text": text, "done": m.group(1) != " " or done.get(text, False)})
    f["human"] = items
    return items


def cmd_feature(root, a):
    state = load_state(root)
    if a.action == "add":
        if not NAME_RE.match(a.name):
            die("tên feature chỉ gồm [a-z0-9-]")
        if a.name in state["features"]:
            die(f"feature '{a.name}' đã có")
        state["features"][a.name] = {"step": "spec", "tasks": [], "verify": [], "human": [], "updated": now()}
    elif a.action == "step":
        if a.step not in STEPS:
            die(f"bước phải là một trong {STEPS}")
        f = get_feature(state, a.name)
        if a.step == "done":
            boxes = verify_boxes(root, a.name)
            if boxes is None:
                die(f"chưa có {FEATURES_REL / a.name / 'verify.md'} — chạy bước verify trước")
            machine, human = boxes
            if machine:
                die(f"verify.md còn {len(machine)} ô chưa tick ngoài mục Người, ví dụ: {machine[0][:70]}\n"
                    f"→ về bước build sửa, hoặc chạy lại lệnh rồi tick")
            left = [h for h in sync_human(root, state, a.name) if not h["done"]]
            if left:
                print(f"{len(left)} mục Người để pending (bạn tự kiểm sau): state.py human {a.name} list")
            repeats = repeated_issues(state)
            if repeats:
                print("lỗi lặp cần chặn bằng máy (chạy /retro): " + ", ".join(f"{k}×{v}" for k, v in repeats))
        f["step"] = a.step
        f["updated"] = now()
    elif a.action == "show":
        print(json.dumps(get_feature(state, a.name), ensure_ascii=False, indent=2))
        return
    save_state(root, state)


def repeated_issues(state):
    """[(tag, số feature gặp)] cho tag xuất hiện ở ≥ REPEAT_AT feature."""
    seen = {}
    for name, f in state["features"].items():
        for r in f.get("verify", []):
            for tag in r.get("issues", []):
                seen.setdefault(tag, set()).add(name)
    return sorted(((t, len(v)) for t, v in seen.items() if len(v) >= REPEAT_AT), key=lambda x: -x[1])


def cmd_task(root, a):
    state = load_state(root)
    f = get_feature(state, a.feature)
    if a.action == "add":
        tid = max([t["id"] for t in f["tasks"]], default=0) + 1
        files = [x.strip() for x in (a.files or "").split(",") if x.strip()]
        f["tasks"].append({"id": tid, "title": a.title, "status": "todo", "files": files, "blocker": "",
                           "commit": "", "checks": {}})
        print(tid)
    elif a.action == "done":
        t = get_task(f, a.id)
        checks, failed = {}, []
        if a.skip_conform:
            checks["conform"] = "bỏ qua theo cờ --skip-conform"
        else:
            ok, msg = gate_conform(root, t.get("files") or [])
            checks["conform"] = msg
            failed += [] if ok else [f"conform: {msg}"]
        if a.skip_tests:
            checks["test"] = "bỏ qua theo cờ --skip-tests"
        else:
            base = last_commit(f, a.id) or "HEAD"
            ok, msg = gate_tests(root, base, a.timeout)
            checks["test"] = msg
            failed += [] if ok else [f"test: {msg}"]
        for k, v in checks.items():
            print(f"{k}: {v}")
        if failed:
            save_state(root, state)            # giữ kết quả kiểm để phiên sau đọc được
            die("task chưa done — sửa rồi chạy lại:\n- " + "\n- ".join(failed))
        t["status"], t["blocker"], t["checks"] = "done", "", checks
        t["commit"] = git_head(root)
    else:
        t = get_task(f, a.id)
        if a.action == "start":
            t["status"], t["blocker"] = "in_progress", ""
        elif a.action == "block":
            t["status"], t["blocker"] = "blocked", a.reason
    f["updated"] = now()
    save_state(root, state)


def last_commit(feature, task_id):
    """sha lúc đóng task trước đó — mốc diff cho test theo thay đổi."""
    prev = [t for t in feature["tasks"] if t["id"] < task_id and t.get("commit")]
    return prev[-1]["commit"] if prev else ""


def cmd_verify(root, a):
    state = load_state(root)
    f = get_feature(state, a.feature)
    f["verify"].append({"at": now(), "result": a.result, "issues": sorted(set(a.issue or [])), "note": a.note or ""})
    f["updated"] = now()
    rounds = len(f["verify"])
    save_state(root, state)
    print(f"verify lần {rounds}: {a.result}" + (f" — {', '.join(sorted(set(a.issue or [])))}" if a.issue else ""))
    if a.result == "fail":
        print(f"→ về bước build: state.py feature step {a.feature} build")
    for tag, n in repeated_issues(state):
        if tag in (a.issue or []):
            print(f"lỗi '{tag}' đã gặp ở {n} feature → /retro để chặn bằng máy")


def cmd_human(root, a):
    state = load_state(root)
    get_feature(state, a.feature)
    items = sync_human(root, state, a.feature)
    if a.action == "list":
        for i, h in enumerate(items, 1):
            print(f"{i}. [{'x' if h['done'] else ' '}] {h['text']}")
        if not items:
            print("không có mục Người trong verify.md")
    elif a.action == "tick-all":
        for h in items:
            h["done"] = True
        print(f"đã tick {len(items)} mục")
    else:
        if not 1 <= a.n <= len(items):
            die(f"số thứ tự phải trong 1..{len(items)}")
        items[a.n - 1]["done"] = True
        print(f"đã tick: {items[a.n - 1]['text']}")
    save_state(root, state)


def cmd_followup(root, a):
    state = load_state(root)
    if a.action == "add":
        get_feature(state, a.feature)
        fid = max([x["id"] for x in state["followups"]], default=0) + 1
        state["followups"].append({"id": fid, "feature": a.feature, "text": a.text, "source": a.source or "",
                                   "status": "open", "at": now()})
        print(fid)
    elif a.action == "list":
        for x in state["followups"]:
            if a.all or x["status"] == "open":
                print(f"#{x['id']} [{x['status']}] {x['feature']}: {x['text']}" + (f" ({x['source']})" if x["source"] else ""))
        if not state["followups"]:
            print("không có followup")
    elif a.action == "done":
        for x in state["followups"]:
            if x["id"] == a.id:
                x["status"] = "done"
                break
        else:
            die(f"không có followup #{a.id}")
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

    sub.add_parser("init")

    s = sub.add_parser("show")
    s.add_argument("--brief", action="store_true")
    s.add_argument("--json", action="store_true")

    fe = sub.add_parser("feature").add_subparsers(dest="action", required=True)
    x = fe.add_parser("add"); x.add_argument("name")
    x = fe.add_parser("step"); x.add_argument("name"); x.add_argument("step")
    x = fe.add_parser("show"); x.add_argument("name")

    ta = sub.add_parser("task").add_subparsers(dest="action", required=True)
    x = ta.add_parser("add"); x.add_argument("feature"); x.add_argument("title"); x.add_argument("--files")
    x = ta.add_parser("start"); x.add_argument("feature"); x.add_argument("id", type=int)
    x = ta.add_parser("done"); x.add_argument("feature"); x.add_argument("id", type=int)
    x.add_argument("--skip-tests", action="store_true"); x.add_argument("--skip-conform", action="store_true")
    x.add_argument("--timeout", type=int, default=900)
    x = ta.add_parser("block"); x.add_argument("feature"); x.add_argument("id", type=int); x.add_argument("reason")

    ve = sub.add_parser("verify")
    ve.add_argument("feature"); ve.add_argument("result", choices=["pass", "fail"])
    ve.add_argument("--issue", action="append", help="nhãn ngắn loại lỗi, lặp được: --issue hardcode --issue ham-dai")
    ve.add_argument("--note")

    hu = sub.add_parser("human")
    hu.add_argument("feature"); hu.add_argument("action", choices=["list", "tick", "tick-all"])
    hu.add_argument("n", type=int, nargs="?")

    fu = sub.add_parser("followup").add_subparsers(dest="action", required=True)
    x = fu.add_parser("add"); x.add_argument("feature"); x.add_argument("text"); x.add_argument("--source")
    x = fu.add_parser("list"); x.add_argument("--all", action="store_true")
    x = fu.add_parser("done"); x.add_argument("id", type=int)

    se = sub.add_parser("session").add_subparsers(dest="action", required=True)
    x = se.add_parser("note"); x.add_argument("feature"); x.add_argument("note")

    so = sub.add_parser("sources").add_subparsers(dest="action", required=True)
    so.add_parser("mark"); so.add_parser("show")

    a = p.parse_args(argv)
    if a.cmd == "human" and a.action == "tick" and a.n is None:
        die("thiếu số thứ tự: state.py human <feature> tick <n>")
    fn = {"init": cmd_init, "show": cmd_show, "feature": cmd_feature, "task": cmd_task, "verify": cmd_verify,
          "human": cmd_human, "followup": cmd_followup, "session": cmd_session, "sources": cmd_sources}[a.cmd]
    fn(a.root, a)


if __name__ == "__main__":
    main()

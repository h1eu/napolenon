#!/usr/bin/env python3
"""Hook PreToolUse: chặn hai việc mà rule bằng chữ không chặn được.

1. Ghi file nguồn bằng Bash (`cat > a.dart`, `sed -i`, `python3 - <<EOF ... open(...,'w')`).
   Phải dùng Write/Edit để hook format/analyze (check.sh) chạy được.
2. Sửa tay docs/napoleon/state.json — trạng thái chỉ đi qua state.py.

  guard.py           # PreToolUse: chặn (2 việc trên)
  guard.py --post    # PostToolUse: nhắc dùng codegraph khi grep tên symbol, không chặn

stdin: JSON của hook. stdout: JSON quyết định / additionalContext. Luôn exit 0.
Mở lối thoát: NAPOLEON_ALLOW_BASH_WRITES=1 (vd: script dựng fixture).
"""
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from imports import LANG_BY_EXT  # noqa: E402

STATE_REL = "docs/napoleon/state.json"
EXT = "|".join(re.escape(e[1:]) for e in LANG_BY_EXT)
PATH = r"[\w./@+-]*\.(?:" + EXT + r")"
TMP = re.compile(r"(^|/)(tmp|temp|scratchpad|\.git|build|node_modules)/")
SHELL_WRITERS = [
    (re.compile(r"(?<![\w>])>>?\s*['\"]?(" + PATH + r")"), "ghi đè bằng '>'"),
    (re.compile(r"\|\s*tee\s+(?:-a\s+)?['\"]?(" + PATH + r")"), "ghi bằng tee"),
    (re.compile(r"\bsed\s+(?:[^|;&]*\s)?-i(?:\.\w+)?\b[^|;&]*?['\"]?(" + PATH + r")"), "sửa tại chỗ bằng sed -i"),
    (re.compile(r"\bperl\s+[^|;&]*-i[^|;&]*?['\"]?(" + PATH + r")"), "sửa tại chỗ bằng perl -i"),
    (re.compile(r"\bcp\s+[^|;&]*\s(" + PATH + r")\s*$"), "chép đè bằng cp"),
    (re.compile(r"\bmv\s+[^|;&]*\s(" + PATH + r")\s*$"), "đổi tên đè bằng mv"),
]
# Trong thân heredoc chỉ soi lệnh ghi của python: chữ như "cat > a.dart" ở đó là nội dung, không phải lệnh.
SCRIPT_WRITERS = [
    (re.compile(r"\bopen\(\s*['\"](" + PATH + r")['\"]\s*,\s*['\"][wa]"), "ghi bằng open(...,'w') trong python"),
    (re.compile(r"['\"](" + PATH + r")['\"]\s*\)?\s*\.write_text\("), "ghi bằng Path.write_text"),
]
HEREDOC = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?")
QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")
DENY_BASH = ("Ghi file nguồn bằng Bash thì hook format/analyze không chạy và diff khó đọc.\n"
             "Dùng Write hoặc Edit cho {path} ({why}).\n"
             "Thật sự cần script: đặt NAPOLEON_ALLOW_BASH_WRITES=1 trước lệnh và nói rõ vì sao.")
DENY_STATE = ("state.json chỉ sửa qua .claude/tools/state.py (feature/task/verify/human/followup).\n"
              "Xem: python3 .claude/tools/state.py --help")
GREP = re.compile(r"(?:^|[|;&]|\$\()\s*(?:grep|rg)\b")          # chỉ khi grep là đầu một lệnh
GREP_SYMBOL = re.compile(r"(?<![\w-])['\"]?([A-Z][a-zA-Z0-9]*[a-z][A-Za-z0-9]*)['\"]?")
GREP_DIR = re.compile(r"(?:^|\s)(?:lib|src|app|main)(?:/|\s|$)")
NUDGE = ("napoleon: tìm symbol '{name}' thì dùng codegraph (codegraph_search / codegraph_callers / codegraph_impact) "
         "thay grep — grep chỉ cho chuỗi văn bản thuần. Xem skill using-codegraph.")


def project_dir():
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()).resolve()


def inside_project(path):
    try:
        return Path(path).resolve().is_relative_to(project_dir()) if hasattr(Path, "is_relative_to") \
            else str(Path(path).resolve()).startswith(str(project_dir()))
    except OSError:
        return False


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                             "permissionDecisionReason": reason}}, ensure_ascii=False))
    sys.exit(0)


def split_heredocs(command):
    """(phần lệnh, [thân heredoc]). Thân heredoc là dữ liệu, soi bằng bộ luật riêng."""
    lines = command.split("\n")
    shell, bodies, marker, body = [], [], None, []
    for line in lines:
        if marker is None:
            shell.append(line)
            m = HEREDOC.search(line)
            if m:
                marker, body = m.group(1), []
        elif line.strip() == marker:
            bodies.append("\n".join(body)); marker, body = None, []
        else:
            body.append(line)
    if marker is not None:
        bodies.append("\n".join(body))
    return "\n".join(shell), bodies


def first_write(text, writers):
    for rx, why in writers:
        for m in rx.finditer(text):
            path = m.group(1)
            if TMP.search("/" + path) or (path.startswith("/") and not inside_project(path)):
                continue                       # thư mục tạm, hoặc file ngoài dự án: kệ
            return path, why
    return None


def bash_target(command):
    """(path, vì sao) của lần ghi file nguồn đầu tiên, hoặc None."""
    shell, bodies = split_heredocs(command)
    hit = first_write(QUOTED.sub(" ", shell), SHELL_WRITERS)   # chuỗi trong đối số là dữ liệu, không phải lệnh
    if hit:
        return hit
    for body in bodies:
        hit = first_write(body, SCRIPT_WRITERS)
        if hit:
            return hit
    return first_write(shell, SCRIPT_WRITERS)


def nudge(command):
    """Câu nhắc codegraph, hoặc None. Chỉ xét đúng đoạn lệnh grep, bỏ qua script có heredoc."""
    if "<<" in command:
        return None
    for m in GREP.finditer(command):
        seg = re.split(r"[|;&]", command[m.end():], 1)[0]
        if not GREP_DIR.search(seg):
            continue
        sym = GREP_SYMBOL.search(seg)
        if sym:
            return NUDGE.format(name=sym.group(1))
    return None


def main():
    try:
        data = json.load(sys.stdin)
    except (ValueError, OSError):
        sys.exit(0)
    tool = data.get("tool_name", "")
    inp = data.get("tool_input") or {}
    if "--post" in sys.argv:
        text = nudge(inp.get("command", "")) if tool in ("Bash", "Grep") else None
        if text:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": text}},
                             ensure_ascii=False))
        sys.exit(0)
    if tool == "Bash" and not os.environ.get("NAPOLEON_ALLOW_BASH_WRITES"):
        hit = bash_target(inp.get("command", ""))
        if hit:
            deny(DENY_BASH.format(path=hit[0], why=hit[1]))
    if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        if Path(inp.get("file_path", "")).as_posix().endswith(STATE_REL):
            deny(DENY_STATE)
    sys.exit(0)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Hook PreToolUse: chặn ba việc mà rule bằng chữ không chặn được.

1. Ghi file nguồn bằng Bash (`cat > a.dart`, `sed -i`, `python3 - <<EOF ... open(...,'w')`).
   Phải dùng Write/Edit để hook format/analyze (check.sh) chạy được.
2. Sửa tay docs/napoleon/state.json — trạng thái chỉ đi qua state.py.
3. grep/rg đệ quy (hoặc tool Grep) trong thư mục code tìm đúng một tên symbol đã có trong index codegraph.
   Câu nhắc sau khi grep xong không đổi được thói quen; chặn kèm lệnh thay thế thì có.

  guard.py           # PreToolUse: chặn (3 việc trên)
  guard.py --post    # PostToolUse: nhắc dùng codegraph cho các lần grep symbol còn lọt, không chặn

stdin: JSON của hook. stdout: JSON quyết định / additionalContext. Luôn exit 0.
Mở lối thoát: NAPOLEON_ALLOW_BASH_WRITES=1 (vd: script dựng fixture); NAPOLEON_ALLOW_GREP=1 đặt trước lệnh grep.
"""
import json
import os
import re
import shlex
import shutil
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cgdb import open_db  # noqa: E402
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
# Chỉ chặn tên chắc chắn là symbol (≥ 2 bướu): 'Future' hay 'Settings' có thể là chữ thường trong UI.
BARE_SYMBOL = re.compile(r"(?:[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]*)+|[a-z][a-z0-9]*(?:[A-Z][a-z0-9]*)+)")
CODE_ROOTS = {"lib", "src", "app", "main", "test", "tests", "packages", "pkg", "cmd", "internal"}
GREP_VALUE_FLAGS = {"-A", "-B", "-C", "-m", "-f", "-g", "-t", "-T", "--include", "--exclude", "--exclude-dir",
                    "--glob", "--type", "--max-count", "--context"}
ALLOW_GREP = "NAPOLEON_ALLOW_GREP"
DENY_GREP = ("'{name}' là tên symbol — tìm đệ quy trong code thì hỏi codegraph, không grep.\n"
             "- Định nghĩa ở đâu: Bash `codegraph query {name}`\n"
             "- Ai gọi, sửa thì ảnh hưởng gì: codegraph_callers / codegraph_impact (chưa thấy tool → ToolSearch "
             "\"select:mcp__codegraph__codegraph_search,mcp__codegraph__codegraph_callers,"
             "mcp__codegraph__codegraph_impact\")\n"
             "Grep trong một file cụ thể vẫn được. Cần tìm chữ này như văn bản (comment, chuỗi, file chưa index): "
             "Bash với " + ALLOW_GREP + "=1 đặt trước lệnh grep.")


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


def indexed(name):
    """Symbol do dự án định nghĩa và index đã có. API thư viện ngoài (showModalBottomSheet…) không có node:
    tìm nơi dùng nó thì grep mới đúng, nên không chặn."""
    if shutil.which("codegraph") is None:
        return False
    with open_db(project_dir()) as con:
        if con is None:
            return False
        try:
            return con.execute("SELECT 1 FROM nodes WHERE name = ? AND kind NOT IN ('import', 'file') LIMIT 1",
                               (name,)).fetchone() is not None
        except sqlite3.Error:
            return False


def is_code_dir(path):
    """Thư mục code (hoặc glob trong đó). Một file cụ thể thì không: grep trong file là đọc, không phải tìm."""
    p = Path(path)
    if p.is_absolute():
        try:
            p = p.resolve().relative_to(project_dir())
        except (ValueError, OSError):
            return False
    parts = [x for x in p.parts if x != "."]
    if not parts:
        return True
    return parts[0] in CODE_ROOTS and ("*" in path or not p.suffix)


def grep_args(tokens):
    """(cờ ngắn gộp, mẫu tìm, [đường dẫn]) của một lệnh grep/rg đã tách token."""
    short, pattern, paths, skip = "", None, [], False
    for tok in tokens:
        if skip:
            skip = False
        elif tok == "-e":
            pattern, skip = "", False
        elif tok in GREP_VALUE_FLAGS:
            skip = True
        elif tok.startswith("--"):
            short += "r" if tok == "--recursive" else "i" if tok == "--ignore-case" else ""
        elif tok.startswith("-") and len(tok) > 1:
            short += tok[1:]
        elif not pattern:
            pattern = tok
        else:
            paths.append(tok)
    return short, pattern, paths


def bash_symbol_grep(command):
    """Tên symbol nếu lệnh là grep/rg đệ quy tìm đúng một tên symbol trong thư mục code, không thì None."""
    if "<<" in command or ALLOW_GREP + "=1" in command:
        return None
    for m in GREP.finditer(command):
        head = command[:m.start() + 1].rstrip()
        if head.endswith("|") and not head.endswith("||"):
            continue                           # lọc output của lệnh khác, không phải tìm trong code
        lex = shlex.shlex(command[m.end():], posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        tokens = []
        try:
            for tok in lex:
                if tok and set(tok) <= set(";|&()<>"):
                    break
                tokens.append(tok)
        except ValueError:
            continue
        short, pattern, paths = grep_args(tokens)
        recursive = "rg" in m.group(0) or "r" in short or "R" in short
        if not recursive or "i" in short or not pattern or not BARE_SYMBOL.fullmatch(pattern):
            continue
        if not paths and "rg" not in m.group(0):
            continue
        if all(is_code_dir(p) for p in paths):
            return pattern
    return None


def tool_symbol_grep(inp):
    pattern = inp.get("pattern") or ""
    if inp.get("-i") or not BARE_SYMBOL.fullmatch(pattern):
        return None
    return pattern if is_code_dir(inp.get("path") or ".") else None


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
    if tool in ("Bash", "Grep") and not os.environ.get(ALLOW_GREP):
        name = bash_symbol_grep(inp.get("command", "")) if tool == "Bash" else tool_symbol_grep(inp)
        if name and indexed(name):
            deny(DENY_GREP.format(name=name))
    if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        if Path(inp.get("file_path", "")).as_posix().endswith(STATE_REL):
            deny(DENY_STATE)
    sys.exit(0)


if __name__ == "__main__":
    main()

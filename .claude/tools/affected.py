#!/usr/bin/env python3
"""Chọn test cần chạy cho một thay đổi: file nào đổi → ai import chúng (bắc cầu) → test nào chạm tới.

  affected.py [--root DIR] [--base REF] [--files a,b] [--json] [--max-ratio 0.6]

In ra lệnh chạy test (theo toolchain.json) và lý do. Không có git, không chắc, hoặc diện ảnh hưởng
quá rộng → in lệnh chạy toàn bộ. Dùng sau mỗi task; bước verify vẫn chạy toàn bộ.

toolchain.json dùng thêm (tuỳ chọn):
  "test_one":    lệnh chạy một số file, {files} = danh sách cách nhau khoảng trắng (mặc định "<test> {files}")
  "test_files":  glob file test (mặc định "**/*_test.*", "**/*Test.*", "**/*.spec.*", "test/**", "tests/**")
  "full_test_when": glob mà hễ đụng tới là chạy toàn bộ (pubspec, DI, router, theme, l10n, code sinh)
  "affected_hubs":  glob file "tổng đài" import gần hết app (router, DI). Lan tới hub thì dừng, không đi tiếp
                    sang ai import hub — nếu không, sửa một màn kéo theo mọi test dựng app. File code sinh
                    (rules.json exclude) luôn là hub. Sửa chính hub → nên nằm trong full_test_when.
"""
import argparse
import json
import shlex
import subprocess
import sys
from collections import defaultdict, deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit  # noqa: E402
from globs import excluded_globs, match  # noqa: E402

TOOLCHAIN_REL = Path(".claude/instructions/toolchain.json")
TEST_GLOBS = ["**/*_test.*", "**/*Test.*", "**/*.spec.*", "**/*.test.*", "test/**", "tests/**"]
KEEP_DIRS = {"test", "tests"}                  # audit bỏ test khi soi kiến trúc; ở đây thì cần


def toolchain(root):
    p = Path(root) / TOOLCHAIN_REL
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        print(f"{TOOLCHAIN_REL} không đọc được — chạy toàn bộ", file=sys.stderr)
        return {}


def changed_files(root, base):
    """(list file tương đối, lý do lỗi). Lỗi → list rỗng và lý do khác None."""
    def git(*args):
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=30)
    try:
        if git("rev-parse", "--git-dir").returncode != 0:
            return [], "không phải git repo"
        if git("rev-parse", "--verify", "--quiet", base).returncode != 0:
            return [], f"không có mốc git '{base}'"
        out = set(git("diff", "--name-only", base, "--").stdout.split())
        out |= set(git("ls-files", "--others", "--exclude-standard").stdout.split())
    except (OSError, subprocess.TimeoutExpired) as e:
        return [], f"git lỗi ({e.__class__.__name__})"
    return sorted(out), None


def dependents(root):
    """file → set(file import nó trực tiếp), tính cả thư mục test."""
    skip = audit.SKIP_DIRS - KEEP_DIRS
    files, edges, *_ = audit.edges_from_scan(Path(root), skip)
    rev = defaultdict(set)
    for src, dst in edges:
        rev[dst].add(src)
    return files, rev


def closure(seeds, rev, hubs=()):
    """Mọi file bắc cầu import seeds, kể cả seeds. Tới hub (không phải seed) thì ghi nhận nhưng không lan tiếp."""
    seeds = set(seeds)
    seen, q = set(seeds), deque(seeds)
    while q:
        cur = q.popleft()
        if cur not in seeds and any(match(cur, h) for h in hubs):
            continue
        for nxt in rev.get(cur, ()):
            if nxt not in seen:
                seen.add(nxt); q.append(nxt)
    return seen


def is_test(rel, globs):
    return any(match(rel, g) for g in globs)


def plan(root, base, files_arg, max_ratio):
    """{mode: all|some, tests[], reason, command}."""
    tc = toolchain(root)
    test_globs = tc.get("test_files") or TEST_GLOBS
    full_cmd = tc.get("test", "")
    one_cmd = tc.get("test_one") or (full_cmd + " {files}" if full_cmd else "")

    def whole(reason):
        return {"mode": "all", "tests": [], "reason": reason, "command": full_cmd}

    if files_arg is not None:
        changed, err = [x.strip() for x in files_arg.split(",") if x.strip()], None
    else:
        changed, err = changed_files(root, base)
    if err:
        return whole(err)
    if not changed:
        return {"mode": "some", "tests": [], "reason": "không có file nào đổi", "command": ""}
    for g in tc.get("full_test_when", []):
        hit = [c for c in changed if match(c, g)]
        if hit:
            return whole(f"{hit[0]} khớp full_test_when '{g}'")

    files, rev = dependents(root)
    known = set(files)
    unknown = [c for c in changed if c not in known and Path(c).suffix in audit.LANG_BY_EXT]
    if unknown:
        return whole(f"{unknown[0]} chưa có trong đồ thị import (file mới hoặc ngoài phạm vi)")
    all_tests = {f for f in files if is_test(f, test_globs)}
    hubs = list(tc.get("affected_hubs", [])) + excluded_globs(root)
    tests = sorted(f for f in closure([c for c in changed if c in known], rev, hubs) if f in all_tests)
    if not one_cmd:
        return whole("toolchain.json chưa có lệnh test")
    if all_tests and len(tests) > len(all_tests) * max_ratio:
        return whole(f"{len(tests)}/{len(all_tests)} file test bị ảnh hưởng (> {int(max_ratio * 100)}%)")
    if not tests:
        return {"mode": "some", "tests": [], "reason": f"{len(changed)} file đổi, không test nào chạm tới", "command": ""}
    return {"mode": "some", "tests": tests, "reason": f"{len(changed)} file đổi → {len(tests)}/{len(all_tests)} file test",
            "command": one_cmd.replace("{files}", " ".join(shlex.quote(t) for t in tests))}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", default=".")
    p.add_argument("--base", default="HEAD", help="mốc git để so (mặc định HEAD: mọi thay đổi chưa commit)")
    p.add_argument("--files", help="dùng danh sách này thay cho git diff")
    p.add_argument("--max-ratio", type=float, default=0.6)
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    d = plan(Path(a.root).resolve(), a.base, a.files, a.max_ratio)
    if a.json:
        print(json.dumps(d, ensure_ascii=False, indent=2))
        return
    print(f"{'toàn bộ' if d['mode'] == 'all' else 'theo diff'}: {d['reason']}")
    for t in d["tests"]:
        print(f"- {t}")
    if d["command"]:
        print(d["command"])


if __name__ == "__main__":
    main()

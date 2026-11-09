#!/usr/bin/env python3
"""Tài liệu nguồn (docs/sources/) đổi gì so với mốc đồng bộ cuối, và harness trích dẫn chúng ở đâu.

  sources.py [--root DIR] diff [--json] [--max-diff-lines N]

Mốc lấy từ state.json (state.py sources mark). Chưa có mốc → mọi file coi là mới.
File đổi: so sha256 với manifest ở mốc. Có git và mốc có commit → in thêm hunk `git diff`.
Nơi trích dẫn: dòng trong .claude/instructions/, docs/napoleon/features.md, docs/napoleon/features/*/
nhắc tới đường dẫn hoặc tên file đổi. Tool không đoán điểm lệch; việc đó là của người đọc.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from state import SOURCES_REL, STATE_REL, empty_sources, sources_manifest  # noqa: E402

REF_GLOBS = [
    (".claude/instructions", "**/*.md"),
    ("docs/napoleon", "features.md"),
    ("docs/napoleon/features", "*/brief.md"),
    ("docs/napoleon/features", "*/spec.md"),
    ("docs/napoleon/features", "*/plan.md"),
]


def load_sources(root):
    p = Path(root) / STATE_REL
    if not p.exists():
        return None, None
    state = json.loads(p.read_text(encoding="utf-8"))
    return state, state.get("sources") or empty_sources()


def git_diff(root, commit, path, max_lines):
    if not commit:
        return []
    try:
        r = subprocess.run(["git", "-C", str(root), "diff", "--no-color", commit, "--", path],
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return []
    if r.returncode != 0:
        return []
    lines = [ln for ln in r.stdout.splitlines() if ln[:1] in "+-@" and not ln.startswith(("+++", "---"))]
    if len(lines) > max_lines:
        lines = lines[:max_lines] + [f"… còn {len(lines) - max_lines} dòng, xem: git diff {commit[:8]} -- {path}"]
    return lines


def find_references(root, paths):
    """{path đổi: [file:dòng: nội dung]} — khớp đường dẫn đầy đủ hoặc tên file."""
    keys = {p: {p, Path(p).name} for p in paths}
    refs = {p: [] for p in paths}
    for base, pattern in REF_GLOBS:
        for f in sorted((Path(root) / base).glob(pattern)):
            if not f.is_file():
                continue
            rel = f.relative_to(root).as_posix()
            for i, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                for p, needles in keys.items():
                    if any(n in line for n in needles):
                        refs[p].append(f"{rel}:{i}: {line.strip()}")
    return refs


def open_features(state):
    out = []
    for name, f in (state or {}).get("features", {}).items():
        if f.get("step") != "done":
            cur = [t for t in f.get("tasks", []) if t.get("status") == "in_progress"]
            out.append({"name": name, "step": f.get("step"), "in_progress": cur[0]["title"] if cur else ""})
    return out


def compute(root, max_lines):
    state, src = load_sources(root)
    if state is None:
        return {"error": f"chưa có {STATE_REL} — chạy /start-build trước"}
    old = src.get("manifest", {})
    new = sources_manifest(root)
    has_mark = bool(src.get("at"))
    added = sorted(p for p in new if p not in old)
    removed = sorted(p for p in old if p not in new)
    changed = sorted(p for p in new if p in old and old[p] != new[p])
    affected = added + changed + removed
    return {
        "mark": {"at": src.get("at", ""), "commit": src.get("commit", ""), "files": len(old)} if has_mark else None,
        "sources_dir": SOURCES_REL.as_posix(),
        "total_files": len(new),
        "added": added, "changed": changed, "removed": removed,
        "diff": {p: git_diff(root, src.get("commit", ""), p, max_lines) for p in changed + added + removed},
        "references": find_references(root, affected),
        "open_features": open_features(state),
    }


def print_text(r):
    if "error" in r:
        print(r["error"], file=sys.stderr)
        sys.exit(1)
    m = r["mark"]
    print(f"== Mốc: " + (f"{m['at']} · commit {m['commit'][:8] or '(không git)'} · {m['files']} file"
                         if m else "CHƯA CÓ — mọi file coi là mới"))
    print(f"== {r['sources_dir']}: {r['total_files']} file · mới {len(r['added'])} · đổi {len(r['changed'])} · xoá {len(r['removed'])}")
    for label, key in (("MỚI", "added"), ("ĐỔI", "changed"), ("XOÁ", "removed")):
        for p in r[key]:
            print(f"\n-- {label} {p}")
            for ln in r["diff"].get(p, []):
                print(f"   {ln}")
            refs = r["references"].get(p, [])
            print(f"   trích dẫn ({len(refs)}):" if refs else "   trích dẫn: không nơi nào trong harness nhắc tới")
            for ref in refs:
                print(f"     {ref}")
    if not (r["added"] or r["changed"] or r["removed"]):
        print("\nKhông có gì đổi so với mốc.")
    print("\n== Feature chưa done:")
    if not r["open_features"]:
        print("   (không có)")
    for f in r["open_features"]:
        print(f"   {f['name']}: bước {f['step']}" + (f", đang: {f['in_progress']}" if f["in_progress"] else ""))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", default=".")
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("diff")
    d.add_argument("--json", action="store_true")
    d.add_argument("--max-diff-lines", type=int, default=80)
    a = p.parse_args(argv)
    r = compute(a.root, a.max_diff_lines)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
        sys.exit(1 if "error" in r else 0)
    print_text(r)


if __name__ == "__main__":
    main()

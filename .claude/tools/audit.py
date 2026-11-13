#!/usr/bin/env python3
"""Dependency audit: cycles, phụ thuộc giữa module, vi phạm ranh giới, dep ngoài, file mồ côi.

  audit.py [--root DIR] [--source auto|codegraph|scan] [--module-depth N] [--json]

Nguồn cạnh phụ thuộc file → file:
  codegraph  .codegraph/codegraph.db — mọi cạnh khác 'contains' giữa hai node ở hai file khác nhau
             (calls/references/instantiates/implements/extends). Cạnh 'imports' của codegraph trỏ vào
             node import cùng file nên không dùng cho phụ thuộc; node kind=import dùng để đếm dep ngoài.
  scan       regex import (imports.py). Dart: đường dẫn + package:; Kotlin: theo khai báo `package`.
             Swift: import chỉ là framework ngoài, không có phụ thuộc file↔file.
Output luôn ghi rõ nguồn và ghi chú ngôn ngữ nào scan chưa resolve được. Không trộn.
"""
import argparse
import json
import os
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cgdb import DB_REL, open_db  # noqa: E402
from globs import excluded_globs, is_excluded  # noqa: E402
from imports import LANG_BY_EXT, read_imports  # noqa: E402

MODULE_MAP_REL = Path(".claude/instructions/module-map.md")
SKIP_DIRS = {".git", ".codegraph", ".claude", "build", "node_modules", ".dart_tool", ".gradle", ".idea", "test", "tests",
             ".agents", ".ai", ".superpowers", "raw"}
# Ngôn ngữ mà "không ai import" không có nghĩa là mồ côi khi scan: Kotlin cùng package không cần import, Swift cùng module không cần import
NO_ORPHAN_BY_IMPORT = {"kotlin": "Kotlin cùng package không cần import → mồ côi không tính từ scan, chỉ tin codegraph",
                       "swift": "Swift cùng module không cần import → mồ côi không tính từ scan, chỉ tin codegraph"}
SKIP_PREFIXES = ("docs/sources/",)        # tài liệu người dùng đưa, không phải code dự án
ENTRY_NAMES = {"main.dart", "main.py", "Main.kt", "App.swift", "main.swift", "index.ts", "index.tsx", "index.js",
               "main.ts", "main.js", "main.kt", "App.kt", "MainActivity.kt", "MainApplication.kt"}

SRC_COL = re.compile(r"^(source|src|from)(_id)?$", re.I)
DST_COL = re.compile(r"^(target|dst|to)(_id)?$", re.I)
PATH_COL = re.compile(r"^(path|file_path|file|filepath)$", re.I)
KIND_COL = re.compile(r"^(kind|type|edge_type|relation)$", re.I)
KT_PACKAGE = re.compile(r"^\s*package\s+([\w.]+)", re.M)
KT_DECL = re.compile(r"^\s*(?:(?:public|internal|private|open|abstract|sealed|data|enum|annotation|inline|value|expect|actual)\s+)*"
                     r"(?:class|object|interface|fun|val|var|typealias)\s+(?:<[^>]*>\s*)?(\w+)", re.M)


# ---------- file ----------

def in_scope(rel, skip=SKIP_DIRS):
    return not (set(Path(rel).parts[:-1]) & skip) and not rel.startswith(SKIP_PREFIXES)


def source_files(root, skip=SKIP_DIRS):
    out = []
    for p in root.rglob("*"):
        if p.is_file() and p.suffix in LANG_BY_EXT and in_scope(p.relative_to(root).as_posix(), skip):
            out.append(p.relative_to(root).as_posix())
    return sorted(out)


def package_name(root):
    pub = root / "pubspec.yaml"
    if pub.exists():
        m = re.search(r"^name:\s*(\S+)", pub.read_text(encoding="utf-8", errors="replace"), re.M)
        if m:
            return m.group(1)
    return None


def external_key(imp):
    if imp.startswith("package:"):
        return "package:" + imp[len("package:"):].split("/")[0]
    if imp.startswith("dart:"):
        return imp
    return imp.split("/")[0].split(".")[0] if "/" in imp else imp.split(".")[0]


def norm_rel(base_dir, imp):
    parts = []
    for part in (Path(base_dir) / imp).parts:
        if part == "..":
            if parts:
                parts.pop()
        elif part != ".":
            parts.append(part)
    return "/".join(parts)


# ---------- nguồn: scan ----------

class ScanIndex:
    """Chỉ mục để resolve import: Dart theo path/package, Kotlin theo package + symbol."""

    def __init__(self, root, files):
        self.root = root
        self.files = files
        self.fileset = set(files)
        self.pkg = package_name(root)
        self.kt_pkg = defaultdict(list)   # package → [file]
        self.kt_sym = {}                  # (package, symbol) → file
        for rel in files:
            if LANG_BY_EXT[Path(rel).suffix] != "kotlin":
                continue
            text = (root / rel).read_text(encoding="utf-8", errors="replace")
            m = KT_PACKAGE.search(text)
            if not m:
                continue
            pkg = m.group(1)
            self.kt_pkg[pkg].append(rel)
            for d in KT_DECL.finditer(text):
                self.kt_sym.setdefault((pkg, d.group(1)), rel)
        self.kt_roots = {p.split(".")[0] for p in self.kt_pkg}

    def resolve(self, rel, imp, lang):
        """Trả về list file đích trong repo; [] = dep ngoài; None = không biết (ngôn ngữ chưa hỗ trợ)."""
        if lang == "dart":
            if imp.startswith("package:"):
                name, _, rest = imp[len("package:"):].partition("/")
                if self.pkg and name == self.pkg:
                    cand = f"lib/{rest}"
                    return [cand] if cand in self.fileset else []
                return []
            if imp.startswith("dart:"):
                return []
            cand = norm_rel(Path(rel).parent, imp)
            for c in (cand, cand + ".dart"):
                if c in self.fileset:
                    return [c]
            return []
        if lang == "kotlin":
            pkg, _, sym = imp.rpartition(".")
            if sym == "*":
                return list(self.kt_pkg.get(pkg, []))
            hit = self.kt_sym.get((pkg, sym))
            if hit:
                return [hit]
            if pkg in self.kt_pkg:
                return list(self.kt_pkg[pkg])          # cùng package nội bộ, symbol lồng/ngoài regex
            if imp.split(".")[0] in self.kt_roots:
                return list(self.kt_pkg.get(imp, []))  # import cả package nội bộ
            return []
        if lang == "swift":
            return []                                  # import Swift = framework ngoài
        if lang == "py":
            dotted = imp.replace(".", "/")
            for c in (dotted + ".py", dotted + "/__init__.py"):
                if c in self.fileset:
                    return [c]
            return []
        if lang == "ts":
            if imp.startswith("."):
                cand = norm_rel(Path(rel).parent, imp)
                for c in (cand, cand + ".ts", cand + ".tsx", cand + ".js", cand + "/index.ts", cand + "/index.js"):
                    if c in self.fileset:
                        return [c]
                return []
            return []
        return None


def edges_from_scan(root, skip=SKIP_DIRS):
    """Trả về (files, edges, external, notes, unreliable_langs)."""
    files = source_files(root, skip)
    idx = ScanIndex(root, files)
    edges, external = [], defaultdict(int)
    seen, resolved_langs = defaultdict(int), set()
    for rel in files:
        lang = LANG_BY_EXT[Path(rel).suffix]
        for imp in read_imports(root / rel):
            seen[lang] += 1
            targets = idx.resolve(rel, imp, lang)
            if targets is None:
                continue
            if targets:
                resolved_langs.add(lang)
                for t in targets:
                    if t != rel:
                        edges.append((rel, t))
            elif not imp.startswith("."):
                external[external_key(imp)] += 1
    # Ngôn ngữ có import nhưng không resolve được cái nào (trừ swift: không có file↔file là bình thường)
    unreliable = sorted(l for l in seen if l not in resolved_langs and l != "swift")
    notes = [f"scan không resolve import {l} ({seen[l]} import) — orphans/module_edges cho {l} không tin được"
             for l in unreliable]
    orphan_unreliable = set(unreliable)
    for l, why in NO_ORPHAN_BY_IMPORT.items():
        if any(LANG_BY_EXT[Path(f).suffix] == l for f in files):
            notes.append(why)
            orphan_unreliable.add(l)
    return files, sorted(set(edges)), dict(external), notes, orphan_unreliable


# ---------- nguồn: codegraph ----------

def _norm_path(root, pth):
    if os.path.isabs(pth):
        pth = os.path.relpath(os.path.realpath(pth), root)
    return Path(pth).as_posix()


def _read_graph(root, con):
    """(nodes, raw_edges, external) từ DB; (None, None, None) nếu schema không nhận dạng được."""
    tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    cols = {t: [c[1] for c in con.execute(f'PRAGMA table_info("{t}")')] for t in tables}

    edge_t = s_col = d_col = k_col = None
    for t, cs in cols.items():
        s = next((c for c in cs if SRC_COL.match(c)), None)
        d = next((c for c in cs if DST_COL.match(c)), None)
        k = next((c for c in cs if KIND_COL.match(c)), None)
        if s and d and k:
            edge_t, s_col, d_col, k_col = t, s, d, k
    if not edge_t:
        return None, None, None
    raw = con.execute(f'SELECT "{s_col}", "{d_col}", "{k_col}" FROM "{edge_t}"').fetchall()
    if not raw:
        return None, None, None

    # Bảng node: thử mọi bảng có id + cột path; chọn bảng resolve được nhiều cạnh nhất
    best = None
    for t, cs in cols.items():
        pc = next((c for c in cs if PATH_COL.match(c)), None)
        if not pc or "id" not in [c.lower() for c in cs]:
            continue
        nodes = {}
        for nid, pth in con.execute(f'SELECT id, "{pc}" FROM "{t}"'):
            if pth:
                nodes[nid] = _norm_path(root, pth)
        hit = sum(1 for s, d, _ in raw if s in nodes and d in nodes)
        if best is None or hit > best[0]:
            best = (hit, t, nodes, cs)
    if best is None or best[0] * 2 < len(raw):
        return None, None, None
    _, node_t, nodes, ncs = best

    # Dep ngoài: node kind=import, name không thuộc gốc package nội bộ
    external = defaultdict(int)
    lc = [c.lower() for c in ncs]
    if "kind" in lc and "name" in lc:
        qn = "qualified_name" if "qualified_name" in lc else "name"
        roots = {str(q).split(".")[0] for (q,) in con.execute(
            f'SELECT "{qn}" FROM "{node_t}" WHERE lower(kind) IN (\'class\',\'interface\',\'object\',\'function\',\'enum\') AND "{qn}" IS NOT NULL')}
        pkg = package_name(root)
        for (name,) in con.execute(f'SELECT name FROM "{node_t}" WHERE lower(kind) = \'import\' AND name IS NOT NULL'):
            name = str(name)
            if name.startswith("package:"):
                if pkg and name[len("package:"):].split("/")[0] == pkg:
                    continue                        # package nội bộ của chính dự án
            elif name.startswith(".") or "/" in name or name.split(".")[0] in roots:
                continue                            # import theo đường dẫn hoặc package nội bộ
            external[external_key(name)] += 1
# Cùng phạm vi với scan: bỏ test, tool của harness, thư mục build — codegraph index cả repo
    return nodes, raw, dict(external)


def edges_from_codegraph(root):
    """Trả về (files, edges, external) hoặc None nếu không có DB / schema không nhận dạng được."""
    with open_db(root) as con:
        if con is None:
            return None
        try:
            nodes, raw, external = _read_graph(root, con)
        except sqlite3.Error:
            return None
    if nodes is None:
        return None
    fileset = {p for p in nodes.values() if not p.startswith("..") and in_scope(p) and (root / p).is_file()}
    files = sorted(fileset)
    edges = set()
    for s, d, kind in raw:
        if str(kind).lower() == "contains":
            continue
        sp, dp = nodes.get(s), nodes.get(d)
        if sp and dp and sp != dp and sp in fileset and dp in fileset:
            ls, ld = LANG_BY_EXT.get(Path(sp).suffix), LANG_BY_EXT.get(Path(dp).suffix)
            if ls and ld and ls != ld:
                continue                       # cạnh khác ngôn ngữ là do codegraph khớp theo tên, không phải phụ thuộc
            edges.add((sp, dp))
    if not edges:
        return None  # có cạnh nhưng không suy ra được phụ thuộc file↔file → schema không như ta nghĩ
    return files, sorted(edges), external


# ---------- phân tích ----------

def module_of(rel, depth):
    parts = Path(rel).parent.parts[:depth]
    return "/".join(parts) if parts else "."


def find_cycles(files, edges):
    """SCC ≥ 2 bằng Tarjan; trả về list các path."""
    graph = defaultdict(list)
    for s, d in edges:
        graph[s].append(d)
    index, low, on, stack, out = {}, {}, set(), [], []
    counter = [0]

    def strong(v):
        index[v] = low[v] = counter[0]; counter[0] += 1
        stack.append(v); on.add(v)
        for w in graph[v]:
            if w not in index:
                strong(w); low[v] = min(low[v], low[w])
            elif w in on:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp = []
            while True:
                w = stack.pop(); on.discard(w); comp.append(w)
                if w == v:
                    break
            if len(comp) > 1:
                out.append(sorted(comp))

    sys.setrecursionlimit(max(10000, sys.getrecursionlimit()))
    for v in list(files):
        if v not in index:
            strong(v)
    return sorted(out)


def allowed_from_module_map(root):
    p = root / MODULE_MAP_REL
    if not p.exists():
        return None
    text = p.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"^##\s+Phụ thuộc cho phép\s*$(.*?)(?=^##\s|\Z)", text, re.M | re.S)
    if not m:
        return None
    allowed = set()
    for line in m.group(1).splitlines():
        cells = [c.strip().strip("`").strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2 or not cells[0] or set(cells[0]) <= {"-", ":"} or cells[0].lower() in ("từ", "tu", "from"):
            continue
        allowed.add((cells[0], cells[1]))
    return allowed


def collect(root, source="auto", module_depth=2):
    root = Path(root).resolve()
    data = used = None
    notes, unreliable, incoming = [], set(), set()
    if source in ("auto", "codegraph"):
        data = edges_from_codegraph(root)
        used = "codegraph" if data else None
    if data is None:
        if source == "codegraph":
            print("không đọc được codegraph.db — dùng --source scan hoặc chạy: codegraph init", file=sys.stderr)
            sys.exit(2)
        files, edges, external, notes, unreliable = edges_from_scan(root)
        used = "scan"
    else:
        files, edges, external = data
        notes.append("codegraph: mồ côi = không ai import (scan) và không có cạnh tới trong graph; DI, expect/actual "
                     "(KMP), navigation, reflection vẫn có thể gây dương tính giả — xác nhận bằng codegraph_callers "
                     "trước khi xoá")
        incoming |= {d for _, d in edges_from_scan(root)[1]}   # chỉ để bớt mồ côi giả; cạnh module vẫn thuần codegraph

    # Code sinh (rules.json exclude) không báo cycle hay mồ côi, nhưng cạnh từ nó vẫn giữ để tính mồ côi:
    # file DI sinh ra là nơi duy nhất "dùng" class đăng ký, bỏ cạnh đó sẽ sinh mồ côi giả.
    ex = excluded_globs(root)
    skip = {f for f in files if is_excluded(f, ex)}
    if skip:
        files = [f for f in files if f not in skip]
        notes.append(f"bỏ qua {len(skip)} file khớp rules.json exclude (code sinh) khỏi cycles và mồ côi")
    cycle_edges = [(s, d) for s, d in edges if s not in skip and d not in skip]

    mod_edges = defaultdict(set)
    for s, d in edges:
        ms, md = module_of(s, module_depth), module_of(d, module_depth)
        if ms != md:
            mod_edges[ms].add(md)
    allowed = allowed_from_module_map(root)
    violations = []
    if allowed is not None:
        for ms, dsts in mod_edges.items():
            for md in dsts:
                if (ms, md) not in allowed:
                    violations.append({"from": ms, "to": md})
    imported = incoming | {d for _, d in edges}
    orphans = [f for f in files if f not in imported and Path(f).name not in ENTRY_NAMES
               and Path(f).suffix != ".kts"                          # build script không ai import là bình thường
               and LANG_BY_EXT.get(Path(f).suffix) is not None      # file không phải code (xml, sq…) không tính
               and LANG_BY_EXT[Path(f).suffix] not in unreliable]
    return {
        "source": used,
        "notes": notes,
        "files": len(files),
        "cycles": find_cycles(files, cycle_edges),
        "module_edges": {k: sorted(v) for k, v in sorted(mod_edges.items())},
        "boundary_violations": sorted(violations, key=lambda x: (x["from"], x["to"])),
        "external": dict(sorted(external.items())),
        "orphans": orphans,
    }


def to_markdown(d):
    L = [f"source: {d['source']}"] + [f"ghi chú: {n}" for n in d.get("notes", [])] + ["", "## Số liệu", "",
         f"- File: {d['files']}", f"- Cycles: {len(d['cycles'])}",
         f"- Vi phạm ranh giới: {len(d['boundary_violations'])}",
         f"- Dep ngoài: {len(d['external'])} gói", f"- File mồ côi: {len(d['orphans'])}", ""]
    if d["cycles"]:
        L += ["### Cycles"] + [f"- {' ↔ '.join(c)}" for c in d["cycles"]] + [""]
    if d["module_edges"]:
        L += ["### Phụ thuộc giữa module"] + [f"- {k} → {', '.join(v)}" for k, v in d["module_edges"].items()] + [""]
    if d["boundary_violations"]:
        L += ["### Vi phạm ranh giới"] + [f"- {v['from']} → {v['to']}" for v in d["boundary_violations"]] + [""]
    if d["external"]:
        L += ["### Dep ngoài"] + [f"- {k}: {v}" for k, v in d["external"].items()] + [""]
    if d["orphans"]:
        L += ["### File mồ côi"] + [f"- {f}" for f in d["orphans"]] + [""]
    return "\n".join(L)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", default=".")
    p.add_argument("--source", choices=["auto", "codegraph", "scan"], default="auto")
    p.add_argument("--module-depth", type=int, default=2)
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    d = collect(a.root, a.source, a.module_depth)
    print(json.dumps(d, ensure_ascii=False, indent=2) if a.json else to_markdown(d))


if __name__ == "__main__":
    main()

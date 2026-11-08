"""Tạo DB codegraph giả với schema tối thiểu mà audit.py nhận dạng được."""
import sqlite3
from pathlib import Path


def make_db(path, files, edges, kind="import"):
    """files: list path tương đối; edges: list (src_path, dst_path)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE nodes (id INTEGER PRIMARY KEY, path TEXT)")
    con.execute("CREATE TABLE edges (source_id INTEGER, target_id INTEGER, kind TEXT)")
    ids = {}
    for i, f in enumerate(files, 1):
        ids[f] = i
        con.execute("INSERT INTO nodes VALUES (?, ?)", (i, f))
    for s, d in edges:
        con.execute("INSERT INTO edges VALUES (?, ?, ?)", (ids[s], ids[d], kind))
    con.commit()
    con.close()


def make_unknown_db(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE foo (a TEXT, b TEXT)")
    con.commit()
    con.close()


def make_db_no_kind(path, files, edges):
    """Bảng cạnh không có cột kind → audit phải từ chối (scan)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE nodes (id INTEGER PRIMARY KEY, path TEXT)")
    con.execute("CREATE TABLE edges (source_id INTEGER, target_id INTEGER)")
    ids = {f: i for i, f in enumerate(files, 1)}
    con.executemany("INSERT INTO nodes VALUES (?, ?)", [(i, f) for f, i in ids.items()])
    con.executemany("INSERT INTO edges VALUES (?, ?)", [(ids[s], ids[d]) for s, d in edges])
    con.commit(); con.close()


def make_db_split_ids(path, files, edges):
    """Hai bảng node; cạnh trỏ id của bảng symbols (lệch 1000) → không resolve → scan."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE files (id INTEGER PRIMARY KEY, path TEXT)")
    con.execute("CREATE TABLE symbols (id INTEGER PRIMARY KEY, file_path TEXT, name TEXT)")
    con.execute("CREATE TABLE edges (source_id INTEGER, target_id INTEGER, kind TEXT)")
    ids = {f: i for i, f in enumerate(files, 1)}
    con.executemany("INSERT INTO files VALUES (?, ?)", [(i, f) for f, i in ids.items()])
    con.executemany("INSERT INTO symbols VALUES (?, ?, ?)", [(i + 1000, f, "S") for f, i in ids.items()])
    con.executemany("INSERT INTO edges VALUES (?, ?, 'import')", [(ids[s] + 5000, ids[d] + 5000) for s, d in edges])
    con.commit(); con.close()


def make_db_real_schema(path, files, edges, imports_external=()):
    """Mô phỏng schema codegraph 1.4: nodes(id TEXT, kind, name, file_path), edges(source, target, kind).
    Cạnh 'imports' đi file: → import: cùng file (không nói gì về file đích).
    Phụ thuộc file↔file nằm ở cạnh calls/references giữa node khác file.
    Có bảng unresolved_refs (id, file_path) tạo SAU nodes để bẫy chọn nhầm bảng."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE files (path TEXT PRIMARY KEY, language TEXT)")
    con.execute("CREATE TABLE nodes (id TEXT PRIMARY KEY, kind TEXT, name TEXT, qualified_name TEXT, file_path TEXT)")
    con.execute("CREATE TABLE edges (id INTEGER PRIMARY KEY, source TEXT, target TEXT, kind TEXT, metadata TEXT)")
    con.execute("CREATE TABLE unresolved_refs (id INTEGER PRIMARY KEY, from_node_id TEXT, reference_name TEXT, file_path TEXT)")
    for f in files:
        con.execute("INSERT INTO files VALUES (?, 'dart')", (f,))
        con.execute("INSERT INTO nodes VALUES (?, 'file', ?, ?, ?)", (f"file:{f}", f.split("/")[-1], f, f))
        cls = f.split("/")[-1].replace(".dart", "").title().replace("_", "")
        con.execute("INSERT INTO nodes VALUES (?, 'class', ?, ?, ?)", (f"class:{f}", cls, f"app.{cls}", f))
        con.execute("INSERT INTO edges (source, target, kind) VALUES (?, ?, 'contains')", (f"file:{f}", f"class:{f}"))
        con.execute("INSERT INTO unresolved_refs (from_node_id, reference_name, file_path) VALUES (?, 'X', ?)", (f"file:{f}", f))
    for i, (s, d) in enumerate(edges):
        # import node nằm trong file nguồn; cạnh imports file→import (cùng file)
        con.execute("INSERT INTO nodes VALUES (?, 'import', ?, ?, ?)", (f"import:{i}", d, d, s))
        con.execute("INSERT INTO edges (source, target, kind) VALUES (?, ?, 'imports')", (f"file:{s}", f"import:{i}"))
        # phụ thuộc thật: class trong s gọi class trong d
        con.execute("INSERT INTO edges (source, target, kind) VALUES (?, ?, 'calls')", (f"class:{s}", f"class:{d}"))
    for i, (s, name) in enumerate(imports_external):
        con.execute("INSERT INTO nodes VALUES (?, 'import', ?, ?, ?)", (f"import:ext{i}", name, name, s))
        con.execute("INSERT INTO edges (source, target, kind) VALUES (?, ?, 'imports')", (f"file:{s}", f"import:ext{i}"))
    con.commit(); con.close()

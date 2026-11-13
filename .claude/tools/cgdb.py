"""Mở .codegraph/codegraph.db để đọc.

WAL: `mode=ro` cần ghi được file -shm, nên thất bại khi thư mục chỉ đọc (sandbox, CI).
Khi đó chép db + -wal + -shm sang thư mục tạm rồi mở ở đó — chép để đọc được cả phần
chưa checkpoint trong -wal, thay vì `immutable=1` (bỏ qua -wal → số liệu cũ).
"""
import shutil
import sqlite3
import tempfile
from contextlib import contextmanager
from pathlib import Path

DB_REL = Path(".codegraph/codegraph.db")


@contextmanager
def open_db(root):
    """Context manager: sqlite3.Connection chỉ đọc, hoặc None nếu không có/không mở được DB."""
    db = Path(root) / DB_REL
    if not db.exists():
        yield None
        return
    try:
        con = sqlite3.connect(f"{db.as_uri()}?mode=ro", uri=True)
        con.execute("SELECT name FROM sqlite_master LIMIT 1")
    except sqlite3.Error:
        con = None
    if con is not None:
        try:
            yield con
        finally:
            con.close()
        return
    tmp = tempfile.mkdtemp(prefix="napoleon-cg-")
    try:
        for suffix in ("", "-wal", "-shm"):
            src = db.with_name(db.name + suffix)
            if src.exists():
                shutil.copy2(src, Path(tmp) / (db.name + suffix))
        con = sqlite3.connect(str(Path(tmp) / db.name))
        try:
            con.execute("SELECT name FROM sqlite_master LIMIT 1")
            yield con
        finally:
            con.close()
    except (OSError, sqlite3.Error):
        yield None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

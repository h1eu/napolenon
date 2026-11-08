import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / ".claude" / "tools"
FIX = ROOT / "tests" / "fixtures" / "flutter_mini"
sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
from make_fake_codegraph import make_db, make_unknown_db, make_db_no_kind, make_db_split_ids, make_db_real_schema  # noqa: E402

FILES = [
    "lib/main.dart", "lib/domain/user.dart", "lib/data/ok_repository.dart", "lib/data/big.dart",
    "lib/features/login/bloc/login_bloc.dart", "lib/features/login/user_repository.dart",
]
EDGES = [
    ("lib/main.dart", "lib/features/login/bloc/login_bloc.dart"),
    ("lib/domain/user.dart", "lib/data/ok_repository.dart"),
    ("lib/data/ok_repository.dart", "lib/domain/user.dart"),
    ("lib/features/login/bloc/login_bloc.dart", "lib/domain/user.dart"),
    ("lib/features/login/user_repository.dart", "lib/domain/user.dart"),
]


def run(root, *args):
    return subprocess.run([sys.executable, str(TOOLS / "audit.py"), "--root", str(root), *args],
                          capture_output=True, text=True)


def run_json(root, *args):
    r = run(root, *args, "--json")
    assert r.returncode == 0, r.stdout + r.stderr
    return json.loads(r.stdout)


class AuditTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "proj"
        shutil.copytree(FIX, self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_scan_detects_cycle(self):
        d = run_json(self.root, "--source", "scan")
        self.assertEqual(d["source"], "scan")
        self.assertEqual(len(d["cycles"]), 1)
        self.assertEqual(set(d["cycles"][0]), {"lib/domain/user.dart", "lib/data/ok_repository.dart"})

    def test_codegraph_source_used_when_db_valid(self):
        make_db(self.root / ".codegraph/codegraph.db", FILES, EDGES)
        d = run_json(self.root)
        self.assertEqual(d["source"], "codegraph")
        self.assertEqual(set(d["cycles"][0]), {"lib/domain/user.dart", "lib/data/ok_repository.dart"})

    def test_unknown_schema_falls_back_to_scan(self):
        make_unknown_db(self.root / ".codegraph/codegraph.db")
        r = run(self.root, "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        self.assertEqual(json.loads(r.stdout)["source"], "scan")

    def test_external_counts(self):
        d = run_json(self.root, "--source", "scan")
        self.assertGreaterEqual(d["external"]["package:flutter"], 1)
        self.assertGreaterEqual(d["external"]["package:flutter_bloc"], 1)

    def test_module_edges_depth2(self):
        d = run_json(self.root, "--source", "scan")
        self.assertIn("lib/domain", d["module_edges"]["lib/data"])
        self.assertIn("lib/domain", d["module_edges"]["lib/features"])

    def test_boundary_violation_from_module_map(self):
        mm = self.root / ".claude/instructions/module-map.md"
        mm.parent.mkdir(parents=True)
        mm.write_text("# Module\n\n## Phụ thuộc cho phép\n\n| từ | đến | lý do |\n|---|---|---|\n| lib/features | lib/domain | UI dùng entity |\n")
        d = run_json(self.root, "--source", "scan")
        self.assertIn({"from": "lib/data", "to": "lib/domain"}, d["boundary_violations"])
        self.assertNotIn({"from": "lib/features", "to": "lib/domain"}, d["boundary_violations"])

    def test_no_module_map_no_violations(self):
        d = run_json(self.root, "--source", "scan")
        self.assertEqual(d["boundary_violations"], [])

    def test_orphans(self):
        d = run_json(self.root, "--source", "scan")
        self.assertIn("lib/features/login/user_repository.dart", d["orphans"])
        self.assertIn("lib/data/big.dart", d["orphans"])
        self.assertNotIn("lib/main.dart", d["orphans"])

    def test_markdown_has_source_line(self):
        r = run(self.root, "--source", "scan")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.splitlines()[0], "source: scan")
        self.assertIn("## Số liệu", r.stdout)

    def test_module_map_cells_with_backticks(self):
        mm = self.root / ".claude/instructions/module-map.md"
        mm.parent.mkdir(parents=True)
        mm.write_text("## Phụ thuộc cho phép\n\n| từ | đến | lý do |\n|---|---|---|\n| `lib/features` | `lib/domain` | x |\n")
        d = run_json(self.root, "--source", "scan")
        self.assertNotIn({"from": "lib/features", "to": "lib/domain"}, d["boundary_violations"])

    def test_codegraph_absolute_paths_normalized(self):
        make_db(self.root / ".codegraph/codegraph.db", [str(self.root / f) for f in FILES],
                [(str(self.root / s), str(self.root / d)) for s, d in EDGES])
        d = run_json(self.root)
        self.assertEqual(d["source"], "codegraph")
        self.assertIn("lib/domain", d["module_edges"]["lib/data"])
        self.assertEqual(set(d["cycles"][0]), {"lib/domain/user.dart", "lib/data/ok_repository.dart"})

    def test_codegraph_edge_table_without_kind_falls_back(self):
        make_db_no_kind(self.root / ".codegraph/codegraph.db", FILES, EDGES)
        self.assertEqual(run_json(self.root)["source"], "scan")

    def test_codegraph_unresolvable_ids_fall_back(self):
        make_db_split_ids(self.root / ".codegraph/codegraph.db", FILES, EDGES)
        self.assertEqual(run_json(self.root)["source"], "scan")

    def test_scan_unresolved_language_notes_and_no_orphans(self):
        """Ngôn ngữ có import nhưng không resolve được cái nào → ghi chú, không báo mồ côi cho ngôn ngữ đó."""
        py = self.root / "scripts/a.py"
        py.parent.mkdir(parents=True)
        py.write_text("import os\nimport requests\n")
        (py.parent / "b.py").write_text("x = 1\n")
        import shutil as _sh
        _sh.rmtree(self.root / "lib")
        d = run_json(self.root, "--source", "scan")
        self.assertEqual(d["orphans"], [])
        self.assertTrue(any("py" in n for n in d["notes"]), d)

    def test_codegraph_real_schema_uses_cross_file_edges(self):
        """Schema codegraph 1.4: phải lấy cạnh calls/references khác file, bỏ cạnh imports cùng file,
        không chọn nhầm unresolved_refs làm bảng node, và đếm import ngoài từ node kind=import."""
        make_db_real_schema(self.root / ".codegraph/codegraph.db", FILES, EDGES,
                            imports_external=[("lib/domain/user.dart", "package:flutter/material.dart")])
        d = run_json(self.root)
        self.assertEqual(d["source"], "codegraph")
        self.assertEqual(set(d["cycles"][0]), {"lib/domain/user.dart", "lib/data/ok_repository.dart"})
        self.assertIn("lib/domain", d["module_edges"]["lib/data"])
        self.assertIn("lib/data/big.dart", d["orphans"])
        self.assertGreaterEqual(d["external"].get("package:flutter", 0), 1)

    def test_scan_resolves_kotlin_by_package(self):
        """import a.b.X → file khai báo `package a.b` chứa X."""
        src = self.root / "app/src/main/kotlin"
        (src / "a/b").mkdir(parents=True); (src / "a/c").mkdir(parents=True)
        (src / "a/b/X.kt").write_text("package a.b\n\nclass X\n")
        (src / "a/c/Y.kt").write_text("package a.c\n\nimport a.b.X\nimport kotlinx.coroutines.flow.Flow\n\nclass Y(val x: X)\n")
        import shutil as _sh
        _sh.rmtree(self.root / "lib")
        d = run_json(self.root, "--source", "scan", "--module-depth", "6")
        self.assertFalse(any("không resolve" in n for n in d["notes"]), d["notes"])
        self.assertTrue(any("kotlin" in n.lower() and "mồ côi" in n for n in d["notes"]), d["notes"])
        self.assertIn("app/src/main/kotlin/a/b", d["module_edges"]["app/src/main/kotlin/a/c"])
        self.assertNotIn("app/src/main/kotlin/a/b/X.kt", d["orphans"])
        self.assertGreaterEqual(d["external"].get("kotlinx", 0), 1)

    def test_codegraph_files_with_unknown_suffix_do_not_crash(self):
        """codegraph index cả .xml/.sq; audit không được KeyError, và không tính chúng là mồ côi."""
        files = FILES + ["android/res/values/strings.xml"]
        make_db_real_schema(self.root / ".codegraph/codegraph.db", files, EDGES)
        (self.root / "android/res/values").mkdir(parents=True)
        (self.root / "android/res/values/strings.xml").write_text("<resources/>")
        d = run_json(self.root)
        self.assertEqual(d["source"], "codegraph")
        self.assertNotIn("android/res/values/strings.xml", d["orphans"])

    def test_collect_function(self):
        sys.path.insert(0, str(TOOLS))
        import audit
        d = audit.collect(self.root, "scan", 2)
        self.assertEqual(d["files"], 6)


if __name__ == "__main__":
    unittest.main()

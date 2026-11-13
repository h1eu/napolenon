"""affected.py: file đổi → test nào chạy, khi nào phải chạy toàn bộ."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / ".claude" / "tools" / "affected.py"

TOOLCHAIN = {
    "by_ext": {".dart": {"format": "", "analyze": ""}},
    "test": "echo ALL",
    "test_one": "echo ONE {files}",
    "test_files": ["test/**"],
    "full_test_when": ["pubspec.yaml", "lib/core/di/**"],
}


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                          env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x",
                               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x"})


class AffectedTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.write("pubspec.yaml", "name: app\n")
        self.write(".claude/instructions/toolchain.json", json.dumps(TOOLCHAIN))
        self.write("lib/core/theme.dart", "const c = 1;\n")
        self.write("lib/core/di/injection.dart", "const d = 1;\n")
        self.write("lib/features/a/a.dart", "import 'package:app/core/theme.dart';\n")
        self.write("lib/features/b/b.dart", "const b = 1;\n")
        self.write("test/a_test.dart", "import 'package:app/features/a/a.dart';\n")
        self.write("test/b_test.dart", "import 'package:app/features/b/b.dart';\n")
        self.write("test/theme_test.dart", "import 'package:app/core/theme.dart';\n")
        git(self.root, "init", "-q")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "init")

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def run_tool(self, *args):
        r = subprocess.run([sys.executable, str(TOOL), "--root", str(self.root), "--json", *args],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_leaf_change_runs_only_its_test(self):
        d = self.run_tool("--files", "lib/features/b/b.dart")
        self.assertEqual(d["mode"], "some")
        self.assertEqual(d["tests"], ["test/b_test.dart"])
        self.assertEqual(d["command"], "echo ONE test/b_test.dart")

    def test_transitive_dependent_test_included(self):
        d = self.run_tool("--files", "lib/core/theme.dart", "--max-ratio", "1")
        self.assertEqual(d["tests"], ["test/a_test.dart", "test/theme_test.dart"])

    def test_changed_test_file_runs_itself(self):
        d = self.run_tool("--files", "test/a_test.dart")
        self.assertEqual(d["tests"], ["test/a_test.dart"])

    def test_full_test_when_glob(self):
        d = self.run_tool("--files", "lib/core/di/injection.dart")
        self.assertEqual(d["mode"], "all")
        self.assertEqual(d["command"], "echo ALL")
        self.assertIn("full_test_when", d["reason"])

    def test_too_many_tests_runs_all(self):
        d = self.run_tool("--files", "lib/core/theme.dart", "--max-ratio", "0.3")
        self.assertEqual(d["mode"], "all")
        self.assertIn("2/3", d["reason"])

    def test_new_file_not_in_graph_runs_all(self):
        d = self.run_tool("--files", "lib/features/c/c.dart")
        self.assertEqual(d["mode"], "all")
        self.assertIn("chưa có trong đồ thị", d["reason"])

    def test_non_source_change_has_no_tests(self):
        d = self.run_tool("--files", "README.md")
        self.assertEqual(d["mode"], "some")
        self.assertEqual(d["tests"], [])
        self.assertEqual(d["command"], "")

    def test_git_diff_against_head(self):
        (self.root / "lib/features/b/b.dart").write_text("const b = 2;\n")
        d = self.run_tool()
        self.assertEqual(d["tests"], ["test/b_test.dart"])

    def test_untracked_file_counts_as_changed(self):
        self.write("test/c_test.dart", "import 'package:app/features/b/b.dart';\n")
        d = self.run_tool()
        self.assertIn("test/c_test.dart", d["tests"])

    def test_unknown_base_runs_all(self):
        d = self.run_tool("--base", "khong-co-nhanh")
        self.assertEqual(d["mode"], "all")
        self.assertIn("khong-co-nhanh", d["reason"])

    def test_without_git_runs_all(self):
        with tempfile.TemporaryDirectory() as d2:
            Path(d2, ".claude/instructions").mkdir(parents=True)
            Path(d2, ".claude/instructions/toolchain.json").write_text(json.dumps(TOOLCHAIN))
            r = subprocess.run([sys.executable, str(TOOL), "--root", d2, "--json"], capture_output=True, text=True)
            self.assertEqual(json.loads(r.stdout)["mode"], "all")

    def test_without_toolchain_runs_all(self):
        (self.root / ".claude/instructions/toolchain.json").unlink()
        d = self.run_tool("--files", "lib/features/b/b.dart")
        self.assertEqual(d["mode"], "all")
        self.assertEqual(d["command"], "")

    def test_hub_stops_propagation(self):
        # router.dart import mọi màn; app_test dựng cả app qua router → sửa một màn không nên kéo app_test
        self.write("lib/router.dart", "import 'package:app/features/a/a.dart';\nimport 'package:app/features/b/b.dart';\n")
        self.write("test/app_test.dart", "import 'package:app/router.dart';\n")
        self.write("test/router_test.dart", "import 'package:app/router.dart';\n")
        tc = dict(TOOLCHAIN, affected_hubs=["lib/router.dart"])
        self.write(".claude/instructions/toolchain.json", json.dumps(tc))
        d = self.run_tool("--files", "lib/features/b/b.dart", "--max-ratio", "1")
        self.assertEqual(d["tests"], ["test/b_test.dart"])

    def test_without_hub_propagates_through_router(self):
        self.write("lib/router.dart", "import 'package:app/features/b/b.dart';\n")
        self.write("test/app_test.dart", "import 'package:app/router.dart';\n")
        d = self.run_tool("--files", "lib/features/b/b.dart", "--max-ratio", "1")
        self.assertEqual(d["tests"], ["test/app_test.dart", "test/b_test.dart"])

    def test_generated_files_are_hubs(self):
        self.write("lib/di.config.dart", "import 'package:app/features/b/b.dart';\n")
        self.write("test/di_test.dart", "import 'package:app/di.config.dart';\n")
        self.write(".claude/instructions/rules.json", json.dumps({"exclude": ["*.config.dart"], "rules": []}))
        d = self.run_tool("--files", "lib/features/b/b.dart", "--max-ratio", "1")
        self.assertEqual(d["tests"], ["test/b_test.dart"])

    def test_changing_the_hub_itself_still_finds_its_tests(self):
        self.write("lib/router.dart", "import 'package:app/features/b/b.dart';\n")
        self.write("test/app_test.dart", "import 'package:app/router.dart';\n")
        self.write(".claude/instructions/toolchain.json", json.dumps(dict(TOOLCHAIN, affected_hubs=["lib/router.dart"])))
        d = self.run_tool("--files", "lib/router.dart", "--max-ratio", "1")
        self.assertEqual(d["tests"], ["test/app_test.dart"])

    def test_text_output_lists_tests_and_command(self):
        r = subprocess.run([sys.executable, str(TOOL), "--root", str(self.root),
                            "--files", "lib/features/b/b.dart"], capture_output=True, text=True)
        self.assertIn("- test/b_test.dart", r.stdout)
        self.assertIn("echo ONE", r.stdout)


if __name__ == "__main__":
    unittest.main()

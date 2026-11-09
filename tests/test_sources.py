import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".claude" / "tools" / "state.py"
SOURCES = ROOT / ".claude" / "tools" / "sources.py"


def run(tool, root, *args):
    return subprocess.run([sys.executable, str(tool), "--root", str(root), *args], capture_output=True, text=True)


def diff_json(root):
    r = run(SOURCES, root, "diff", "--json")
    return r, (json.loads(r.stdout) if r.stdout.strip() else None)


class SourcesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.assertEqual(run(STATE, self.root, "init").returncode, 0)
        self.prd = self.root / "docs/sources/prd"
        self.prd.mkdir(parents=True)
        (self.prd / ".gitkeep").touch()
        (self.prd / "login.md").write_text("Đăng nhập bằng email\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_no_state_is_error(self):
        with tempfile.TemporaryDirectory() as empty:
            r, _ = diff_json(empty)
            self.assertEqual(r.returncode, 1)

    def test_without_mark_everything_is_new(self):
        r, d = diff_json(self.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIsNone(d["mark"])
        self.assertEqual(d["added"], ["docs/sources/prd/login.md"])
        self.assertEqual(d["total_files"], 1, ".gitkeep không tính")

    def test_mark_then_no_change(self):
        self.assertEqual(run(STATE, self.root, "sources", "mark").returncode, 0)
        r = run(STATE, self.root, "sources", "show")
        self.assertIn("login.md", r.stdout)
        _, d = diff_json(self.root)
        self.assertIsNotNone(d["mark"])
        self.assertEqual((d["added"], d["changed"], d["removed"]), ([], [], []))
        text = run(SOURCES, self.root, "diff").stdout
        self.assertIn("Không có gì đổi", text)

    def test_change_add_remove_and_references(self):
        (self.prd / "pay.md").write_text("v1\n", encoding="utf-8")
        run(STATE, self.root, "sources", "mark")
        (self.prd / "login.md").write_text("Đăng nhập bằng số điện thoại\n", encoding="utf-8")
        (self.prd / "pay.md").unlink()
        (self.prd / "profile.md").write_text("mới\n", encoding="utf-8")
        inst = self.root / ".claude/instructions"
        inst.mkdir(parents=True)
        (inst / "project.md").write_text("Nguồn: docs/sources/prd/login.md mục 2\n", encoding="utf-8")
        feat = self.root / "docs/napoleon/features/login"
        feat.mkdir(parents=True)
        (feat / "spec.md").write_text("# Spec\nNguồn: login.md\n", encoding="utf-8")
        (self.root / "docs/napoleon/features.md").write_text("- pay — thanh toán — nguồn: docs/sources/prd/pay.md\n", encoding="utf-8")
        run(STATE, self.root, "feature", "add", "login")
        run(STATE, self.root, "feature", "step", "login", "build")

        r, d = diff_json(self.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(d["changed"], ["docs/sources/prd/login.md"])
        self.assertEqual(d["removed"], ["docs/sources/prd/pay.md"])
        self.assertEqual(d["added"], ["docs/sources/prd/profile.md"])
        refs = d["references"]["docs/sources/prd/login.md"]
        self.assertEqual(len(refs), 2)
        self.assertTrue(any(x.startswith(".claude/instructions/project.md:1:") for x in refs))
        self.assertTrue(any(x.startswith("docs/napoleon/features/login/spec.md:2:") for x in refs))
        self.assertEqual(len(d["references"]["docs/sources/prd/pay.md"]), 1)
        self.assertEqual(d["references"]["docs/sources/prd/profile.md"], [])
        self.assertEqual(d["open_features"], [{"name": "login", "step": "build", "in_progress": ""}])

        text = run(SOURCES, self.root, "diff").stdout
        self.assertIn("-- ĐỔI docs/sources/prd/login.md", text)
        self.assertIn("không nơi nào trong harness nhắc tới", text)
        self.assertIn("login: bước build", text)

    def test_git_diff_hunks_when_commit_recorded(self):
        git = lambda *a: subprocess.run(["git", "-C", str(self.root), *a], capture_output=True, text=True)
        if git("init", "-q").returncode != 0:
            self.skipTest("không có git")
        git("-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
        git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init")
        run(STATE, self.root, "sources", "mark")
        self.assertTrue(json.loads(run(STATE, self.root, "sources", "show").stdout)["commit"])
        (self.prd / "login.md").write_text("Đăng nhập bằng số điện thoại\n", encoding="utf-8")
        _, d = diff_json(self.root)
        hunks = d["diff"]["docs/sources/prd/login.md"]
        self.assertTrue(any(h.startswith("-Đăng nhập bằng email") for h in hunks), hunks)
        self.assertTrue(any(h.startswith("+Đăng nhập bằng số điện thoại") for h in hunks), hunks)


if __name__ == "__main__":
    unittest.main()

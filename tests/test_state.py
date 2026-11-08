import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / ".claude" / "tools" / "state.py"


def run(root, *args):
    return subprocess.run(
        [sys.executable, str(TOOL), "--root", str(root), *args],
        capture_output=True, text=True,
    )


def state_of(root):
    return json.loads((Path(root) / "docs/napoleon/state.json").read_text())


class StateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.assertEqual(run(self.root, "init").returncode, 0)

    def tearDown(self):
        self.tmp.cleanup()

    def test_init_creates_schema(self):
        s = state_of(self.root)
        self.assertEqual(s["version"], 1)
        self.assertEqual(s["features"], {})
        self.assertEqual(set(s["last_session"]), {"feature", "note", "at"})

    def test_init_twice_fails(self):
        r = run(self.root, "init")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(len(r.stderr.strip().splitlines()), 1)

    def test_feature_add_and_step(self):
        self.assertEqual(run(self.root, "feature", "add", "login").returncode, 0)
        self.assertEqual(state_of(self.root)["features"]["login"]["step"], "spec")
        run(self.root, "feature", "step", "login", "build")
        self.assertEqual(state_of(self.root)["features"]["login"]["step"], "build")
        self.assertEqual(run(self.root, "feature", "step", "login", "xyz").returncode, 1)

    def test_feature_name_with_spaces(self):
        r = run(self.root, "feature", "add", "dang nhap")
        self.assertEqual(r.returncode, 1)
        self.assertIn("[a-z0-9-]", r.stderr)
        self.assertNotIn("dang nhap", state_of(self.root)["features"])

    def test_task_lifecycle(self):
        run(self.root, "feature", "add", "login")
        r = run(self.root, "task", "add", "login", "Tạo repo", "--files", "a.dart,b.dart")
        self.assertEqual(r.returncode, 0, r.stderr)
        t = state_of(self.root)["features"]["login"]["tasks"][0]
        self.assertEqual((t["id"], t["status"], t["files"]), (1, "todo", ["a.dart", "b.dart"]))
        run(self.root, "task", "start", "login", "1")
        self.assertEqual(state_of(self.root)["features"]["login"]["tasks"][0]["status"], "in_progress")
        run(self.root, "task", "done", "login", "1")
        self.assertEqual(state_of(self.root)["features"]["login"]["tasks"][0]["status"], "done")
        run(self.root, "task", "block", "login", "1", "chờ API")
        t = state_of(self.root)["features"]["login"]["tasks"][0]
        self.assertEqual((t["status"], t["blocker"]), ("blocked", "chờ API"))

    def test_task_unknown_id(self):
        run(self.root, "feature", "add", "login")
        self.assertEqual(run(self.root, "task", "done", "login", "9").returncode, 1)

    def test_session_note_updates_and_journals(self):
        run(self.root, "feature", "add", "login")
        r = run(self.root, "session", "note", "login", "dừng task 1")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(state_of(self.root)["last_session"]["feature"], "login")
        journal = self.root / "docs/napoleon/journal.md"
        self.assertTrue(journal.exists())
        self.assertIn("dừng task 1", journal.read_text().strip().splitlines()[-1])
        run(self.root, "session", "note", "login", "mục hai")
        self.assertEqual(journal.read_text().count("## "), 2)

    def test_show_brief_max_5_lines(self):
        run(self.root, "feature", "add", "login")
        run(self.root, "feature", "step", "login", "build")
        run(self.root, "task", "add", "login", "T1")
        run(self.root, "task", "start", "login", "1")
        out = run(self.root, "show", "--brief").stdout
        self.assertLessEqual(len(out.strip().splitlines()), 5)
        self.assertIn("login", out)
        self.assertIn("build", out)

    def test_show_json(self):
        run(self.root, "feature", "add", "login")
        out = run(self.root, "show", "--json").stdout
        self.assertEqual(json.loads(out), state_of(self.root))

    def test_corrupt_state_json_one_line_error(self):
        (self.root / "docs/napoleon/state.json").write_text("{not json")
        r = run(self.root, "show")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("Traceback", r.stderr)
        self.assertEqual(len(r.stderr.strip().splitlines()), 1)
        self.assertIn("hỏng", r.stderr)

    def test_task_files_are_stripped(self):
        run(self.root, "feature", "add", "login")
        run(self.root, "task", "add", "login", "T", "--files", " a.dart, b.dart ,")
        self.assertEqual(state_of(self.root)["features"]["login"]["tasks"][0]["files"], ["a.dart", "b.dart"])

    def test_atomic_write_no_tmp_left(self):
        run(self.root, "feature", "add", "login")
        run(self.root, "task", "add", "login", "T1")
        leftovers = list((self.root / "docs/napoleon").glob("*.tmp"))
        self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()

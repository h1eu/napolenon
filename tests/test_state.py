import json
import os
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


def write(root, rel, text):
    p = Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


class StateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.assertEqual(run(self.root, "init").returncode, 0)

    def tearDown(self):
        self.tmp.cleanup()

    def test_init_creates_schema(self):
        s = state_of(self.root)
        self.assertEqual(s["version"], 2)
        self.assertEqual(s["features"], {})
        self.assertEqual(s["followups"], [])
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
        r = run(self.root, "feature", "add", "my feature")
        self.assertEqual(r.returncode, 1)
        self.assertIn("a-z0-9-", r.stderr)

    def test_task_lifecycle(self):
        run(self.root, "feature", "add", "login")
        tid = run(self.root, "task", "add", "login", "viết bloc", "--files", "lib/a.dart").stdout.strip()
        self.assertEqual(tid, "1")
        run(self.root, "task", "start", "login", tid)
        self.assertEqual(state_of(self.root)["features"]["login"]["tasks"][0]["status"], "in_progress")
        run(self.root, "task", "block", "login", tid, "chờ API")
        t = state_of(self.root)["features"]["login"]["tasks"][0]
        self.assertEqual((t["status"], t["blocker"]), ("blocked", "chờ API"))
        run(self.root, "task", "done", "login", tid)
        t = state_of(self.root)["features"]["login"]["tasks"][0]
        self.assertEqual((t["status"], t["blocker"]), ("done", ""))

    def test_task_unknown_id(self):
        run(self.root, "feature", "add", "login")
        self.assertEqual(run(self.root, "task", "start", "login", "9").returncode, 1)

    def test_session_note_updates_and_journals(self):
        run(self.root, "feature", "add", "login")
        run(self.root, "session", "note", "login", "dừng ở task 2")
        s = state_of(self.root)
        self.assertEqual(s["last_session"]["feature"], "login")
        journal = (self.root / "docs/napoleon/journal.md").read_text()
        self.assertIn("dừng ở task 2", journal)
        self.assertIn("— login", journal)

    def test_show_brief_max_5_lines(self):
        for i in range(8):
            run(self.root, "feature", "add", f"f{i}")
        r = run(self.root, "show", "--brief")
        self.assertLessEqual(len(r.stdout.strip().splitlines()), 5)

    def test_show_json(self):
        run(self.root, "feature", "add", "login")
        self.assertIn("login", json.loads(run(self.root, "show", "--json").stdout)["features"])

    def test_corrupt_state_json_one_line_error(self):
        (self.root / "docs/napoleon/state.json").write_text("{không phải json")
        r = run(self.root, "show")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(len(r.stderr.strip().splitlines()), 1)
        self.assertNotIn("Traceback", r.stderr)

    def test_task_files_are_stripped(self):
        run(self.root, "feature", "add", "login")
        run(self.root, "task", "add", "login", "t", "--files", " a.dart , b.dart ,")
        self.assertEqual(state_of(self.root)["features"]["login"]["tasks"][0]["files"], ["a.dart", "b.dart"])

    def test_atomic_write_no_tmp_left(self):
        run(self.root, "feature", "add", "login")
        self.assertFalse(list((self.root / "docs/napoleon").glob("*.tmp")))

    def test_v1_state_still_readable(self):
        old = {"version": 1, "features": {"login": {"step": "build", "tasks": [
            {"id": 1, "title": "t", "status": "done", "files": [], "blocker": ""}], "updated": "2026-01-01T00:00:00"}},
            "last_session": {"feature": "login", "note": "n", "at": ""}, "sources": {"commit": "", "manifest": {}, "at": ""}}
        (self.root / "docs/napoleon/state.json").write_text(json.dumps(old))
        r = run(self.root, "show", "--brief")
        self.assertEqual(r.returncode, 0, r.stderr)
        run(self.root, "feature", "step", "login", "verify")
        s = state_of(self.root)
        self.assertEqual(s["version"], 2)
        self.assertEqual(s["features"]["login"]["verify"], [])
        self.assertEqual(s["features"]["login"]["tasks"][0]["commit"], "")


class GateTest(unittest.TestCase):
    """task done chạy conform + test theo diff; feature step done đọc verify.md."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        run(self.root, "init")
        run(self.root, "feature", "add", "login")
        write(self.root, "pubspec.yaml", "name: app\n")
        write(self.root, "lib/a.dart", "class A {}\n")
        write(self.root, "test/a_test.dart", "import 'package:app/a.dart';\n")
        self.toolchain({"test": "exit 0", "test_one": "exit 0", "test_files": ["test/**"]})
        env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x"}
        for args in (["init", "-q"], ["add", "-A"], ["commit", "-qm", "i"]):
            subprocess.run(["git", "-C", str(self.root), *args], capture_output=True, env=env)

    def tearDown(self):
        self.tmp.cleanup()

    def toolchain(self, data):
        write(self.root, ".claude/instructions/toolchain.json", json.dumps(data))

    def rules(self, *rules):
        write(self.root, ".claude/instructions/rules.json", json.dumps({"rules": list(rules)}))

    def add_task(self, files="lib/a.dart"):
        return run(self.root, "task", "add", "login", "t", "--files", files).stdout.strip()

    def status(self, tid="1"):
        return [t for t in state_of(self.root)["features"]["login"]["tasks"] if t["id"] == int(tid)][0]

    def test_conform_violation_blocks_done(self):
        self.rules({"id": "max-0", "type": "max-lines", "in": "lib/**", "max": 0})
        tid = self.add_task()
        r = run(self.root, "task", "done", "login", tid)
        self.assertEqual(r.returncode, 1)
        self.assertIn("conform", r.stderr)
        self.assertEqual(self.status(tid)["status"], "todo")

    def test_failing_test_blocks_done(self):
        self.toolchain({"test": "exit 1", "test_one": "exit 1", "test_files": ["test/**"]})
        write(self.root, "lib/a.dart", "class A { int x = 1; }\n")
        tid = self.add_task()
        r = run(self.root, "task", "done", "login", tid)
        self.assertEqual(r.returncode, 1)
        self.assertIn("test", r.stderr)
        self.assertEqual(self.status(tid)["status"], "todo")

    def test_clean_task_done_records_checks_and_commit(self):
        self.rules({"id": "max-400", "type": "max-lines", "in": "lib/**", "max": 400})
        write(self.root, "lib/a.dart", "class A { int x = 1; }\n")
        tid = self.add_task()
        r = run(self.root, "task", "done", "login", tid)
        self.assertEqual(r.returncode, 0, r.stderr)
        t = self.status(tid)
        self.assertEqual(t["status"], "done")
        self.assertEqual(len(t["commit"]), 40)
        self.assertIn("conform", t["checks"])
        self.assertIn("test", t["checks"])

    def test_skip_flags_are_recorded(self):
        self.rules({"id": "max-0", "type": "max-lines", "in": "lib/**", "max": 0})
        tid = self.add_task()
        r = run(self.root, "task", "done", "login", tid, "--skip-tests", "--skip-conform")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("bỏ qua", self.status(tid)["checks"]["conform"])
        self.assertIn("bỏ qua", self.status(tid)["checks"]["test"])

    def test_missing_rules_does_not_block(self):
        tid = self.add_task()
        r = run(self.root, "task", "done", "login", tid)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("bỏ qua", self.status(tid)["checks"]["conform"])

    def test_step_done_needs_verify_md(self):
        r = run(self.root, "feature", "step", "login", "done")
        self.assertEqual(r.returncode, 1)
        self.assertIn("verify.md", r.stderr)
        self.assertNotEqual(state_of(self.root)["features"]["login"]["step"], "done")

    def test_step_done_blocked_by_unticked_machine_box(self):
        write(self.root, "docs/napoleon/features/login/verify.md",
              "# Verify\n## Máy\n- [ ] test — chưa chạy\n## Người\n- [ ] nhìn màn hình\n")
        r = run(self.root, "feature", "step", "login", "done")
        self.assertEqual(r.returncode, 1)
        self.assertIn("chưa tick", r.stderr)

    def test_step_done_allows_pending_human_boxes(self):
        write(self.root, "docs/napoleon/features/login/verify.md",
              "# Verify\n## Máy\n- [x] test — 10 pass\n## Verifier\n- [x] mọi yêu cầu\n"
              "## Người\n- [ ] nhìn màn hình\n- [ ] thử trên máy thật\n")
        r = run(self.root, "feature", "step", "login", "done")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(state_of(self.root)["features"]["login"]["step"], "done")
        self.assertIn("2 mục Người", r.stdout)
        self.assertEqual(len(state_of(self.root)["features"]["login"]["human"]), 2)

    def test_human_list_and_tick(self):
        write(self.root, "docs/napoleon/features/login/verify.md",
              "# Verify\n## Người\n- [ ] nhìn màn hình\n- [x] thử trên máy thật\n")
        r = run(self.root, "human", "login", "list")
        self.assertIn("1. [ ] nhìn màn hình", r.stdout)
        self.assertIn("2. [x] thử trên máy thật", r.stdout)
        run(self.root, "human", "login", "tick", "1")
        self.assertTrue(all(h["done"] for h in state_of(self.root)["features"]["login"]["human"]))
        self.assertEqual(run(self.root, "human", "login", "tick", "9").returncode, 1)

    def test_verify_rounds_and_repeat_warning(self):
        run(self.root, "feature", "add", "profile")
        r = run(self.root, "verify", "login", "fail", "--issue", "hardcode", "--issue", "thieu-test")
        self.assertIn("verify lần 1: fail", r.stdout)
        self.assertIn("build", r.stdout)
        r = run(self.root, "verify", "profile", "fail", "--issue", "hardcode")
        self.assertIn("/retro", r.stdout)
        self.assertEqual(len(state_of(self.root)["features"]["login"]["verify"]), 1)

    def test_followup_add_list_done(self):
        fid = run(self.root, "followup", "add", "login", "thêm chip B26", "--source", "ADR-020").stdout.strip()
        self.assertEqual(fid, "1")
        r = run(self.root, "followup", "list")
        self.assertIn("thêm chip B26", r.stdout)
        self.assertIn("ADR-020", r.stdout)
        self.assertIn("followup chờ: 1", run(self.root, "show", "--brief").stdout)
        run(self.root, "followup", "done", "1")
        self.assertNotIn("thêm chip B26", run(self.root, "followup", "list").stdout)
        self.assertIn("thêm chip B26", run(self.root, "followup", "list", "--all").stdout)
        self.assertEqual(run(self.root, "followup", "done", "9").returncode, 1)


if __name__ == "__main__":
    unittest.main()

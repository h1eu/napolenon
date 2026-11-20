import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / ".claude" / "tools"


def tool(name, root, *args):
    return subprocess.run([sys.executable, str(TOOLS / name), "--root", str(root), *args],
                          capture_output=True, text=True)


def write(root, rel, text):
    p = Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "proj"
        self.root.mkdir()
        self.bare = Path(self.tmp.name) / "bare"
        self.bare.mkdir()
        self.env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x",
                    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x"}
        self.st("init")
        self.st("feature", "add", "login")
        write(self.root, "pubspec.yaml", "name: app\n")
        write(self.root, "lib/a.dart", "class A {}\n")
        write(self.root, "test/a_test.dart", "import 'package:app/a.dart';\n")
        self.toolchain({"test": "exit 0", "test_one": "exit 0", "test_files": ["test/**"]})
        subprocess.run(["git", "-C", str(self.root), "init", "-q"], capture_output=True, env=self.env)
        self.commit("i")

    def tearDown(self):
        self.tmp.cleanup()

    def st(self, *args):
        return tool("state.py", self.root, *args)

    def toolchain(self, data):
        write(self.root, ".claude/instructions/toolchain.json", json.dumps(data))

    def commit(self, msg):
        for args in (["add", "-A"], ["commit", "-qm", msg]):
            subprocess.run(["git", "-C", str(self.root), *args], capture_output=True, env=self.env)

    def head(self):
        r = subprocess.run(["git", "-C", str(self.root), "rev-parse", "HEAD"], capture_output=True, text=True)
        return r.stdout.strip()

    def gen(self):
        tool("implementation.py", self.root)
        return (self.root / "docs/napoleon/implementation.md").read_text(encoding="utf-8")

    def row(self, md, key):
        return next(l for l in md.splitlines() if key in l)


class CoreTest(Base):
    def test_no_state_writes_nothing(self):
        r = tool("implementation.py", self.bare)
        self.assertEqual(r.returncode, 0)
        self.assertFalse((self.bare / "docs/napoleon/implementation.md").exists())

    def test_header_and_section_order(self):
        md = self.gen()
        self.assertTrue(md.startswith("<!-- napoleon:generated"))
        heads = [l for l in md.splitlines() if l.startswith("## ")]
        self.assertEqual(heads[:3], ["## Tổng quan", "## Task", "## Thay đổi theo task"])

    def test_deterministic_and_no_rewrite(self):
        a = self.gen()
        p = self.root / "docs/napoleon/implementation.md"
        m = p.stat().st_mtime_ns
        self.assertEqual(self.gen(), a)
        self.assertEqual(p.stat().st_mtime_ns, m)

    def test_overview_row(self):
        self.st("task", "add", "login", "A")
        self.st("task", "add", "login", "B")
        self.st("task", "done", "login", "1", "--skip-tests", "--skip-conform")
        self.st("verify", "login", "fail", "--issue", "null-state")
        self.assertEqual(self.row(self.gen(), "| login |"),
                         "| login | spec | 1/2 | lần 1 fail (null-state) | — |")

    def test_task_row_done_blocked_and_routes(self):
        self.st("task", "add", "login", "Form | đăng nhập", "--routes", "/login")
        self.st("task", "add", "login", "Quên mật khẩu")
        self.st("task", "block", "login", "2", "chờ API reset")
        md = self.gen()
        self.assertIn("| login#1 | Form \\| đăng nhập | todo | /login | — | — | — |", md)
        self.assertIn("| login#2 | Quên mật khẩu | blocked: chờ API reset | — | — | — | — |", md)

    def test_commit_column_lifecycle(self):
        self.commit("state")
        self.st("task", "add", "login", "A")
        self.st("task", "start", "login", "1")
        write(self.root, "lib/a.dart", "class A { int x = 1; }\n")
        self.commit("giữa chừng")
        write(self.root, "lib/a.dart", "class A { int x = 2; }\n")
        self.st("task", "done", "login", "1", "--skip-conform")
        self.assertTrue(self.row(self.gen(), "login#1").endswith("| commit kế tiếp |"))
        self.commit("task 1")
        sha = self.head()[:7]
        self.assertTrue(self.row(self.gen(), "login#1").endswith(f"| {sha} (+1) |"))

    def test_rewritten_history_shows_dash(self):
        self.st("task", "add", "login", "A")
        self.st("task", "done", "login", "1", "--skip-tests", "--skip-conform")
        subprocess.run(["git", "-C", str(self.root), "checkout", "-q", "--orphan", "moi"], capture_output=True)
        self.commit("gốc mới")
        self.assertIn("— (lịch sử đã viết lại)", self.row(self.gen(), "login#1"))

    def test_changes_table(self):
        self.commit("state")
        self.st("task", "add", "login", "A")
        self.st("task", "start", "login", "1")
        write(self.root, "lib/a.dart", "class A { int x = 1; }\n")
        write(self.root, "lib/b.dart", "class B {}\n")
        self.st("task", "done", "login", "1", "--skip-tests", "--skip-conform")
        md = self.gen()
        self.assertIn("| login#1 | lib/a.dart | sửa |", md)
        self.assertIn("| login#1 | lib/b.dart | thêm |", md)
        self.assertRegex(self.row(md, "| login#1 | A |"), r"\| 2 \| bỏ qua \|")

    def test_task_missing_new_fields_still_renders(self):
        self.st("task", "add", "login", "A")
        p = self.root / "docs/napoleon/state.json"
        s = json.loads(p.read_text())
        for k in ("routes", "base", "changed", "test"):
            s["features"]["login"]["tasks"][0].pop(k, None)
        p.write_text(json.dumps(s))
        self.assertIn("| login#1 | A | todo |", self.gen())

    def test_no_git(self):
        tool("state.py", self.bare, "init")
        tool("state.py", self.bare, "feature", "add", "x")
        tool("state.py", self.bare, "task", "add", "x", "A")
        tool("state.py", self.bare, "task", "done", "x", "1", "--skip-tests", "--skip-conform")
        tool("implementation.py", self.bare)
        md = (self.bare / "docs/napoleon/implementation.md").read_text(encoding="utf-8")
        self.assertTrue(self.row(md, "x#1").endswith("| — |"))


class EvidenceTest(Base):
    PLAN = ("# Plan: login\n\n## Task\n### Task 1: Form\n- File: lib/a.dart\n"
            "- Test chứng minh: `submits valid form` trong `test/a_test.dart`\n- Yêu cầu spec: #1\n\n"
            "### Task 2: Khác\n- File: x\n")

    def test_row_joins_plan_run_and_conform(self):
        write(self.root, "docs/napoleon/features/login/plan.md", self.PLAN)
        write(self.root, "test/b_test.dart", "void main() {}\n")
        self.commit("b")
        self.st("task", "add", "login", "Form")
        write(self.root, "lib/a.dart", "class A { int x = 1; }\n")
        self.st("task", "done", "login", "1")
        r =self.row(self.gen().split("## Test và bằng chứng")[1], "login#1")
        self.assertIn("`submits valid form` trong `test/a_test.dart`", r)
        self.assertIn("test/a_test.dart", r.split("|")[3])
        self.assertIn("pass", r)

    def test_failed_run_of_open_task_is_shown(self):
        self.toolchain({"test": "exit 1", "test_one": "exit 1", "test_files": ["test/**"]})
        self.st("task", "add", "login", "Form")
        write(self.root, "lib/a.dart", "class A { int x = 1; }\n")
        self.st("task", "done", "login", "1")
        self.assertIn("FAIL", self.row(self.gen().split("## Test và bằng chứng")[1], "login#1"))

    def test_task_never_run_is_not_listed(self):
        self.st("task", "add", "login", "Form")
        self.assertNotIn("login#1", self.gen().split("## Test và bằng chứng")[1].split("\n## ")[0])

    def test_missing_plan_gives_dash(self):
        self.st("task", "add", "login", "Form"); self.st("task", "done", "login", "1", "--skip-conform")
        self.assertEqual(self.row(self.gen().split("## Test và bằng chứng")[1], "login#1").split("|")[2].strip(), "—")

    def test_verify_line(self):
        write(self.root, "docs/napoleon/features/login/verify.md",
              "## Máy\n- [x] a\n- [x] b\n## Verifier\n- [ ] c\n## Người\n- [ ] UI\n- [ ] UI2\n")
        self.st("verify", "login", "fail", "--issue", "null-state"); self.st("verify", "login", "pass")
        self.assertIn("login — verify lần 1 fail (null-state), lần 2 pass · máy+verifier 2/3 · người chờ 2", self.gen())


if __name__ == "__main__":
    unittest.main()

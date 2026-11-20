import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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
        self.assertEqual(heads, ["## Tổng quan", "## Task", "## Thay đổi theo task", "## Test và bằng chứng",
                                 "## Route và màn", "## Nguồn sự thật", "## Logic tái dùng",
                                 "## Quyết định và việc hẹn lại"])

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


class GitCostTest(Base):
    """build() chạy sau mỗi lần ghi state → số lệnh git không được tăng theo số task."""

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], capture_output=True, text=True, env=self.env)

    def empty_commit(self, msg):
        self.git("commit", "-q", "--allow-empty", "-m", msg)
        return self.head()

    def put_tasks(self, tasks):
        p = self.root / "docs/napoleon/state.json"
        s = json.loads(p.read_text())
        s["features"]["login"]["tasks"] = tasks
        p.write_text(json.dumps(s))

    def build_counting(self):
        sys.path.insert(0, str(TOOLS))
        try:
            import implementation
        finally:
            sys.path.remove(str(TOOLS))
        calls = []
        real = subprocess.run

        def counting(cmd, *a, **k):
            if cmd and cmd[0] == "git":
                calls.append(cmd)
            return real(cmd, *a, **k)

        with mock.patch.object(implementation.subprocess, "run", counting):
            md = implementation.build(self.root)
        return md, calls

    def test_git_calls_do_not_grow_with_tasks(self):
        shas = [self.empty_commit(f"c{i}") for i in range(31)]
        self.put_tasks([{"id": i + 1, "title": "t", "status": "done", "base": shas[i], "commit": shas[i]}
                        for i in range(30)] + [{"id": 31, "title": "t", "status": "done", "base": shas[29],
                                                "commit": shas[30]}])
        md, calls = self.build_counting()
        self.assertLessEqual(len(calls), 6, [c[3:5] for c in calls[:8]])
        self.assertTrue(self.row(md, "| login#1 |").endswith(f"| {shas[1][:7]} |"))
        self.assertTrue(self.row(md, "| login#30 |").endswith(f"| {shas[30][:7]} |"))
        self.assertTrue(self.row(md, "| login#31 |").endswith("| commit kế tiếp |"))

    def test_mid_commits_counted_from_index(self):
        base = self.empty_commit("base")
        self.empty_commit("giữa 1")
        self.empty_commit("giữa 2")
        done = self.empty_commit("done")
        close = self.empty_commit("đóng")
        self.put_tasks([{"id": 1, "title": "t", "status": "done", "base": base, "commit": done}])
        md, _ = self.build_counting()
        self.assertTrue(self.row(md, "| login#1 |").endswith(f"| {close[:7]} (+3) |"))

    def test_commit_off_first_parent_chain_falls_back(self):
        base = self.head()
        self.git("checkout", "-q", "-b", "side")
        side = self.empty_commit("side")
        self.git("checkout", "-q", "-")
        main2 = self.empty_commit("main 2")
        self.git("merge", "-q", "--no-ff", "-m", "merge", "side")
        self.put_tasks([{"id": 1, "title": "t", "status": "done", "base": base, "commit": side}])
        md, _ = self.build_counting()
        self.assertTrue(self.row(md, "| login#1 |").endswith(f"| {main2[:7]} (+1) |"))


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


class RouteTest(Base):
    ROUTES = ("# Route\n\n| Route | Màn (class) | Feature | Design |\n|---|---|---|---|\n"
              "| /login | LoginScreen | login | docs/sources/design/login.png |\n"
              "| /forgot | ForgotScreen | login | |\n"
              "| /ghost | GhostScreen | login | |\n"
              "| <route> | <Màn> | <feature> | |\n")

    def setUp(self):
        super().setUp()
        write(self.root, ".claude/instructions/routes.md", self.ROUTES)
        write(self.root, "lib/router.dart",
              "GoRoute(path: '/login', builder: (_) => LoginScreen());\nGoRoute(path: '/forgot');\n"
              "GoRoute(path: '/extra');\nclass ForgotScreenState {}\n")
        write(self.root, "lib/login_screen.dart", "class LoginScreen {}\n")
        self.st("task", "add", "login", "A", "--routes", "/login")
        self.st("task", "add", "login", "B", "--routes", "/login,/forgot")
        self.st("task", "add", "login", "C", "--routes", "/nowhere")
        self.st("task", "done", "login", "1", "--skip-tests", "--skip-conform")

    def sec(self):
        return self.gen().split("## Route và màn")[1].split("\n## ")[0]

    def test_rows(self):
        s = self.sec()
        self.assertIn("| /login | LoginScreen | login | login#1, login#2 | đang làm | docs/sources/design/login.png | có |", s)
        self.assertIn("| /forgot | ForgotScreen | login | login#2 | đang làm | — | thiếu màn |", s)
        self.assertIn("| /ghost | GhostScreen | login | — | chưa có task | — | thiếu route, màn |", s)
        self.assertNotIn("<route>", s)

    def test_all_tasks_done_is_xong(self):
        self.st("task", "done", "login", "2", "--skip-tests", "--skip-conform")
        self.assertIn("| login#1, login#2 | xong |", self.sec())

    def test_task_route_not_declared(self):
        self.assertIn("- task login#3 khai route /nowhere không có trong routes.md", self.sec())

    def test_pattern_off_says_so(self):
        self.assertIn("chưa bật dò route trong code", self.sec())

    def test_pattern_finds_undeclared_route(self):
        self.toolchain({"test": "exit 0", "test_files": ["test/**"], "route_pattern": "path:\\s*'([^']+)'"})
        s = self.sec()
        self.assertIn("- route /extra có trong code, chưa khai trong routes.md", s)
        self.assertNotIn("route /login có trong code", s)

    def test_bad_pattern_does_not_break_report(self):
        for bad in ("path: '([^']+", "path: '[^']+'", "(a)(b)"):
            self.toolchain({"test": "exit 0", "test_files": ["test/**"], "route_pattern": bad})
            md = self.gen()
            self.assertIn("route_pattern không hợp lệ", md)
            self.assertIn("## Tổng quan", md)

    def test_no_routes_file(self):
        (self.root / ".claude/instructions/routes.md").unlink()
        self.assertIn("chưa có .claude/instructions/routes.md", self.sec())

    def test_non_utf8_source_file(self):
        (self.root / "lib/bad.dart").write_bytes(b"\xff\xfe class X {}\n")
        self.assertIn("| /login |", self.sec())

    def test_empty_screen_cell_is_not_found(self):
        write(self.root, ".claude/instructions/routes.md", self.ROUTES + "| /blank | | login | |\n")
        self.assertIn("| /blank | — | login | — | chưa có task | — | thiếu route, màn |", self.sec())


class ArchTest(Base):
    ARCH = ("# Kiến trúc\n\n## Nguồn sự thật dùng chung\nmô tả\n\n"
            "| Trạng thái | Owner (class, path) | Phát ra qua | Ai được ghi |\n|---|---|---|---|\n"
            "| auth | `AuthManager, core/auth/` | `Stream<AuthState>` | chỉ AuthManager |\n"
            "| premium | `PremiumManager, core/iap/` | `Stream<bool>` | chỉ PremiumManager |\n"
            "| <network status> | | | |\n\n"
            "## Logic tái dùng (manager)\n| Class | Việc duy nhất | Nằm ở | Test |\n|---|---|---|---|\n"
            "| `AuthManager` | giữ phiên | `lib/core/auth/` | `test/a_test.dart` |\n"
            "| `CartRuntime` | tính giỏ | `lib/core/cart/` | `test/cart_test.dart` |\n\n## DI\n")

    def setUp(self):
        super().setUp()
        write(self.root, ".claude/instructions/architecture.md", self.ARCH)
        write(self.root, "lib/core/auth/auth_manager.dart", "class AuthManager {}\n")
        write(self.root, "lib/core/cart/cart_runtime.dart", "class CartRuntime {}\n")
        write(self.root, "test/a_test.dart", "void main() {}\n")

    def test_truth_table_gets_in_code_column(self):
        s = self.gen().split("## Nguồn sự thật")[1].split("\n## ")[0]
        self.assertIn("| auth | `AuthManager, core/auth/` | `Stream<AuthState>` | chỉ AuthManager | có |", s)
        self.assertIn("| chỉ PremiumManager | thiếu |", s)
        self.assertNotIn("network status", s)

    def test_manager_table_checks_class_and_test_file(self):
        s = self.gen().split("## Logic tái dùng")[1].split("\n## ")[0]
        self.assertIn("| `test/a_test.dart` | có · test có |", s)
        self.assertIn("| `test/cart_test.dart` | có · thiếu test |", s)

    def test_empty_owner_cell_is_not_found(self):
        write(self.root, ".claude/instructions/architecture.md",
              "## Nguồn sự thật dùng chung\n| Trạng thái | Owner | Phát ra qua | Ai ghi |\n|---|---|---|---|\n"
              "| x | | | |\n")
        self.assertIn("| x | — | — | — | thiếu |", self.gen())

    def test_no_architecture_file(self):
        (self.root / ".claude/instructions/architecture.md").unlink()
        self.assertIn("chưa có .claude/instructions/architecture.md", self.gen())

    def test_empty_tables_say_not_declared(self):
        write(self.root, ".claude/instructions/architecture.md", "# Kiến trúc\n")
        self.assertIn("chưa khai", self.gen().split("## Nguồn sự thật")[1].split("\n## ")[0])

    def test_decisions_join_followups(self):
        write(self.root, ".claude/instructions/decisions/012-sheet.md", "# ADR-012: Dùng bottom sheet\n\nNgày: x\n")
        write(self.root, ".claude/instructions/decisions/003-di.md", "# ADR-003: DI bằng tay\n")
        self.st("followup", "add", "login", "Đổi lại khi design cập nhật", "--source", "ADR-012")
        self.st("followup", "add", "login", "Dọn log")
        self.st("followup", "add", "login", "Đã xong", "--source", "ADR-003"); self.st("followup", "done", "3")
        s = self.gen().split("## Quyết định và việc hẹn lại")[1]
        self.assertLess(s.index("ADR-003"), s.index("ADR-012"))
        self.assertIn("| ADR-003 | DI bằng tay | — |", s)
        self.assertIn("| ADR-012 | Dùng bottom sheet | #1 Đổi lại khi design cập nhật |", s)
        self.assertIn("| — | — | #2 Dọn log |", s)

    def test_followup_matches_whole_adr_code(self):
        write(self.root, ".claude/instructions/decisions/001-a.md", "# ADR-1: A\n")
        write(self.root, ".claude/instructions/decisions/012-b.md", "# ADR-12: B\n")
        self.st("followup", "add", "login", "Việc", "--source", "ADR-12")
        s = self.gen().split("## Quyết định và việc hẹn lại")[1]
        self.assertIn("| ADR-1 | A | — |", s)
        self.assertIn("| ADR-12 | B | #1 Việc |", s)

    def test_manager_test_cell_directory_is_not_a_test(self):
        write(self.root, ".claude/instructions/architecture.md",
              "## Logic tái dùng (manager)\n| Class | Việc | Nằm ở | Test |\n|---|---|---|---|\n"
              "| `AuthManager` | x | `lib/` | `test/` |\n")
        self.assertIn("| `test/` | có · thiếu test |", self.gen())

    def test_no_decisions_no_followups(self):
        self.assertIn("không có", self.gen().split("## Quyết định và việc hẹn lại")[1])


if __name__ == "__main__":
    unittest.main()

import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / ".claude" / "tools"
FIX = ROOT / "tests" / "fixtures" / "flutter_mini"


def tool(name, root, *args):
    return subprocess.run([sys.executable, str(TOOLS / name), "--root", str(root), *args],
                          capture_output=True, text=True)


class ReportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "proj"
        shutil.copytree(FIX, self.root)
        tool("state.py", self.root, "init")
        tool("state.py", self.root, "feature", "add", "login")
        tool("state.py", self.root, "feature", "add", "profile")
        for t in ("A", "B", "C"):
            tool("state.py", self.root, "task", "add", "login", t)
        for i in ("1", "2", "3"):
            tool("state.py", self.root, "task", "done", "login", i, "--skip-tests")
        tool("state.py", self.root, "task", "add", "profile", "D")
        v = self.root / "docs/napoleon/features/login/verify.md"
        v.parent.mkdir(parents=True)
        v.write_text("## Máy\n- [x] format\n- [x] test\n## Verifier\n- [x] yêu cầu 1\n## Người\n- [ ] UI\n")

    def tearDown(self):
        self.tmp.cleanup()

    def render(self):
        r = tool("report.py", self.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return (self.root / "reports/roadmap.html").read_text(encoding="utf-8")

    def test_html_generated_with_sections(self):
        html = self.render()
        for s in ("Feature", "Task", "Commit", "Codegraph", "Verify", "Việc hẹn lại", "Audit"):
            self.assertIn(s, html)

    def test_numbers_from_state(self):
        html = self.render()
        self.assertRegex(html, r'data-stat="features">2<')
        self.assertRegex(html, r'data-stat="tasks-done">3<')
        self.assertRegex(html, r'data-stat="tasks-total">4<')

    def test_no_git_repo(self):
        html = self.render()
        m = re.search(r'id="commits".*?</section>', html, re.S)
        self.assertIsNotNone(m)
        self.assertIn("không có dữ liệu", m.group(0))

    def test_no_external_resources(self):
        html = self.render()
        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)
        self.assertNotIn("<script src", html)

    def test_verify_counts_separate_machine_from_human(self):
        html = self.render()
        self.assertRegex(html, r"data-stat='verify-login'>3/3<")    # máy + verifier
        self.assertRegex(html, r"data-stat='human-login'>1<")       # người chờ, không kéo tỉ lệ xuống
        self.assertRegex(html, r'data-stat="verify-human">1<')

    def test_followups_section(self):
        tool("state.py", self.root, "followup", "add", "login", "thêm chip B26", "--source", "ADR-020")
        html = self.render()
        self.assertRegex(html, r'data-stat="followups-open">1<')
        self.assertIn("thêm chip B26", html)
        self.assertIn("ADR-020", html)

    def test_verify_rounds_column(self):
        tool("state.py", self.root, "verify", "login", "fail", "--issue", "hardcode")
        tool("state.py", self.root, "verify", "login", "pass")
        m = re.search(r'id="verify".*?</section>', self.render(), re.S)
        self.assertIn("<td>2</td>", m.group(0))

    def test_every_stat_has_source_note(self):
        html = self.render()
        sections = re.findall(r"<section.*?</section>", html, re.S)
        self.assertGreaterEqual(len(sections), 6)
        for s in sections:
            self.assertIn('class="src"', s)

    def test_codegraph_section_no_data_when_schema_unknown(self):
        sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
        from make_fake_codegraph import make_unknown_db
        make_unknown_db(self.root / ".codegraph/codegraph.db")
        html = self.render()
        m = re.search(r'id="codegraph".*?</section>', html, re.S)
        self.assertIn("không có dữ liệu", m.group(0))
        self.assertNotIn("foo", m.group(0))

    def test_codegraph_section_counts_when_schema_known(self):
        sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
        from make_fake_codegraph import make_db_real_schema
        files = ["lib/main.dart", "lib/domain/user.dart"]
        make_db_real_schema(self.root / ".codegraph/codegraph.db", files, [("lib/main.dart", "lib/domain/user.dart")])
        html = self.render()
        m = re.search(r'id="codegraph".*?</section>', html, re.S)
        self.assertRegex(m.group(0), r'data-stat="cg-files">2<')
        self.assertNotIn("unresolved_refs", m.group(0))

    def test_commit_count_uses_word_boundary(self):
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        import os
        env = {**os.environ, **env}
        tool("state.py", self.root, "feature", "add", "ui")
        for msg in ("feat(ui): header", "build ui-kit", "guide update", "fix: ui"):
            subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", msg], cwd=self.root, env=env, check=True)
        html = self.render()
        m = re.search(r"<td>ui</td><td>(\d+)</td>", html)
        self.assertIsNotNone(m, html)
        self.assertEqual(m.group(1), "2")  # "feat(ui): header" và "fix: ui"; không tính ui-kit, guide

    def test_audit_exception_does_not_kill_report(self):
        mm = self.root / ".claude/instructions/module-map.md"
        mm.parent.mkdir(parents=True)
        mm.write_bytes(b"\xff\xfe## Ph\xe1\xbb\xa5 thu\xe1\xbb\x99c cho ph\xc3\xa9p\n| a | b |\n")
        html = self.render()
        self.assertIn("Audit", html)

    def test_custom_out_path(self):
        r = tool("report.py", self.root, "--out", "x/y.html")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.root / "x/y.html").exists())


if __name__ == "__main__":
    unittest.main()

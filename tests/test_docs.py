"""Kiểm tra cấu trúc markdown của bộ: frontmatter, độ dài, dấu generated."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
C = ROOT / ".claude"
GEN = "<!-- napoleon:generated -->"


def frontmatter(path):
    """Frontmatter chỉ hợp lệ khi '---' ở dòng 1 (Claude Code không bỏ qua comment phía trước)."""
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    return m.group(1) if m else None


def body_after_frontmatter(path):
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n.*?\n---\n(.*)$", text, re.S)
    return m.group(1) if m else text


def fm_field(fm, key):
    """Giá trị field, gồm cả dòng tiếp theo thụt đầu dòng (multi-line)."""
    m = re.search(rf"^{key}:(.*(?:\n[ \t]+.*)*)", fm, re.M)
    return m.group(1).strip() if m else None


class DocsTest(unittest.TestCase):
    def test_claude_md_under_100_lines(self):
        n = len((C / "CLAUDE.md").read_text(encoding="utf-8").splitlines())
        self.assertLessEqual(n, 100)
        self.assertGreater(n, 20, "CLAUDE.md còn là placeholder")

    def test_every_skill_has_frontmatter(self):
        skills = sorted(C.glob("skills/*/SKILL.md"))
        self.assertGreaterEqual(len(skills), 7)
        for s in skills:
            fm = frontmatter(s)
            self.assertIsNotNone(fm, s)
            self.assertEqual(fm_field(fm, "name"), s.parent.name, s)
            desc = fm_field(fm, "description")
            self.assertTrue(desc, s)
            self.assertLessEqual(len(desc.splitlines()), 3, s)

    def test_every_command_has_description(self):
        cmds = sorted(C.glob("commands/*.md"))
        self.assertEqual({c.stem for c in cmds},
                         {"map-codebase", "start-build", "setup-agents", "feature", "status", "report", "retro"})
        for c in cmds:
            fm = frontmatter(c)
            self.assertIsNotNone(fm, c)
            self.assertTrue(fm_field(fm, "description"), c)

    def test_agent_frontmatter(self):
        agents = sorted(C.glob("agents/*.md"))
        self.assertEqual([a.stem for a in agents], ["verifier"])
        fm = frontmatter(agents[0])
        for k in ("name", "description", "tools"):
            self.assertTrue(fm_field(fm, k), k)
        self.assertLessEqual(len(fm_field(fm, "description").splitlines()), 3)

    def test_conventions_template_common_block_is_filled(self):
        """Khối 'Chung' phải điền sẵn (không placeholder), các khối khác được phép có placeholder."""
        text = (C / "templates" / "conventions.md").read_text(encoding="utf-8")
        for h in ("## Chung", "## Theo stack", "## Bổ sung của bạn", "## Không kiểm tự động"):
            self.assertIn(h, text)
        common = text.split("## Chung", 1)[1].split("## Theo stack", 1)[0]
        self.assertNotRegex(common, r"<[^>]*>", "khối Chung còn placeholder")
        self.assertGreaterEqual(common.count("[rules.json]"), 3)

    def test_brief_template_exists(self):
        text = (C / "templates" / "brief.md").read_text(encoding="utf-8")
        self.assertIn("nguyên văn", text)

    def test_feature_loop_names_spec_plan_paths(self):
        text = (C / "skills" / "feature-loop" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("docs/napoleon/features/<tên>/spec.md", text)
        self.assertIn("docs/napoleon/features/<tên>/plan.md", text)
        self.assertIn("docs/superpowers", text)  # phải nói rõ KHÔNG dùng

    def test_generated_templates_marked_after_frontmatter(self):
        for name in ("feature-skill.md", "feature-agent.md", "path-rule.md", "project-command.md"):
            p = C / "templates" / name
            self.assertTrue(p.exists(), p)
            self.assertIsNotNone(frontmatter(p), f"{p}: frontmatter phải ở dòng 1")
            first_body = body_after_frontmatter(p).lstrip("\n").splitlines()[0]
            self.assertEqual(first_body, GEN, p)

    def test_frontmatter_descriptions_yaml_safe(self):
        """Giá trị description chứa ': ' phải được bọc trong ngoặc kép để parser YAML chặt không hỏng."""
        files = list(C.glob("skills/*/SKILL.md")) + list(C.glob("commands/*.md")) + list(C.glob("agents/*.md")) \
            + [C / "templates" / n for n in ("feature-skill.md", "feature-agent.md")]
        for f in files:
            fm = frontmatter(f)
            self.assertIsNotNone(fm, f)
            for key in ("description", "argument-hint"):
                v = fm_field(fm, key)
                if v and ": " in v:
                    self.assertTrue(v.startswith('"') and v.endswith('"'), f"{f}: {key} chứa ': ' mà không bọc ngoặc kép")

    def test_reference_files_under_80_lines(self):
        refs = sorted(C.glob("skills/architecture-interview/references/*.md"))
        self.assertGreaterEqual(len(refs), 7)
        for r in refs:
            self.assertLessEqual(len(r.read_text(encoding="utf-8").splitlines()), 80, r)

    def test_templates_json_valid(self):
        for name in ("rules.json", "toolchain.json"):
            data = json.loads((C / "templates" / name).read_text(encoding="utf-8"))
            self.assertTrue(data)

    def test_module_map_template_has_allowed_table(self):
        text = (C / "templates" / "module-map.md").read_text(encoding="utf-8")
        self.assertIn("## Phụ thuộc cho phép", text)
        self.assertRegex(text, r"\|\s*từ\s*\|\s*đến\s*\|")

    def test_verify_template_sections(self):
        text = (C / "templates" / "verify.md").read_text(encoding="utf-8")
        for h in ("## Máy", "## Verifier", "## Người"):
            self.assertIn(h, text)


if __name__ == "__main__":
    unittest.main()

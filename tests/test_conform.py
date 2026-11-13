import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / ".claude" / "tools"
FIX = ROOT / "tests" / "fixtures" / "flutter_mini"
sys.path.insert(0, str(TOOLS))

from imports import read_imports  # noqa: E402


def run(*args):
    return subprocess.run([sys.executable, str(TOOLS / "conform.py"), *args], capture_output=True, text=True)


class ReadImportsTest(unittest.TestCase):
    def _file(self, name, text):
        d = tempfile.mkdtemp()
        p = Path(d) / name
        p.write_text(text)
        return p

    def test_read_imports_dart(self):
        p = self._file("a.dart", "import 'package:flutter/material.dart';\nimport \"../x.dart\" as x;\nexport 'y.dart';\n")
        self.assertEqual(read_imports(p), ["package:flutter/material.dart", "../x.dart"])

    def test_read_imports_kotlin(self):
        p = self._file("A.kt", "package a.b\nimport kotlinx.coroutines.flow.Flow\nimport a.b.c.*\n")
        self.assertEqual(read_imports(p), ["kotlinx.coroutines.flow.Flow", "a.b.c.*"])

    def test_read_imports_swift_multiline(self):
        p = self._file("A.swift", "import Foundation\nimport UIKit\n@testable import App\nimport struct Foundation.Date\n")
        self.assertEqual(read_imports(p), ["Foundation", "UIKit", "App", "Foundation.Date"])

    def test_read_imports_ts(self):
        p = self._file("a.ts", "import x from './x';\nimport {y} from \"lib/y\";\nconst z = require('z');\n")
        self.assertEqual(read_imports(p), ["./x", "lib/y", "z"])

    def test_read_imports_py(self):
        p = self._file("a.py", "import os\nfrom pathlib import Path\nimport a.b as c\n")
        self.assertEqual(read_imports(p), ["os", "pathlib", "a.b"])


class ConformTest(unittest.TestCase):
    def test_four_violations_detected(self):
        r = run("--root", str(FIX), "--rules", str(FIX / "rules.json"))
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        for rid in ("no-flutter-in-domain", "bloc-suffix", "repo-in-data", "max-400"):
            self.assertIn(rid, r.stdout)
        self.assertEqual(r.stdout.strip().splitlines()[-1], "6 file quét, 4 vi phạm")

    def test_json_output(self):
        r = run("--root", str(FIX), "--rules", str(FIX / "rules.json"), "--json")
        data = json.loads(r.stdout)
        self.assertEqual(len(data), 4)
        self.assertEqual(set(data[0]), {"path", "line", "rule", "message"})

    def test_no_files_matched(self):
        with tempfile.TemporaryDirectory() as d:
            rules = Path(d) / "rules.json"
            rules.write_text(json.dumps({"rules": [{"id": "x", "type": "max-lines", "in": "nothing/**", "max": 1}]}))
            r = run("--root", str(FIX), "--rules", str(rules))
            self.assertEqual(r.returncode, 0)
            self.assertEqual(r.stdout.strip(), "0 file quét, 0 vi phạm")

    def test_doublestar_matches_zero_dirs(self):
        """'lib/**/domain/**' phải khớp cả 'lib/domain/user.dart' (0 thư mục giữa)."""
        with tempfile.TemporaryDirectory() as d:
            rules = Path(d) / "rules.json"
            rules.write_text(json.dumps({"rules": [{"id": "x", "type": "forbidden-import",
                                                    "in": "lib/**/domain/**", "forbid": ["package:flutter/**"]}]}))
            r = run("--root", str(FIX), "--rules", str(rules))
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("lib/domain/user.dart", r.stdout)

    def test_must_be_under_does_not_match_prefix_dir(self):
        """must_be_under 'lib/data' không được chấp nhận 'lib/database/x_repository.dart'."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); (root / "lib/database").mkdir(parents=True)
            (root / "lib/database/x_repository.dart").write_text("class X {}\n")
            rules = root / "rules.json"
            rules.write_text(json.dumps({"rules": [{"id": "loc", "type": "location",
                                                    "pattern": "*_repository.dart", "must_be_under": "lib/data"}]}))
            r = run("--root", str(root), "--rules", str(rules))
            self.assertEqual(r.returncode, 1, r.stdout)

    def _ratio_rule(self, d, **kw):
        rules = Path(d) / "rules.json"
        rule = {"id": "few-comments", "type": "max-comment-ratio", "in": "lib/**", "max_ratio": 0.15}
        rule.update(kw)
        rules.write_text(json.dumps({"rules": [rule]}))
        return rules

    def test_comment_ratio_flags_comment_heavy_file(self):
        """big.dart trong fixture ~99% dòng là comment → vi phạm; file khác không."""
        with tempfile.TemporaryDirectory() as d:
            r = run("--root", str(FIX), "--rules", str(self._ratio_rule(d)), "--json")
            data = json.loads(r.stdout)
            self.assertEqual([v["path"] for v in data], ["lib/data/big.dart"])
            self.assertIn("%", data[0]["message"])

    def test_comment_ratio_skips_small_files(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); (root / "lib").mkdir()
            (root / "lib/a.dart").write_text("// a\n// b\n// c\nclass A {}\n")
            r = run("--root", str(root), "--rules", str(self._ratio_rule(d, min_lines=20)))
            self.assertEqual(r.returncode, 0, r.stdout)

    def test_comment_ratio_counts_block_and_python_comments(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); (root / "lib").mkdir()
            kt = "/*\n * banner\n * banner\n */\n" + "val x = 1\n" * 2
            (root / "lib/A.kt").write_text(kt)
            py = "# c1\n# c2\n# c3\nx = 1\n"
            (root / "lib/b.py").write_text(py)
            r = run("--root", str(root), "--rules", str(self._ratio_rule(d, min_lines=1)), "--json")
            paths = sorted(v["path"] for v in json.loads(r.stdout))
            self.assertEqual(paths, ["lib/A.kt", "lib/b.py"])

    def test_rules_json_without_rules_key_exit2(self):
        with tempfile.TemporaryDirectory() as d:
            rules = Path(d) / "rules.json"
            rules.write_text("{}")
            r = run("--root", str(FIX), "--rules", str(rules))
            self.assertEqual(r.returncode, 2)
            self.assertNotIn("Traceback", r.stderr)

    def test_missing_rules_exit2(self):
        r = run("--root", str(FIX), "--rules", str(FIX / "khong_co.json"))
        self.assertEqual(r.returncode, 2)

    def test_unknown_rule_type_exit2(self):
        with tempfile.TemporaryDirectory() as d:
            rules = Path(d) / "rules.json"
            rules.write_text(json.dumps({"rules": [{"id": "x", "type": "khong-co-loai", "in": "lib/**"}]}))
            r = run("--root", str(FIX), "--rules", str(rules))
            self.assertEqual(r.returncode, 2)
            self.assertIn("khong-co-loai", r.stderr)
            self.assertNotIn("Traceback", r.stderr)

    def test_bad_regex_exit2(self):
        with tempfile.TemporaryDirectory() as d:
            rules = Path(d) / "rules.json"
            rules.write_text(json.dumps({"rules": [{"id": "x", "type": "forbidden-pattern", "in": "lib/**",
                                                    "regex": "Color(0x"}]}))
            r = run("--root", str(FIX), "--rules", str(rules))
            self.assertEqual(r.returncode, 2)
            self.assertNotIn("Traceback", r.stderr)


class NewRuleTypesTest(unittest.TestCase):
    """forbidden-pattern, max-function-lines, max-params, no-sibling-import, exclude, --files."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.write("pubspec.yaml", "name: app\n")
        self.write("lib/core/theme/colors.dart", "const c = Color(0xFF00FF00);\n")
        self.write("lib/features/home/home_page.dart",
                   "import 'package:app/features/login/login_page.dart';\n"
                   "// Color(0x trong comment không tính\n"
                   "const bad = Color(0xFFFFFFFF);\n"
                   "String label() => 'Color(0xAA) trong chuỗi';\n")
        self.write("lib/features/login/login_page.dart",
                   "import 'package:app/core/theme/colors.dart';\n"
                   "int big(int a, int b, int c, int d, int e, int f) {\n" + "  print(a);\n" * 45 + "  return a;\n}\n")
        self.write("lib/features/login/login_page.g.dart", "const gen = Color(0xFF123456);\n")

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def rules(self, *rules, exclude=None):
        p = self.root / "rules.json"
        p.write_text(json.dumps({"exclude": exclude or [], "rules": list(rules)}, ensure_ascii=False))
        return str(p)

    def violations(self, *rules, exclude=None, extra=()):
        r = run("--root", str(self.root), "--rules", self.rules(*rules, exclude=exclude), "--json", *extra)
        return json.loads(r.stdout)

    def test_forbidden_pattern_skips_comments_and_honours_allow(self):
        v = self.violations({"id": "color", "type": "forbidden-pattern", "in": "lib/**", "regex": r"Color\(0x",
                             "allow": ["lib/core/theme/**"], "message": "màu phải từ theme"})
        self.assertEqual([(x["path"], x["line"]) for x in v],
                         [("lib/features/home/home_page.dart", 3), ("lib/features/home/home_page.dart", 4),
                          ("lib/features/login/login_page.g.dart", 1)])   # dòng 2 là comment → không tính
        self.assertEqual(v[0]["message"], "màu phải từ theme")

    def test_exclude_covers_generated_file(self):
        v = self.violations({"id": "color", "type": "forbidden-pattern", "in": "lib/**", "regex": r"Color\(0x",
                             "allow": ["lib/core/theme/**"], "skip_strings": True}, exclude=["*.g.dart"])
        self.assertEqual([x["path"] for x in v], ["lib/features/home/home_page.dart"])

    def test_skip_strings_ignores_string_literals(self):
        v = self.violations({"id": "paren", "type": "forbidden-pattern", "in": "lib/features/home/**",
                             "regex": r"Color\(0x", "skip_strings": True})
        self.assertEqual([x["line"] for x in v], [3])

    def test_max_function_lines_and_params(self):
        v = self.violations({"id": "fn", "type": "max-function-lines", "in": "lib/**", "max": 40},
                            {"id": "pr", "type": "max-params", "in": "lib/**", "max": 5})
        self.assertEqual({(x["rule"], x["path"]) for x in v},
                         {("fn", "lib/features/login/login_page.dart"), ("pr", "lib/features/login/login_page.dart")})
        self.assertIn("big", v[0]["message"])

    def test_max_params_can_skip_constructors(self):
        self.write("lib/core/data.dart", "class Data {\n  const Data(this.a, this.b, this.c, this.d, this.e, this.f);\n}\n")
        rule = {"id": "pr", "type": "max-params", "in": "lib/core/**", "max": 5}
        self.assertEqual(len(self.violations(dict(rule))), 1)
        self.assertEqual(self.violations(dict(rule, constructors=False)), [])

    def test_no_sibling_import_both_directions(self):
        v = self.violations({"id": "sib", "type": "no-sibling-import", "base": "lib/features"})
        self.assertEqual([x["path"] for x in v], ["lib/features/home/home_page.dart"])
        self.assertIn("features/login", v[0]["message"])

    def test_no_sibling_import_allows_listed_dir(self):
        self.assertEqual(self.violations({"id": "sib", "type": "no-sibling-import", "base": "lib/features",
                                          "allow": ["login"]}), [])

    def test_no_sibling_import_ignores_relative_inside_feature(self):
        self.write("lib/features/home/widgets/row.dart", "import '../home_page.dart';\n")
        v = self.violations({"id": "sib", "type": "no-sibling-import", "base": "lib/features", "allow": ["login"]})
        self.assertEqual(v, [])

    def test_files_flag_limits_scan(self):
        v = self.violations({"id": "color", "type": "forbidden-pattern", "in": "lib/**", "regex": r"Color\(0x",
                             "skip_strings": True}, extra=("--files", "lib/features/home/home_page.dart"))
        self.assertEqual([x["path"] for x in v], ["lib/features/home/home_page.dart"])


class CoverageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "lib").mkdir()
        (self.root / "lib/a.dart").write_text("class A {}\n")
        self.rules_path = self.root / "rules.json"
        self.conv = self.root / "conventions.md"

    def tearDown(self):
        self.tmp.cleanup()

    def run_cov(self, rules, conventions):
        self.rules_path.write_text(json.dumps({"rules": rules}, ensure_ascii=False), encoding="utf-8")
        self.conv.write_text(conventions, encoding="utf-8")
        return run("--root", str(self.root), "--rules", str(self.rules_path), "--coverage",
                   "--conventions", str(self.conv))

    def test_clean_coverage(self):
        r = self.run_cov([{"id": "max-400", "type": "max-lines", "in": "lib/**", "max": 400}],
                         "# Quy ước\n- File ≤ 400 dòng. `[rule: max-400]`\n- Tên nói việc. `[tay]`\n")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("0 lỗi", r.stdout)

    def test_untagged_convention_is_error(self):
        r = self.run_cov([{"id": "max-400", "type": "max-lines", "in": "lib/**", "max": 400}],
                         "# Quy ước\n- File ≤ 400 dòng. `[rule: max-400]`\n- Code phải sạch.\n")
        self.assertEqual(r.returncode, 1)
        self.assertIn("chưa gắn", r.stdout)

    def test_tag_pointing_at_missing_rule(self):
        r = self.run_cov([{"id": "max-400", "type": "max-lines", "in": "lib/**", "max": 400}],
                         "# Quy ước\n- File ngắn. `[rule: khong-co]`\n")
        self.assertEqual(r.returncode, 1)
        self.assertIn("khong-co", r.stdout)

    def test_dead_rule_is_warning_not_error(self):
        r = self.run_cov([{"id": "max-400", "type": "max-lines", "in": "khong_co_thu_muc/**", "max": 400}],
                         "# Quy ước\n- File ≤ 400 dòng. `[rule: max-400]`\n")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("không khớp file nào", r.stdout)

    def test_manual_section_needs_no_tag(self):
        r = self.run_cov([{"id": "max-400", "type": "max-lines", "in": "lib/**", "max": 400}],
                         "# Quy ước\n- File ≤ 400 dòng. `[rule: max-400]`\n"
                         "## Không kiểm tự động\n- Owner duy nhất — nhận ra: hai nơi giữ cùng biến.\n")
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_template_placeholder_line_skipped(self):
        r = self.run_cov([{"id": "max-400", "type": "max-lines", "in": "lib/**", "max": 400}],
                         "# Quy ước\n- File ≤ 400 dòng. `[rule: max-400]`\n- <quy ước riêng dự án 1>\n")
        self.assertEqual(r.returncode, 0, r.stdout)


class TemplateRulesTest(unittest.TestCase):
    def test_template_rules_json_types_are_known(self):
        sys.path.insert(0, str(TOOLS))
        from conform import REQUIRED  # noqa: E402
        doc = json.loads((ROOT / ".claude/templates/rules.json").read_text(encoding="utf-8"))
        self.assertIn("exclude", doc)
        ids = [r["id"] for r in doc["rules"]]
        self.assertEqual(len(ids), len(set(ids)))
        for r in doc["rules"]:
            self.assertIn(r["type"], REQUIRED, r["id"])
            for k in REQUIRED[r["type"]]:
                self.assertIn(k, r, r["id"])

    def test_template_conventions_tags_point_at_template_rules(self):
        doc = json.loads((ROOT / ".claude/templates/rules.json").read_text(encoding="utf-8"))
        ids = {r["id"] for r in doc["rules"]}
        text = (ROOT / ".claude/templates/conventions.md").read_text(encoding="utf-8")
        common = text.split("## Chung", 1)[1].split("## Theo stack", 1)[0]
        tags = {t.strip() for m in re.finditer(r"\[rule:\s*([^\]]+)\]", common) for t in m.group(1).split(",")}
        self.assertTrue(tags)
        self.assertEqual(tags - ids, set(), "nhãn trong khối Chung trỏ rule không có trong templates/rules.json")


if __name__ == "__main__":
    unittest.main()

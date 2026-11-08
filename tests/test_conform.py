import json
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


if __name__ == "__main__":
    unittest.main()

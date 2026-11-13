"""stack.py: đọc manifest + lockfile → stack.md, giữ ghi chú của người, --check khi manifest đổi."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / ".claude" / "tools" / "stack.py"

PUBSPEC = """name: demo_app
version: 1.2.3+4
environment:
  sdk: ^3.5.0
dependencies:
  flutter:
    sdk: flutter
  dio: ^5.4.0 # HTTP
  go_router: ">=14.0.0 <15.0.0"
  my_local:
    path: ../my_local
  from_git:
    git:
      url: https://example.com/x.git
dev_dependencies:
  flutter_test:
    sdk: flutter
  mocktail: ^1.0.0
dependency_overrides:
  intl: 0.19.0
flutter:
  uses-material-design: true
"""

LOCK = """packages:
  dio:
    dependency: "direct main"
    description:
      name: dio
    source: hosted
    version: "5.4.3+1"
  flutter:
    dependency: "direct main"
    description: flutter
    source: sdk
    version: "0.0.0"
  go_router:
    dependency: "direct main"
    source: hosted
    version: "14.2.0"
  mocktail:
    dependency: "direct dev"
    source: hosted
    version: "1.0.4"
  intl:
    dependency: "direct overridden"
    source: hosted
    version: "0.19.0"
  meta:
    dependency: transitive
    source: hosted
    version: "1.15.0"
sdks:
  dart: ">=3.5.0 <4.0.0"
  flutter: ">=3.24.0"
"""

APP_GRADLE = """plugins { id("com.android.application") }
android {
    namespace = "com.example.demo"
    compileSdk = 35
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17 }
    defaultConfig {
        applicationId = "com.example.demo"
        minSdk = 24
        targetSdk = 35
    }
}
"""

SETTINGS_GRADLE = """plugins {
    id("com.android.application") version "8.7.0" apply false
    id("org.jetbrains.kotlin.android") version "2.1.0" apply false
}
"""

CATALOG = """[versions]
okhttp = "4.12.0"
[libraries]
okhttp = { module = "com.squareup.okhttp3:okhttp", version.ref = "okhttp" }
koin = { group = "io.insert-koin", name = "koin-android", version = "3.5.6" }
material = "com.google.android.material:material:1.12.0"
"""


class StackTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def run_tool(self, *args):
        return subprocess.run([sys.executable, str(TOOL), "--root", str(self.root), "--no-probe", *args],
                              capture_output=True, text=True)

    def data(self):
        r = self.run_tool("--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def flutter_project(self):
        self.write("pubspec.yaml", PUBSPEC)
        self.write("pubspec.lock", LOCK)
        self.write(".fvmrc", '{"flutter": "3.24.5"}')

    def section(self, kind):
        return next(s for s in self.data()["sections"] if s["kind"] == kind)

    def test_dart_declared_and_locked_versions(self):
        self.flutter_project()
        s = self.section("Dart/Flutter")
        deps = {n: (d, u, r) for n, d, u, r in s["deps"]}
        self.assertEqual(deps["dio"], ("^5.4.0", "5.4.3+1", "HTTP"))
        self.assertEqual(deps["go_router"][1], "14.2.0")
        self.assertEqual(deps["flutter"][1], "theo SDK")
        self.assertEqual(deps["my_local"][:2], ("path: ../my_local", "chưa khoá"))
        self.assertEqual(deps["from_git"][0], "git")
        self.assertEqual([n for n, *_ in s["dev"]], ["flutter_test", "mocktail"])
        self.assertEqual([n for n, *_ in s["overrides"]], ["intl"])
        self.assertIn("1 gói bắc cầu", s["note"])

    def test_platform_versions_from_pins(self):
        self.flutter_project()
        plat = {a: (b, c) for a, b, c in self.section("Dart/Flutter")["platform"]}
        self.assertEqual(plat["Flutter"], ("3.24.5", ".fvmrc"))
        self.assertEqual(plat["Dart SDK"][0], ">=3.5.0 <4.0.0")
        self.assertEqual(self.data()["version"], "1.2.3+4")
        self.assertEqual(self.data()["app"], "demo_app")

    def test_without_lock_says_unlocked(self):
        self.write("pubspec.yaml", PUBSPEC)
        s = self.section("Dart/Flutter")
        self.assertEqual({n: u for n, _, u, _ in s["deps"]}["dio"], "chưa khoá")
        self.assertIn("pub get", s["note"])

    def test_android_from_gradle_and_catalog(self):
        self.write("android/app/build.gradle.kts", APP_GRADLE)
        self.write("android/settings.gradle.kts", SETTINGS_GRADLE)
        self.write("android/gradle/libs.versions.toml", CATALOG)
        self.write("android/gradle/wrapper/gradle-wrapper.properties",
                   "distributionUrl=https\\://services.gradle.org/distributions/gradle-8.10.2-all.zip\n")
        s = self.section("Android")
        plat = {a: b for a, b, _ in s["platform"]}
        self.assertEqual((plat["compileSdk"], plat["targetSdk"], plat["minSdk"]), ("35", "35", "24"))
        self.assertEqual(plat["Java/JVM"], "17")
        self.assertEqual(plat["Android Gradle Plugin"], "8.7.0")
        self.assertEqual(plat["Kotlin"], "2.1.0")
        self.assertEqual(plat["Gradle"], "8.10.2")
        deps = {n: u for n, _, u, _ in s["deps"]}
        self.assertEqual(deps, {"com.squareup.okhttp3:okhttp": "4.12.0", "io.insert-koin:koin-android": "3.5.6",
                                "com.google.android.material:material": "1.12.0"})

    def test_ios_deployment_target_and_flutter_pods_summarised(self):
        self.flutter_project()
        self.write("ios/Runner.xcodeproj/project.pbxproj",
                   "IPHONEOS_DEPLOYMENT_TARGET = 13.0;\nIPHONEOS_DEPLOYMENT_TARGET = 13.0;\nSWIFT_VERSION = 5.0;\n")
        self.write("ios/Podfile.lock", "PODS:\n  - Flutter (1.0.0)\n  - camera (0.0.1):\n    - Flutter\n\nDEPENDENCIES:\n"
                                       "  - Flutter (from `Flutter`)\n")
        s = self.section("iOS")
        self.assertEqual({a: b for a, b, _ in s["platform"]}["iOS deployment target"], "13.0")
        self.assertEqual(s["deps"], [])
        self.assertIn("2 pod", s["note"])

    def test_node_project(self):
        self.write("package.json", json.dumps({"name": "web", "version": "0.1.0", "engines": {"node": ">=20"},
                                               "dependencies": {"react": "^18.2.0", "axios": "^1.6.0"},
                                               "devDependencies": {"vitest": "^1.0.0"}}))
        self.write("package-lock.json", json.dumps({"packages": {"": {}, "node_modules/react": {"version": "18.3.1"},
                                                                 "node_modules/axios": {"version": "1.7.2"},
                                                                 "node_modules/a/node_modules/react": {"version": "1"}}}))
        s = self.section("Node/TS")
        self.assertEqual({n: (u, r) for n, _, u, r in s["deps"]},
                         {"axios": ("1.7.2", "HTTP"), "react": ("18.3.1", "UI")})
        self.assertEqual(s["dev"][0][2], "chưa khoá")
        self.assertEqual(s["platform"], [["engines.node", ">=20", "package.json"]])

    def test_python_project(self):
        self.write("pyproject.toml", '[project]\nname = "x"\nrequires-python = ">=3.11"\n'
                                     'dependencies = [\n  "httpx>=0.27",\n  "pydantic==2.7.1",\n]\n')
        s = self.section("Python")
        self.assertEqual([n for n, *_ in s["deps"]], ["httpx", "pydantic"])
        self.assertEqual({a: b for a, b, _ in s["platform"]}["Python"], ">=3.11")

    def test_writes_markdown_and_keeps_user_notes(self):
        self.flutter_project()
        r = self.run_tool()
        self.assertEqual(r.returncode, 0, r.stderr)
        out = self.root / "docs/napoleon/stack.md"
        text = out.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# Tech stack — demo_app"))
        self.assertIn("| `dio` | ^5.4.0 | `5.4.3+1` | HTTP |", text)
        out.write_text(text + "\nKhông dùng gói http, đã có dio.\n", encoding="utf-8")
        self.write("pubspec.lock", LOCK.replace('version: "5.4.3+1"', 'version: "5.5.0"'))
        self.run_tool()
        text = out.read_text(encoding="utf-8")
        self.assertIn("`5.5.0`", text)
        self.assertNotIn("`5.4.3+1`", text)
        self.assertIn("Không dùng gói http, đã có dio.", text)
        self.assertEqual(text.count("napoleon:stack:begin"), 1)

    def test_regenerating_unchanged_project_is_byte_identical(self):
        self.flutter_project()
        self.run_tool()
        first = (self.root / "docs/napoleon/stack.md").read_bytes()
        self.run_tool()
        self.assertEqual(first, (self.root / "docs/napoleon/stack.md").read_bytes())

    def test_check_detects_manifest_change(self):
        self.flutter_project()
        self.assertEqual(self.run_tool("--check").returncode, 1)     # chưa có stack.md
        self.run_tool()
        self.assertEqual(self.run_tool("--check").returncode, 0)
        self.write("pubspec.yaml", PUBSPEC.replace("dio: ^5.4.0", "dio: ^5.6.0"))
        r = self.run_tool("--check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("pubspec.yaml", r.stdout)
        self.assertIn("/stack", r.stdout)

    def test_empty_project(self):
        r = self.run_tool()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Không tìm thấy manifest", (self.root / "docs/napoleon/stack.md").read_text(encoding="utf-8"))

    def test_toolchain_commands_listed(self):
        self.flutter_project()
        self.write(".claude/instructions/toolchain.json", json.dumps({"test": "flutter test", "build": "", "_doc": "x"}))
        self.assertEqual(self.data()["toolchain"], {"test": "flutter test"})


if __name__ == "__main__":
    unittest.main()

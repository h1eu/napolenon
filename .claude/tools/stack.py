#!/usr/bin/env python3
"""Tech stack của dự án: nền tảng, SDK, thư viện và phiên bản đang dùng → docs/napoleon/stack.md.

  stack.py [--root DIR] [--out PATH] [--no-probe]   # sinh/cập nhật stack.md
  stack.py [--root DIR] --check                     # exit 1 nếu manifest đổi mà stack.md chưa cập nhật
  stack.py [--root DIR] --json                      # dữ liệu thô

Chỉ đọc manifest và lockfile (pubspec, Gradle, Xcode/CocoaPods/SPM, package.json, pyproject/requirements),
không đoán. Phiên bản "đang dùng" lấy từ lockfile; không có lock → ghi "chưa khoá".
Khối giữa hai dấu napoleon:stack được sinh lại mỗi lần; phần ngoài khối (ghi chú của bạn) giữ nguyên.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

OUT_REL = Path("docs/napoleon/stack.md")
TOOLCHAIN_REL = Path(".claude/instructions/toolchain.json")
BEGIN = "<!-- napoleon:stack:begin — sinh bởi .claude/tools/stack.py, sửa trong khối này sẽ bị ghi đè -->"
END = "<!-- napoleon:stack:end -->"
SOURCES_RE = re.compile(r"<!-- napoleon:stack:sources (\{.*?\}) -->")
MANIFESTS = ["pubspec.yaml", "pubspec.lock", ".fvmrc", ".fvm/fvm_config.json", ".metadata",
             "android/app/build.gradle", "android/app/build.gradle.kts", "android/settings.gradle",
             "android/settings.gradle.kts", "android/build.gradle", "android/build.gradle.kts",
             "android/gradle/libs.versions.toml", "gradle/libs.versions.toml", "app/build.gradle.kts",
             "app/build.gradle", "settings.gradle.kts", "settings.gradle",
             "android/gradle/wrapper/gradle-wrapper.properties", "gradle/wrapper/gradle-wrapper.properties",
             "ios/Podfile", "ios/Podfile.lock", "Podfile", "Podfile.lock",
             "ios/Runner.xcodeproj/project.pbxproj",
             "ios/Runner.xcworkspace/xcshareddata/swiftpm/Package.resolved", "Package.resolved",
             "package.json", "package-lock.json", "pyproject.toml", "requirements.txt",
             ".claude/instructions/toolchain.json"]

# Vai trò của thư viện phổ biến: để agent thấy "đã có X cho việc này" trước khi thêm thư viện thứ hai.
ROLES = {
    "flutter_bloc": "state management", "bloc": "state management", "provider": "state management",
    "riverpod": "state management", "flutter_riverpod": "state management", "hooks_riverpod": "state management",
    "get": "state + DI + routing", "mobx": "state management", "redux": "state management",
    "get_it": "DI", "injectable": "DI (sinh code)", "injectable_generator": "DI (sinh code)",
    "go_router": "navigation", "auto_route": "navigation", "go_router_builder": "navigation (sinh code)",
    "dio": "HTTP", "http": "HTTP", "retrofit": "HTTP (sinh code)", "chopper": "HTTP",
    "drift": "DB SQLite", "drift_flutter": "DB SQLite", "drift_dev": "DB (sinh code)", "sqflite": "DB SQLite",
    "isar": "DB", "hive": "key-value", "hive_flutter": "key-value", "shared_preferences": "key-value",
    "flutter_secure_storage": "lưu bí mật (Keychain/Keystore)", "objectbox": "DB",
    "freezed": "model bất biến (sinh code)", "freezed_annotation": "model bất biến (sinh code)",
    "json_serializable": "JSON (sinh code)", "json_annotation": "JSON (sinh code)", "build_runner": "chạy sinh code",
    "equatable": "so sánh giá trị", "fpdart": "Either/Option", "dartz": "Either/Option",
    "intl": "i18n, định dạng số/ngày", "flutter_localizations": "i18n", "easy_localization": "i18n",
    "flutter_svg": "SVG", "cached_network_image": "ảnh mạng có cache", "flutter_lucide": "icon",
    "lucide_icons": "icon", "font_awesome_flutter": "icon",
    "uuid": "UUID", "crypto": "hash", "image": "xử lý ảnh", "image_picker": "chọn ảnh/camera hệ thống",
    "camera": "camera", "mobile_scanner": "quét mã vạch", "google_mlkit_barcode_scanning": "quét mã vạch",
    "permission_handler": "quyền", "url_launcher": "mở link", "package_info_plus": "thông tin app",
    "connectivity_plus": "trạng thái mạng", "device_info_plus": "thông tin máy",
    "google_sign_in": "đăng nhập Google", "sign_in_with_apple": "đăng nhập Apple",
    "firebase_core": "Firebase", "firebase_auth": "Firebase Auth", "firebase_analytics": "analytics",
    "firebase_crashlytics": "crash report", "sentry_flutter": "crash report",
    "in_app_purchase": "mua trong app", "purchases_flutter": "mua trong app",
    "flutter_test": "test", "bloc_test": "test bloc", "mocktail": "mock", "mockito": "mock",
    "fake_async": "test thời gian", "integration_test": "test tích hợp", "flutter_lints": "lint",
    "very_good_analysis": "lint",
    # Android / Kotlin
    "androidx.compose.material3:material3": "UI Compose", "io.insert-koin:koin-android": "DI",
    "com.google.dagger:hilt-android": "DI", "com.squareup.retrofit2:retrofit": "HTTP",
    "com.squareup.okhttp3:okhttp": "HTTP", "io.ktor:ktor-client-core": "HTTP",
    "androidx.room:room-runtime": "DB SQLite", "org.jetbrains.kotlinx:kotlinx-coroutines-android": "coroutine",
    "org.jetbrains.kotlinx:kotlinx-serialization-json": "JSON", "io.coil-kt:coil-compose": "ảnh",
    "androidx.navigation:navigation-compose": "navigation", "junit:junit": "test", "io.mockk:mockk": "mock",
    # JS / TS
    "react": "UI", "react-native": "UI native", "next": "framework web", "vue": "UI", "redux": "state",
    "@reduxjs/toolkit": "state", "zustand": "state", "axios": "HTTP", "@tanstack/react-query": "data fetching",
    "react-router-dom": "navigation", "@react-navigation/native": "navigation", "zod": "validate",
    "jest": "test", "vitest": "test", "typescript": "ngôn ngữ", "eslint": "lint", "prettier": "format",
}


def read(root, rel):
    p = Path(root) / rel
    return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else None


def clean(v):
    v = re.sub(r"\s+#.*$", "", v or "").strip()
    return v[1:-1] if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"" else v


# ---------- Dart / Flutter ----------

def yaml_block(text, key):
    """Dòng con của khoá cấp 0 `key:` (YAML đơn giản, thụt 2 dấu cách)."""
    out, inside = [], False
    for line in text.splitlines():
        if re.match(r"^\S", line):
            inside = line.split("#")[0].rstrip() == f"{key}:"
            continue
        if inside and line.strip() and not line.lstrip().startswith("#"):
            out.append(line)
    return out


def pubspec_deps(text, key):
    """[(tên, khai báo)] — khai báo là constraint, 'sdk: flutter', 'git', 'path: ..'."""
    out, cur = [], None
    for line in yaml_block(text, key):
        m = re.match(r"^  (\S[^:]*):\s*(.*)$", line)
        if m:
            cur = [m.group(1).strip(), clean(m.group(2))]
            out.append(cur)
            continue
        m = re.match(r"^\s{4,}(sdk|git|path|version|url|ref)\s*:\s*(.*)$", line)
        if m and cur is not None and not cur[1]:
            k, v = m.group(1), clean(m.group(2))
            cur[1] = v if k == "version" else (f"{k}: {v}" if v and k in ("sdk", "path") else k)
    return [tuple(x) for x in out]


def pubspec_lock(text):
    """({tên: (version, dependency, source)}, {sdk: constraint})."""
    pkgs, sdks, cur, section = {}, {}, None, None
    for line in text.splitlines():
        if re.match(r"^\S", line):
            section = line.split(":")[0]
            continue
        if section == "packages":
            m = re.match(r"^  (\S+):\s*$", line)
            if m:
                cur = pkgs.setdefault(m.group(1), {})
                continue
            m = re.match(r"^    (dependency|version|source):\s*(.*)$", line)
            if m and cur is not None:
                cur[m.group(1)] = clean(m.group(2))
        elif section == "sdks":
            m = re.match(r"^  (\w+):\s*(.*)$", line)
            if m:
                sdks[m.group(1)] = clean(m.group(2))
    return pkgs, sdks


def flutter_version(root, probe):
    """(phiên bản, nguồn)."""
    fvmrc = read(root, ".fvmrc")
    if fvmrc:
        try:
            return json.loads(fvmrc).get("flutter", ""), ".fvmrc"
        except ValueError:
            pass
    fvm = read(root, ".fvm/fvm_config.json")
    if fvm:
        try:
            return json.loads(fvm).get("flutterSdkVersion", ""), ".fvm/fvm_config.json"
        except ValueError:
            pass
    meta = read(root, ".metadata") or ""
    rev = re.search(r'revision:\s*"?(\w{7})', meta)
    chan = re.search(r'channel:\s*"?(\w+)', meta)
    if probe:
        try:
            r = subprocess.run(["flutter", "--version", "--machine"], capture_output=True, text=True, timeout=30)
            v = json.loads(r.stdout[r.stdout.find("{"):]) if r.returncode == 0 else {}
            if v.get("frameworkVersion"):
                return (f"{v['frameworkVersion']} ({v.get('channel', '')}, Dart {v.get('dartSdkVersion', '?')})",
                        "flutter --version trên máy sinh file — chưa ghim bằng .fvmrc")
        except (OSError, subprocess.TimeoutExpired, ValueError):
            pass
    if rev:
        return f"revision {rev.group(1)}" + (f" ({chan.group(1)})" if chan else ""), ".metadata"
    return "", ""


def dart_section(root, probe):
    spec = read(root, "pubspec.yaml")
    if spec is None:
        return None
    lock = read(root, "pubspec.lock")
    pkgs, sdks = pubspec_lock(lock) if lock else ({}, {})
    env = dict(pubspec_deps(spec, "environment"))
    name = re.search(r"^name:\s*(\S+)", spec, re.M)
    version = re.search(r"^version:\s*(\S+)", spec, re.M)
    is_flutter = any(n == "flutter" for n, _ in pubspec_deps(spec, "dependencies"))
    platform = []
    if is_flutter:
        fv, src = flutter_version(root, probe)
        platform.append(("Flutter", fv or "không đọc được", src or "—"))
        if sdks.get("flutter"):
            platform.append(("Flutter (lock yêu cầu)", sdks["flutter"], "pubspec.lock"))
    platform.append(("Dart SDK", sdks.get("dart") or env.get("sdk", "—"),
                     "pubspec.lock" if sdks.get("dart") else "pubspec.yaml"))

    def rows(key):
        out = []
        for n, decl in pubspec_deps(spec, key):
            p = pkgs.get(n, {})
            if decl.startswith("sdk") or p.get("source") == "sdk":
                used = "theo SDK"              # lock ghi 0.0.0 cho gói đi kèm SDK
            else:
                used = p.get("version") or "chưa khoá"
            out.append((n, decl, used, ROLES.get(n, "")))
        return out

    overrides = rows("dependency_overrides")
    transitive = sum(1 for p in pkgs.values() if p.get("dependency") == "transitive")
    return {"kind": "Dart/Flutter" if is_flutter else "Dart", "app": name.group(1) if name else "",
            "version": version.group(1) if version else "", "platform": platform,
            "deps": rows("dependencies"), "dev": rows("dev_dependencies"), "overrides": overrides,
            "note": f"{transitive} gói bắc cầu trong pubspec.lock" if lock else "chưa có pubspec.lock — chạy pub get"}


# ---------- Android / Gradle ----------

def gradle_value(text, key):
    m = re.search(rf"\b{key}\s*(?:=|\s)\s*([^\n]+)", text or "")
    return clean(m.group(1)).rstrip(")") if m else ""


def toml_sections(text):
    """{section: {key: value-thô}} cho TOML đơn giản (libs.versions.toml)."""
    out, sec = {}, ""
    for line in (text or "").splitlines():
        line = line.split("#")[0].strip()
        if not line:
            continue
        m = re.match(r"^\[([\w.-]+)\]$", line)
        if m:
            sec = m.group(1); out.setdefault(sec, {}); continue
        m = re.match(r"^([\w.-]+)\s*=\s*(.+)$", line)
        if m:
            out.setdefault(sec, {})[m.group(1)] = m.group(2).strip()
    return out


def version_catalog(text):
    """[(module, version)] từ [libraries] của libs.versions.toml."""
    t = toml_sections(text)
    versions = {k: clean(v) for k, v in t.get("versions", {}).items()}
    out = []
    for alias, raw in t.get("libraries", {}).items():
        module = re.search(r'module\s*=\s*"([^"]+)"', raw)
        group, name = re.search(r'group\s*=\s*"([^"]+)"', raw), re.search(r'name\s*=\s*"([^"]+)"', raw)
        ver = re.search(r'version\.ref\s*=\s*"([^"]+)"', raw)
        lit = re.search(r'version\s*=\s*"([^"]+)"', raw)
        if raw.startswith('"'):
            parts = clean(raw).split(":")
            mod, v = ":".join(parts[:2]), (parts[2] if len(parts) > 2 else "")
        else:
            mod = module.group(1) if module else (f"{group.group(1)}:{name.group(1)}" if group and name else alias)
            v = versions.get(ver.group(1), "") if ver else (lit.group(1) if lit else "")
        out.append((mod, v or "BOM/không ghi"))
    return out


def android_section(root):
    base = "android/" if (Path(root) / "android").is_dir() else ""
    app = read(root, f"{base}app/build.gradle.kts") or read(root, f"{base}app/build.gradle")
    if app is None:
        return None
    settings = (read(root, f"{base}settings.gradle.kts") or read(root, f"{base}settings.gradle") or "") + \
        (read(root, f"{base}build.gradle.kts") or read(root, f"{base}build.gradle") or "")
    wrapper = read(root, f"{base}gradle/wrapper/gradle-wrapper.properties") or ""
    platform = []
    for label, key in (("compileSdk", "compileSdk"), ("targetSdk", "targetSdk"), ("minSdk", "minSdk"),
                       ("applicationId", "applicationId"), ("namespace", "namespace")):
        v = gradle_value(app, key)
        if v:
            platform.append((label, v, f"{base}app/build.gradle*"))
    java = re.search(r"JavaVersion\.VERSION_(\d+)|JVM_(\d+)|jvmToolchain\((\d+)\)", app)
    if java:
        platform.append(("Java/JVM", next(g for g in java.groups() if g), f"{base}app/build.gradle*"))
    for label, pid in (("Android Gradle Plugin", "com.android.application"),
                       ("Kotlin", "org.jetbrains.kotlin.android")):
        m = re.search(rf'id\(?\s*"{re.escape(pid)}"\)?\s*version\s*"([^"]+)"', settings)
        if m:
            platform.append((label, m.group(1), f"{base}settings.gradle*"))
    g = re.search(r"gradle-([\d.]+)-(?:all|bin)\.zip", wrapper)
    if g:
        platform.append(("Gradle", g.group(1), "gradle-wrapper.properties"))
    catalog = read(root, f"{base}gradle/libs.versions.toml")
    deps = [(m, "", v, ROLES.get(m, "")) for m, v in version_catalog(catalog)] if catalog else []
    if not deps:
        for m in re.finditer(r'(?:implementation|api|ksp|kapt)\s*\(?\s*"([\w.-]+:[\w.-]+):([\w.+-]+)"', app):
            deps.append((m.group(1), "", m.group(2), ROLES.get(m.group(1), "")))
    return {"kind": "Android", "platform": platform, "deps": deps, "dev": [], "overrides": [],
            "note": "thư viện từ gradle/libs.versions.toml" if catalog else ""}


# ---------- iOS ----------

def ios_section(root, flutter):
    base = "ios/" if (Path(root) / "ios").is_dir() else ""
    pbx = read(root, f"{base}Runner.xcodeproj/project.pbxproj") or ""
    if not pbx:
        found = next(iter(sorted(Path(root, base or ".").glob("*.xcodeproj/project.pbxproj"))), None)
        pbx = found.read_text(encoding="utf-8", errors="replace") if found else ""
    podfile = read(root, f"{base}Podfile") or ""
    podlock = read(root, f"{base}Podfile.lock") or ""
    spm = read(root, f"{base}Runner.xcworkspace/xcshareddata/swiftpm/Package.resolved") or read(root, "Package.resolved")
    if not (pbx or podfile or spm):
        return None
    platform = []
    targets = sorted(set(re.findall(r"IPHONEOS_DEPLOYMENT_TARGET = ([\d.]+);", pbx)))
    if targets:
        platform.append(("iOS deployment target", ", ".join(targets), "project.pbxproj"))
    m = re.search(r"^\s*platform\s+:ios,\s*'([\d.]+)'", podfile, re.M)
    if m:
        platform.append(("Podfile platform", m.group(1), "Podfile"))
    swift = sorted(set(re.findall(r"SWIFT_VERSION = ([\d.]+);", pbx)))
    if swift:
        platform.append(("Swift", ", ".join(swift), "project.pbxproj"))
    deps, notes = [], []
    pods = dict(re.findall(r"^  - ([\w/+-]+) \(([^)]+)\):?$", podlock, re.M))
    if spm and flutter:
        try:
            d = json.loads(spm)
            n = len(d.get("pins") or d.get("object", {}).get("pins", []))
            notes.append(f"{n} gói SPM do plugin Flutter kéo vào, phiên bản theo pubspec")
        except ValueError:
            pass
    elif spm:
        try:
            d = json.loads(spm)
            pins = d.get("pins") or d.get("object", {}).get("pins", [])
            for p in pins:
                deps.append((p.get("identity") or p.get("package", "?"), "SPM",
                             (p.get("state") or {}).get("version") or "branch/revision", ""))
        except ValueError:
            pass
    if pods:
        if flutter:
            notes.append(f"{len(pods)} pod trong Podfile.lock do plugin Flutter kéo vào, phiên bản theo pubspec")
        else:
            direct = re.findall(r"^  - ([\w/+-]+)", podlock.split("DEPENDENCIES:")[-1].split("\n\n")[0], re.M)
            deps += [(n, "CocoaPods", pods.get(n, "?"), "") for n in direct]
    return {"kind": "iOS", "platform": platform, "deps": deps, "dev": [], "overrides": [], "note": "; ".join(notes)}


# ---------- JS / Python ----------

def node_section(root):
    pkg = read(root, "package.json")
    if pkg is None:
        return None
    try:
        d = json.loads(pkg)
    except ValueError:
        return {"kind": "Node", "platform": [], "deps": [], "dev": [], "overrides": [],
                "note": "package.json không đọc được"}
    lock = read(root, "package-lock.json")
    resolved = {}
    if lock:
        try:
            for k, v in json.loads(lock).get("packages", {}).items():
                if k.startswith("node_modules/") and k.count("node_modules/") == 1:
                    resolved[k[len("node_modules/"):]] = v.get("version", "")
        except ValueError:
            pass
    rows = lambda key: [(n, c, resolved.get(n, "chưa khoá"), ROLES.get(n, ""))  # noqa: E731
                        for n, c in sorted((d.get(key) or {}).items())]
    platform = [(f"engines.{k}", v, "package.json") for k, v in (d.get("engines") or {}).items()]
    return {"kind": "Node/TS", "app": d.get("name", ""), "version": d.get("version", ""), "platform": platform,
            "deps": rows("dependencies"), "dev": rows("devDependencies"), "overrides": [],
            "note": "" if lock else "không có package-lock.json (yarn/pnpm chưa đọc)"}


def python_section(root):
    py, req = read(root, "pyproject.toml"), read(root, "requirements.txt")
    if py is None and req is None:
        return None
    deps, platform = [], []
    if py:
        m = re.search(r"^\[project\][^\[]*?^dependencies\s*=\s*\[(.*?)\]", py, re.M | re.S)
        for spec in re.findall(r'"([^"]+)"', m.group(1) if m else ""):
            n = re.split(r"[<>=!~;\[ ]", spec, 1)[0]
            deps.append((n, spec[len(n):].strip() or "*", "chưa khoá", ROLES.get(n, "")))
        rp = re.search(r'^requires-python\s*=\s*"([^"]+)"', py, re.M)
        if rp:
            platform.append(("Python", rp.group(1), "pyproject.toml"))
    if req and not deps:
        for line in req.splitlines():
            line = line.split("#")[0].strip()
            if line and not line.startswith("-"):
                n = re.split(r"[<>=!~;\[ ]", line, 1)[0]
                pin = re.search(r"==\s*([\w.]+)", line)
                deps.append((n, line[len(n):].strip() or "*", pin.group(1) if pin else "chưa khoá", ""))
    return {"kind": "Python", "platform": platform, "deps": deps, "dev": [], "overrides": [], "note": ""}


# ---------- gom ----------

def fingerprint(root):
    out = {}
    for rel in MANIFESTS:
        p = Path(root) / rel
        if p.is_file():
            out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
    return out


def collect(root, probe=True):
    dart = dart_section(root, probe)
    sections = [s for s in (dart, android_section(root), ios_section(root, bool(dart and dart["kind"] == "Dart/Flutter")),
                            node_section(root), python_section(root)) if s]
    tc = read(root, TOOLCHAIN_REL)
    try:
        toolchain = json.loads(tc) if tc else {}
    except ValueError:
        toolchain = {}
    app = next((s for s in sections if s.get("app")), {})
    return {"app": app.get("app", Path(root).resolve().name), "version": app.get("version", ""),
            "sections": sections, "toolchain": {k: v for k, v in toolchain.items()
                                                if k in ("test", "test_one", "build", "codegen") and v},
            "sources": fingerprint(root)}


def table(head, rows):
    if not rows:
        return []
    esc = lambda x: str(x).replace("|", "\\|")  # noqa: E731
    return ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + \
        ["| " + " | ".join(esc(c) or "" for c in r) + " |" for r in rows] + [""]


def render(data):
    # Không ghi giờ sinh: chạy lại khi manifest không đổi thì file không đổi, git không có diff rác.
    L = [BEGIN, "",
         "Sinh từ manifest và lockfile; không có gì gõ tay. Cập nhật: `/stack`. Cũ hay chưa: `stack.py --check`.",
         "Dùng thư viện: phiên bản ở cột **Đang dùng** là phiên bản để tra doc (context7). "
         "Cần một việc mà cột **Vai trò** đã có thư viện lo → dùng thư viện đó, không thêm cái thứ hai.", ""]
    if data["version"]:
        L += [f"Phiên bản app: `{data['version']}`", ""]
    for s in data["sections"]:
        L += [f"## {s['kind']}", ""]
        L += table(["Thành phần", "Phiên bản", "Nguồn"], [(a, f"`{b}`", c) for a, b, c in s["platform"]])
        if s["deps"]:
            L += ["### Thư viện", ""] + table(["Gói", "Khai báo", "Đang dùng", "Vai trò"],
                                              [(f"`{n}`", d, f"`{u}`", r) for n, d, u, r in s["deps"]])
        if s["dev"]:
            L += ["### Thư viện cho dev/test", ""] + table(["Gói", "Khai báo", "Đang dùng", "Vai trò"],
                                                          [(f"`{n}`", d, f"`{u}`", r) for n, d, u, r in s["dev"]])
        if s["overrides"]:
            L += ["### Ép phiên bản (dependency_overrides)", ""] + table(
                ["Gói", "Ép", "Đang dùng", ""], [(f"`{n}`", d, f"`{u}`", "") for n, d, u, _ in s["overrides"]])
        if s.get("note"):
            L += [f"_{s['note']}_", ""]
    if data["toolchain"]:
        L += ["## Lệnh", ""] + table(["Việc", "Lệnh"], [(k, f"`{v}`") for k, v in data["toolchain"].items()])
    if not data["sections"]:
        L += ["_Không tìm thấy manifest nào (pubspec, Gradle, Xcode, package.json, pyproject)._", ""]
    L += [f"<!-- napoleon:stack:sources {json.dumps(data['sources'], sort_keys=True)} -->", END]
    return "\n".join(L)


NOTES = ("\n\n## Ghi chú\n\nPhần dưới dấu `napoleon:stack:end` là của bạn và giữ nguyên khi sinh lại: "
         "lý do chọn thư viện, thư viện bị cấm, kế hoạch nâng cấp.\n")


def write(root, out_rel, data):
    out = Path(root) / out_rel
    old = out.read_text(encoding="utf-8") if out.exists() else ""
    block = render(data)
    if BEGIN in old and END in old:
        head, rest = old.split(BEGIN, 1)
        tail = rest.split(END, 1)[1]
        text = head + block + tail
    else:
        text = f"# Tech stack — {data['app']}\n\n{block}{NOTES}"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return out


def check(root, out_rel):
    """[] nếu stack.md khớp manifest hiện tại; ngược lại danh sách file đã đổi/thêm/bớt."""
    out = Path(root) / out_rel
    if not out.exists():
        return [f"chưa có {out_rel}"]
    m = SOURCES_RE.search(out.read_text(encoding="utf-8"))
    if not m:
        return [f"{out_rel} thiếu dấu nguồn — sinh lại"]
    old, now = json.loads(m.group(1)), fingerprint(root)
    return sorted(k for k in set(old) | set(now) if old.get(k) != now.get(k))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", default=".")
    p.add_argument("--out", default=str(OUT_REL))
    p.add_argument("--check", action="store_true")
    p.add_argument("--json", action="store_true")
    p.add_argument("--no-probe", action="store_true", help="không chạy `flutter --version` khi chưa ghim .fvmrc")
    a = p.parse_args(argv)
    root = Path(a.root).resolve()
    if a.check:
        changed = check(root, a.out)
        if changed:
            print(f"stack.md cũ so với: {', '.join(changed)} — chạy /stack")
            sys.exit(1)
        return
    data = collect(root, probe=not a.no_probe)
    if a.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    out = write(root, a.out, data)
    n = sum(len(s["deps"]) + len(s["dev"]) for s in data["sections"])
    print(f"đã ghi {out.relative_to(root) if out.is_relative_to(root) else out}: "
          f"{', '.join(s['kind'] for s in data['sections']) or 'không có manifest'}, {n} thư viện trực tiếp")


if __name__ == "__main__":
    main()

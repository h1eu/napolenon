"""Đọc chuỗi import thô theo ngôn ngữ bằng regex. Đủ cho v1, không parse AST."""
import re
from pathlib import Path

LANG_BY_EXT = {
    ".dart": "dart",
    ".kt": "kotlin", ".kts": "kotlin",
    ".swift": "swift",
    ".ts": "ts", ".tsx": "ts", ".js": "ts", ".jsx": "ts", ".mjs": "ts",
    ".py": "py",
}

_PATTERNS = {
    "dart": [re.compile(r"""^\s*import\s+['"]([^'"]+)['"]""", re.M)],
    "kotlin": [re.compile(r"^\s*import\s+(\w+(?:\.\w+)*(?:\.\*)?)", re.M)],
    "swift": [re.compile(r"^[ \t]*(?:@testable[ \t]+)?import[ \t]+(?:(?:struct|class|enum|protocol|func|var|let|typealias)[ \t]+)?([\w.]+)", re.M)],
    "ts": [
        re.compile(r"""^\s*import\s+[^'"]*?from\s+['"]([^'"]+)['"]""", re.M),
        re.compile(r"""^\s*import\s+['"]([^'"]+)['"]""", re.M),
        re.compile(r"""require\(\s*['"]([^'"]+)['"]\s*\)"""),
    ],
    "py": [
        re.compile(r"^\s*import\s+([\w.]+)", re.M),
        re.compile(r"^\s*from\s+([\w.]+)\s+import", re.M),
    ],
}


def find_imports(text, lang):
    """[(số_dòng, import)] theo thứ tự xuất hiện. lang lạ → []."""
    found = []
    for pat in _PATTERNS.get(lang, []):
        for m in pat.finditer(text):
            found.append((m.start(), m.group(1)))
    found.sort()
    return [(text.count("\n", 0, pos) + 1, s) for pos, s in found]


def read_imports(path):
    """Trả về list import theo thứ tự xuất hiện; đuôi lạ → []."""
    path = Path(path)
    lang = LANG_BY_EXT.get(path.suffix)
    if not lang:
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    return [s for _, s in find_imports(text, lang)]

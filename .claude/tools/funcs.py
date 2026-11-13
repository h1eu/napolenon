"""Tìm khai báo hàm có tên bằng quét ký tự (không AST). Đủ để đếm số dòng và số tham số.

Ngôn ngữ ngoặc nhọn (dart/kotlin/swift/ts): `tên(tham số) … {thân}`, `tên(tham số) => biểu thức;`,
và khai báo không thân (constructor `const Foo({...});`, method trừu tượng). Python: `def` + khối thụt lề.
Closure không tên và lời gọi hàm không tính. Kotlin/Swift cần `fun`/`func`/`class`/`init` vì lời gọi kèm
trailing lambda trông giống hệt khai báo.
"""
import re

CONTROL = {"if", "for", "while", "switch", "catch", "return", "await", "throw", "new", "else", "do", "try",
           "assert", "super", "this", "when", "guard", "in", "is", "as", "function", "Function", "typeof"}
HEAD_BAD = re.compile(r"=|\b(?:return|await|throw|new|yield|case|if|else|for|while|do|try|catch|switch|when)\b")
NAME_BEFORE_PAREN = re.compile(r"([A-Za-z_]\w*)\s*(?:<[^<>(){};=]*>)?\s*$")
ANNOTATION = re.compile(r"@\w+(?:\.\w+)*(?:\([^()]*\))?")
CLASS_NAME = re.compile(r"\b(?:class|enum|mixin|struct|extension)\s+(\w+)")
KT_CLASS = re.compile(r"\b(?:class|object|interface)\b")
PY_DEF = re.compile(r"^([ \t]*)(?:async[ \t]+)?def[ \t]+(\w+)[ \t]*\(", re.M)
OPEN, CLOSE = "([{", ")]}"
HEAD_WINDOW = 400


def strip_code(text, lang):
    """Thay nội dung chuỗi và comment bằng khoảng trắng, giữ nguyên vị trí và xuống dòng."""
    out = list(text)
    i, n = 0, len(text)
    line_c = "#" if lang == "py" else "//"

    def blank(a, b):
        for k in range(a, min(b, n)):
            if out[k] != "\n":
                out[k] = " "

    while i < n:
        c = text[i]
        if text.startswith(line_c, i):
            j = text.find("\n", i)
            j = n if j < 0 else j
            blank(i, j); i = j
        elif lang != "py" and text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            blank(i, j); i = j
        elif c in "'\"" or (c == "`" and lang == "ts"):
            q = text[i:i + 3] if text[i:i + 3] in ("'''", '"""') else c
            j = i + len(q)
            while j < n and not text.startswith(q, j):
                if text[j] == "\\":
                    j += 1
                elif len(q) == 1 and c != "`" and text[j] == "\n":
                    break                      # chuỗi một dòng không đóng: dừng ở cuối dòng
                j += 1
            blank(i + len(q), j); i = j + len(q)
        else:
            i += 1
    return "".join(out)


def _match_close(s, i):
    """i trỏ vào ngoặc mở; trả về vị trí ngoặc đóng tương ứng hoặc -1."""
    depth = 0
    for j in range(i, len(s)):
        if s[j] in OPEN:
            depth += 1
        elif s[j] in CLOSE:
            depth -= 1
            if depth == 0:
                return j
    return -1


def count_params(inner):
    """Đếm tham số trong phần giữa hai ngoặc tròn. Nhóm {named} / [optional] của Dart tính từng phần tử."""
    count, cur, depth, angle, groups = 0, False, 0, 0, 0
    for k, ch in enumerate(inner):
        if ch in "{[" and depth == 0 and not cur:
            groups += 1                        # mở nhóm tham số Dart, không phải giá trị mặc định
        elif ch in "}]" and depth == 0 and groups:
            groups -= 1
        elif ch in OPEN:
            depth += 1; cur = True
        elif ch in CLOSE:
            depth -= 1
        elif depth == 0 and ch == "<":
            angle += 1; cur = True
        elif depth == 0 and ch == ">" and angle and inner[k - 1:k] not in ("=", "-"):
            angle -= 1
        elif depth == 0 and angle == 0 and ch == ",":
            count += cur; cur = False
        elif not ch.isspace():
            cur = True
    return count + cur


def _head(s, pos):
    """Phần câu lệnh đứng trước tên hàm. None = tên nằm trong danh sách đối số/biểu thức."""
    depth = angle = 0
    k, lo = pos - 1, max(0, pos - HEAD_WINDOW)
    while k >= lo:
        c = s[k]
        if c in ")]":
            depth += 1
        elif c in "([":
            if depth == 0:
                return None
            depth -= 1
        elif depth == 0:
            if c == ">" and s[k - 1:k] not in ("=", "-"):
                angle += 1
            elif c == "<" and angle:
                angle -= 1
            elif c in ";{}":
                break
            elif c == "," and angle == 0:
                return None
        k -= 1
    return s[k + 1:pos]


def _line(s, pos):
    return s.count("\n", 0, pos) + 1


def _python_functions(s):
    out = []
    lines = s.split("\n")
    for m in PY_DEF.finditer(s):
        open_i = m.end() - 1
        close_i = _match_close(s, open_i)
        if close_i < 0:
            continue
        indent = len(m.group(1).expandtabs(4))
        start = end = _line(s, m.start(2))
        for k in range(_line(s, close_i), len(lines)):
            ln = lines[k]
            if not ln.strip():
                continue
            if len(ln[:len(ln) - len(ln.lstrip())].expandtabs(4)) <= indent:
                break
            end = k + 1
        params = [p for p in s[open_i + 1:close_i].split(",")
                  if p.strip() and p.strip().split(":")[0].strip() not in ("self", "cls", "*", "/")]
        out.append({"name": m.group(2), "line": start, "lines": end - start + 1, "params": len(params),
                    "ctor": m.group(2) == "__init__"})
    return out


def _body(s, close, lang, is_class):
    """Sau ')' của khai báo. Trả về (vị trí cuối thân hoặc None nếu không thân, vị trí quét tiếp)."""
    n = len(s)
    limit = n
    if lang in ("kotlin", "swift"):            # không có ';' → khai báo không thân kết thúc ở cuối dòng
        nl = s.find("\n", close)
        limit = n if nl < 0 else nl
    j = close + 1
    while j < limit:
        c = s[j]
        if c in "([":
            j = _match_close(s, j)
            if j < 0:
                return None, close + 1
        elif c == ";":
            return None, close + 1
        elif c == "{":
            if is_class:
                return None, j + 1
            end = _match_close(s, j)
            return (end if end >= 0 else None), j + 1
        elif c == "=" and s[j + 1:j + 2] != "=":
            if s.startswith("=>", j) or lang == "kotlin":
                end, depth = j, 0
                stop = ";" if lang != "kotlin" else "\n"
                while end < n and not (s[end] == stop and depth <= 0):
                    depth += (s[end] in OPEN) - (s[end] in CLOSE)
                    if depth < 0:
                        break
                    end += 1
                return min(end, n - 1), close + 1
            # Dart: `Foo(this.a) : b = a, super(a) {…}` — gán trong initializer list, đi tiếp tới thân
        j += 1
    return None, close + 1


def _function_at(s, i, lang, classes):
    m = NAME_BEFORE_PAREN.search(s, max(0, i - 200), i)
    if not m or m.group(1) in CONTROL or s[m.start(1) - 1:m.start(1)] == "@":
        return None                            # từ khoá điều khiển, hoặc annotation có đối số
    name = m.group(1)
    head = _head(s, m.start(1))
    if head is None or HEAD_BAD.search(head) or head.rstrip()[-1:] in tuple(".:?!&|"):
        return None
    is_class = lang == "kotlin" and bool(KT_CLASS.search(head))
    if lang == "kotlin" and not (is_class or re.search(r"\bfun\b", head) or name == "constructor"):
        return None
    if lang == "swift" and not (re.search(r"\bfunc\b", head) or name == "init"):
        return None
    close = _match_close(s, i)
    if close < 0:
        return None
    end, resume = _body(s, close, lang, is_class)
    if end is None:
        declared = lang in ("kotlin", "swift") or ANNOTATION.sub("", head).strip() or name in classes
        if not declared:
            return None
        end = close
    start = _line(s, m.start(1))
    ctor = is_class or name in classes or name in ("constructor", "init")
    return {"name": name, "line": start, "lines": _line(s, end) - start + 1,
            "params": count_params(s[i + 1:close]), "ctor": ctor}, resume


def find_functions(text, lang):
    """[{name, line, lines, params, ctor}] cho mọi hàm/method/constructor có tên."""
    s = strip_code(text, lang)
    if lang == "py":
        return _python_functions(s)
    classes = set(CLASS_NAME.findall(s))
    out, i = [], 0
    while True:
        i = s.find("(", i)
        if i < 0:
            return out
        found = _function_at(s, i, lang, classes)
        if found:
            out.append(found[0]); i = found[1]
        else:
            i += 1

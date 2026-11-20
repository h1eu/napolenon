# Báo cáo implementation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sinh `docs/napoleon/implementation.md` gồm các bảng task, thay đổi, test, route, nguồn sự thật, ADR; tự cập nhật sau mỗi lần `state.py` ghi state.

**Architecture:** `state.py` ghi thêm dữ liệu cho task (`base`, `routes`, `changed`, `test`) rồi gọi `implementation.py` sau mỗi `save_state`. `implementation.py` chỉ đọc (state, git, markdown trong `instructions/` và `features/`, file nguồn) và ghi một file markdown tất định. Route khai tay ở `.claude/instructions/routes.md`, tool đối chiếu với code bằng tìm chuỗi.

**Tech Stack:** Python 3 stdlib, `unittest`, git CLI. Không thêm thư viện.

**Spec:** `docs/superpowers/specs/2026-11-21-implementation-report-design.md`

## Global Constraints

- Chỉ stdlib Python 3. Thông báo, tiêu đề bảng bằng tiếng Việt; tên file, lệnh, hàm tiếng Anh.
- File sinh ra không chứa giờ sinh; chạy hai lần trên cùng dữ liệu cho nội dung giống hệt từng byte; nội dung không đổi thì không ghi lại file.
- Mọi ô trong file lấy từ dữ liệu repo. Không có dữ liệu → `—`.
- `implementation.py` lỗi (kể cả exception) không được đổi exit code hay stdout của `state.py`; chỉ in một dòng `cảnh báo: …` ra stderr.
- State cũ thiếu trường mới vẫn đọc được; `VERSION` giữ nguyên 2.
- Comment chỉ cho "vì sao". `.claude/CLAUDE.md` ≤ 100 dòng (`tests/test_docs.py` kiểm).
- Chạy toàn bộ test: `bash tests/run.sh` → dòng cuối `TẤT CẢ PASS`.
- **Trước khi bắt đầu:** cây làm việc đang có thay đổi chưa commit của việc `/perf` trên chính các file plan này sẽ sửa (`.claude/CLAUDE.md`, `napoleon-core/SKILL.md`, `templates/toolchain.json`, `README.md`, `tests/test_docs.py`). Phải commit việc đó trước, rồi mới làm Task 1. Mỗi bước commit dưới đây chỉ `git add` đúng các file đã nêu.

## Review Focus

1. `route_pattern` không hợp lệ (regex sai, 0 hoặc ≥ 2 nhóm bắt) → mục Route in `route_pattern không hợp lệ: …`, các mục khác vẫn sinh. (Task 5)
2. Repo git chưa có commit nào (HEAD chưa sinh) → `task start`/`task done` và sinh file không lỗi; `base`, `commit` rỗng; cột Commit `—`. (Task 1, Task 3)
3. File nguồn không phải UTF-8 hoặc rất lớn khi tìm "có trong code" → không lỗi, đọc với `errors="replace"`. (Task 5)
4. `implementation.py` chạy thẳng trên state cũ chưa qua `migrate` (task thiếu `routes`/`changed`/`test`/`base`) → sinh bình thường. (Task 3)
5. Tên file có dấu cách, ký tự Unicode hoặc bị đổi tên trong `changed` → đường dẫn đúng nguyên văn, không bị git bọc ngoặc kép. (Task 2)

---

### Task 1: `state.py` — `base`, `routes`, mốc diff theo task

**Files:**
- Modify: `.claude/tools/state.py` (`migrate`, `cmd_task`, `last_commit`, `main`, docstring đầu file)
- Test: `tests/test_state.py` (thêm vào `GateTest`)

**Interfaces:**
- Produces: trường task `routes: list[str]`, `base: str` (sha 40 ký tự hoặc `""`). `task add <feature> "<title>" [--files a,b] [--routes /a,/b]`. Hàm `dirty_outside_napoleon(root) -> bool`.

- [ ] **Step 1: Viết test trượt** (trong `GateTest`; thêm helper `commit(self, msg)` chạy `git add -A` + `git commit -qm` với cùng `env` như `setUp`, và `head(self)` trả `git rev-parse HEAD`)

```python
def test_task_add_routes(self):
    run(self.root, "task", "add", "login", "t", "--routes", " /login , /forgot ")
    self.assertEqual(self.status("1")["routes"], ["/login", "/forgot"])

def test_start_records_base_and_restart_keeps_it(self):
    tid = self.add_task()
    run(self.root, "task", "start", "login", tid)
    first = self.status(tid)["base"]
    self.assertEqual(first, self.head())
    write(self.root, "lib/a.dart", "class A { int x = 1; }\n"); self.commit("giữa chừng")
    run(self.root, "task", "start", "login", tid)
    self.assertEqual(self.status(tid)["base"], first)

def test_start_warns_when_tree_dirty(self):
    tid = self.add_task()
    write(self.root, "lib/a.dart", "class A { int y = 2; }\n")
    r = run(self.root, "task", "start", "login", tid)
    self.assertEqual(r.returncode, 0)
    self.assertIn("cảnh báo", r.stderr)

def test_start_clean_tree_no_warning(self):
    self.commit("state")                       # state.json do setUp tạo ra chưa commit
    tid = self.add_task()                      # chỉ đổi docs/napoleon/ → không tính là bẩn
    r = run(self.root, "task", "start", "login", tid)
    self.assertNotIn("cảnh báo", r.stderr)

def test_tests_diff_from_own_base_not_previous_task(self):
    # task 1 sửa lib/a.dart rồi commit; task 2 không đụng code → không được chạy lại test của task 1
    self.toolchain({"test": "touch ran.txt", "test_one": "touch ran.txt", "test_files": ["test/**"]})
    self.commit("toolchain")
    t1 = self.add_task(); run(self.root, "task", "start", "login", t1)
    write(self.root, "lib/a.dart", "class A { int x = 1; }\n")
    run(self.root, "task", "done", "login", t1)
    (self.root / "ran.txt").unlink(); self.commit("task 1")
    t2 = self.add_task(); run(self.root, "task", "start", "login", t2)
    run(self.root, "task", "done", "login", t2)
    self.assertFalse((self.root / "ran.txt").exists())

def test_old_task_gets_new_field_defaults(self):
    tid = self.add_task()
    s = state_of(self.root)
    for k in ("routes", "base", "changed", "test"):
        s["features"]["login"]["tasks"][0].pop(k, None)
    (self.root / "docs/napoleon/state.json").write_text(json.dumps(s))
    run(self.root, "task", "start", "login", tid)
    t = self.status(tid)
    self.assertEqual((t["routes"], t["changed"], t["test"]), ([], [], {}))
```

Thêm `class NoCommitTest(unittest.TestCase)`: `git init` nhưng không commit, `init`, `feature add login`, `task add`, `task start`, `task done --skip-tests --skip-conform` → mọi lệnh exit 0, `base == ""`.

- [ ] **Step 2: Chạy, xác nhận trượt**

Run: `python3 -m unittest tests.test_state -v 2>&1 | tail -n 15`
Expected: các test mới FAIL/ERROR (`KeyError: 'routes'`, `unrecognized arguments: --routes`).

- [ ] **Step 3: Sửa `state.py`**

- `migrate`: `t.setdefault("routes", [])`, `("base", "")`, `("changed", [])`, `("test", {})`.
- `task add`: thêm `--routes`, tách theo dấu phẩy và strip như `--files`; task mới có đủ bốn trường trên.
- `dirty_outside_napoleon(root) -> bool`: `git status --porcelain -z`, True khi có mục nào không nằm dưới `docs/napoleon/`. Không git → False.
- `task start`: `if not t["base"]: t["base"] = git_head(root)`; nếu `dirty_outside_napoleon` → in ra stderr `cảnh báo: cây làm việc còn thay đổi chưa commit — commit task trước để diff của task này không gộp`.
- `task done`: mốc = `t["base"] or git_head(root)`; nếu `t["base"]` rỗng thì gán bằng mốc đó. Truyền `mốc or "HEAD"` cho `gate_tests`. Xoá hàm `last_commit` (không còn ai gọi).
- Docstring đầu file: thêm `[--routes /a,/b]` vào dòng `task add`.

- [ ] **Step 4: Chạy lại**

Run: `python3 -m unittest tests.test_state 2>&1 | tail -n 3`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add .claude/tools/state.py tests/test_state.py
git commit -m "feat(state): task ghi base lúc start và routes, mốc diff theo chính task"
```

---

### Task 2: `state.py` — ghi `changed`, `test`; giữ kết quả khi `task done` trượt

**Files:**
- Modify: `.claude/tools/state.py` (`gate_tests`, `cmd_task`, hàm mới `changed_since`)
- Test: `tests/test_state.py` (`GateTest`)

**Interfaces:**
- Consumes: `t["base"]` từ Task 1.
- Produces:
  - `changed_since(root, base) -> list[dict]`: `[{"path": str, "kind": "thêm"|"sửa"|"xoá"|"đổi tên"}]`, sắp theo `path`; rỗng khi không git hoặc `base` rỗng.
  - `gate_tests(root, base, timeout) -> (ok: bool, msg: str, detail: dict)`; `detail = {"mode": str, "files": list[str], "command": str, "result": "pass"|"FAIL"|"bỏ qua"|"không có test", "tail": str}`.
  - Trường task `changed` (như trên) và `test` (= `detail`), ghi cả khi done trượt.

- [ ] **Step 1: Viết test trượt**

```python
def test_done_records_changed_with_kinds(self):
    self.commit("state")
    tid = self.add_task(); run(self.root, "task", "start", "login", tid)
    write(self.root, "lib/a.dart", "class A { int x = 1; }\n")
    write(self.root, "lib/màn hình mới.dart", "class B {}\n")
    (self.root / "test/a_test.dart").unlink()
    subprocess.run(["git", "-C", str(self.root), "mv", "pubspec.yaml", "pubspec2.yaml"], capture_output=True)
    run(self.root, "task", "done", "login", tid, "--skip-tests", "--skip-conform")
    got = {c["path"]: c["kind"] for c in self.status(tid)["changed"]}
    self.assertEqual(got, {"lib/a.dart": "sửa", "lib/màn hình mới.dart": "thêm",
                           "test/a_test.dart": "xoá", "pubspec2.yaml": "đổi tên"})

def test_changed_excludes_generated_files(self):
    tid = self.add_task(); run(self.root, "task", "start", "login", tid)
    write(self.root, "docs/napoleon/implementation.md", "x\n")
    run(self.root, "task", "done", "login", tid, "--skip-tests", "--skip-conform")
    paths = [c["path"] for c in self.status(tid)["changed"]]
    self.assertNotIn("docs/napoleon/state.json", paths)
    self.assertNotIn("docs/napoleon/implementation.md", paths)

def test_reopened_task_keeps_first_changes(self):
    self.commit("state")
    tid = self.add_task(); run(self.root, "task", "start", "login", tid)
    write(self.root, "lib/a.dart", "class A { int x = 1; }\n")
    run(self.root, "task", "done", "login", tid, "--skip-tests", "--skip-conform"); self.commit("t1")
    run(self.root, "task", "start", "login", tid)
    write(self.root, "lib/b.dart", "class B {}\n")
    run(self.root, "task", "done", "login", tid, "--skip-tests", "--skip-conform")
    self.assertEqual({c["path"] for c in self.status(tid)["changed"]} & {"lib/a.dart", "lib/b.dart"},
                     {"lib/a.dart", "lib/b.dart"})

def test_done_records_test_detail(self):
    write(self.root, "lib/a.dart", "class A { int x = 1; }\n")
    tid = self.add_task()
    run(self.root, "task", "done", "login", tid)
    t = self.status(tid)["test"]
    self.assertEqual(set(t), {"mode", "files", "command", "result", "tail"})
    self.assertEqual(t["result"], "pass")
    self.assertTrue(t["command"])

def test_failed_done_keeps_checks_and_test(self):
    self.toolchain({"test": "exit 1", "test_one": "exit 1", "test_files": ["test/**"]})
    write(self.root, "lib/a.dart", "class A { int x = 1; }\n")
    tid = self.add_task()
    self.assertEqual(run(self.root, "task", "done", "login", tid).returncode, 1)
    t = self.status(tid)
    self.assertEqual(t["status"], "todo")
    self.assertEqual(t["test"]["result"], "FAIL")
    self.assertIn("conform", t["checks"])

def test_skip_tests_recorded_in_test_detail(self):
    tid = self.add_task()
    run(self.root, "task", "done", "login", tid, "--skip-tests")
    self.assertEqual(self.status(tid)["test"]["result"], "bỏ qua")
```

- [ ] **Step 2: Chạy, xác nhận trượt**

Run: `python3 -m unittest tests.test_state.GateTest -v 2>&1 | tail -n 12`
Expected: 6 test mới FAIL.

- [ ] **Step 3: Sửa `state.py`**

- `changed_since`: gộp `git diff --name-status -M -z <base>` (cây làm việc so với `base`: `A`→thêm, `M`/`T`→sửa, `D`→xoá, `R*`→đổi tên với đường dẫn mới) và `git ls-files --others --exclude-standard -z` (→ thêm). Dùng `-z` để tên file không bị bọc ngoặc. Bỏ `docs/napoleon/state.json` và `docs/napoleon/implementation.md`.
- `gate_tests` trả thêm `detail`. `result`: `"pass"`/`"FAIL"` khi có chạy; `"không có test"` khi `command` rỗng; `"bỏ qua"` khi `affected.py` lỗi. `tail` = dòng cuối không rỗng của output, cắt 160 ký tự (với hai trường hợp không chạy: lý do).
- `cmd_task` nhánh `done`: `--skip-tests` hoặc conform trượt trước → `t["test"] = {"mode": "", "files": [], "command": "", "result": "bỏ qua", "tail": checks["test"]}`. Gán `t["checks"]`, `t["test"]`, `t["changed"]` **trước** khi `save_state` + `die` ở nhánh trượt; `status` và `commit` chỉ đổi khi đạt.

- [ ] **Step 4: Chạy lại**

Run: `python3 -m unittest tests.test_state 2>&1 | tail -n 3`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add .claude/tools/state.py tests/test_state.py
git commit -m "feat(state): task done ghi file đổi và chi tiết test, giữ kết quả khi trượt"
```

---

### Task 3: `implementation.py` — khung, Tổng quan, Task, Thay đổi theo task

**Files:**
- Create: `.claude/tools/implementation.py`
- Create: `tests/test_implementation.py`
- Modify: `tests/test_docs.py:109-110` (thêm `"implementation.py"` vào tập tool)

**Interfaces:**
- Consumes: trường task của Task 1–2; `report.verify_counts(root) -> {feature: (done, total, human)}`.
- Produces (các task sau gọi/ghép vào):
  - `OUT_REL = Path("docs/napoleon/implementation.md")`, `HEADER = "<!-- napoleon:generated — không sửa tay, chạy implementation.py -->"`
  - `cell(x) -> str`: `None`/`""`/`[]` → `—`; thoát `|` thành `\|`; xuống dòng → dấu cách.
  - `table(headers: list[str], rows: list[list]) -> str`: bảng markdown, mọi ô qua `cell`.
  - `section(title: str, body: str, src: str) -> str`: `## <title>\n\n<body>\n\nnguồn: <src>\n`.
  - `tid(feature: str, t: dict) -> str`: `login#3`.
  - `build(root: Path) -> str | None` (None khi chưa có `state.json`); ghép các mục theo thứ tự trong spec mục 4.
  - `write(root, out=None) -> bool`: True khi có ghi file; không ghi khi nội dung trùng.
  - CLI: `implementation.py [--root DIR] [--out PATH]`; chưa có state → in `chưa có state.json — chưa sinh báo cáo`, exit 0.

- [ ] **Step 1: Viết test trượt** — `tests/test_implementation.py`

Khung test: `class Base(unittest.TestCase)` dựng repo git tạm giống `GateTest.setUp` (`pubspec.yaml`, `lib/a.dart`, `test/a_test.dart`, `toolchain.json` với lệnh `exit 0`, commit đầu), đã `state.py init` + `feature add login`. Thuộc tính `self.env` (biến môi trường git như `GateTest`), `self.bare` (một thư mục tạm rỗng thứ hai, không git, không state). Helper: `tool(name, root, *args)` cấp module như trong `tests/test_report.py`; `st(*args)` gọi `state.py` trên `self.root`; `toolchain(data)` ghi `.claude/instructions/toolchain.json`; `commit(msg)`; `head()`; `gen()` gọi `implementation.py --root` và trả nội dung file; `row(md, key)` trả dòng đầu tiên chứa `key`.

```python
class CoreTest(Base):
    def test_no_state_writes_nothing(self):
        r = tool("implementation.py", self.bare)           # thư mục tạm rỗng
        self.assertEqual(r.returncode, 0)
        self.assertFalse((self.bare / "docs/napoleon/implementation.md").exists())

    def test_header_and_section_order(self):
        md = self.gen()
        self.assertTrue(md.startswith("<!-- napoleon:generated"))
        heads = [l for l in md.splitlines() if l.startswith("## ")]
        self.assertEqual(heads[:3], ["## Tổng quan", "## Task", "## Thay đổi theo task"])

    def test_deterministic_and_no_rewrite(self):
        a = self.gen(); p = self.root / "docs/napoleon/implementation.md"
        m = p.stat().st_mtime_ns
        self.assertEqual(self.gen(), a)
        self.assertEqual(p.stat().st_mtime_ns, m)

    def test_overview_row(self):
        self.st("task", "add", "login", "A"); self.st("task", "add", "login", "B")
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
        self.st("task", "add", "login", "A"); self.st("task", "start", "login", "1")
        write(self.root, "lib/a.dart", "class A { int x = 1; }\n"); self.commit("giữa chừng")
        write(self.root, "lib/a.dart", "class A { int x = 2; }\n")
        self.st("task", "done", "login", "1", "--skip-conform")
        self.assertTrue(self.row(self.gen(), "login#1").endswith("| commit kế tiếp |"))
        self.commit("task 1"); sha = self.head()[:7]
        self.assertTrue(self.row(self.gen(), "login#1").endswith(f"| {sha} (+1) |"))

    def test_rewritten_history_shows_dash(self):
        # done ở HEAD=X, rồi tạo nhánh mồ côi không chứa X
        self.st("task", "add", "login", "A"); self.st("task", "done", "login", "1", "--skip-tests", "--skip-conform")
        subprocess.run(["git", "-C", str(self.root), "checkout", "-q", "--orphan", "moi"], capture_output=True)
        self.commit("gốc mới")
        self.assertIn("— (lịch sử đã viết lại)", self.row(self.gen(), "login#1"))

    def test_changes_table(self):
        self.commit("state")
        self.st("task", "add", "login", "A"); self.st("task", "start", "login", "1")
        write(self.root, "lib/a.dart", "class A { int x = 1; }\n"); write(self.root, "lib/b.dart", "class B {}\n")
        self.st("task", "done", "login", "1", "--skip-tests", "--skip-conform")
        md = self.gen()
        self.assertIn("| login#1 | lib/a.dart | sửa |", md)
        self.assertIn("| login#1 | lib/b.dart | thêm |", md)
        self.assertRegex(self.row(md, "| login#1 | A |"), r"\| 2 \| bỏ qua \|")

    def test_task_missing_new_fields_still_renders(self):
        self.st("task", "add", "login", "A")
        p = self.root / "docs/napoleon/state.json"; s = json.loads(p.read_text())
        for k in ("routes", "base", "changed", "test"):
            s["features"]["login"]["tasks"][0].pop(k)
        p.write_text(json.dumps(s))
        self.assertIn("| login#1 | A | todo |", self.gen())

    def test_no_git(self):
        # self.bare không phải repo git
        tool("state.py", self.bare, "init"); tool("state.py", self.bare, "feature", "add", "x")
        tool("state.py", self.bare, "task", "add", "x", "A")
        tool("state.py", self.bare, "task", "done", "x", "1", "--skip-tests", "--skip-conform")
        tool("implementation.py", self.bare)
        md = (self.bare / "docs/napoleon/implementation.md").read_text(encoding="utf-8")
        self.assertTrue(self.row(md, "x#1").endswith("| — |"))
```

- [ ] **Step 2: Chạy, xác nhận trượt**

Run: `python3 -m unittest tests.test_implementation -v 2>&1 | tail -n 5`
Expected: FAIL, `implementation.py` chưa tồn tại.

- [ ] **Step 3: Viết `implementation.py`**

Khuôn giống `report.py`: `sys.path.insert(0, TOOLS)`, `--root`, `main(argv=None)`. Đọc state bằng `json.loads` trực tiếp, mọi trường task lấy bằng `.get` với mặc định rỗng.

- **Tổng quan** — cột `Feature | Bước | Task xong | Verify | Người chờ`. Verify = lần verify cuối trong state: `lần <n> <result>` + ` (<issues, cách nhau ", ">)` khi có. Người chờ = số mục `human` chưa `done`, 0 → `—`. Nguồn: `docs/napoleon/state.json`.
- **Task** — mỗi feature một `### <tên>` và một bảng `ID | Việc | Trạng thái | Route | File đổi | Test | Commit`. Trạng thái: `blocked: <lý do>` khi blocked. File đổi: số phần tử `changed`. Test: `<result> · <n> file` khi có `files`, ngược lại chỉ `<result>`. Nguồn: `docs/napoleon/state.json, git`.
- **Thay đổi theo task** — `ID | File | Kiểu`, chỉ task `done`, theo thứ tự feature → id → path. Không có dòng nào → `chưa có task done`.
- **Cột Commit** (`task_commit(root, t) -> str`), thuật toán cố định:

```python
if t.get("status") != "done" or not t.get("commit"): return "—"
if not is_ancestor(root, t["commit"], "HEAD"): return "— (lịch sử đã viết lại)"
after = rev_list(root, "--reverse", "--first-parent", f"{t['commit']}..HEAD")
if not after: return "commit kế tiếp"
base = t.get("base") or ""
mid = len(rev_list(root, "--first-parent", f"{base}..{t['commit']}")) if base and base != t["commit"] else 0
return after[0][:7] + (f" (+{mid})" if mid else "")
```

`is_ancestor` = `git merge-base --is-ancestor`; lệnh git lỗi/không có git → coi như không phải tổ tiên chỉ khi git có mặt, còn không có git → `—`.

- [ ] **Step 4: Thêm vào tập tool trong `tests/test_docs.py`, chạy toàn bộ**

Run: `python3 -m unittest tests.test_implementation tests.test_docs 2>&1 | tail -n 3`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add .claude/tools/implementation.py tests/test_implementation.py tests/test_docs.py
git commit -m "feat(implementation): sinh implementation.md — tổng quan, task, thay đổi theo task"
```

---

### Task 4: Mục "Test và bằng chứng"

**Files:**
- Modify: `.claude/tools/implementation.py`
- Test: `tests/test_implementation.py`

**Interfaces:**
- Consumes: `table`, `section`, `tid`, `report.verify_counts`.
- Produces: `plan_tests(root, feature) -> dict[int, str]` (id task → nội dung dòng "Test chứng minh"); `render_tests(root, state) -> str`, đặt sau "Thay đổi theo task".

- [ ] **Step 1: Viết test trượt**

```python
class EvidenceTest(Base):
    PLAN = ("# Plan: login\n\n## Task\n### Task 1: Form\n- File: lib/a.dart\n"
            "- Test chứng minh: `submits valid form` trong `test/a_test.dart`\n- Yêu cầu spec: #1\n\n"
            "### Task 2: Khác\n- File: x\n")

    def test_row_joins_plan_run_and_conform(self):
        write(self.root, "docs/napoleon/features/login/plan.md", self.PLAN)
        self.st("task", "add", "login", "Form")
        write(self.root, "lib/a.dart", "class A { int x = 1; }\n")
        self.st("task", "done", "login", "1")
        r = self.row(self.gen().split("## Test và bằng chứng")[1], "login#1")
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
```

- [ ] **Step 2: Chạy, xác nhận trượt**

Run: `python3 -m unittest tests.test_implementation.EvidenceTest 2>&1 | tail -n 3`
Expected: FAILED

- [ ] **Step 3: Viết `plan_tests` và `render_tests`**

- `plan_tests`: đọc `docs/napoleon/features/<feature>/plan.md`; khối bắt đầu bằng `### Task <n>`; trong khối lấy phần sau `- Test chứng minh:`. Thiếu file → `{}`.
- Bảng `ID | Test chứng minh (plan) | Test đã chạy | Lệnh | Kết quả | Conform`. Chỉ task có `test` hoặc `checks` không rỗng. Test đã chạy: `toàn bộ` khi `mode == "all"`, ngược lại các file cách nhau `, `. Lệnh bọc backtick. Kết quả: `<result>: <tail>` (không `tail` → chỉ `result`). Conform: `checks["conform"]`.
- Dưới bảng, mỗi feature có lần verify trong state hoặc có `verify.md` một dòng: `<tên> — verify lần 1 <kq> (<issues>), lần 2 <kq> · máy+verifier <d>/<n> · người chờ <h>`; phần nào thiếu dữ liệu thì bỏ phần đó.
- Nguồn: `plan.md, verify.md, docs/napoleon/state.json`.

- [ ] **Step 4: Chạy lại**

Run: `python3 -m unittest tests.test_implementation 2>&1 | tail -n 3`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add .claude/tools/implementation.py tests/test_implementation.py
git commit -m "feat(implementation): bảng test và bằng chứng theo task"
```

---

### Task 5: Mục "Route và màn", `routes.md`, `route_pattern`

**Files:**
- Modify: `.claude/tools/implementation.py`
- Create: `.claude/templates/routes.md`
- Modify: `.claude/templates/toolchain.json` (thêm `"route_pattern": ""` và một câu trong `_doc`)
- Test: `tests/test_implementation.py`

**Interfaces:**
- Consumes: `audit.source_files(root) -> list` để liệt kê file nguồn.
- Produces (Task 6 dùng lại):
  - `md_table(text: str, heading: str | None) -> list[list[str]]`: các dòng dữ liệu của bảng markdown đầu tiên dưới `heading` (None → bảng đầu file), ô đã strip; bỏ dòng tiêu đề, dòng `---`, và dòng placeholder (ô đầu, sau khi bỏ backtick, bắt đầu bằng `<`). Không xét các ô sau vì giá trị thật như `Stream<AuthState>` cũng có `<`.
  - `class Code`: `Code(root)` đọc một lần mọi file nguồn (`errors="replace"`); `.has(text: str) -> bool` tìm chuỗi thuần; `.has_word(name: str) -> bool` khớp theo ranh giới từ; `.findall(pattern: re.Pattern) -> set[str]`.
  - `render_routes(root, state, code) -> str`.

- [ ] **Step 1: Viết test trượt**

```python
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
              "GoRoute(path: '/extra');\nclass ForgotScreenState {}\n")   # không được khớp nhầm ForgotScreen
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
```

- [ ] **Step 2: Chạy, xác nhận trượt**

Run: `python3 -m unittest tests.test_implementation.RouteTest 2>&1 | tail -n 3`
Expected: FAILED

- [ ] **Step 3: Viết phần route**

- Bảng `Route | Màn | Feature | Task | Trạng thái | Design | Trong code`, giữ thứ tự dòng của `routes.md`. Task = mọi task (mọi feature) có route này trong `routes`, theo thứ tự feature → id.
- Trạng thái: không task → `chưa có task`; mọi task `done` → `xong`; còn lại → `đang làm`.
- Trong code: `có` / `thiếu route` / `thiếu màn` / `thiếu route, màn` (`Code.has(route)`, `Code.has_word(màn)`).
- Dưới bảng, theo thứ tự: các dòng `- task <id> khai route <r> không có trong routes.md`; rồi phần dò code:
  - `route_pattern` rỗng/không có → `chưa bật dò route trong code (đặt route_pattern trong .claude/instructions/toolchain.json)`
  - không biên dịch được hoặc số nhóm bắt ≠ 1 → `route_pattern không hợp lệ: <lý do>`
  - hợp lệ → mỗi route tìm thấy mà chưa khai một dòng `- route <r> có trong code, chưa khai trong routes.md`, sắp theo chữ cái.
- Chưa có `routes.md` → thân mục chỉ gồm `chưa có .claude/instructions/routes.md — tạo từ .claude/templates/routes.md`.
- Nguồn: `.claude/instructions/routes.md, docs/napoleon/state.json, file nguồn`.
- `build` tạo một `Code(root)` dùng chung cho Task 5 và 6.

`.claude/templates/routes.md`:

```markdown
# Route

Mỗi route một dòng. Thêm dòng ở bước spec của feature; đổi route đã duyệt phải hỏi.
`implementation.py` đối chiếu bảng này với code và với `--routes` của task.

| Route | Màn (class) | Feature | Design |
|---|---|---|---|
| <route, vd /login> | <LoginScreen> | <feature> | <docs/sources/design/… hoặc để trống> |
```

- [ ] **Step 4: Chạy lại**

Run: `python3 -m unittest tests.test_implementation tests.test_docs 2>&1 | tail -n 3`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add .claude/tools/implementation.py .claude/templates/routes.md .claude/templates/toolchain.json tests/test_implementation.py
git commit -m "feat(implementation): bảng route và màn, đối chiếu routes.md với code"
```

---

### Task 6: Mục "Nguồn sự thật", "Logic tái dùng", "Quyết định và việc hẹn lại"

**Files:**
- Modify: `.claude/tools/implementation.py`
- Test: `tests/test_implementation.py`

**Interfaces:**
- Consumes: `md_table`, `Code`, `table`, `section`.
- Produces: `render_truth(root, code) -> str` (hai mục), `render_decisions(root, state) -> str`.

- [ ] **Step 1: Viết test trượt**

```python
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

    def test_truth_table_gets_in_code_column(self):
        s = self.gen().split("## Nguồn sự thật")[1].split("\n## ")[0]
        self.assertIn("| auth | `AuthManager, core/auth/` | `Stream<AuthState>` | chỉ AuthManager | có |", s)
        self.assertIn("| chỉ PremiumManager | thiếu |", s)
        self.assertNotIn("network status", s)

    def test_manager_table_checks_class_and_test_file(self):
        s = self.gen().split("## Logic tái dùng")[1].split("\n## ")[0]
        self.assertIn("| `test/a_test.dart` | có · test có |", s)
        self.assertIn("| `test/cart_test.dart` | có · thiếu test |", s)

    def test_no_architecture_file(self):
        (self.root / ".claude/instructions/architecture.md").unlink()
        self.assertIn("chưa có .claude/instructions/architecture.md", self.gen())

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

    def test_no_decisions_no_followups(self):
        self.assertIn("không có", self.gen().split("## Quyết định và việc hẹn lại")[1])
```

- [ ] **Step 2: Chạy, xác nhận trượt**

Run: `python3 -m unittest tests.test_implementation.ArchTest 2>&1 | tail -n 3`
Expected: FAILED

- [ ] **Step 3: Viết hai hàm**

- **Nguồn sự thật**: `md_table(arch, "## Nguồn sự thật dùng chung")`, giữ nguyên bốn ô, thêm cột `Trong code`: tên class = định danh viết hoa đầu tiên (`[A-Z]\w+`) trong ô Owner; `có`/`thiếu` theo `Code.has_word`.
- **Logic tái dùng**: `md_table(arch, "## Logic tái dùng (manager)")`, thêm cột `Trong code`: class thiếu → `thiếu`; có → `có · test có` hoặc `có · thiếu test` theo việc đường dẫn ở ô Test (bỏ backtick) có tồn tại.
- Thiếu file → cả hai mục in `chưa có .claude/instructions/architecture.md`. Có file nhưng bảng rỗng → `chưa khai`.
- Nguồn hai mục: `.claude/instructions/architecture.md, file nguồn`.
- **Quyết định và việc hẹn lại** — `ADR | Tiêu đề | Followup mở`. Mỗi file trong `.claude/instructions/decisions/*.md`: dòng `# ` đầu, mã = `ADR-\d+` trong dòng đó, tiêu đề = phần sau dấu `:`. Sắp theo mã. Followup mở có `source` chứa mã → `#<id> <text>`, nhiều cái cách nhau `; `. Followup mở không khớp ADR nào → dòng `— | — | #<id> <text>` ở cuối. Không ADR, không followup mở → `không có`. Nguồn: `.claude/instructions/decisions/, docs/napoleon/state.json`.

- [ ] **Step 4: Chạy lại, kiểm thứ tự đủ 8 mục**

Thêm vào `CoreTest.test_header_and_section_order`:

```python
self.assertEqual(heads, ["## Tổng quan", "## Task", "## Thay đổi theo task", "## Test và bằng chứng",
                         "## Route và màn", "## Nguồn sự thật", "## Logic tái dùng",
                         "## Quyết định và việc hẹn lại"])
```

Run: `python3 -m unittest tests.test_implementation 2>&1 | tail -n 3`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add .claude/tools/implementation.py tests/test_implementation.py
git commit -m "feat(implementation): bảng nguồn sự thật, manager, ADR và việc hẹn lại"
```

---

### Task 7: Tự cập nhật — `state.py` gọi tool, `guard.py` chặn sửa tay

**Files:**
- Modify: `.claude/tools/state.py` (`save_state`)
- Modify: `.claude/tools/guard.py` (hằng và nhánh Write/Edit trong `main`)
- Test: `tests/test_state.py`, `tests/test_hooks.sh`

**Interfaces:**
- Consumes: `implementation.write(root) -> bool`.

- [ ] **Step 1: Viết test trượt**

`tests/test_state.py` (`GateTest`):

```python
IMPL = "docs/napoleon/implementation.md"

def test_every_state_write_refreshes_report(self):
    tid = self.add_task()
    self.assertIn("| login#1 | t | todo |", (self.root / self.IMPL).read_text())
    run(self.root, "task", "start", "login", tid)
    self.assertIn("| login#1 | t | in_progress |", (self.root / self.IMPL).read_text())

def test_report_is_in_task_commit(self):
    tid = self.add_task()
    write(self.root, "lib/a.dart", "class A { int x = 1; }\n")
    run(self.root, "task", "done", "login", tid)
    self.commit("task 1")
    shown = subprocess.run(["git", "-C", str(self.root), "show", f"HEAD:{self.IMPL}"], capture_output=True, text=True).stdout
    self.assertIn("| login#1 | t | done |", shown)

def test_broken_report_tool_does_not_fail_state(self):
    # bản sao tools với implementation.py hỏng; state.py vẫn exit 0 và in cảnh báo
    tools = self.root / "t"; shutil.copytree(TOOL.parent, tools)
    (tools / "implementation.py").write_text("raise RuntimeError('hỏng')\n")
    r = subprocess.run([sys.executable, str(tools / "state.py"), "--root", str(self.root), "task", "add", "login", "x"],
                       capture_output=True, text=True)
    self.assertEqual(r.returncode, 0)
    self.assertEqual(r.stdout.strip(), "1")
    self.assertIn("cảnh báo", r.stderr)
```

`tests/test_hooks.sh`: thêm một ca theo đúng khuôn ca `state.json` sẵn có — Write vào `docs/napoleon/implementation.md` bị từ chối, thông báo chứa `implementation.py`.

- [ ] **Step 2: Chạy, xác nhận trượt**

Run: `python3 -m unittest tests.test_state.GateTest 2>&1 | tail -n 3; bash tests/test_hooks.sh | tail -n 3`
Expected: 3 test Python FAIL; ca hook mới FAIL.

- [ ] **Step 3: Sửa**

- `tests/test_state.py` cần thêm `import shutil`. `state.py` `save_state`: sau `os.replace`, gọi `implementation.write(Path(root))` (đưa `TOOLS` vào `sys.path`, import trong hàm và trong cùng khối `try` để lỗi lúc import cũng bị bắt) bọc `try/except Exception as e` → `print(f"cảnh báo: không sinh được implementation.md ({e.__class__.__name__}: {e})", file=sys.stderr)`. Một dòng comment nêu lý do nuốt lỗi: báo cáo hỏng không được chặn cổng task.
- `guard.py`: thêm `IMPL_REL = "docs/napoleon/implementation.md"` và `DENY_IMPL = "implementation.md do .claude/tools/implementation.py sinh — không sửa tay. Muốn đổi nội dung → sửa tool."`; từ chối trong nhánh Write/Edit/MultiEdit/NotebookEdit như với `STATE_REL`.

- [ ] **Step 4: Chạy toàn bộ**

Run: `bash tests/run.sh | tail -n 4`
Expected: `TẤT CẢ PASS`

- [ ] **Step 5: Commit**

```bash
git add .claude/tools/state.py .claude/tools/guard.py tests/test_state.py tests/test_hooks.sh
git commit -m "feat(implementation): state.py tự sinh lại báo cáo sau mỗi lần ghi, guard chặn sửa tay"
```

---

### Task 8: Tài liệu, lệnh, skill

**Files:**
- Modify: `.claude/CLAUDE.md` (mục Tool, mục Vị trí)
- Modify: `.claude/commands/where.md`, `.claude/commands/report.md`, `.claude/commands/feature.md`
- Modify: `.claude/skills/napoleon-core/SKILL.md`, `.claude/skills/feature-loop/SKILL.md`, `.claude/skills/architecture-interview/SKILL.md`
- Modify: `README.md`
- Test: `tests/test_docs.py`

- [ ] **Step 1: Viết test trượt** — thêm vào `tests/test_docs.py` (dùng hằng `C` sẵn có)

```python
def test_implementation_report_is_documented(self):
    claude = (C / "CLAUDE.md").read_text(encoding="utf-8")
    self.assertIn("implementation.py", claude)
    self.assertIn("docs/napoleon/implementation.md", claude)
    self.assertIn("routes.md", claude)
    for rel in ("commands/where.md", "commands/report.md"):
        self.assertIn("implementation.py", (C / rel).read_text(encoding="utf-8"), rel)
    loop = (C / "skills/feature-loop/SKILL.md").read_text(encoding="utf-8")
    self.assertIn("--routes", loop)
    self.assertIn("routes.md", loop)
    self.assertIn("routes.md", (C / "skills/architecture-interview/SKILL.md").read_text(encoding="utf-8"))
    self.assertIn("implementation.md", (C / "skills/napoleon-core/SKILL.md").read_text(encoding="utf-8"))
    self.assertTrue((C / "templates/routes.md").exists())
```

- [ ] **Step 2: Chạy, xác nhận trượt**

Run: `python3 -m unittest tests.test_docs 2>&1 | tail -n 3`
Expected: FAILED

- [ ] **Step 3: Sửa tài liệu** — mỗi chỗ một dòng hoặc một mệnh đề, đúng giọng file đang có:

- `CLAUDE.md` mục Tool: `python3 .claude/tools/implementation.py` — bảng task/file đổi/test/route/nguồn sự thật → `docs/napoleon/implementation.md`; `state.py` tự gọi sau mỗi lần ghi, không sửa tay.
- `CLAUDE.md` mục Vị trí: thêm `implementation.md` vào dòng `docs/napoleon/`; thêm `routes.md` vào dòng `.claude/instructions/`.
- `where.md`: thêm bước chạy `python3 .claude/tools/implementation.py` trước khi in, và in đường dẫn file.
- `report.md`: thêm bước chạy `implementation.py` cùng `report.py`.
- `feature.md` + `feature-loop/SKILL.md`: bước spec — thêm dòng cho route/màn mới vào `.claude/instructions/routes.md`; bước plan — `state.py task add … --routes <route>` cho task làm route; bước build — `task start` trước khi sửa code (để có mốc), commit ngay sau `task done` kèm `implementation.md`.
- `architecture-interview/SKILL.md`: khi sinh `instructions/`, tạo `routes.md` từ template với bảng rỗng.
- `napoleon-core/SKILL.md`: thêm `implementation.md` vào danh sách `docs/napoleon/` và một dòng "xem đã làm gì → `implementation.md`".
- `README.md`: một đoạn ngắn mô tả file và các bảng của nó; thêm `route_pattern` vào chỗ nói về `toolchain.json` nếu có.

- [ ] **Step 4: Chạy toàn bộ**

Run: `bash tests/run.sh | tail -n 4`
Expected: `TẤT CẢ PASS`

- [ ] **Step 5: Commit**

```bash
git add .claude/CLAUDE.md .claude/commands/where.md .claude/commands/report.md .claude/commands/feature.md .claude/skills/napoleon-core/SKILL.md .claude/skills/feature-loop/SKILL.md .claude/skills/architecture-interview/SKILL.md README.md tests/test_docs.py
git commit -m "docs(implementation): hướng dẫn implementation.md, routes.md và --routes"
```

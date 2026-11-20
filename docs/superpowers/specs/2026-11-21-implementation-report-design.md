# Báo cáo implementation — `docs/napoleon/implementation.md`

Ngày: 2026-11-21
Trạng thái: chờ duyệt

## 1. Mục tiêu và lý do

Hiện thông tin "đã làm gì" của một dự án dùng Napoleon nằm rải ở `state.json` (máy đọc), `journal.md` (một dòng mỗi phiên), `verify.md` từng feature và `reports/roadmap.html` (chỉ có số tổng). Không có chỗ nào một người mở ra là thấy: task nào đã làm, sửa file nào, test nào chứng minh, route nào đã xong, state nào do ai giữ.

Thêm một file markdown duy nhất, do tool sinh, gồm nhiều bảng, tự cập nhật mỗi khi trạng thái đổi. Vì `state.py task done` chạy trước khi commit, file luôn nằm trong commit của chính task đó.

## 2. Phạm vi

**Làm:**
- Tool mới `.claude/tools/implementation.py` sinh `docs/napoleon/implementation.md`.
- `state.py` tự gọi tool sau mỗi lần ghi state; lưu thêm dữ liệu cho task (mục 5).
- File khai route `.claude/instructions/routes.md` và template của nó.
- Cập nhật skill, lệnh, CLAUDE.md, README, test.

**Không làm:**
- Không phân tích cấu hình router theo từng stack (go_router, Navigation Compose, SwiftUI).
- Không ghi nhật ký theo phiên; `journal.md` giữ nguyên.
- Không đổi `reports/roadmap.html`.
- Không tự chạy `git commit`.

**Không được xảy ra:**
- Con số hoặc trạng thái gõ tay vào file. Mọi ô đều từ dữ liệu repo.
- File đổi nội dung khi dữ liệu không đổi (gây nhiễu diff). Không in giờ sinh; thứ tự dòng ổn định.
- Tool sinh báo cáo lỗi làm hỏng `task done` hay bất kỳ lệnh `state.py` nào.

## 3. Các cách đã cân nhắc

**Cách cập nhật file**
1. **Tool riêng, `state.py` tự gọi — đã chọn.** Cùng khuôn với `report.py`, `stack.py`; không cần cài gì vào dự án; file vào đúng commit của task.
2. Git pre-commit hook. Phủ cả commit ngoài luồng task, nhưng Napoleon chỉ dùng hook của Claude Code; phải cài git hook vào từng dự án và dễ đụng hook có sẵn.
3. Cờ `--md` cho `report.py`. Ít code nhất, nhưng một tool gánh hai việc với hai nhịp cập nhật khác nhau.

**Nguồn dữ liệu route**
1. **Khai một bảng, tool đối chiếu với code — đã chọn.** Chạy được trên mọi stack.
2. Trích từ code. Không phải khai, nhưng mỗi stack một bộ trích, dễ gãy.
3. Gom từ spec. Nhẹ nhất, nhưng chỉ phản ánh ý định.

## 4. File sinh ra

Đường dẫn: `docs/napoleon/implementation.md`. Dòng đầu `<!-- napoleon:generated — không sửa tay, chạy implementation.py -->`. `guard.py` chặn Write/Edit vào file này như đang chặn `state.json`.

ID task viết `<feature>#<id>` (vd `login#3`) vì id trong state chỉ là số đếm trong từng feature.

Các mục, theo thứ tự:

### 4.1 Tổng quan
| Feature | Bước | Task xong | Verify | Người chờ |
|---|---|---|---|---|
| login | build | 3/5 | lần 1 fail (null-state) | 2 |

Nguồn: `state.json`.

### 4.2 Task
Một bảng cho mỗi feature, feature theo thứ tự trong state, task theo id.

| ID | Việc | Trạng thái | Route | File đổi | Test | Commit |
|---|---|---|---|---|---|---|
| login#3 | Form đăng nhập | done | /login | 4 | pass · 2 file | a1b2c3d |
| login#4 | Quên mật khẩu | blocked: chờ API reset | /forgot | — | — | — |
| login#5 | Ghi nhớ phiên | done | — | 2 | pass · 1 file | commit kế tiếp |

Nguồn: `state.json`, `git`.

### 4.3 Thay đổi theo task
| ID | File | Kiểu |
|---|---|---|
| login#3 | lib/features/login/login_screen.dart | thêm |
| login#3 | lib/core/auth/auth_manager.dart | sửa |

Chỉ task đã `done`. Nguồn: trường `changed` của task (mục 5).

### 4.4 Test và bằng chứng
| ID | Test chứng minh (plan) | Test đã chạy | Lệnh | Kết quả | Conform |
|---|---|---|---|---|---|
| login#3 | `submits valid form` trong test/login/form_test.dart | test/login/form_test.dart, test/core/auth_test.dart | `flutter test …` | pass: All tests passed! | 0 vi phạm |

Dưới bảng, mỗi feature một dòng verify: `login — verify lần 1 fail (null-state), lần 2 pass · máy+verifier 9/9 · người chờ 2`.

Nguồn: `plan.md` của feature (dòng "Test chứng minh" trong khối `### Task N`), trường `test` và `checks` của task, `verify.md`, `state.json`. Không có plan hoặc không tìm thấy khối task → ghi `—`.

### 4.5 Route và màn
| Route | Màn | Feature | Task | Trạng thái | Design | Trong code |
|---|---|---|---|---|---|---|
| /login | LoginScreen | login | login#3 | xong | design/login.png | có |
| /forgot | ForgotScreen | login | login#4 | đang làm | — | thiếu màn |

- Trạng thái suy từ task nối với route: mọi task done → `xong`; có task nhưng chưa done hết → `đang làm`; không task nào → `chưa có task`.
- "Trong code": `có` khi cả chuỗi route và tên class màn đều tìm thấy trong file nguồn; thiếu cái nào ghi rõ cái đó.
- Dưới bảng liệt kê hai loại lệch: route mà task khai nhưng `routes.md` không có; và (chỉ khi dự án đặt `route_pattern`, mục 6) route tìm thấy trong code mà `routes.md` chưa khai. Chưa đặt `route_pattern` → in một dòng "chưa bật dò route trong code".
- Chưa có `routes.md` → mục này in một dòng hướng dẫn tạo.

### 4.6 Nguồn sự thật và logic tái dùng
Lấy nguyên hai bảng "Nguồn sự thật dùng chung" và "Logic tái dùng (manager)" từ `.claude/instructions/architecture.md`, bỏ dòng còn placeholder `<…>`, thêm cột **Trong code** (class owner có trong file nguồn hay không; với bảng manager thêm file test có tồn tại hay không).

### 4.7 Quyết định và việc hẹn lại
| ADR | Tiêu đề | Followup mở |
|---|---|---|
| ADR-012 | Dùng bottom sheet thay dialog ở màn thanh toán | #4 Đổi lại khi design cập nhật |

Nguồn: `.claude/instructions/decisions/*.md` (tiêu đề = dòng `#` đầu), followup trong `state.json` ghép theo trường `source`. Followup mở không có ADR liệt kê ở cuối bảng.

Mỗi mục kết thúc bằng một dòng `nguồn: …` như `roadmap.html`.

## 5. Thay đổi trong `state.py`

**Trường mới của task** (tuỳ chọn; state cũ thiếu trường vẫn đọc được, coi như rỗng):
- `routes`: danh sách route, khai bằng `task add … --routes /login,/forgot`.
- `base`: sha HEAD lúc `task start` lần đầu. Không có git → rỗng. Task đã done được `start` lại (sau verify fail) → giữ `base` cũ, nên `changed` ở lần done sau vẫn là toàn bộ file của task, và test chạy lại trên toàn bộ phần đó.
- `changed`: danh sách `{path, kind}` ghi lúc `task done` — file khác biệt giữa `base` và cây làm việc (đã commit, đã stage, chưa stage, chưa theo dõi), trừ `docs/napoleon/state.json` và `docs/napoleon/implementation.md`. `kind` ∈ thêm / sửa / xoá / đổi tên.
- `test`: `{mode, files, command, result}` lấy từ JSON của `affected.py` và kết quả chạy. `checks` giữ nguyên dạng chuỗi như hiện tại.

**Sửa mốc diff.** Hiện mốc test của task N là `commit` của task trước, tức HEAD lúc task trước đóng — commit *trước* commit của task trước, nên diff gộp luôn phần của task trước. Đổi: mốc của task N là `base` của chính nó; thiếu `base` (đóng task mà chưa `start`) thì dùng HEAD. Mốc này dùng cho cả `gate_tests` lẫn `changed`.

**Cảnh báo ở `task start`:** cây làm việc còn thay đổi chưa commit ngoài `docs/napoleon/` → in một dòng nhắc commit task trước, không chặn.

**`task done` trượt.** Hiện `checks` không được gán vào task trước khi `die` nên kết quả trượt bị mất, trái với comment trong code. Sửa: gán `checks` và `test` vào task rồi mới lưu và thoát; trạng thái task giữ nguyên. Bảng 4.4 hiện cả lần FAIL gần nhất của task chưa done.

**Commit của task.** `commit` vẫn là HEAD lúc `task done`. Sha hiển thị trong bảng tính lúc sinh file, không lưu vào state:
- Commit đóng task = commit first-parent đầu tiên sau `commit` trên nhánh hiện tại. Chưa có → `commit kế tiếp`.
- Có commit giữa chừng (nằm giữa `base` và `commit`) → hiện sha đóng task kèm `(+n)`, n là số commit giữa chừng.
- `commit` không còn là tổ tiên của HEAD (rebase, amend, squash) → `— (lịch sử đã viết lại)`.

**Độ trễ chấp nhận.** File chỉ sinh lại khi state được ghi, nên bản nằm trong commit của task N ghi `commit kế tiếp` cho chính N; sha thật hiện ở lần ghi state sau (task kế tiếp, hoặc `feature step` khi chuyển sang verify). Các cột "Trong code" cũng chỉ mới bằng lần ghi state gần nhất. `/where` và `/report` chạy thêm `implementation.py` để làm mới khi người dùng chủ động xem. Không gọi ở hook SessionStart để khỏi làm bẩn cây làm việc khi vừa mở phiên.

**Gọi tool.** Sau mỗi lần `save_state`, `state.py` gọi `implementation.py`. Tool lỗi → in một dòng cảnh báo ra stderr, lệnh `state.py` vẫn giữ nguyên exit code của nó.

## 6. `implementation.py`

```
implementation.py [--root DIR] [--out docs/napoleon/implementation.md]
```

- Chỉ đọc: `state.json`, `git`, `plan.md`/`verify.md` của feature, `instructions/{routes.md,architecture.md,decisions/}`, file nguồn.
- Chưa có `state.json` → in một dòng, exit 0, không ghi file.
- Không có git → cột File đổi, Commit ghi `—`.
- Nội dung không đổi → không ghi lại file.
- Tìm "có trong code": tìm chuỗi thuần trong file nguồn của dự án, dùng nguyên `audit.source_files` để liệt kê file nguồn. Tên class khớp theo ranh giới từ.
- `route_pattern` (tuỳ chọn, trong `.claude/instructions/toolchain.json`): một regex có đúng một nhóm bắt, vd `path:\s*'([^']+)'`. Có → tool quét file nguồn, gom route trong code để so với `routes.md`.
- Ô bảng: thoát `|`, xuống dòng → dấu cách.

## 7. `routes.md`

`.claude/instructions/routes.md`, template ở `.claude/templates/routes.md`:

```markdown
# Route

| Route | Màn (class) | Feature | Design |
|---|---|---|---|
| /login | LoginScreen | login | docs/sources/design/login.png |
```

- `/start-build` (skill `architecture-interview`) tạo file với bảng rỗng.
- Bước **spec** của feature: thêm dòng cho màn/route mới của feature (đã có mục "Màn hình / luồng" trong spec).
- Bước **plan**: `task add` kèm `--routes` cho task làm route đó.
- File thuộc `instructions/` nên theo luật "Thiết kế là luật": đổi route đã duyệt phải hỏi.

## 8. Chỗ khác phải sửa theo

- `.claude/CLAUDE.md`: mục Tool và mục Vị trí (giữ giới hạn độ dài hiện có).
- `.claude/commands/where.md`, `.claude/commands/report.md`: thêm bước chạy `implementation.py`.
- `.claude/skills/napoleon-core/SKILL.md`, `.claude/skills/feature-loop/SKILL.md`, `.claude/skills/architecture-interview/SKILL.md`, `.claude/commands/feature.md`: nhắc `routes.md`, `--routes`, và file báo cáo.
- `.claude/templates/toolchain.json`: thêm khoá `route_pattern` rỗng.
- `.claude/tools/guard.py`: chặn sửa tay `implementation.md`.
- `README.md`.
- `tests/test_docs.py`: thêm `implementation.py` vào tập tool.

## 9. Test

`tests/test_implementation.py` với repo git tạm:
- Sinh hai lần liên tiếp → nội dung giống hệt.
- Task done có `changed`, `test` → đúng dòng ở 4.2, 4.3, 4.4.
- Sha hiển thị là commit ngay sau khi đóng task; chưa commit → `commit kế tiếp`; có commit giữa chừng → `(+n)`; lịch sử viết lại → `—`.
- Task done được mở lại: `base` giữ nguyên, `changed` gồm cả file của lần đầu.
- `task done` trượt: `checks` và `test` được lưu, bảng 4.4 hiện FAIL.
- Route: đủ / thiếu màn / thiếu chuỗi route / task khai route không có trong `routes.md` / `route_pattern` bắt được route chưa khai.
- Bảng nguồn sự thật: bỏ dòng placeholder, cột Trong code đúng.
- Không git, không state, không `routes.md`, không `architecture.md` → không lỗi.
- Ô có `|` được thoát.

`tests/test_state.py` thêm: `task start` ghi `base`; `task done` ghi `changed` và `test`; mốc diff là `base` của chính task; tool báo cáo lỗi không làm `state.py` trượt; state cũ thiếu trường mới vẫn chạy.

## 10. Để người triển khai tự quyết

- Gọi `implementation.py` bằng import hay subprocess.
- Tên hàm, cách chia file, có tách phần parse markdown ra module dùng chung hay không.
- Chữ chính xác của các dòng cảnh báo và dòng hướng dẫn.

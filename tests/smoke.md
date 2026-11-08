# Smoke test chạy tay (~15 phút)

Cần: Flutter SDK, codegraph, Claude Code có superpowers. Mỗi bước có "kỳ vọng"; lệch → ghi lại.

## 0. Chuẩn bị
```bash
flutter create smoke_app && cd smoke_app
~/napoleon/install.sh . && codegraph init
```
Kỳ vọng: in "đã copy N file", `.mcp.json` có codegraph + context7, `.gitignore` có `.codegraph/` và `reports/`.

## 1. Mở Claude Code
Kỳ vọng: SessionStart hook im lặng (chưa có state). `/help` thấy 7 lệnh napoleon.

## 2. `/map-codebase`
Kỳ vọng: `docs/napoleon/codebase-report.md` có `## Số liệu` với dòng `source: codegraph`, `## Nhận xét`, 3–5 câu hỏi.

## 3. `/start-build Flutter + BLoC + clean architecture, app todo đơn giản: thêm/sửa/xoá việc, lọc theo trạng thái`
Trả lời nhanh, chọn khuyến nghị. Kỳ vọng:
- Hỏi một câu một lần, có `(Khuyến nghị)`.
- Không hỏi lại stack đã nêu.
- Sinh `.claude/instructions/{project,architecture,conventions,module-map}.md`, `rules.json`, `toolchain.json`, ≥ 1 ADR.
- Không còn `<...>` trong file sinh.
- `python3 .claude/tools/conform.py` chạy, không "0 file quét".
- `docs/napoleon/features.md` có ≥ 3 feature tên `[a-z0-9-]`; `state.json` tồn tại.
- Khung thư mục `lib/features/...` chỉ có `.gitkeep`.

## 4. `/setup-agents`
Kỳ vọng: `.claude/rules/*.md` (≥ 2, có `paths:`), `.claude/skills/project-new-feature/SKILL.md`, frontmatter ở dòng 1, dòng đầu thân `<!-- napoleon:generated -->`. Không sinh agent nếu không có lý do; nếu có, frontmatter ghi lý do.

## 5. `/feature todo-list`
Chạy lần lượt 5 lần (mỗi lần một bước). Kỳ vọng:
- spec: hỏi ≤ 3 câu, `features/todo-list/spec.md` có "Yêu cầu" đánh số.
- plan: `codegraph status` được gọi; `plan.md` có task kèm file và test; `state.py show` thấy task `todo`.
- build: sửa file → hook in output `dart format`/`dart analyze`; sau mỗi task chạy `conform.py`; task chuyển `done`.
- verify: `verify.md` có 3 mục, agent verifier được gọi, bảng yêu cầu có bằng chứng `file:dòng`.
- done: `journal.md` có mục mới, `state.py show` thấy `[done]`.

## 6. Phiên mới
Đóng, mở lại Claude Code. Kỳ vọng: hook in ≤ 5 dòng trạng thái. `/status` in state + journal.

## 7. `/report`
Kỳ vọng: `reports/roadmap.html` mở được, số feature/task khớp `state.py show`, mục Commit "không có dữ liệu" nếu chưa `git init`, mỗi bảng có "nguồn: ...".

## 8. `/retro`
Kỳ vọng: liệt kê lỗi lặp (có thể rỗng), nếu đề xuất rule → chạy `conform.py` sau khi áp.

## 9. Cập nhật bộ
```bash
echo "# sửa tay" >> .claude/rules/<một-file>.md   # xoá dòng generated trước
~/napoleon/install.sh . --update
```
Kỳ vọng: file sửa tay giữ nguyên; `CLAUDE.md`, `tools/` được đè; `settings.json`, `instructions/`, `docs/napoleon/` không đổi.

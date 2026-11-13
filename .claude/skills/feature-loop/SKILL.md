---
name: feature-loop
description: Vòng đời một feature spec → plan → build → verify → done, với state.py và skill superpowers ở mỗi bước. Dùng trong /feature, hoặc khi tiếp tục một feature dở ở phiên mới.
---

# Vòng đời feature

Trạng thái thật nằm ở `state.py`. Đọc trước, ghi sau mỗi bước. Không nhảy bước.

```bash
python3 .claude/tools/state.py feature show <tên>     # đang ở bước nào
python3 .claude/tools/state.py feature step <tên> <bước>
```

## Bước

| Bước | Vào khi | Làm | Skill superpowers | Ra khi |
|---|---|---|---|---|
| **spec** | feature mới (`feature add`) | Đọc `features/<tên>/brief.md` (chưa có → tạo từ template, dán nguyên văn lời người dùng), `docs/sources/{prd,api,design}/` liên quan, `instructions/project.md`. Hỏi phần chưa rõ, một câu một lần. Viết spec từ template napoleon. | `brainstorming` — đường **bounded**. **Spec lưu tại `docs/napoleon/features/<tên>/spec.md`**, không dùng đường mặc định `docs/superpowers/specs/`. | spec có mục "Yêu cầu" đánh số, phủ hết ý trong brief, người dùng duyệt |
| **plan** | spec duyệt | `codegraph status` → sync nếu cũ. Mỗi task: file sẽ đụng (`codegraph_impact` cho symbol sửa), test chứng minh. `state.py task add` cho từng task kèm `--files` (cổng `task done` dùng danh sách này). | `writing-plans`. **Plan lưu tại `docs/napoleon/features/<tên>/plan.md`**, không dùng `docs/superpowers/plans/`. | mọi task có trong `state.json` |
| **build** | plan xong | Bước 0 một lần: đọc `architecture.md#Nguồn sự thật dùng chung` + `codegraph_explore` `core/`. Rồi từng task: `task start` → `codegraph_search` tên gần giống trước khi tạo mới → TDD → `task done` (tự chạy cổng) → commit. API thư viện mới → context7 trước. Mơ hồ → hỏi. Kẹt → `task block` kèm lý do. | `test-driven-development`, `systematic-debugging` khi lỗi | mọi task `done` |
| **verify** | build xong | Theo skill `verifying`: máy (toàn bộ test, không theo diff) → verifier → người. `state.py verify <tên> pass\|fail --issue <nhãn>`. Ghi `verify.md`. | `verification-before-completion` | mọi mục Máy và Verifier `[x]`; mục Người đã liệt kê |
| **done** | verify đạt | `codegraph sync`. `feature step <tên> done` (cổng kiểm `verify.md`). Việc ADR hẹn lại → `followup add`. `session note`. Commit. Gợi ý `/report` và phiên mới cho feature kế. | `finishing-a-development-branch` nếu có branch | — |

## Đóng task: cổng chạy bằng code
```bash
python3 .claude/tools/state.py task done <feature> <id>
```
Lệnh tự làm, không tin lời ai: `conform.py` trên `--files` của task, rồi test theo diff (`affected.py` → `toolchain.json`).
- Trượt → in lý do, task vẫn `in_progress`. Sửa rồi chạy lại.
- `--skip-tests` / `--skip-conform` chỉ khi người dùng đồng ý; lý do bị ghi vào `state.json` và hiện trong `/report`.
- Sau khi done thì commit một commit cho task đó (`state.py` lưu sha làm mốc diff cho task sau). Chưa commit → task sau chạy test trên diff gộp, rộng hơn mức cần.

## Quay lui
- verify fail → `state.py verify <tên> fail --issue <nhãn>` (nhãn ngắn, lặp lại được: `hardcode`, `ham-dai`, `thieu-test`, `lech-design`) → `feature step <tên> build` → mở lại task liên quan hoặc `task add` task sửa.
- Nhãn lỗi lặp ở ≥ 2 feature → `state.py` nhắc chạy `/retro` để chặn bằng máy. Làm, đừng bỏ qua.
- plan sai khi build → sửa `plan.md`, `task add`/cập nhật, ghi một dòng "đổi plan vì …" vào `plan.md`.

## Mục Người được phép pending
`feature step … done` chặn khi còn ô trống ngoài mục `## Người`; ô trong mục Người thì chỉ nhắc và đếm — người dùng tự kiểm sau bằng `state.py human <tên> list` / `tick <n>`. Không tự tick hộ. Không coi feature là chưa xong chỉ vì mục Người còn trống.

## Phiên mới giữa chừng
1. `state.py show --brief` (hook SessionStart đã in).
2. Đọc `features/<tên>/plan.md`, mục task đang `in_progress`.
3. Tiếp tục ở đúng task. Không làm lại từ đầu.

## Cuối mỗi phiên (dù chưa xong bước)
```bash
python3 .claude/tools/state.py session note <tên> "dừng ở task N, còn X"
```

## Cấm
- Không viết code ở spec/plan.
- Không đánh task `done` bằng cách sửa state.json tay (hook chặn) hoặc bằng `--skip-*` không có người duyệt.
- Không chạy toàn bộ test sau mỗi task; đó là việc của bước verify.

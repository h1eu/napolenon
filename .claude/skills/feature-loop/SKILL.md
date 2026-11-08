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
| **plan** | spec duyệt | `codegraph status` → sync nếu cũ. Mỗi task: file sẽ đụng (`codegraph_impact` cho symbol sửa), test chứng minh. `state.py task add` cho từng task. | `writing-plans`. **Plan lưu tại `docs/napoleon/features/<tên>/plan.md`**, không dùng `docs/superpowers/plans/`. | mọi task có trong `state.json` |
| **build** | plan xong | Bước 0 một lần: đọc `architecture.md#Nguồn sự thật dùng chung` + `codegraph_explore` `core/`. Rồi từng task: `task start` → `codegraph_search` tên gần giống trước khi tạo mới → TDD → `conform.py` → `task done`. API thư viện mới → context7 trước. Mơ hồ → hỏi, không tự quyết. Kẹt → `task block` kèm lý do. | `test-driven-development`, `systematic-debugging` khi lỗi | mọi task `done` |
| **verify** | build xong | Theo skill `verifying`: máy → verifier → người. Ghi `verify.md`. | `verification-before-completion` | mọi mục Máy và Verifier `[x]`; mục Người đã liệt kê |
| **done** | verify đạt | `codegraph sync`. `state.py session note <tên> "<tóm tắt>"`. `feature step <tên> done`. Gợi ý `/report`. | `finishing-a-development-branch` nếu có branch | — |

## Quay lui
- verify fail → `feature step <tên> build`, mở lại task liên quan (`task start`), hoặc `task add` task sửa lỗi. Không đánh `done` khi còn `[ ]` ở Máy/Verifier.
- plan sai khi build → sửa `plan.md`, `task add`/cập nhật, ghi một dòng "đổi plan vì …" vào `plan.md`.

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
- Không tự đánh task `done` khi test chưa chạy xanh trong phiên này.
- Không bỏ qua `conform.py` sau task.

---
description: Làm một feature theo vòng spec → plan → build → verify → done. Không truyền bước → bước kế tiếp.
argument-hint: <tên> [spec|plan|build|verify|done]
---
Dùng skill `feature-loop`. Đối số: $ARGUMENTS (tên, bước tuỳ chọn).

1. `python3 .claude/tools/state.py feature show <tên>`. Chưa có → `feature add <tên>` (tên phải `[a-z0-9-]`, không thì hỏi tên khác).
2. Bước = đối số thứ hai nếu có; không → bước hiện tại trong state. Không được nhảy quá bước kế tiếp; muốn lùi (verify → build) thì được.
3. `mkdir -p docs/napoleon/features/<tên>`. Bước spec mà chưa có `brief.md` → tạo từ `.claude/templates/brief.md`, dán nguyên văn phần mô tả trong $ARGUMENTS hoặc hỏi người dùng đề bài.
4. Làm đúng một bước theo bảng trong skill `feature-loop`, gọi skill superpowers tương ứng. Khi gọi brainstorming/writing-plans: nói rõ "lưu tại `docs/napoleon/features/<tên>/spec.md`" (hoặc `plan.md`), theo template napoleon. Bước verify → dùng skill `verifying`.
5. Bước build: đóng từng task bằng `state.py task done <tên> <id>` (tự chạy conform + test theo diff), rồi commit task đó. Bước verify: ghi kết quả bằng `state.py verify <tên> pass|fail [--issue <nhãn>]`.
6. Xong bước → `state.py feature step <tên> <bước-kế>`. Bước `done` có cổng đọc `verify.md`; việc ADR hẹn lại → `state.py followup add`. In 3 dòng: làm gì, còn gì, lệnh tiếp theo.
7. Dừng giữa chừng vì bất kỳ lý do gì → `state.py session note <tên> "<dừng ở đâu>"` trước khi kết thúc lượt.

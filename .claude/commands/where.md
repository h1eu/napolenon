---
description: "Đang ở đâu: state.json + 20 dòng journal cuối. Không suy luận thêm."
---
1. `python3 .claude/tools/state.py show` (có cả followup đang mở và số mục Người chờ tick)
2. `python3 .claude/tools/implementation.py` (làm mới `docs/napoleon/implementation.md`), in đường dẫn file.
3. `tail -n 20 docs/napoleon/journal.md` (không có → bỏ qua).
4. In nguyên output, thêm đúng một dòng gợi ý lệnh tiếp theo (`/feature <tên>` của feature đang dở, hoặc `/start-build` nếu chưa có state).

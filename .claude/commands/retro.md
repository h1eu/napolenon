---
description: Tìm lỗi/sửa lặp ≥ 2 lần trong journal, verify.md, git log → đề xuất một chỗ chặn bằng máy cho mỗi lỗi.
---
Dùng skill `writing-conventions` (mục "Từ lỗi lặp").

1. `python3 .claude/tools/state.py show --json` → nhãn trong `features[].verify[].issues` (nguồn chính). Thêm: `docs/napoleon/journal.md`, `docs/napoleon/features/*/verify.md`, `git log --oneline -100` (không có git → bỏ).
2. Liệt kê lỗi hoặc sửa lặp ≥ 2 lần. Mỗi dòng: lỗi, số lần, nơi xuất hiện.
3. Mỗi lỗi → **một** chỗ chặn, theo thứ tự ưu tiên: `rules.json` (có `forbidden-pattern`, `max-function-lines`, `max-params`, `no-sibling-import`) → test trong repo → hook → rule theo path → chữ trong `conventions.md`. Ghi rõ nội dung thay đổi đề xuất.
4. Hỏi người dùng duyệt từng mục (AskUserQuestion, multiSelect).
5. Áp dụng mục được duyệt. Rule mới → `python3 .claude/tools/conform.py` và `--coverage` phải sạch (quy ước mới nhớ gắn nhãn `[rule: <id>]`). Quyết định đáng nhớ → ADR ngắn, việc hẹn lại → `state.py followup add`.
6. Có feature trong state → `python3 .claude/tools/state.py session note <feature-gần-nhất> "retro: <tóm tắt>"`. Chưa có feature → ghi một dòng vào `docs/napoleon/journal.md` tay.

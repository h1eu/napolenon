---
description: Đọc .claude/instructions/ → sinh rule theo path, skill project-*, agent project-* (chỉ khi cần). Chạy lại được.
---
Dùng skill `generating-project-agents`.

1. Không có `.claude/instructions/architecture.md` → dừng: "Chạy `/start-build` trước."
2. Đọc `.claude/instructions/` (không đọc code).
3. Mỗi module/tầng → `.claude/rules/<tên>.md` từ `.claude/templates/path-rule.md`, ≤ 15 dòng, có `paths:` khớp cấu trúc thật.
4. `.claude/skills/project-new-feature/SKILL.md` từ `.claude/templates/feature-skill.md`.
5. Tác vụ lặp lại mà `instructions/` mô tả rõ các bước (thêm endpoint, thêm bảng DB, thêm màn hình) → `.claude/commands/project-<việc>.md` từ `.claude/templates/project-command.md`. Skill/agent thêm chỉ theo tiêu chí trong skill. Mỗi agent ghi lý do một dòng.
6. File đích đã có và không có dòng `<!-- napoleon:generated -->` ngay sau frontmatter → bỏ qua, in tên.
7. `python3 .claude/tools/conform.py --coverage` và `python3 .claude/tools/conform.py` phải sạch. Còn lỗi → sửa `rules.json`/`conventions.md` rồi chạy lại, đừng kết thúc.
8. In danh sách file sinh/bỏ qua. Nhắc: "Sửa tay file nào thì xoá dòng generated để lần sau không bị đè."

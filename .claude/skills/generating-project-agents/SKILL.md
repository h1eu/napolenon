---
name: generating-project-agents
description: Sinh rule theo path, skill và agent riêng cho dự án từ .claude/instructions/. Dùng trong /setup-agents. Mặc định sinh skill; agent chỉ khi cần song song, context cô lập, hoặc phân quyền khác.
---

# Sinh rule / skill / agent cho dự án

## Đầu vào
Đọc toàn bộ `.claude/instructions/`: `architecture.md`, `conventions.md`, `module-map.md`, `rules.json`, `toolchain.json`, `decisions/`. Không đọc code.

## Quy trình
1. Liệt kê module/tầng từ `module-map.md` và cấu trúc thư mục trong `architecture.md`.
2. **Mỗi module hoặc tầng một rule theo path** → `.claude/rules/<tên>.md` từ `templates/path-rule.md`. ≤ 15 dòng. Chỉ ghi điều phải làm/cấm khi sửa file trong path đó, kèm `Xem: .claude/instructions/<file>#<mục>`.
3. **Một skill `project-new-feature`** → `.claude/skills/project-new-feature/SKILL.md` từ `templates/feature-skill.md`: các bước tạo một feature đúng kiến trúc này, file nào ở đâu, lệnh codegen nếu có, test tối thiểu.
4. Tác vụ lặp lại khác mà `instructions/` mô tả rõ bước (thêm endpoint, thêm bảng DB, thêm màn hình): người dùng gõ một lệnh là chạy → **command** `.claude/commands/project-<việc>.md` từ `templates/project-command.md`; cần kiến thức nền dài hơn 20 dòng → **skill** `project-<việc>` và command gọi skill đó. Không có quy trình rõ → không sinh.
5. **Agent chỉ khi đạt một trong ba**:
   - cần chạy **song song** với việc chính (vd: viết test cho nhiều module độc lập),
   - cần **context cô lập** (vd: review không được thấy lời giải thích của người build),
   - cần **phân quyền khác** (vd: chỉ đọc, hoặc chỉ được chạy lệnh test).
   Không đạt → làm skill. Agent từ `templates/feature-agent.md`, tên `project-<việc>`, ghi lý do một dòng.
6. In danh sách file đã sinh và câu "chạy lại /setup-agents khi instructions/ đổi".

## Dấu generated và chạy lại
- Mọi file sinh: frontmatter `---` ở dòng 1 (Claude Code đòi vậy), dòng đầu tiên của thân là `<!-- napoleon:generated -->`.
- Chạy lại: file có dấu → ghi đè; file không dấu (người sửa tay) → bỏ qua, in tên.
- Người muốn giữ sửa tay → xoá dòng dấu.

## Viết gọn
- `description` ≤ 3 dòng, có "Dùng khi …".
- Thân: bước đánh số, lệnh chạy, điều cấm. Không giải thích lý do quá một dòng.
- Không lặp nội dung `instructions/`; trỏ sang.

## Cấm
- Không sinh agent "cho đủ bộ".
- Không sinh rule cho path không tồn tại trong kiến trúc.
- Không sửa `instructions/`.

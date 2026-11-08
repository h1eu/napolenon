---
name: napoleon-core
description: Napoleon hoạt động thế nào, phân vai với superpowers, file nào ở đâu, tool nào khi nào. Dùng khi bắt đầu dùng bộ này trong một dự án hoặc khi không chắc việc này thuộc napoleon hay superpowers.
---

# Napoleon core

## Phân vai

| Việc | Ai lo |
|---|---|
| Làm rõ yêu cầu, thiết kế một feature | superpowers `brainstorming` (bounded, vì kiến trúc đã chốt) |
| Tách task, viết plan | superpowers `writing-plans` |
| Viết code | superpowers `test-driven-development` |
| Debug | superpowers `systematic-debugging` |
| Trước khi nói "xong" | superpowers `verification-before-completion` |
| Chốt kiến trúc, quy ước của **dự án này** | napoleon `/start-build`, skill `architecture-interview` |
| Sinh rule/skill/agent riêng dự án | napoleon `/setup-agents` |
| Trạng thái feature/task xuyên phiên | napoleon `state.py` |
| Truy vấn code | codegraph MCP, skill `using-codegraph` |
| Kiểm tra quy ước, phụ thuộc, báo cáo | napoleon `conform.py`, `audit.py`, `report.py` |
| Kiểm tra độc lập sau build | napoleon agent `verifier` |

Napoleon không viết lại quy trình superpowers. Ở mỗi bước của `/feature`, nó gọi skill superpowers tương ứng.

## File ở đâu

- `.claude/instructions/` — **cách** làm việc: `project.md`, `architecture.md`, `conventions.md`, `module-map.md`, `rules.json`, `toolchain.json`, `decisions/ADR-*.md`. Sinh một lần bởi `/start-build`, người sửa tay được.
- `.claude/rules/` — rule ≤ 15 dòng, frontmatter `paths:`, trỏ về mục trong `instructions/`. Sinh bởi `/setup-agents`.
- `.claude/skills/project-*/`, `.claude/agents/project-*.md` — sinh bởi `/setup-agents`, có dấu generated.
- `docs/sources/{prd,api,design}/` — **tài liệu người dùng đưa**: PRD, API docs, Figma export/mockup. Tool chỉ đọc. `/start-build` và bước spec đọc từ đây.
- `docs/napoleon/` — **đang ở đâu**: `state.json`, `journal.md`, `codebase-report.md`, `features/<tên>/{brief,spec,plan,verify}.md`. `brief.md` = đề bài nguyên văn, không sửa sau khi có spec.
- Spec/plan **luôn** ở `docs/napoleon/features/<tên>/`. Superpowers brainstorming/writing-plans mặc định ghi `docs/superpowers/` — phải nói rõ đường dẫn napoleon khi gọi.
- Không có `context/`, `drafts/`, `commands/` ngoài `.claude/`: quy ước ở `instructions/`, code dở ở git branch, lệnh ở `.claude/commands/project-*`.
- `reports/roadmap.html` — sinh bởi `report.py`. Không commit mặc định.

## Nguyên tắc gọn
- Mô tả agent/skill ≤ 3 dòng. Thân chỉ ghi việc phải làm, việc cấm, lệnh chạy.
- Không giải thích lý do quá một dòng.
- Không checklist cho việc tool đã kiểm.
- Context luôn nạp (`CLAUDE.md` + rule khớp path) giữ dưới ~100 dòng. Phần còn lại nằm trong skill, nạp khi cần.
- Lỗi lặp lại → `/retro` → chặn bằng máy, không thêm chữ.

## Tool nào khi nào
- Mở phiên: `state.py show --brief`.
- Trước plan: `codegraph status`; cũ → `codegraph sync`.
- Sau mỗi task build: `conform.py`.
- Bước verify: toolchain (format/analyze/test/build) → `conform.py` → `audit.py` → agent `verifier`.
- Bước done: `codegraph sync`, `state.py session note`.
- Muốn số liệu: `report.py`. Không gõ tay.

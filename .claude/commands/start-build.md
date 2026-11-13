---
description: Phỏng vấn để chốt kiến trúc, quy ước, toolchain → sinh .claude/instructions/ + khung thư mục + features.md + state.json
argument-hint: [mô tả dự án hoặc đường dẫn tài liệu]
---
Dùng skill `architecture-interview`. Đầu vào: $ARGUMENTS

1. Đã có `.claude/instructions/project.md` → hỏi: "Đã có instructions. Làm lại từ đầu hay chỉ cập nhật mục nào?" Dừng chờ trả lời.
2. Đọc `docs/sources/prd/`, `api/`, `design/` và tài liệu trong $ARGUMENTS (đường dẫn → Read; đoạn văn → dùng trực tiếp). Có `docs/napoleon/codebase-report.md` → đọc, không hỏi lại điều report đã trả lời.
3. Phỏng vấn 8 chủ đề theo skill (1→4, 4b, 5→7), một câu một lần. Chủ đề 7 không hỏi từng quy ước: in baseline + stack, hỏi một câu bổ sung. Tài liệu tham khảo trong `references/` chỉ đọc khi chủ đề chạm tới.
4. Quyết định không hiển nhiên → ADR từ `.claude/templates/adr.md` vào `.claude/instructions/decisions/`.
5. Sinh từ `.claude/templates/`: `project.md`, `architecture.md`, `conventions.md`, `module-map.md`, `rules.json`, `toolchain.json` → `.claude/instructions/`. Không để placeholder `<...>` sót lại.
6. `python3 .claude/tools/conform.py` → phải chạy được, 0 file quét là glob sai, sửa. `python3 .claude/tools/stack.py` → `docs/napoleon/stack.md` (dự án mới chưa có manifest thì chạy lại sau khi tạo project).
7. Khung thư mục rỗng theo `architecture.md`: `mkdir -p` + `.gitkeep`. Không tạo file code.
8. `docs/napoleon/features.md` từ tài liệu (một dòng/feature, tên `[a-z0-9-]`). `python3 .claude/tools/state.py init` rồi `python3 .claude/tools/state.py sources mark` (mốc để `/sync-docs` so sau này).
9. `codegraph status`; chưa có → `codegraph init`.
10. Tóm tắt ≤ 8 dòng những gì đã chốt, rồi: "Chạy `/setup-agents` để sinh rule/skill riêng cho dự án."

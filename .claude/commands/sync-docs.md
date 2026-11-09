---
description: "Tài liệu trong docs/sources/ đổi → so với mốc cuối, chỉ ra điểm lệch với instructions/ và spec, hỏi bạn quyết từng điểm, áp dụng, đánh mốc mới."
argument-hint: [tên feature để chỉ soi spec của nó]
---
Đối số: $ARGUMENTS (tuỳ chọn: tên feature → chỉ đối chiếu `docs/napoleon/features/<tên>/`).

1. Không có `.claude/instructions/project.md` → dừng: "Chạy `/start-build` trước."
2. `python3 .claude/tools/sources.py diff`. Không có file mới/đổi/xoá → in "Không có gì đổi so với mốc", dừng.
3. Chưa có mốc (tool in "CHƯA CÓ") → hỏi: "Lần đầu đồng bộ. Coi tài liệu hiện tại là đã khớp harness (chỉ đánh mốc), hay đối chiếu toàn bộ?" Dừng chờ. Chọn đánh mốc → bước 8.
4. Mỗi file đổi: đọc hunk tool in (hoặc cả file nếu mới), rồi đọc **đúng** những chỗ trích dẫn tool liệt kê và file instructions cùng chủ đề (PRD → `project.md`, `features.md`; API → `architecture.md`, spec mục "Dữ liệu & API"; design → spec mục "Design nguồn"). Không đọc toàn bộ `instructions/`.
5. Liệt kê điểm lệch, mỗi dòng: `tài liệu mới: B · harness đang ghi: A · tại <file:dòng>`. Chỉ ghi điểm hai bên **mâu thuẫn** hoặc tài liệu có mà harness chưa có. Không bịa điểm lệch; không có → "không lệch", sang bước 8. File bị xoá mà harness còn trích dẫn → một điểm lệch.
6. Mỗi điểm lệch **một** câu AskUserQuestion, một câu một lần: (a) Theo tài liệu mới `(Khuyến nghị)` (b) Giữ harness như cũ, ghi lý do (c) Để sau. Không gộp nhiều điểm vào một câu. Không tự chọn hộ.
7. Áp dụng theo trả lời:
   - (a) sửa đúng dòng trong `instructions/*.md`, `features.md`, `spec.md`. Kiến trúc/quy ước/ranh giới module đổi → ADR từ `.claude/templates/adr.md`. Feature ở `build`/`verify` bị ảnh hưởng → `python3 .claude/tools/state.py task add <tên> "đồng bộ tài liệu: <việc>"`; ở `spec`/`plan` → thêm dòng vào mục "Câu hỏi đã chốt" của `spec.md`. `brief.md` không sửa.
   - (b) ADR ngắn ghi lý do giữ, trạng thái "chấp nhận".
   - (c) ghi một dòng vào `docs/napoleon/journal.md`: `sync-docs: để sau — <điểm lệch>`.
8. `python3 .claude/tools/state.py sources mark`. Có feature trong state → `python3 .claude/tools/state.py session note <feature-liên-quan> "sync-docs: <N> điểm lệch, <tóm tắt quyết định>"`.
9. In tóm tắt ≤ 6 dòng, số lấy từ output tool: file đổi, điểm lệch, quyết định từng điểm. Đã sửa `instructions/` → "Chạy `/setup-agents`." Đã sửa spec → "Chạy `/feature <tên> <bước hiện tại>`."

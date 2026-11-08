---
description: "Map dự án có sẵn: check codegraph → full scan → dependency audit → docs/napoleon/codebase-report.md"
---
Dùng skill `using-codegraph`.

1. `codegraph status`. Chưa có index → `codegraph init`. Cũ → `codegraph sync`. Không có codegraph → báo một dòng kèm lệnh cài, tiếp tục với `--source scan`.
2. Liệt kê thư mục gốc chứa code (bỏ `build/`, `.dart_tool/`, `node_modules/`). Với mỗi thư mục: `codegraph_explore` → ghi 2–4 dòng: vai trò, entry point, pattern đang dùng.
3. `python3 .claude/tools/audit.py` (markdown) và `python3 .claude/tools/audit.py --json`.
4. Ghi `docs/napoleon/codebase-report.md`:
   - `## Số liệu` — dán nguyên output markdown của audit.py. Không sửa, không thêm số.
   - `## Cấu trúc` — kết quả bước 2.
   - `## Nhận xét` — ≤ 10 dòng: pattern nhất quán hay lẫn lộn, cycles đáng ngại, module phình, chỗ không ai gọi.
   - `## Câu hỏi cho bạn` — 3–5 câu, chỗ agent không chắc (vd: "lib/legacy/ còn dùng không?").
5. In đường dẫn report và câu: "Dự án chưa có `.claude/instructions/` → chạy `/start-build`, mình sẽ đọc report này thay vì hỏi từ đầu."

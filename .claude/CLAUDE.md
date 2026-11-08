# Napoleon — tầng dự án cho Claude Code

Napoleon bổ sung cho superpowers phần **riêng của từng dự án**: kiến trúc đã chốt, quy ước, trạng thái feature/task xuyên phiên, truy vấn code bằng codegraph, tool bằng code để không ảo giác số liệu. Superpowers lo quy trình chung (brainstorm, plan, TDD, debug, review). Chi tiết phân vai: skill `napoleon-core`.

## Bắt đầu phiên
1. Có `.claude/instructions/project.md` → đọc nó trước. Chưa có → dự án chưa `/start-build`.
2. Chạy `python3 .claude/tools/state.py show --brief` để biết đang ở feature nào, bước nào, task nào dở.
3. Không đọc toàn bộ `instructions/`. Rule theo path trong `.claude/rules/` tự nạp phần cần khi sửa file.

## Quy tắc cứng
- **Codegraph trước grep.** Tìm symbol, file, ai gọi ai, ảnh hưởng khi sửa → `codegraph_*`. Grep chỉ cho chuỗi văn bản thuần (string literal, log, config). Xem skill `using-codegraph`.
- **Tra doc, không đoán.** Dùng API thư viện ngoài lần đầu trong phiên → context7 (`resolve-library-id` → `query-docs`), đúng version trong pubspec/gradle/package.json.
- **Trạng thái chỉ qua `state.py`.** Không sửa tay `docs/napoleon/state.json`. Không ghi tiến độ vào nơi khác.
- **Số liệu chỉ qua tool.** `audit.py`, `conform.py`, `report.py`. Không gõ tay con số vào báo cáo. Muốn thêm số → sửa tool.
- **Không nhảy bước feature.** spec → plan → build → verify → done. verify fail → về build.
- **Trả lời tiếng Việt.** Tên file, lệnh, code tiếng Anh.

## Quy tắc code
- **Tìm trước, viết sau.** Trước khi tạo hàm/widget/class mới: `codegraph_search` tên gần giống và xem `core/`/`common/`. Có rồi → dùng hoặc mở rộng, không tạo bản thứ hai.
- **Comment chỉ cho "vì sao".** Không banner, không docstring lặp tên hàm, không giải thích code hiển nhiên. `conform.py` bắt tỉ lệ comment.
- **Thiết kế là luật.** `instructions/architecture.md`, `module-map.md` và design UI (Figma/ảnh) không tự lệch, không tự thêm bớt. Muốn lệch → hỏi, được duyệt → ADR.
- **Mơ hồ → hỏi.** Một câu trắc nghiệm, dừng chờ. Không chọn hộ rồi báo sau.
- **Một nguồn sự thật.** Trạng thái dùng ở ≥ 2 nơi → một owner phát ra (Flow/Stream/Listenable), các nơi quan sát. Không nơi nào giữ bản sao rồi tự đồng bộ. Bảng owner ở `architecture.md#Nguồn sự thật dùng chung`.
- **Logic tái dùng → class riêng** (`XxxManager`/`XxxRuntime`), inject qua DI, có test riêng, nằm ngoài `presentation/`. Một class một việc; > ~300 dòng → tách.

## Lệnh
| Lệnh | Dùng khi |
|---|---|
| `/map-codebase` | Dự án có sẵn, hoặc muốn báo cáo lại cấu trúc. Chạy trước `/start-build` với dự án cũ. |
| `/start-build` | Dự án mới hoặc chưa có `instructions/`. Phỏng vấn → sinh chỉ dẫn + khung thư mục. |
| `/setup-agents` | Sau `/start-build`, hoặc khi kiến trúc đổi. Sinh rule/skill/agent riêng dự án. |
| `/feature <tên> [bước]` | Làm một feature. Không truyền bước → bước kế tiếp. |
| `/status` | Mở phiên mới, muốn biết đang ở đâu. |
| `/report` | Sinh `reports/roadmap.html`. |
| `/retro` | Thấy lỗi lặp lại. Biến nó thành test/rule/hook. |

## Tool (chạy từ gốc dự án)
- `python3 .claude/tools/state.py --help` — trạng thái feature/task.
- `python3 .claude/tools/conform.py` — soi code theo `instructions/rules.json`.
- `python3 .claude/tools/audit.py` — cycles, ranh giới module, dep ngoài, file mồ côi.
- `python3 .claude/tools/report.py` — roadmap.html.

## Khi viết agent/skill/rule cho dự án
- Mô tả ≤ 3 dòng. Chỉ ghi việc phải làm và việc cấm. Không giải thích dài.
- Một agent một việc. Mặc định sinh skill; agent chỉ khi cần song song, context cô lập, hoặc phân quyền khác.
- File sinh ra: frontmatter ở dòng 1, dòng đầu thân là `<!-- napoleon:generated -->`.

## Vị trí
- `.claude/instructions/` — cách làm việc trong dự án này (sinh bởi `/start-build`).
- `.claude/rules/` — rule ngắn theo path (sinh bởi `/setup-agents`).
- `docs/sources/{prd,api,design}/` — tài liệu bạn đưa; tool chỉ đọc.
- `docs/napoleon/` — đang ở đâu: `state.json`, `journal.md`, `codebase-report.md`, `features/<tên>/{brief,spec,plan,verify}.md`.
- Spec/plan của feature **luôn** ở `docs/napoleon/features/<tên>/`, kể cả khi gọi superpowers brainstorming/writing-plans. Không tạo `docs/superpowers/` trong dự án.
- `reports/` — sinh ra, không sửa tay.

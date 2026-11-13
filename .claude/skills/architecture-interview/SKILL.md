---
name: architecture-interview
description: Phỏng vấn người dùng để chốt kiến trúc, quy ước, toolchain cho một dự án rồi sinh .claude/instructions/. Dùng trong /start-build, hoặc khi kiến trúc dự án thay đổi lớn.
---

# Phỏng vấn kiến trúc

Mục tiêu: sau phỏng vấn, mọi phiên sau đều biết dự án này xây thế nào mà không cần hỏi lại.

## Cách hỏi
- **Một câu một lần.** Dùng AskUserQuestion. Trắc nghiệm khi có thể, khuyến nghị đứng đầu, ghi `(Khuyến nghị)`.
- Mỗi lựa chọn mô tả ≤ 2 câu: nó là gì, đổi lại cái gì.
- **Không hỏi điều tài liệu đã trả lời.** Đọc tài liệu người dùng đưa và `docs/napoleon/codebase-report.md` (nếu có) trước. Ghi "tài liệu nói X, mình lấy X" rồi đi tiếp.
- Người dùng trả lời ngoài lựa chọn → nhận, không ép về lựa chọn.
- Chủ đề nào tài liệu tham khảo có ích → đọc file tương ứng trong `references/` rồi mới hỏi. Không đọc hết.

## Tám chủ đề, theo thứ tự

1. **Mục tiêu & phạm vi.** Sản phẩm làm gì, cho ai, v1 gồm gì, không gồm gì. Câu mẫu: "Trong tài liệu có N màn hình, v1 lấy hết hay nhóm nào trước?"
2. **Stack & ràng buộc.** Ngôn ngữ, framework, version tối thiểu, nền tảng, thư viện bắt buộc/cấm, backend có sẵn chưa. Dự án có sẵn → chạy `stack.py` trước và chỉ hỏi phần manifest không trả lời được (thư viện cấm, lý do chọn, có ghim SDK không). Câu mẫu: "Flutter version nào? Có package nào công ty bắt buộc dùng?"
3. **Kiến trúc tầng.** Tham khảo `references/layered-clean.md`. Câu mẫu: "Tách presentation / domain / data đầy đủ, hay bỏ domain cho app nhỏ?"
4. **Quản lý state.** Tham khảo `references/mvi.md`, `bloc.md`, `mvvm.md` theo stack. Câu mẫu: "Một Bloc cho mỗi màn hình, hay theo feature?"
4b. **Trạng thái dùng chung.** Liệt kê state nhiều màn hình cùng đọc (auth, premium, config, network, giỏ hàng…). Mỗi cái chốt **một owner** và cách phát ra (Flow/Stream/Listenable). Logic nghiệp vụ lặp ở nhiều nơi → chốt tên manager và chỗ đặt. Kết quả: hai bảng trong `architecture.md` ("Nguồn sự thật dùng chung", "Logic tái dùng"). Câu mẫu: "Premium có mấy nơi đọc? Ai là nơi duy nhất được ghi?"
5. **Ranh giới module.** Feature-first hay layer-first; module nào được import module nào. Kết quả thành bảng trong `module-map.md`. Câu mẫu: "Feature A được gọi thẳng repository của feature B không?"
6. **Toolchain.** Lệnh format, analyze, test, build. Hỏi từng lệnh nếu không hiển nhiên. Kết quả thành `toolchain.json`.
7. **Quy ước.** Không hỏi từng quy ước. Làm theo thứ tự:
   - Lấy khối **Chung** từ `templates/conventions.md` nguyên văn (đó là quan điểm của người dùng, áp mọi dự án).
   - Điền khối **Theo stack** từ `references/<stack>.md` mục "quy ước nên máy hoá" + "lỗi hay gặp".
   - In tóm tắt ≤ 12 dòng hai khối trên, rồi **một câu** (AskUserQuestion, multiSelect): "Bổ sung gì, bỏ gì?" với 4–6 bổ sung hay gặp theo stack (vd: cấm `print`/`Log.d` trong code chạy, bắt buộc `const`/`val`, i18n bắt buộc, giới hạn tham số hàm, viết tắt cho phép) + ô tự ghi. "Giữ nguyên" là xong.
   - Mỗi bổ sung máy hoá được → `rules.json`; không → "Không kiểm tự động" kèm cách nhận ra.

## Khi nào viết ADR
Quyết định có ≥ 2 lựa chọn hợp lý và đổi sau này tốn công → một ADR từ `templates/adr.md`, ≤ 25 dòng: bối cảnh, quyết định, hệ quả, lựa chọn bị bỏ. Đặt tên `ADR-001-<slug>.md`, tăng dần.

## Tài liệu nguồn
Đọc `docs/sources/prd/` (yêu cầu), `docs/sources/api/` (API docs), `docs/sources/design/` (Figma export, ảnh, mockup) trước khi hỏi. Người dùng đưa đường dẫn khác → đọc thêm, gợi ý copy vào `docs/sources/` để các phiên sau tìm thấy.

## Rút feature từ tài liệu
Mỗi dòng trong `features.md`: `- <tên-a-z0-9-> — <một câu mô tả> — nguồn: <docs/sources/prd/<file> trang/mục>`. Chỉ ghi feature có trong tài liệu hoặc người dùng nói. Không bịa feature "hiển nhiên".

## Sinh file
1. Điền `templates/project.md`, `architecture.md`, `module-map.md` → `.claude/instructions/`. `conventions.md`: khối Chung giữ nguyên văn, điền Theo stack + Bổ sung + Không kiểm tự động.
2. Điền `templates/rules.json` (phần chung đã có, thêm phần stack và bổ sung), `toolchain.json`. Chạy `conform.py` kiểm glob.
3. ADR → `.claude/instructions/decisions/`.
4. Khung thư mục rỗng theo kiến trúc: chỉ `mkdir` + `.gitkeep`. Không tạo file code.
5. `python3 .claude/tools/state.py init`; `features.md` → `docs/napoleon/features.md`.
6. `codegraph status`; chưa có → `codegraph init`.
7. Nói người dùng chạy `/setup-agents`.

## Cấm
- Không chọn sẵn stack/pattern rồi hỏi cho có.
- Không viết code trong `/start-build`.
- Không sinh `instructions/` trước khi đủ 8 chủ đề (1–4, 4b, 5–7) hoặc người dùng bảo "đủ rồi".

---
name: writing-conventions
description: Viết conventions.md và chuyển quy ước thành rule máy đọc trong rules.json. Dùng trong /start-build bước quy ước, trong /retro khi biến lỗi lặp thành rule, hoặc khi thêm quy ước mới.
---

# Viết quy ước

Một quy ước tốt: máy kiểm được, hoặc ghi rõ vì sao máy không kiểm được. Mỗi dòng quy ước phải mang nhãn `[rule: <id>]` (máy kiểm) hoặc `[tay]` (verifier xem tay) — `conform.py --coverage` chặn dòng không nhãn.

## Cấu trúc `conventions.md`
Theo `templates/conventions.md`: 4 khối (Chung · Theo stack · Bổ sung của bạn · Không kiểm tự động). Mỗi dòng một quy ước, kèm nhãn. Dòng dưới heading "Không kiểm tự động" không cần nhãn.

## Quy ước → loại rule

| Quy ước dạng | Loại rule | Ví dụ |
|---|---|---|
| "Tầng A không được import B" | `forbidden-import` `{in, forbid[]}` | domain cấm `package:flutter/**` |
| "Feature không import feature khác" | `no-sibling-import` `{base, allow[]}` | `base: lib/features`, `allow: ["shared"]` — một rule thay cho N² rule |
| "File loại X phải có class tên kết thúc Y" | `naming` `{in, class_regex}` | `*_bloc.dart` → `.*Bloc$` |
| "File loại X phải nằm trong thư mục Y" | `location` `{pattern, must_be_under}` | `*_repository_impl.dart` dưới `lib/**/data/` |
| "File không quá N dòng" | `max-lines` `{in, max}` | 400 |
| "Hàm không quá N dòng" | `max-function-lines` `{in, max}` | 40 |
| "Hàm không quá N tham số" | `max-params` `{in, max, constructors}` | 5; `constructors: false` bỏ qua constructor của data class |
| "Không hardcode màu/icon/chuỗi" | `forbidden-pattern` `{in, regex, allow[], message}` | `Color\(0x` trừ `lib/core/theme/**` |
| "Không comment quá nhiều" | `max-comment-ratio` `{in, max_ratio, min_lines}` | 0.15, bỏ qua file < 20 dòng |

Khoá `exclude` ở cấp cao nhất: glob code sinh (`*.g.dart`, `*.freezed.dart`, `lib/l10n/gen/**`) — `conform.py`, `audit.py`, `affected.py` đều dùng chung danh sách này.
Glob: fnmatch, `*` và `**` đều khớp qua `/`. Đường dẫn tương đối gốc dự án. `id` ngắn, kebab-case, nói điều cấm: `no-ui-in-domain`, `bloc-suffix`.

Kiểm rule mới chạy đúng:
```bash
python3 .claude/tools/conform.py              # phải 0 vi phạm, hoặc vi phạm đúng chỗ bạn muốn bắt
python3 .claude/tools/conform.py --coverage   # quy ước chưa gắn nhãn, nhãn trỏ rule không có, rule không khớp file nào
```
Rule mới mà `--coverage` báo "không khớp file nào" → glob sai. Sửa trước khi lưu.

## Không máy hoá được
Ghi vào mục "Không kiểm tự động" khi quy ước cần hiểu ngữ nghĩa: "owner duy nhất cho state dùng chung", "không nuốt lỗi", "comment chỉ vì sao". Mỗi dòng kèm cách verifier nhận ra vi phạm (một câu). Không ghi quy ước mơ hồ kiểu "code sạch".
Trước khi cho một quy ước vào đây, thử ba cách máy hoá: `forbidden-pattern` (regex), test trong repo (`test/project/*`), hoặc rule theo path. Chỉ khi cả ba không được thì ghi `[tay]`.

## Từ lỗi lặp (dùng trong /retro)
Thứ tự ưu tiên chặn: `rules.json` → test trong repo → hook → rule theo path → chữ trong `conventions.md`. Đi từ trên xuống, dừng ở mức đầu tiên làm được. Nguồn lỗi lặp: `state.py show --json` (nhãn `verify[].issues`), journal, `verify.md`.

## Cấm
- Không thêm quy ước không có lý do một dòng.
- Không thêm rule không chạy thử.
- Không để quy ước mới thiếu nhãn `[rule: …]`/`[tay]`.
- Không trùng quy ước đã có trong `architecture.md`; trỏ sang đó.

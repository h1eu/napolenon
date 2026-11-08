---
name: writing-conventions
description: Viết conventions.md và chuyển quy ước thành rule máy đọc trong rules.json. Dùng trong /start-build bước quy ước, trong /retro khi biến lỗi lặp thành rule, hoặc khi thêm quy ước mới.
---

# Viết quy ước

Một quy ước tốt: máy kiểm được, hoặc ghi rõ vì sao máy không kiểm được.

## Cấu trúc `conventions.md`
Theo `templates/conventions.md`, 6 mục: Đặt tên · Thư mục · Bắt buộc · Cấm · Không kiểm tự động · Định dạng & lint. Mỗi dòng một quy ước. Quy ước có rule máy đọc → gắn `[rules.json]`.

## Quy ước → loại rule

| Quy ước dạng | Loại rule | Ví dụ |
|---|---|---|
| "Tầng A không được import B" | `forbidden-import` `{in, forbid[]}` | domain cấm `package:flutter/**` |
| "File loại X phải có class tên kết thúc Y" | `naming` `{in, class_regex}` | `*_bloc.dart` → `.*Bloc$` |
| "File loại X phải nằm trong thư mục Y" | `location` `{pattern, must_be_under}` | `*_repository_impl.dart` dưới `lib/**/data/` |
| "File không quá N dòng" | `max-lines` `{in, max}` | 400 |
| "Không comment quá nhiều" | `max-comment-ratio` `{in, max_ratio, min_lines}` | 0.15, bỏ qua file < 20 dòng |

Glob: fnmatch, `*` và `**` đều khớp qua `/`. Đường dẫn tương đối gốc dự án.
`id` ngắn, kebab-case, nói điều cấm: `no-ui-in-domain`, `bloc-suffix`.

Kiểm rule mới chạy đúng:
```bash
python3 .claude/tools/conform.py
```
Rule mới mà 0 file quét → glob sai. Sửa trước khi lưu.

## Không máy hoá được
Ghi vào mục "Không kiểm tự động" khi quy ước cần hiểu ngữ nghĩa: "không gọi IO trong reducer", "side effect không nằm trong State", "mỗi use case một việc". Mỗi dòng kèm cách verifier nhận ra vi phạm (một câu). Không ghi quy ước mơ hồ kiểu "code sạch".

## Từ lỗi lặp (dùng trong /retro)
Thứ tự ưu tiên chặn: test → `rules.json` → hook → rule theo path → chữ trong `conventions.md`. Đi từ trên xuống, dừng ở mức đầu tiên làm được.

## Cấm
- Không thêm quy ước không có lý do một dòng.
- Không thêm rule không chạy thử.
- Không trùng quy ước đã có trong `architecture.md`; trỏ sang đó.

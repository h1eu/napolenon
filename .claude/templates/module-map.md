# Bản đồ module

Module = thư mục cấp <2> tính từ gốc (`audit.py --module-depth 2`). Đổi độ sâu nếu dự án tổ chức khác.

## Module
| Module | Vai trò | Entry point |
|---|---|---|
| `<lib/core>` | <dùng chung> | — |
| `<lib/features>` | <từng feature> | — |

## Phụ thuộc cho phép
Cạnh không có trong bảng này bị `audit.py` báo là vi phạm ranh giới.

| từ | đến | lý do |
|---|---|---|
| `<lib/features>` | `<lib/core>` | feature dùng tiện ích chung |
| `<lib>` | `<lib/features>` | main/router gọi màn hình |

## Cấm rõ
- `<lib/core>` → `<lib/features>`: core không biết feature
- feature A → feature B trực tiếp: qua `core/` hoặc route

## Dep ngoài quan trọng
| Gói | Dùng ở module | Ghi chú |
|---|---|---|
| `<package>` | `<module>` | <version pin, lý do> |

# Kiến trúc tầng / Clean Architecture

## Khi nào hợp
- App có logic nghiệp vụ đáng kể, sống > 1 năm, nhiều người sửa.
- Cần test logic không phụ thuộc UI và network.
- Không hợp: app demo, prototype, app 3–5 màn hình chỉ hiển thị dữ liệu. Khi đó bỏ tầng domain, giữ presentation + data.

## Ba tầng và hướng phụ thuộc
```
presentation  →  domain  ←  data
(UI, state)      (entity,    (repository impl,
                  use case,   datasource, DTO,
                  repository  mapper)
                  interface)
```
- domain không import gì từ presentation hay data, không import framework UI.
- data implement interface của domain.
- presentation chỉ gọi use case (hoặc repository interface nếu bỏ use case).

## Cấu trúc thư mục mẫu

Feature-first (khuyến nghị cho app > 5 feature):
```
lib/
  core/            # dùng chung: network, di, theme, error
  features/
    login/
      presentation/  domain/  data/
    profile/
      presentation/  domain/  data/
```

Layer-first (app nhỏ, ít feature):
```
lib/
  presentation/  domain/  data/  core/
```

## Ba quy ước nên máy hoá (rules.json)
1. `forbidden-import`: trong `**/domain/**` cấm `package:flutter/**`, `dio`, `http`, bất kỳ datasource.
2. `forbidden-import`: trong `**/presentation/**` cấm `**/data/**` (UI không gọi thẳng data).
3. `location`: `*_repository_impl.*` phải nằm dưới `**/data/`.

## Ba lỗi hay gặp
- Entity domain mang annotation JSON → domain lệ thuộc serialization. Tách DTO ở data, map sang entity.
- Use case một dòng gọi thẳng repository, không thêm gì → bỏ use case cho feature đó, gọi repository interface.
- `core/` phình thành bãi rác. Mỗi thứ trong `core/` phải có ≥ 2 feature dùng.

## Câu hỏi nên hỏi người dùng
- Có use case layer không, hay presentation gọi thẳng repository interface?
- Feature-first hay layer-first?
- Feature A có được dùng entity của feature B không? Nếu có, qua đâu (`core/` hay import thẳng)?

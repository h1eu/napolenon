# Navigation

## Nguyên tắc chung
- Route là dữ liệu (enum/sealed/type-safe), không phải chuỗi rải rác.
- Lệnh điều hướng phát từ tầng state (bloc/viewmodel) dưới dạng **effect**, UI thực hiện. Logic không biết framework navigation.
- Deep link và back-stack quyết định sớm; đổi sau tốn.

## Lựa chọn theo stack
| Stack | Phổ biến | Khi chọn |
|---|---|---|
| Flutter | `go_router` | Cần deep link, web, nested routes |
| Flutter | `auto_route` | Muốn codegen type-safe mạnh |
| Flutter | Navigator 1 tay | App nhỏ, không deep link |
| Android | Compose Navigation type-safe (kotlinx.serialization) | Mặc định |
| KMP | Decompose, Voyager | Decompose: back-stack rõ, lifecycle; Voyager: nhẹ |
| iOS | `NavigationStack` + path enum | SwiftUI thuần |

## Cấu trúc mẫu
```
lib/core/router/
  app_router.dart      # cấu hình route
  routes.dart          # tên route, tham số type-safe
lib/features/<x>/presentation/pages/
```

## Ba quy ước nên máy hoá
1. `location`: file cấu hình router (`*_router.dart`, `NavGraph.kt`, `AppRouter.swift`) phải nằm dưới `**/core/router/` hoặc `**/navigation/`.
2. `forbidden-import`: trong `**/bloc/**`, `**/*ViewModel.kt` cấm `go_router`, `androidx.navigation.**` (logic không điều hướng trực tiếp).
3. `forbidden-import`: trong `**/features/**` cấm import page của feature khác (`**/features/*/presentation/pages/**`); điều hướng qua route.

## Ba lỗi hay gặp
- Truyền object lớn qua route → mất khi restore. Truyền id, load lại.
- Điều hướng trong `build`/`LaunchedEffect` không guard → lặp vô hạn.
- Nhiều nguồn sự thật cho back-stack (router + state) → lệch. Một nguồn.

## Câu hỏi nên hỏi
- Có deep link / universal link không?
- Có web target không (ảnh hưởng chọn router Flutter)?
- Tab bar + nested stack hay stack đơn?

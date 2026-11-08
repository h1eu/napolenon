# BLoC / Cubit (Flutter)

## Khi nào hợp
- Flutter, team quen `flutter_bloc`, cần tách logic khỏi widget và test logic bằng `bloc_test`.
- Cubit cho màn hình đơn giản (vài method đổi state). Bloc khi cần event có thể transform (debounce, throttle, sequential).
- Không hợp: app nhỏ 2–3 màn hình → `ChangeNotifier`/Riverpod đơn giản hơn.

## Luồng
```
Widget --add(Event)--> Bloc --emit--> State --BlocBuilder--> Widget
Widget --method()--> Cubit --emit--> State
```
- State: sealed class hoặc một class với `status` enum + copyWith. Chọn một cách cho cả dự án.
- Side effect (snackbar, navigation): `BlocListener`, không trong `build`.

## Cấu trúc mẫu (feature-first + clean)
```
lib/
  core/
  features/login/
    presentation/
      bloc/login_bloc.dart  login_event.dart  login_state.dart
      pages/login_page.dart
      widgets/
    domain/   entities/  repositories/  usecases/
    data/     models/  datasources/  repositories/
```

## Ba quy ước nên máy hoá
1. `naming`: `*_bloc.dart` chứa class kết thúc `Bloc`; `*_cubit.dart` kết thúc `Cubit`.
2. `location`: `*_bloc.dart`, `*_cubit.dart` phải nằm dưới `**/presentation/`.
3. `forbidden-import`: trong `**/presentation/bloc/**` cấm `package:flutter/material.dart` (bloc không biết widget).

## Ba lỗi hay gặp
- `BlocProvider` tạo ở quá cao → bloc sống suốt app, giữ state cũ. Tạo ở route của feature.
- Gọi `context.read` trong `initState` trước khi provider sẵn sàng. Dùng `BlocProvider(create:)` + event `started`.
- Một state class khổng lồ dùng chung cho nhiều màn hình. Mỗi bloc một state.

## Câu hỏi nên hỏi
- Sealed state hay `status` enum + copyWith?
- DI: `get_it` + `injectable`, hay `RepositoryProvider`?
- Navigation: `go_router` hay Navigator 2 tự viết?
- Codegen: `freezed` cho state/event? Nếu có, lệnh build_runner vào `toolchain.json`.

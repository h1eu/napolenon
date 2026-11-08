# Dependency Injection

## Khi nào cần DI framework
- > 10 class cần ghép; cần đổi implementation khi test (fake repository, fake API).
- App nhỏ: constructor injection tay + một file `composition root` là đủ. Đừng cài framework khi chưa đau.

## Lựa chọn theo stack
| Stack | Phổ biến | Ghi chú |
|---|---|---|
| Flutter | `get_it` (+ `injectable` codegen), Riverpod providers, `RepositoryProvider` | `get_it` đơn giản; `injectable` thêm build_runner |
| Android | Hilt | Chuẩn Google, compile-time, cần KSP/kapt |
| KMP | Koin | Chạy được common; runtime, lỗi lộ khi chạy |
| iOS | Tay (init injection), Factory, Swinject | SwiftUI thường dùng `@Environment` cho dependency nhẹ |

## Quy tắc chung
- Inject interface (abstract class / protocol), không inject implementation.
- Đăng ký ở **một chỗ** (composition root / module). Không `register` rải rác.
- Scope: singleton cho client mạng, DB; factory cho ViewModel/Bloc; không singleton cho thứ giữ state màn hình.
- Test: composition root riêng cho test thay bằng fake, không mock từng chỗ.

## Ba quy ước nên máy hoá
1. `forbidden-import`: ngoài `**/di/**` cấm import `get_it`/`koin`/`dagger.hilt.components` để tránh service-locator rải rác.
2. `location`: `*_module.dart`, `*Module.kt` phải nằm dưới `**/di/`.
3. `naming`: file trong `di/` kết thúc `Module`/`_module`.

## Ba lỗi hay gặp
- `GetIt.I<Foo>()` gọi trong widget `build` → không test được. Truyền qua constructor/provider.
- Đăng ký singleton cho ViewModel → state dính giữa màn hình.
- Vòng phụ thuộc A→B→A qua DI → crash lúc chạy. `audit.py` bắt cycle import giúp phát hiện sớm.

## Câu hỏi nên hỏi
- Framework nào, hay inject tay?
- Codegen có chấp nhận không (ảnh hưởng toolchain)?
- Composition root đặt ở đâu?

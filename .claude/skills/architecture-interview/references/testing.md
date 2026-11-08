# Testing

## Tháp test cho app mobile
```
   E2E / integration   ít, chậm, chạy ở CI nightly hoặc trước release
   Widget / UI test    vừa, cho màn hình quan trọng
   Unit test           nhiều, nhanh, chạy ở bước verify của mỗi feature
```
- Unit: reducer, use case, repository với fake datasource, mapper.
- Widget/Compose/SwiftUI test: màn hình có logic hiển thị theo state.
- E2E: 3–5 luồng chính (login, luồng tiền, luồng chính của app).

## Lệnh theo stack (điền vào toolchain.json)
| Stack | format | analyze | test | build |
|---|---|---|---|---|
| Flutter | `dart format {file}` | `dart analyze {file}` | `flutter test` | `flutter build apk --debug` |
| Android | `./gradlew ktlintFormat` hoặc `ktlint -F {file}` | `./gradlew detekt` | `./gradlew testDebugUnitTest` | `./gradlew assembleDebug` |
| KMP | `ktlint -F {file}` | `./gradlew detekt` | `./gradlew allTests` | `./gradlew build` |
| iOS | `swiftformat {file}` | `swiftlint lint {file}` | `xcodebuild test -scheme X -destination '...'` | `xcodebuild build -scheme X` |

`{file}` được check.sh thay bằng đường dẫn file vừa sửa. Lệnh không hỗ trợ từng file → bỏ `{file}`, chạy cả dự án (chậm hơn; cân nhắc chỉ để `format`).

## Quy ước
- Test nằm cạnh cấu trúc source: `test/features/login/...` phản chiếu `lib/features/login/...`.
- Tên test nói hành vi: `emits failure when password empty`, không `test1`.
- Fake thay vì mock khi được; mock chỉ ở biên (network, platform).
- Mỗi feature `done` phải có ≥ 1 unit test cho logic chính; ghi trong `verify.md`.

## Ba quy ước nên máy hoá
1. `location`: `*_test.dart` phải nằm dưới `test/`; `*Test.kt` dưới `src/test/` hoặc `src/commonTest/`.
2. `forbidden-import`: trong `lib/**` cấm `package:flutter_test/**`, `package:mockito/**` (test lib không vào code chạy).
3. `max-lines`: file test ≤ 500 dòng.

## Ba lỗi hay gặp
- Test gọi API thật → chậm, flaky. Fake datasource.
- Test phụ thuộc thứ tự chạy (singleton giữ state). Reset DI trong `setUp`.
- Không test reducer vì "đơn giản" → lỗi state lặng lẽ. Reducer là chỗ rẻ nhất để test.

## Câu hỏi nên hỏi
- Có CI không? Lệnh test chạy ở đâu?
- Có golden/screenshot test không?
- Mức bao phủ tối thiểu team chấp nhận (nếu có)?

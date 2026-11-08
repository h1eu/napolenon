# Quy ước

Bốn khối. Dòng có `[rules.json]` được `conform.py` kiểm tự động; còn lại kiểm ở bước verify và bởi verifier.
Khối **Chung** là của napoleon, áp mọi dự án — sửa ở repo napoleon (`templates/conventions.md`), không sửa ở đây.

## Chung

### Tái sử dụng
- Trước khi tạo hàm/widget/class mới: `codegraph_search` tên gần giống, xem `core/`. Có rồi → dùng hoặc mở rộng. Không có bản thứ hai của cùng một việc.
- Thứ dùng ở ≥ 2 feature mới được vào `core/`. Dùng ở 1 feature → nằm trong feature đó.
- Logic nghiệp vụ tái dùng → class riêng tên theo việc (`XxxManager`/`XxxRuntime`), inject qua DI, có test riêng, nằm ngoài `presentation/` `[rules.json]`. Một class một việc; > 300 dòng → tách.

### Một nguồn sự thật
- Trạng thái dùng ở ≥ 2 nơi → một owner duy nhất phát ra (Flow/Stream/Listenable); nơi khác chỉ quan sát, không giữ bản sao rồi tự đồng bộ. Owner ghi ở `architecture.md#Nguồn sự thật dùng chung`.
- Chỉ owner được ghi. Nơi khác muốn đổi → gọi owner.

### Comment
- Comment chỉ nói *vì sao* (quyết định, ràng buộc, lý do không làm cách hiển nhiên). Không banner, không docstring lặp tên hàm, không mô tả code hiển nhiên. Tỉ lệ comment ≤ 15% dòng `[rules.json]`.
- TODO phải kèm tên feature hoặc ADR: `// TODO(login): …`.

### Kích thước và đặt tên
- File ≤ 400 dòng `[rules.json]`. Hàm làm một việc; > 40 dòng là dấu hiệu tách.
- Tên nói việc, không nói kiểu: `loadUser`, không `getUserData2`. Boolean đọc như câu hỏi: `isReady`, `hasPremium`.
- Không viết tắt ngoài danh sách dự án cho phép (ghi ở "Bổ sung của bạn").

### Lỗi và null
- Lỗi từ data được map sang kiểu lỗi của domain trước khi lên presentation; UI không bắt exception thô.
- Không null-assertion (`!`, `!!`) trừ khi có comment "vì sao" ngay trên dòng đó.
- Không nuốt lỗi im lặng (`catch {}` rỗng, `runCatching` không xử lý).

### Hardcode
- Chuỗi hiển thị, màu, kích thước, URL, key → qua hằng/theme/config/i18n của dự án. Không literal trong UI và logic.

### Test
- Mọi state holder (bloc/store/viewmodel/manager) có unit test cho hành vi chính. Fake thay vì mock khi được.
- Sửa bug → test tái hiện trước, sửa sau.
- Không sửa test để xanh.

### Thiết kế và hỏi
- `architecture.md`, `module-map.md`, design UI nguồn là luật. Lệch → hỏi → ADR. Không tự thêm bớt thành phần, không tự đổi màu/spacing.
- Mơ hồ → một câu hỏi trắc nghiệm, dừng chờ. Không chọn hộ.
- API thư viện ngoài → tra context7, pin version.

## Theo stack
<Điền từ `references/<stack>.md` theo stack đã chốt ở /start-build. Ví dụ Flutter + BLoC:>
- `*_bloc.dart` chứa class kết thúc `Bloc`; `*_cubit.dart` kết thúc `Cubit` `[rules.json]`
- bloc/cubit nằm dưới `**/presentation/` `[rules.json]`
- `**/presentation/bloc/**` không import `package:flutter/material.dart` `[rules.json]`
- `**/domain/**` không import Flutter, dio, http `[rules.json]`
- State: <sealed / status enum + copyWith — một cách cho cả dự án>
- Side effect one-shot qua `BlocListener`, không trong `build`

## Bổ sung của bạn
<Trả lời ở /start-build chủ đề 7. Giữ nguyên nếu không có.>
- <quy ước riêng dự án 1>
- Viết tắt cho phép: <vd: dto, vm, ui>

## Không kiểm tự động
Verifier phải xem tay. Mỗi dòng kèm cách nhận ra vi phạm.
- Owner duy nhất cho state dùng chung — nhận ra: hai nơi cùng giữ biến cùng nghĩa, hoặc có hàm "sync" chép từ nơi này sang nơi kia.
- Comment chỉ "vì sao" — nhận ra: comment đọc được từ tên hàm/biến.
- Không nuốt lỗi — nhận ra: `catch` không log, không map, không rethrow.
- Hardcode — nhận ra: chuỗi tiếng Việt/Anh, mã màu, số px trong file UI hoặc logic.
- Hàm > 40 dòng, class manager > 300 dòng.
- <thêm từ "Bổ sung của bạn" nếu không máy hoá được>

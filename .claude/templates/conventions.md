# Quy ước

Bốn khối. Mỗi dòng quy ước mang **một nhãn**: `[rule: <id>]` = `conform.py` kiểm tự động, `[tay]` = verifier xem tay.
`python3 .claude/tools/conform.py --coverage` chặn dòng thiếu nhãn và nhãn trỏ rule không tồn tại.
Khối **Chung** là của napoleon, áp mọi dự án — sửa ở repo napoleon (`templates/conventions.md`), không sửa ở đây.

## Chung

### Tái sử dụng
- Trước khi tạo hàm/widget/class mới: `codegraph_search` tên gần giống, xem `core/`. Có rồi → dùng hoặc mở rộng. Không có bản thứ hai của cùng một việc. `[tay]`
- Thứ dùng ở ≥ 2 feature mới được vào `core/`. Dùng ở 1 feature → nằm trong feature đó. `[tay]`
- Feature không import feature khác; dùng chung thì lên `core/`. `[rule: no-cross-feature]`
- Logic nghiệp vụ tái dùng → class riêng tên theo việc (`XxxManager`/`XxxRuntime`), inject qua DI, có test riêng, nằm ngoài `presentation/`. `[rule: manager-suffix, manager-not-in-presentation]`

### Một nguồn sự thật
- Trạng thái dùng ở ≥ 2 nơi → một owner duy nhất phát ra (Flow/Stream/Listenable); nơi khác chỉ quan sát, không giữ bản sao rồi tự đồng bộ. Owner ghi ở `architecture.md#Nguồn sự thật dùng chung`. `[tay]`
- Chỉ owner được ghi. Nơi khác muốn đổi → gọi owner. `[tay]`

### Comment
- Comment chỉ nói *vì sao* (quyết định, ràng buộc, lý do không làm cách hiển nhiên). Không banner, không docstring lặp tên hàm. `[rule: few-comments]`
- TODO phải kèm tên feature hoặc ADR: `// TODO(login): …`. `[tay]`

### Kích thước và đặt tên
- File ≤ 400 dòng. `[rule: max-400-lines]`
- Hàm làm một việc, ≤ 40 dòng. `[rule: max-function-lines]`
- Hàm ≤ 5 tham số; nhiều hơn → gói thành object/params. `[rule: max-params]`
- Tên nói việc, không nói kiểu: `loadUser`, không `getUserData2`. Boolean đọc như câu hỏi: `isReady`. `[tay]`
- Không viết tắt ngoài danh sách dự án cho phép (ghi ở "Bổ sung của bạn"). `[tay]`

### Lỗi và null
- Lỗi từ data được map sang kiểu lỗi của domain trước khi lên presentation; UI không bắt exception thô. `[tay]`
- Không null-assertion (`!`, `!!`) trừ khi có comment "vì sao" ngay trên dòng đó. `[tay]`
- Không nuốt lỗi im lặng (`catch {}` rỗng, `runCatching` không xử lý). `[tay]`

### Hardcode
- Màu viết tại chỗ → cấm; lấy từ theme. `[rule: no-hardcoded-color]`
- Chuỗi hiển thị, kích thước, URL, key → qua hằng/theme/config/i18n của dự án. `[tay]`

### Tầng
- `domain/` không import UI framework, HTTP, DB. `[rule: no-ui-in-domain]`
- `presentation/` không import `data/`. `[rule: no-data-from-presentation]`
- `*_repository_impl.dart` nằm trong `data/`. `[rule: repo-impl-in-data]`
- State holder (`*_bloc.dart`) đặt tên theo hậu tố. `[rule: state-holder-suffix]`

### Test
- Mọi state holder (bloc/store/viewmodel/manager) có unit test cho hành vi chính. Fake thay vì mock khi được. `[tay]`
- Sửa bug → test tái hiện trước, sửa sau. `[tay]`
- Không sửa test để xanh. `[tay]`

### Thiết kế và hỏi
- `architecture.md`, `module-map.md`, design UI nguồn là luật. Lệch → hỏi → ADR; việc ADR hẹn làm sau → `state.py followup add`. `[tay]`
- Mơ hồ → một câu hỏi trắc nghiệm, dừng chờ. Không chọn hộ. `[tay]`
- API thư viện ngoài → tra context7, pin version. `[tay]`

## Theo stack
<Điền từ `references/<stack>.md` theo stack đã chốt ở /start-build. Mỗi dòng một nhãn. Ví dụ Flutter + BLoC:>
- `*_cubit.dart` chứa class kết thúc `Cubit` `[rule: cubit-suffix]`
- bloc/cubit nằm dưới `**/presentation/` `[rule: bloc-in-presentation]`
- `**/presentation/bloc/**` không import `package:flutter/material.dart` `[rule: bloc-no-widgets]`
- Icon chỉ từ bộ icon đã chốt, không `Icons.` `[rule: no-material-icons]`
- State: <sealed / status enum + copyWith — một cách cho cả dự án> `[tay]`

## Bổ sung của bạn
<Trả lời ở /start-build chủ đề 7. Giữ nguyên nếu không có. Mỗi dòng một nhãn.>
- <quy ước riêng dự án 1> `[tay]`
- Viết tắt cho phép: <vd: dto, vm, ui> `[tay]`

## Không kiểm tự động
Verifier phải xem tay. Mỗi dòng kèm cách nhận ra vi phạm. (Dòng ở khối này không cần nhãn.)
- Owner duy nhất cho state dùng chung — nhận ra: hai nơi cùng giữ biến cùng nghĩa, hoặc có hàm "sync" chép từ nơi này sang nơi kia.
- Comment chỉ "vì sao" — nhận ra: comment đọc được từ tên hàm/biến.
- Không nuốt lỗi — nhận ra: `catch` không log, không map, không rethrow.
- Chuỗi hiển thị viết thẳng trong UI — nhận ra: literal trong widget/màn hình thay vì khoá i18n.
- <thêm từ "Bổ sung của bạn" nếu không máy hoá được>

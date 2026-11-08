# Kiến trúc

## Tầng
```
<sơ đồ tầng và hướng phụ thuộc, vd:>
presentation → domain ← data
```
- presentation: <gồm gì, không được làm gì>
- domain: <gồm gì, không import gì>
- data: <gồm gì>
- core: <dùng chung gì; điều kiện để một thứ vào core>

## Quản lý state
- Pattern: <BLoC / MVI / MVVM>
- Một <bloc/store/viewmodel> cho mỗi <màn hình / feature>
- State: <sealed / status enum + copyWith / data class bất biến>
- Side effect one-shot: <cách làm>

## Nguồn sự thật dùng chung
Trạng thái nhiều màn hình cùng đọc. Mỗi dòng một owner duy nhất; nơi khác chỉ quan sát, không giữ bản sao.

| Trạng thái | Owner (class, path) | Phát ra qua | Ai được ghi |
|---|---|---|---|
| <auth/session> | `<AuthManager, core/auth/>` | `<StateFlow<AuthState>>` | `<chỉ AuthManager>` |
| <premium/entitlement> | | | |
| <remote config / app status> | | | |
| <network status> | | | |

## Logic tái dùng (manager)
| Class | Việc duy nhất | Nằm ở | Test |
|---|---|---|---|
| `<XxxManager>` | <một câu> | `<core/...>` | `<test/...>` |

## Luồng dữ liệu một feature điển hình
1. <UI phát event/intent>
2. <state holder gọi use case / repository>
3. <repository gọi datasource, map DTO → entity>
4. <emit state mới>

## Cấu trúc thư mục
```
<cây thư mục thật của dự án này>
```

## DI
- <framework hay tay>, composition root ở `<path>`
- Scope: <singleton cho gì, factory cho gì>

## Navigation
- <thư viện>, cấu hình ở `<path>`, route type-safe tại `<path>`
- Điều hướng phát từ <effect/listener>, không từ logic

## Error handling
- <Either/Result/exception>, map lỗi ở tầng <nào>, UI hiển thị theo <state nào>

## Xem thêm
- `decisions/` cho lý do từng lựa chọn

# MVI (Model–View–Intent)

## Khi nào hợp
- KMP / Compose Multiplatform, Android Compose, nơi state bất biến và luồng một chiều hợp với recomposition.
- Màn hình có nhiều trạng thái phụ thuộc lẫn nhau; cần replay/log mọi thay đổi.
- Không hợp: màn hình tĩnh, form một trường. Khi đó ViewModel + StateFlow thường là đủ.

## Luồng
```
View --Intent--> Store/ViewModel --reduce--> State --render--> View
                       |
                    SideEffect (navigation, toast) → kênh riêng, one-shot
```
- State: một data class bất biến cho cả màn hình.
- Intent: sealed interface, mỗi hành động người dùng một biến thể.
- Reducer: hàm thuần `(State, Result) -> State`. Không gọi IO trong reducer.
- Side effect: `Channel`/`SharedFlow`, không nằm trong State.

## Cấu trúc mẫu (KMP, feature-first)
```
shared/src/commonMain/kotlin/<pkg>/
  features/login/
    LoginStore.kt        # state, intent, reducer, effect
    LoginContract.kt     # State, Intent, Effect
    domain/  data/
composeApp/src/commonMain/kotlin/<pkg>/
  features/login/LoginScreen.kt
```

## Ba quy ước nên máy hoá
1. `naming`: file `*Store.kt` hoặc `*ViewModel.kt` phải có class kết thúc `Store`/`ViewModel`.
2. `forbidden-import`: trong `**/features/**/*Contract.kt` cấm `androidx.compose.**` (contract không biết UI).
3. `forbidden-import`: trong `shared/**` cấm `android.**`, `java.**` ngoài allowlist (giữ common thuần).

## Ba lỗi hay gặp
- Nhét navigation vào State → màn hình điều hướng lại khi recompose. Dùng Effect.
- State chứa `MutableList` → recomposition không nhận ra thay đổi. Dùng `List` + copy.
- Store làm luôn gọi API → không test được reducer. Tách Executor/UseCase.

## Câu hỏi nên hỏi
- Thư viện: tự viết Store, hay MVIKotlin / Orbit / Decompose?
- Một Store cho mỗi màn hình hay cho mỗi feature nhiều màn hình?
- Navigation ở đâu: Decompose / Voyager / Compose Navigation?

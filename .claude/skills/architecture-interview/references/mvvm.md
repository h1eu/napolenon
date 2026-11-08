# MVVM (Android Compose / SwiftUI)

## Khi nào hợp
- Android native Kotlin + Compose + `ViewModel` + `StateFlow`; SwiftUI + `@Observable`/`ObservableObject`.
- Mặc định của Google và Apple, tài liệu nhiều, onboarding nhanh.
- Không hợp khi cần replay/log mọi thay đổi state → xem `mvi.md`.

## Luồng
```
View --gọi method--> ViewModel --cập nhật--> UiState (StateFlow) --collect--> View
                          |
                       UseCase / Repository
```
- Một `UiState` data class cho mỗi màn hình, expose qua `StateFlow<UiState>`.
- Event one-shot (navigation, snackbar): `Channel` hoặc field trong state kèm `consumed()`; chọn một cách.
- ViewModel không giữ `Context`, không import Compose.

## Cấu trúc mẫu (Android, feature-first)
```
app/src/main/java/<pkg>/
  core/  di/  network/  ui/theme/
  feature/login/
    LoginScreen.kt      # composable
    LoginViewModel.kt
    LoginUiState.kt
    domain/  data/
```

## Ba quy ước nên máy hoá
1. `forbidden-import`: trong `**/*ViewModel.kt` cấm `androidx.compose.**` và `android.content.Context`.
2. `naming`: `*ViewModel.kt` chứa class kết thúc `ViewModel`.
3. `forbidden-import`: trong `**/domain/**` cấm `androidx.**`, `android.**`, `retrofit2.**`, `room.**`.

## Ba lỗi hay gặp
- Nhiều `StateFlow` rời rạc trong một ViewModel → UI nhận state không nhất quán. Gộp thành một `UiState`.
- `viewModelScope.launch` không bắt exception → crash. Dùng `runCatching`/`CoroutineExceptionHandler` thống nhất.
- Composable lấy ViewModel ở sâu bằng `hiltViewModel()` nhiều lần → nhiều instance. Lấy ở màn hình gốc, truyền state xuống.

## Câu hỏi nên hỏi
- DI: Hilt hay Koin?
- Network: Retrofit hay Ktor? Local: Room hay SQLDelight?
- Có use case layer không?
- Navigation: Compose Navigation type-safe hay thư viện khác?

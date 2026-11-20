---
description: "Đo và cải thiện độ mượt của một màn hoặc flow trên máy Android thật: khai ca, đo baseline, tìm nguyên nhân, sửa từng thứ, đo lại."
argument-hint: <màn hoặc flow>
---
Đối số: $ARGUMENTS. Mọi con số lấy nguyên từ output `perf.py`, không gõ tay, không ước lượng.

1. **Điều kiện.** `adb devices` có đúng một máy thật; bản release đã cài và đang mở đúng màn. Thiếu gì → nói thiếu gì rồi dừng. Không đo emulator hay bản debug để báo số.
2. **Ca đo.** `python3 .claude/tools/perf.py --list`. Màn này chưa có ca → hỏi người dùng một câu: thao tác nào đang giật (vuốt, cuộn, mở, chuyển tab). Viết ca vào `toolchain.json` mục `perf.cases`: `steps` và `reset` là lệnh `input …`, toạ độ tính từ `adb shell wm size`. Mỗi ca ≤ ~2 s (bảng chỉ giữ 127 khung); flow dài → tách `<flow>-1`, `<flow>-2`. Chưa có `perf.package` hoặc `perf.install` (lệnh build + cài bản release) → hỏi rồi ghi.
3. **Đo mốc.** `python3 .claude/tools/perf.py <ca>`. Exit 2 → sửa theo thông báo của tool (tràn → chia ca, không thấy layer → mở app) rồi đo lại; không đi tiếp với số thiếu. Chưa có baseline → chạy lại với `--save-baseline`.
4. **Ngân sách.** Ca chưa có ngưỡng → hỏi người dùng một câu (gợi ý `max_dropped_pct`), ghi vào ca. Đã đạt và `đứng hình 0` → in dòng kết quả, dừng ở đây.
5. **Tìm nguyên nhân.** Tìm file gốc của màn bằng `codegraph_search`, gọi agent `perf-hunter` với prompt đúng 3 dòng:
   ```
   Màn: <file hoặc symbol gốc>
   Số đo: <dán nguyên output perf.py của ca>
   Săn theo thứ tự trong agent. Không sửa file.
   ```
6. **Sửa từng thứ một.** Lấy nghi phạm đứng đầu → sửa → chạy `perf.install` → `perf.py <ca>`. Tool báo "tốt hơn" → giữ, commit riêng thay đổi đó. "trong nhiễu" hoặc "tệ hơn" → hoàn lại đúng thay đổi đó, sang nghi phạm kế. Không gộp hai sửa vào một lần đo. Sửa phải đổi kiến trúc, lệch design hoặc thêm thư viện → dừng, hỏi.
7. **Kết thúc.** Đạt ngân sách → `perf.py <ca> --save-baseline` làm mốc mới. Ba nghi phạm liên tiếp không cải thiện → dừng, báo cần trace thật (Perfetto/DevTools) và nêu mục "Không đọc được từ code" của agent. In: ca, dòng kết quả trước, dòng kết quả sau, thay đổi nào được giữ, nghi phạm nào chưa thử.

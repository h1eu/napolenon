# Spec: <tên feature>

Ngày: <YYYY-MM-DD> · Brief: `brief.md` · Nguồn: <docs/sources/prd/<file> trang/mục> · Trạng thái: <nháp / duyệt>

## Mục đích
<1–2 câu: người dùng làm được gì sau feature này.>

## Yêu cầu
Mỗi dòng một yêu cầu kiểm được. Verifier đối chiếu từng số.
1. <Khi … thì …>
2. <…>
3. <…>

## Không làm trong feature này
- <…>

## Design nguồn
- <docs/sources/design/<file> màn hình X / link Figma / "không có — UI theo component sẵn trong core/">
- Thành phần: <liệt kê component dùng lại từ core/, component mới phải tạo (kèm lý do không dùng lại được)>

## Màn hình / luồng
<mô tả ngắn hoặc trỏ tới ảnh/tài liệu>

## Dữ liệu & API
- Endpoint / bảng: <… — nguồn docs/sources/api/<file>>
- Thư viện ngoài dùng: <tên@version — đã tra context7: có/chưa>

## Lỗi & trạng thái rỗng
- <mạng lỗi → …>
- <không có dữ liệu → …>

## Kịch bản lần hai
Mỗi dòng là một yêu cầu có test, đánh số nối tiếp mục "Yêu cầu". Không áp dụng thì ghi "không áp dụng — vì …".
- Gọi lại khi lần trước chưa về (bấm hai lần, kéo làm mới khi đang tải) → <…>
- Mất mạng rồi có lại → <màn hình tự hồi phục hay cần bấm gì>
- Xung đột / lỗi rồi thử lại → <thay đổi chưa gửi của người dùng đi đâu>
- Rời màn hình khi request còn bay → <…>
- Tài nguyên dùng chung với feature khác (singleton, cache, khoá) → <feature nào, ai thắng>

## Câu hỏi đã chốt
- <câu hỏi> → <trả lời của người dùng>

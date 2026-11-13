---
description: "Sinh/cập nhật docs/napoleon/stack.md: nền tảng, SDK, thư viện và phiên bản đang dùng, đọc từ manifest + lockfile. Chạy khi thêm/nâng thư viện."
---
1. `python3 .claude/tools/stack.py` → ghi `docs/napoleon/stack.md`. Chỉ khối giữa hai dấu `napoleon:stack` được sinh lại; mục "Ghi chú" bên dưới giữ nguyên.
2. In dòng kết quả của tool. Không sửa tay số liệu trong khối sinh; muốn thêm thông tin → sửa `stack.py`.
3. Có thư viện mới mà cột "Vai trò" trùng một thư viện đã có (hai thư viện HTTP, hai state management…) → báo người dùng một dòng, hỏi giữ cái nào; quyết định ghi vào mục "Ghi chú" hoặc ADR.
4. Flutter chưa ghim phiên bản (nguồn ghi "chưa ghim bằng .fvmrc") → gợi ý một dòng: ghim bằng `.fvmrc` để cả nhóm và agent dùng cùng một SDK.

---
name: project-new-feature
description: "Tạo một feature mới đúng kiến trúc của dự án này: file nào ở đâu, thứ tự tạo, codegen, test tối thiểu. Dùng ở bước build của /feature khi bắt đầu feature mới."
---
<!-- napoleon:generated -->

# Tạo feature mới trong dự án này

Kiến trúc: <một dòng>. Chi tiết: `.claude/instructions/architecture.md`.

## Thứ tự tạo
1. `<path>/features/<tên>/` với các thư mục: <liệt kê>
2. domain: <entity, repository interface, use case — tên file theo conventions>
3. data: <model/DTO, datasource, repository impl, mapper>
4. presentation: <state holder, state/event, page, widgets>
5. Đăng ký DI tại `<path>`
6. Thêm route tại `<path>`
7. Codegen (nếu có): `<lệnh từ toolchain.json>`

## Test tối thiểu trước khi `task done`
- <state holder>: <N> test hành vi chính
- repository impl: test với fake datasource
- Chạy: `<lệnh test>`

## Kiểm sau mỗi task
```bash
python3 .claude/tools/conform.py
```

## Cấm trong dự án này
- <từ conventions.md mục Cấm, chỉ những điều hay vi phạm khi tạo feature>

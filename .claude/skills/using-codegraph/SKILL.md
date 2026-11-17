---
name: using-codegraph
description: "Truy vấn code bằng codegraph MCP thay grep: tool nào cho câu hỏi nào, kiểm tra index, xử lý lỗi thường gặp. Dùng khi cần tìm symbol, file, ai gọi ai, hoặc ảnh hưởng khi sửa."
---

# Dùng codegraph

Index nằm ở `.codegraph/codegraph.db`, tự sync khi file đổi (daemon). MCP server khai báo trong `.mcp.json`; codegraph 1.4 bật sẵn: `explore, search, node, callers, callees, impact, context, files, status`.

## Câu hỏi → tool

| Câu hỏi | Tool |
|---|---|
| "Module X làm gì, gồm những gì?" | `codegraph_explore` với đường dẫn thư mục hoặc câu hỏi tự nhiên |
| "Có class/hàm nào tên gần giống Y?" | `codegraph_search` |
| "Chi tiết symbol Y: định nghĩa ở đâu, signature?" | `codegraph_node` |
| "Ai gọi Y?" | `codegraph_callers` |
| "Y gọi những gì?" | `codegraph_callees` |
| "Sửa Y thì ảnh hưởng tới đâu?" (dùng ở bước plan, mỗi task) | `codegraph_impact` |
| "Gom context để làm task Z" (một lần đầu bước build) | `codegraph_context` |
| "Index còn mới không?" | `codegraph_status` |
| "Chuỗi 'Đăng nhập thất bại' ở file nào?" | **Grep** — chuỗi văn bản thuần |
| "Dòng nào trong file X nhắc tới Y?" | **Grep** trong đúng file đó |
| "Chỗ nào gọi API thư viện ngoài (`showModalBottomSheet`…)?" | **Grep** — index chỉ có symbol của dự án |

Một câu trả lời cần nhiều bước → bắt đầu bằng `explore`, rồi đào sâu bằng `node`/`callers`. Không grep tên class để tìm định nghĩa.

## Tool chưa thấy, hoặc đang ở Bash
- Tool `mcp__codegraph__*` chưa có trong danh sách → nạp một lần: ToolSearch `select:mcp__codegraph__codegraph_search,mcp__codegraph__codegraph_callers,mcp__codegraph__codegraph_impact`.
- Chỉ cần biết symbol định nghĩa ở đâu → Bash `codegraph query <tên>`.

## Cổng chặn grep
`guard.py` từ chối `grep -r`/`rg`/tool Grep khi mẫu tìm là đúng một tên symbol có trong index và phạm vi là thư mục code. Bị chặn → dùng lệnh ghi trong lời chặn. Cần tìm tên đó như văn bản (comment, chuỗi, file chưa index) → Bash với `NAPOLEON_ALLOW_GREP=1` đặt trước lệnh grep.

## Trước bước plan
```bash
codegraph status
```
- Chưa có index → `codegraph init` (một lần cho mỗi repo).
- "stale"/có file chưa index → `codegraph sync`.
- Báo DB bị khoá → `codegraph unlock` rồi thử lại.

## Sau khi sửa nhiều file
Hook Stop đã chạy `codegraph sync`. Nếu kết quả truy vấn có vẻ cũ: `codegraph sync` rồi hỏi lại.

## Khi codegraph không có
`command -v codegraph` rỗng → báo người dùng một dòng với lệnh cài (trong README), rồi tạm dùng `audit.py --source scan` cho phụ thuộc và Glob/Grep cho tìm file. Không im lặng chuyển sang grep.

## Cấm
- Không đoán vị trí file từ tên. Hỏi codegraph.
- Không sửa `.codegraph/` tay.
- Không commit `.codegraph/`.

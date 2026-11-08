---
name: verifying
description: "Verify ba lớp cho một feature: máy (toolchain, conform, audit) → agent verifier độc lập → người. Dùng ở bước verify của /feature, hoặc trước khi tuyên bố bất kỳ việc gì \"xong\"."
---

# Verify ba lớp

Máy làm được thì máy làm. Verifier không nhận lời giải thích. Người chỉ kiểm phần còn lại.

## Lớp 1 — Máy, theo thứ tự, dừng ở lỗi đầu tiên
```bash
# từ toolchain.json: format → analyze → test → build (đọc lệnh bằng python3, không gõ tay)
python3 -c "import json;t=json.load(open('.claude/instructions/toolchain.json'));print(t.get('test',''));print(t.get('build',''))"
python3 .claude/tools/conform.py          # phải 0 vi phạm
python3 .claude/tools/audit.py            # không thêm cycle, không vi phạm ranh giới so với codebase-report.md
```
Mỗi lệnh → một dòng `- [x]`/`- [ ]` trong `verify.md` mục `## Máy`, kèm kết quả tóm tắt (vd: `42 test pass`, `0 vi phạm`).

## Lớp 2 — Agent `verifier`
Gọi `.claude/agents/verifier.md` qua Agent tool với prompt đúng 6 dòng:
```
Spec: docs/napoleon/features/<tên>/spec.md
Diff: git diff <base>..HEAD -- <paths>   (hoặc danh sách file nếu không có git)
Quy ước: .claude/instructions/conventions.md mục "Không kiểm tự động"
Kiểm từng yêu cầu trong spec. Đạt/chưa + bằng chứng file:dòng hoặc output lệnh.
Kiểm API thư viện ngoài có trong doc context7 đã tra không.
Không nhận giải thích từ người build. Không sửa file.
```
Kết quả → bảng vào `verify.md` mục `## Verifier`. Mục "chưa" → về build.

## Lớp 3 — Người
Mục `## Người`: liệt kê những gì máy và verifier không kiểm được: UI nhìn đúng không, cảm giác dùng, hành vi trên thiết bị thật. Mỗi dòng một việc cụ thể để người dùng tick. Không ghi "kiểm tra tổng thể".

## Format `verify.md`
Từ `templates/verify.md`. Ba heading cố định `## Máy`, `## Verifier`, `## Người`. `report.py` đếm mọi `- [x]`/`- [ ]` trong file (không theo heading) → chỉ dùng checkbox cho mục cần tick.

## Cấm
- Không ghi `[x]` cho lệnh chưa chạy trong phiên này.
- Không bỏ lớp 2 vì "feature nhỏ".
- Không sửa test để xanh.

---
name: verifying
description: "Verify ba lớp cho một feature: máy (toolchain, conform, audit) → agent verifier độc lập → người. Dùng ở bước verify của /feature, hoặc trước khi tuyên bố bất kỳ việc gì \"xong\"."
---

# Verify ba lớp

Máy làm được thì máy làm. Verifier không nhận lời giải thích. Người chỉ kiểm phần còn lại, và được phép kiểm sau.

## Lớp 1 — Máy, theo thứ tự, dừng ở lỗi đầu tiên
```bash
# từ toolchain.json: format → analyze → test (TOÀN BỘ, không theo diff) → build
python3 -c "import json;t=json.load(open('.claude/instructions/toolchain.json'));print(t.get('test',''));print(t.get('build',''))"
python3 .claude/tools/conform.py          # phải 0 vi phạm
python3 .claude/tools/audit.py            # không thêm cycle, không vi phạm ranh giới so với codebase-report.md
```
Bước verify là chỗ duy nhất chạy toàn bộ test. Trong lúc build, `state.py task done` đã chạy test theo diff.
Mỗi lệnh → một dòng `- [x]`/`- [ ]` trong `verify.md` mục `## Máy`, kèm kết quả tóm tắt (vd: `1811 test pass`, `0 vi phạm`).

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
Kết quả → bảng vào `verify.md` mục `## Verifier`. Verifier không chạy lại toàn bộ test; nó đọc kết quả lớp Máy.

## Lớp 3 — Người
Mục `## Người`: liệt kê những gì máy và verifier không kiểm được: UI nhìn đúng không, cảm giác dùng, hành vi trên thiết bị thật. Mỗi dòng một việc cụ thể để người dùng tick. Không ghi "kiểm tra tổng thể". Không tự tick.
Mục này **không chặn** `done`: người dùng tick sau bằng `state.py human <tên> list` / `tick <n>`, và `/report` đếm riêng.

## Ghi kết quả vòng verify
```bash
python3 .claude/tools/state.py verify <tên> pass
python3 .claude/tools/state.py verify <tên> fail --issue hardcode --issue thieu-test --note "lần 1"
```
Nhãn `--issue` ngắn, dùng lại giữa các feature (`hardcode`, `ham-dai`, `nhieu-tham-so`, `thieu-test`, `lech-design`, `chua-tra-doc`, `trung-code`, `hoi-quy`). Nhãn lặp ở ≥ 2 feature → tool nhắc `/retro`; chặn nó bằng rule/test thay vì nhắc nhau lần nữa.

## Format `verify.md`
Từ `templates/verify.md`. Ba heading cố định `## Máy`, `## Verifier`, `## Người`.
- `report.py` đếm ô ngoài mục Người là "máy + verifier", ô trong mục Người là "chờ bạn".
- `state.py feature step <tên> done` chặn nếu còn ô trống ngoài mục Người.

## Cấm
- Không ghi `[x]` cho lệnh chưa chạy trong phiên này.
- Không bỏ lớp 2 vì "feature nhỏ".
- Không sửa test để xanh.

# Napoleon — thiết kế bộ repository harness cho Claude Code

Ngày: 2026-11-08
Trạng thái: đã duyệt qua hội thoại, chờ triển khai

## 1. Mục tiêu

Một thư mục `.claude/` đóng gói sẵn, copy vào bất kỳ dự án nào là dùng được. Bộ này bổ sung **tầng dự án** mà superpowers không có: chốt kiến trúc theo từng dự án qua hỏi đáp, sinh chỉ dẫn/skill/agent riêng cho dự án, giữ trạng thái feature và task xuyên phiên, truy vấn code bằng codegraph thay grep, tra doc bằng context7 thay đoán, và cung cấp tool bằng code để agent không ảo giác số liệu.

Superpowers vẫn lo quy trình chung (brainstorm, plan, TDD, debug, review, verify). Napoleon không viết lại những thứ đó mà gọi chúng ở đúng bước.

## 2. Nguyên tắc

1. **Một vòng lặp chính.** Subagent chỉ khi cần song song, context cô lập, hoặc phân quyền khác. Trong bộ lõi chỉ có một agent: `verifier`.
2. **Codegraph trước grep.** Grep chỉ cho chuỗi văn bản thuần.
3. **Tra doc, không đoán.** Dùng API thư viện ngoài → context7 trước.
4. **Máy làm được thì máy làm.** Số liệu, trạng thái, kiểm tra quy ước đều qua `tools/*.py`. Agent không sửa tay `state.json`, không gõ tay số vào báo cáo.
5. **Gọn.** Mô tả agent/skill ≤ 3 dòng, chỉ ghi việc phải làm và việc cấm. Context luôn nạp giữ dưới ~100 dòng. Phần còn lại nạp theo rule hoặc skill.
6. **Lỗi lặp → chặn bằng máy.** Thứ tự ưu tiên: test → `rules.json` → hook → rule theo path → chữ.
7. **Toàn bộ nội dung tiếng Việt.** Tên file, tên lệnh, tên tool tiếng Anh để gõ nhanh.

## 3. Cấu trúc repo `napoleon`

```
napoleon/
├── .claude/
│   ├── CLAUDE.md                 # lõi, luôn nạp, ≤ 100 dòng
│   ├── settings.json             # hooks
│   ├── commands/
│   │   ├── map-codebase.md
│   │   ├── start-build.md
│   │   ├── setup-agents.md
│   │   ├── feature.md
│   │   ├── status.md
│   │   ├── report.md
│   │   └── retro.md
│   ├── skills/
│   │   ├── napoleon-core/SKILL.md
│   │   ├── architecture-interview/SKILL.md (+ references/*.md)
│   │   ├── writing-conventions/SKILL.md
│   │   ├── generating-project-agents/SKILL.md
│   │   ├── feature-loop/SKILL.md
│   │   ├── verifying/SKILL.md
│   │   └── using-codegraph/SKILL.md
│   ├── agents/
│   │   └── verifier.md
│   ├── instructions/             # trống trong bộ; /start-build sinh
│   ├── rules/                    # trống trong bộ; /setup-agents sinh
│   ├── tools/
│   │   ├── check.sh
│   │   ├── codegraph-sync.sh
│   │   ├── session-start.sh
│   │   ├── audit.py
│   │   ├── conform.py
│   │   ├── state.py
│   │   └── report.py
│   └── templates/
│       ├── project.md, architecture.md, conventions.md, module-map.md
│       ├── rules.json, toolchain.json
│       ├── adr.md, brief.md, spec.md, plan.md, verify.md
│       └── feature-skill.md, feature-agent.md, path-rule.md, project-command.md
├── .mcp.json
├── install.sh
├── README.md
├── docs/superpowers/specs/…     # spec này
└── tests/
    ├── test_state.py, test_conform.py, test_audit.py, test_report.py
    ├── test_hooks.sh, test_install.sh
    ├── fixtures/
    └── smoke.md
```

### Trong dự án đích sau khi cài và chạy `/start-build`

```
.claude/instructions/   # CÁCH làm việc: project.md, architecture.md, conventions.md,
                        # module-map.md, rules.json, toolchain.json, decisions/ADR-*.md
.claude/rules/          # rule ngắn theo path, trỏ về instructions/
.claude/skills/project-*/, .claude/agents/project-*/   # /setup-agents sinh, có dấu generated
docs/napoleon/          # ĐANG Ở ĐÂU: state.json, journal.md, codebase-report.md, features/<tên>/{spec,plan,verify}.md
reports/roadmap.html    # /report sinh; .gitignore mặc định
.codegraph/             # codegraph; .gitignore
```

## 4. Cài đặt

`install.sh <đường-dẫn-dự-án> [--update]`

- Copy `.claude/` và `.mcp.json` vào dự án. Không ghi đè file đã có; in danh sách file bỏ qua.
- `--update`: ghi đè các file thuộc napoleon (commands, skills lõi, agents lõi, tools, templates, CLAUDE.md). Không bao giờ đè `.claude/settings.json` và `.mcp.json` (in hướng dẫn gộp). Không đụng `instructions/`, `rules/`, `docs/napoleon/`. Dấu generated chỉ phục vụ `/setup-agents` chạy lại.
- Thêm `.codegraph/` và `reports/` vào `.gitignore` nếu chưa có.
- Kiểm tra `codegraph` và `python3` trong PATH. Thiếu → in đúng một lệnh cài, không tự cài.
- Nếu `.mcp.json` đã tồn tại → không ghi đè, in hướng dẫn gộp hai khoá `codegraph` và `context7`.

## 5. `.mcp.json`

```json
{
  "mcpServers": {
    "codegraph": {
      "type": "stdio",
      "command": "codegraph",
      "args": ["serve", "--mcp"],
      "env": {"CODEGRAPH_MCP_TOOLS": "explore,search,node,callers,callees,impact"}
    },
    "context7": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp"]
    }
  }
}
```

## 6. `CLAUDE.md` lõi (nội dung chính)

- Napoleon là gì, phân vai với superpowers (một đoạn).
- Bắt đầu phiên: đọc `.claude/instructions/project.md` nếu có; chạy `tools/state.py show` để biết đang ở đâu.
- Codegraph trước grep. Context7 trước khi dùng API lạ.
- Trạng thái chỉ sửa qua `state.py`. Báo cáo chỉ sinh qua `report.py`.
- Bảng lệnh: tên → dùng khi nào (một dòng mỗi lệnh).
- Nguyên tắc viết agent/skill sinh ra: gọn, một việc, chỉ phải làm/cấm.
- Trả lời tiếng Việt.

## 7. Lệnh

### `/map-codebase`
1. `codegraph status`; chưa có → `codegraph init`; cũ → `codegraph sync`.
2. `codegraph_explore` từng thư mục gốc: module, entry point, pattern đang dùng.
3. `python3 .claude/tools/audit.py --json` → cycles, phụ thuộc giữa module, dep ngoài, file mồ côi.
4. Ghi `docs/napoleon/codebase-report.md`: phần **Số liệu** (từ audit.py, không sửa) tách khỏi phần **Nhận xét** (agent). Kết thúc bằng 3–5 câu hỏi mở cho người dùng.

### `/start-build`
1. Input: tài liệu (đường dẫn hoặc dán), `codebase-report.md` nếu có.
2. Phỏng vấn theo skill `architecture-interview`: một câu một lần, ưu tiên trắc nghiệm có khuyến nghị. Thứ tự: mục tiêu & phạm vi → stack & ràng buộc → kiến trúc tầng → quản lý state → ranh giới module → toolchain → điều cấm. Tài liệu tham khảo trong `references/` nạp khi câu hỏi chạm tới.
3. Quyết định không hiển nhiên → ADR ngắn (bối cảnh, quyết định, hệ quả).
4. Sinh từ template: `instructions/*`, `rules.json`, `toolchain.json`, khung thư mục rỗng theo kiến trúc (chỉ thư mục + `.gitkeep`), `features.md` rút từ tài liệu, `state.py init`.
5. `codegraph init` nếu chưa. Gợi ý `/setup-agents`.

### `/setup-agents`
1. Đọc `instructions/`.
2. Sinh `rules/*.md` theo path cho từng module/tầng, mỗi rule ≤ 15 dòng, trỏ về mục trong `instructions/`.
3. Sinh skill dự án (vd `skills/project-new-feature/`): các bước tạo một feature đúng kiến trúc này, file nào ở đâu.
4. Sinh agent chỉ khi: cần song song, cần context cô lập, hoặc phân quyền khác. Không → skill. Lý do một dòng trong frontmatter.
5. File sinh ra: frontmatter ở dòng 1, dòng đầu của thân là `<!-- napoleon:generated -->`; chạy lại chỉ ghi đè file có dấu này.

### `/feature <tên> [bước]`
Đọc `state.py feature show <tên>`, chạy bước kế tiếp (hoặc bước chỉ định), ghi lại.

| Bước | Làm | Gọi superpowers | Kết quả |
|---|---|---|---|
| spec | Đọc `features.md` + tài liệu, hỏi phần chưa rõ, viết spec | brainstorming (bounded) | `features/<tên>/spec.md` |
| plan | Tách task, mỗi task ghi file sẽ đụng (dùng `codegraph_impact`) | writing-plans | `plan.md` + `state.py task add` |
| build | Từng task: TDD, context7 khi dùng API, `conform.py` sau mỗi task | test-driven-development | code, `state.py task done` |
| verify | Ba lớp (mục 8) | verification-before-completion | `verify.md` |
| done | `codegraph sync`, `state.py session note`, journal, gợi ý `/report` | finishing-a-development-branch | `state.json`, `journal.md` |

verify fail → về build với danh sách lỗi; không được done.

### `/status`
`state.py show` + 3 mục cuối `journal.md`. Không suy luận thêm.

### `/report`
`python3 .claude/tools/report.py` → `reports/roadmap.html`. Agent không sửa HTML tay.

### `/retro`
1. Đọc `journal.md`, mọi `verify.md`, `git log`.
2. Liệt kê lỗi/sửa lặp ≥ 2 lần.
3. Mỗi lỗi → một chỗ chặn theo thứ tự: test → `rules.json` → hook → rule theo path → chữ.
4. Người dùng duyệt → áp dụng → ADR ngắn.

## 8. Verify ba lớp

1. **Máy**: `toolchain.json` → format, analyze, test, build. `conform.py` → 0 vi phạm. `audit.py` → không thêm cycle, không vượt ranh giới `module-map.md`.
2. **Agent `verifier`** (context riêng, chỉ đọc): nhận spec + diff, không nhận giải thích của người build. Trả về từng yêu cầu đạt/chưa kèm bằng chứng `file:dòng` hoặc output lệnh. Không bằng chứng = chưa đạt. Có mục "API dùng có trong doc đã tra không".
3. **Người**: `verify.md` liệt kê phần máy và verifier không kiểm được (UI, cảm nhận).

## 9. Hooks (`settings.json`)

| Event | Matcher | Script | Hành vi |
|---|---|---|---|
| PostToolUse | `Edit\|Write` | `tools/check.sh` | Đọc đuôi file → tra `toolchain.json` → format rồi analyze **file đó** (đường dẫn quote bằng shlex, stdin đóng). Output là JSON `hookSpecificOutput.additionalContext` để Claude nhìn thấy. Không có `toolchain.json` → thoát 0 im lặng. |
| Stop | — | `tools/codegraph-sync.sh` | `git status --porcelain` có thay đổi và `codegraph` có trong PATH → `codegraph sync`. Luôn thoát 0. |
| SessionStart | `startup\|clear\|compact` | `tools/session-start.sh` | In ≤ 5 dòng từ `state.py show --brief`. Không có state → im lặng. |

Hook không bao giờ chặn (exit 0), trừ khi sau này `/retro` quyết định khác.

## 10. Tools (Python 3 stdlib, không dependency)

### `state.py`
File: `docs/napoleon/state.json`. Lệnh:
- `init`
- `show [--brief] [--json]`
- `feature add <tên>` | `feature step <tên> <spec|plan|build|verify|done>` | `feature show <tên>`
- `task add <feature> "<title>" [--files a,b]` | `task start <feature> <id>` | `task done <feature> <id>` | `task block <feature> <id> "<lý do>"`
- `session note <feature> "<ghi chú>"` → cập nhật `last_session` và append `journal.md`

Schema:
```json
{
  "version": 1,
  "features": {
    "<tên>": {
      "step": "spec|plan|build|verify|done",
      "tasks": [{"id": 1, "title": "", "status": "todo|in_progress|done|blocked", "files": [], "blocker": ""}],
      "updated": "ISO-8601"
    }
  },
  "last_session": {"feature": "", "note": "", "at": "ISO-8601"}
}
```
Ghi file atomic (ghi tạm rồi rename). Lỗi đầu vào → exit 1, thông báo một dòng.

### `conform.py`
Đọc `.claude/instructions/rules.json`, quét file theo glob, in vi phạm `file:dòng: rule-id: thông điệp`. `--json`. Exit 1 nếu có vi phạm. Loại rule v1:
- `forbidden-import`: `{ "in": "lib/domain/**", "forbid": ["package:flutter/**"] }`
- `naming`: `{ "in": "lib/**/*_bloc.dart", "class_regex": ".*Bloc$" }`
- `location`: `{ "pattern": "*_repository.dart", "must_be_under": "lib/data/" }`
- `max-lines`: `{ "in": "lib/**", "max": 400 }`

Import được đọc bằng regex theo ngôn ngữ (dart/kotlin/swift/ts/py) — đủ cho v1, không parse AST.

### `audit.py`
Đọc `.codegraph/codegraph.db` (SQLite). Nếu không có DB → exit 2 với hướng dẫn `codegraph init`. Xuất `--json` hoặc markdown:
- Cycles giữa file (DFS trên cạnh import).
- Ma trận phụ thuộc giữa module (module = thư mục cấp N cấu hình được, hoặc từ `module-map.md`).
- Vi phạm ranh giới: cạnh A→B không có trong `module-map.md` phần "cho phép".
- Dep ngoài: import ngoài repo, đếm theo package.
- File mồ côi: không ai import và không phải entry point.

Schema codegraph đọc lúc chạy (`PRAGMA table_info`). Đã kiểm trên codegraph 1.4 (Flora AI): `nodes(id TEXT, kind, name, qualified_name, file_path)`, `edges(source, target, kind)` với kind ∈ contains/calls/imports/instantiates/references/implements/extends; cạnh `imports` trỏ file → node import **cùng file**, nên phụ thuộc file↔file lấy từ mọi cạnh khác `contains` giữa node khác file. Bảng node chọn theo tỉ lệ cạnh resolve (tránh chọn nhầm `unresolved_refs`). Không nhận dạng được hoặc không có DB → `scan`: regex import, Dart theo path/package, Kotlin theo `package` + symbol. Output luôn ghi `source:` và `notes`, không trộn.

### `report.py`
Sinh `reports/roadmap.html` một file, không CDN. Nguồn và cách lấy:
- `state.json`: feature, bước, task theo trạng thái.
- `git log --date=short --pretty=...`: commit theo ngày, theo feature (grep tên feature trong message).
- `.codegraph/codegraph.db`: số file, symbol, module (nếu có).
- `features/*/verify.md`: đếm dòng `- [x]` / `- [ ]`.
- `audit.py --json`: cycles, vi phạm.
Mỗi số có chú thích nguồn. Nguồn thiếu → hiện "không có dữ liệu", không bịa.

## 11. Skills lõi (tóm tắt nội dung)

- **napoleon-core**: phân vai, state ở đâu, lệnh nào khi nào, nguyên tắc gọn.
- **architecture-interview**: cách hỏi (một câu, trắc nghiệm, khuyến nghị), thứ tự chủ đề, khi nào viết ADR, cách rút feature từ tài liệu. `references/`: layered/clean, MVI, BLoC, MVVM, DI, navigation, testing pyramid — mỗi file ≤ 80 dòng, chỉ là tham khảo.
- **writing-conventions**: cấu trúc `conventions.md`, cách chuyển một quy ước thành rule trong `rules.json`, khi nào không thể máy hoá.
- **generating-project-agents**: tiêu chí skill vs agent, template, dấu generated, cách chạy lại.
- **feature-loop**: bảng bước, điều kiện chuyển bước, quy tắc quay lui.
- **verifying**: ba lớp, cách gọi `verifier`, format `verify.md`.
- **using-codegraph**: câu hỏi → tool, kiểm tra index, xử lý lỗi thường gặp.

## 12. Test

- `tests/test_state.py`, `test_conform.py`, `test_audit.py`, `test_report.py`: unittest stdlib, fixture repo mẫu nhỏ trong `tests/fixtures/`, DB codegraph giả tạo bằng sqlite3 theo schema tối thiểu mà `audit.py` hỗ trợ.
- `tests/test_hooks.sh`: `check.sh` với `toolchain.json` giả (format = `echo`), `codegraph-sync.sh` khi không có codegraph, `session-start.sh` khi không có state.
- `tests/test_install.sh`: copy vào thư mục tạm, không ghi đè, `--update` chỉ đè file có dấu generated.
- `tests/smoke.md`: kịch bản chạy tay 15 phút trên repo Flutter mẫu.
- Chạy tất cả: `tests/run.sh`.

## 12b. Bổ sung sau review người dùng (2026-11-08)

- **Quy tắc code xuyên dự án** (CLAUDE.md "Quy tắc code"): tìm trước viết sau; comment chỉ "vì sao" (`max-comment-ratio`); thiết kế là luật, lệch → hỏi → ADR; mơ hồ → hỏi; một nguồn sự thật cho state dùng chung (bảng owner trong `architecture.md`); logic tái dùng → manager class ngoài presentation. Verifier kiểm 3 mục tương ứng.
- **Quy ước hai tầng**: khối "Chung" trong `templates/conventions.md` là của bộ, copy nguyên văn vào mọi dự án; `/start-build` chủ đề 7 chỉ in baseline + stack rồi hỏi một câu bổ sung.
- **Đường dẫn spec/plan**: luôn `docs/napoleon/features/<tên>/`; khi gọi superpowers phải nói rõ, không dùng `docs/superpowers/` trong dự án.
- **Thư mục dự án**: thêm `docs/sources/{prd,api,design}/` (tài liệu người dùng, tool chỉ đọc; `install.sh` tạo) và `features/<tên>/brief.md` (đề bài nguyên văn, verifier đối chiếu). Không có `context/`, `drafts/`, `commands/` ngoài `.claude/`. `/setup-agents` sinh thêm `commands/project-*` cho tác vụ lặp.

## 13. Ngoài phạm vi v1

Đóng gói plugin; nhiều feature song song trong một phiên; memory chia sẻ team; hỗ trợ Codex/Cursor; parse AST cho `conform.py`.

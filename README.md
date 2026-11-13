# Napoleon

Bộ harness tầng dự án cho [Claude Code](https://claude.com/claude-code). Copy một thư mục `.claude/` vào dự án bất kỳ, Claude sẽ:

- phỏng vấn bạn để chốt kiến trúc, quy ước, toolchain rồi sinh chỉ dẫn riêng cho dự án đó;
- sinh rule, skill, agent riêng từ chỉ dẫn đã chốt;
- giữ trạng thái feature/task xuyên phiên trong file, không dựa vào trí nhớ hội thoại;
- truy vấn code bằng [codegraph](https://github.com/colbymchenry/codegraph) thay vì grep, tra doc thư viện bằng [context7](https://github.com/upstash/context7) thay vì đoán;
- kiểm quy ước, phụ thuộc, số liệu bằng tool Python, không tự chứng nhận.

Chạy song song với [superpowers](https://github.com/obra/superpowers): superpowers lo quy trình chung (brainstorm, plan, TDD, debug, review); napoleon lo phần riêng của từng dự án. Không thay thế nhau.

Toàn bộ nội dung tiếng Việt. Không phụ thuộc thư viện ngoài: Python 3 stdlib + bash.

## Mục lục

- [Cài đặt](#cài-đặt)
- [Bắt đầu nhanh](#bắt-đầu-nhanh)
- [Lệnh](#lệnh)
- [Vòng đời một feature](#vòng-đời-một-feature)
- [Quy tắc Claude phải theo](#quy-tắc-claude-phải-theo)
- [Cấu trúc thư mục](#cấu-trúc-thư-mục)
- [Tools](#tools)
- [Hooks](#hooks)
- [Cập nhật và tuỳ biến](#cập-nhật-và-tuỳ-biến)
- [Phát triển bộ này](#phát-triển-bộ-này)
- [Thiết kế](#thiết-kế)

## Cài đặt

Yêu cầu:

| Thứ | Để làm gì | Cài |
|---|---|---|
| Claude Code | chạy lệnh, skill, hook | [docs](https://code.claude.com/docs) |
| Python 3.9+ | `tools/*.py` | có sẵn trên macOS; Linux: `apt install python3` |
| codegraph | index và truy vấn code | `curl -fsSL https://raw.githubusercontent.com/colbymchenry/codegraph/main/install.sh \| sh` rồi `codegraph install` |
| Node (npx) | context7 MCP | [nodejs.org](https://nodejs.org) |
| superpowers | quy trình chung | `claude plugin install superpowers` hoặc theo README của nó |

Clone bộ về một chỗ cố định:

```bash
git clone https://github.com/h1eu/napolenon ~/napoleon
```

Cài vào dự án:

```bash
~/napoleon/install.sh /đường/dẫn/dự/án
```

```bash
cd /đường/dẫn/dự/án && codegraph init
```

`install.sh` copy `.claude/` và `.mcp.json`, tạo `docs/sources/{prd,api,design}/`, thêm `.codegraph/` và `reports/` vào `.gitignore`, báo nếu thiếu `python3` hay `codegraph`. Không ghi đè file đã có. Dự án đã có `.claude/settings.json` hoặc `.mcp.json` → giữ nguyên, in hướng dẫn gộp hai khoá `hooks` / `mcpServers`.

## Bắt đầu nhanh

**Dự án mới**

```
# bỏ PRD vào docs/sources/prd/, Figma export vào docs/sources/design/, API docs vào docs/sources/api/
/start-build Flutter + BLoC + clean architecture
/setup-agents
/feature login   # dán đề bài → brief.md → spec → plan → build → verify → done
```

**Dự án có sẵn**

```
/map-codebase
/start-build
/setup-agents
/feature <tên>
```

**Mỗi ngày**: mở Claude Code → hook in 5 dòng "đang ở đâu" → `/feature <tên>` làm bước kế tiếp. Quên thì `/status`. Muốn số liệu thì `/report`. Thấy lỗi lặp thì `/retro`. Tài liệu trong `docs/sources/` đổi thì `/sync-docs`.

Kịch bản chạy tay đầy đủ 15 phút: [tests/smoke.md](tests/smoke.md).

## Lệnh

| Lệnh | Làm gì | Kết quả |
|---|---|---|
| `/map-codebase` | Index codegraph, quét từng thư mục, chạy `audit.py` | `docs/napoleon/codebase-report.md`: số liệu (máy) tách khỏi nhận xét (agent), kèm 3–5 câu hỏi cho bạn |
| `/start-build [mô tả \| đường dẫn tài liệu]` | Đọc `docs/sources/`, phỏng vấn 8 chủ đề một câu một lần. Quy ước không hỏi từng cái: baseline chung + theo stack, bạn chỉ bổ sung | `.claude/instructions/` (project, architecture, conventions, module-map, rules.json, toolchain.json, ADR), khung thư mục rỗng, `features.md`, `state.json` |
| `/setup-agents` | Đọc `instructions/` | `.claude/rules/*.md` theo path, `skills/project-new-feature`, `commands/project-*` cho tác vụ lặp, agent chỉ khi có lý do. Chạy lại được |
| `/feature <tên> [bước]` | Làm một bước: spec → plan → build → verify → done | `docs/napoleon/features/<tên>/{spec,plan,verify}.md`, `state.json` |
| `/status` | `state.py show` + journal | Không suy luận thêm |
| `/report` | `report.py` | `reports/roadmap.html`, mọi số có ghi nguồn |
| `/retro` | Tìm lỗi lặp ≥ 2 lần | Mỗi lỗi một chỗ chặn: test → rules.json → hook → rule → chữ |
| `/sync-docs [feature]` | `docs/sources/` đổi sau khi đã có harness: `sources.py diff` so với mốc cuối (sha256 + git diff), liệt kê điểm lệch với `instructions/` và spec, hỏi bạn quyết từng điểm | Sửa đúng dòng lệch, ADR khi giữ/đổi kiến trúc, task sửa cho feature đang build, mốc mới trong `state.json` |

## Vòng đời một feature

```
brief ──▶ spec ──▶ plan ──▶ build ──▶ verify ──▶ done
  │        │        │         │          │
  │        │        │         │          └─ fail → về build
  │        │        │         └─ từng task: codegraph_search → TDD → task done (cổng: conform + test theo diff) → commit
  │        │        └─ codegraph_impact cho mỗi symbol sửa; task vào state.json
  │        └─ brainstorming (bounded), hỏi phần chưa rõ, yêu cầu đánh số, phủ hết brief
  └─ đề bài nguyên văn của bạn, không sửa sau khi có spec
```

Mọi file của feature nằm ở `docs/napoleon/features/<tên>/`: `brief.md`, `spec.md`, `plan.md`, `verify.md`. Superpowers mặc định ghi `docs/superpowers/`; napoleon ghi đè đường dẫn đó, dự án không có thư mục `docs/superpowers/`.

Verify ba lớp, lớp nào máy làm được thì máy làm:

1. **Máy** — format, analyze, **toàn bộ** test, build từ `toolchain.json`; `conform.py` 0 vi phạm; `audit.py` không thêm cycle, không vượt ranh giới. (Trong lúc build thì chỉ chạy test theo diff — xem `affected.py`.)
2. **Agent `verifier`** — context riêng, chỉ đọc, nhận spec + diff, không nhận lời giải thích. Trả bảng từng yêu cầu đạt/chưa kèm `file:dòng`. Không bằng chứng = chưa đạt.
   **Agent `bug-hunter`** chạy song song — không chấm spec mà săn kịch bản hỏng: cờ "đang bận" nuốt lần gọi thứ hai, hai lớp gặp nhau, mất mạng rồi có lại, xung đột rồi thử lại, stub trên đường chạy thật. Lỗi nặng → test tái hiện rồi mới sửa. Spec có sẵn mục "Kịch bản lần hai" để những chuyện này thành yêu cầu ngay từ đầu.
3. **Bạn** — những gì máy và verifier không kiểm được (UI trên máy thật, cảm nhận). Mục này **không chặn** `done`: feature vẫn chốt được, mục Người nằm chờ bạn tick sau (`state.py human <tên> tick <n>`), `/report` đếm riêng.

Hai chỗ chặn bằng code, không chặn bằng chữ:

- `state.py task done` tự chạy `conform.py` trên file của task và test theo diff; trượt thì task không được đánh done.
- `state.py feature step <tên> done` đọc `verify.md`: còn ô trống ngoài mục "Người" thì không cho sang `done`.

Verify trượt → `state.py verify <tên> fail --issue <nhãn>`; nhãn lặp ở ≥ 2 feature thì tool nhắc `/retro` để biến nó thành rule. Việc ADR hẹn làm sau → `state.py followup add`, hiện ở `/status` và `/report`.

Trạng thái chỉ sửa qua `state.py` (hook chặn sửa tay). Mở phiên mới chỉ cần `/status`.

## Quy tắc Claude phải theo

Nằm trong [`.claude/CLAUDE.md`](.claude/CLAUDE.md), dưới 100 dòng, luôn nạp. Tóm tắt:

| Quy tắc | Cơ chế ép |
|---|---|
| Codegraph trước grep | skill `using-codegraph`; `/map-codebase` và bước plan gọi codegraph; hook `guard.py --post` nhắc khi grep tên symbol |
| Sửa file nguồn chỉ bằng Write/Edit | hook `guard.py` chặn `cat >`, `sed -i`, `tee`, python ghi file; mở lối bằng `NAPOLEON_ALLOW_BASH_WRITES=1` |
| Mỗi quy ước phải có chỗ chặn hoặc nhãn `[tay]` | `conform.py --coverage`; `/setup-agents` không kết thúc khi còn lỗi |
| Tra doc trước khi dùng API lạ | context7 trong `.mcp.json`; verifier có mục "API chưa tra doc" |
| Tìm trước, viết sau — không tạo bản thứ hai của thứ đã có trong `core/` | bước build gọi `codegraph_search`; verifier có mục "Code trùng" |
| Comment chỉ cho "vì sao" | `conform.py` rule `max-comment-ratio` |
| Quy ước chung của bạn áp mọi dự án, không hỏi lại | khối "Chung" trong `templates/conventions.md` copy nguyên văn vào mỗi dự án; `/start-build` chỉ hỏi bổ sung |
| Thiết kế là luật (kiến trúc lẫn UI); muốn lệch → hỏi → ADR | `architecture.md`, `module-map.md`, mục "Design nguồn" trong spec; `audit.py` bắt vượt ranh giới; verifier đối chiếu design |
| Mơ hồ → hỏi một câu trắc nghiệm, dừng chờ | mọi skill; không có đường "tự quyết" |
| Một nguồn sự thật cho state dùng ở ≥ 2 nơi; nơi khác quan sát | bảng "Nguồn sự thật dùng chung" trong `architecture.md`, chốt ở `/start-build`; verifier kiểm |
| Logic tái dùng → manager class, ngoài `presentation/`, có test, một việc | `rules.json` naming + location; bảng "Logic tái dùng" |
| Trạng thái và số liệu chỉ qua tool | `state.py`, `audit.py`, `report.py`; hook chặn Write/Edit vào `state.json` |
| Task chỉ xong khi máy nói xong | `state.py task done` chạy `conform.py` + test theo diff trước khi đổi trạng thái |
| Gọn: mô tả ≤ 3 dòng, chỉ phải làm / cấm | test `test_docs.py` ép |
| Một vòng lặp chính; subagent chỉ khi cần song song, cô lập, hoặc phân quyền | bộ lõi có đúng hai agent, đều chỉ đọc và context cô lập; `/setup-agents` phải ghi lý do khi sinh agent |

## Cấu trúc thư mục

Trong repo này:

```
.claude/
├── CLAUDE.md                 lõi, luôn nạp
├── settings.json             5 hook
├── commands/                 8 lệnh
├── skills/
│   ├── napoleon-core/        phân vai, file ở đâu, tool nào khi nào
│   ├── architecture-interview/   phỏng vấn + references/ (clean, MVI, BLoC, MVVM, DI, navigation, testing)
│   ├── writing-conventions/  conventions.md ↔ rules.json
│   ├── generating-project-agents/  tiêu chí skill vs agent
│   ├── feature-loop/         5 bước, điều kiện vào/ra
│   ├── verifying/            3 lớp
│   └── using-codegraph/      câu hỏi → tool
├── agents/                   verifier.md (đối chiếu spec) · bug-hunter.md (săn lỗi vận hành)
├── tools/                    state.py conform.py audit.py affected.py report.py sources.py
│                             guard.py (hook) + funcs.py globs.py cgdb.py imports.py + 3 hook .sh
├── templates/                khuôn cho mọi file sinh ra
├── instructions/             (trống) /start-build sinh
└── rules/                    (trống) /setup-agents sinh
.mcp.json                     codegraph + context7
install.sh
tests/                        unittest + bash + smoke.md
docs/superpowers/             spec và plan của chính bộ này
```

Trong dự án sau khi dùng:

```
.claude/instructions/         CÁCH làm việc: project, architecture, conventions, module-map,
                              rules.json, toolchain.json, decisions/ADR-*.md
.claude/rules/*.md            rule ≤ 15 dòng theo path, trỏ về instructions/
.claude/skills/project-*/     skill riêng dự án (có dấu generated)
.claude/commands/project-*.md lệnh cho tác vụ lặp của dự án (có dấu generated)
docs/sources/                 TÀI LIỆU BẠN ĐƯA: prd/ api/ design/ — tool chỉ đọc
docs/napoleon/                ĐANG Ở ĐÂU: state.json, journal.md, codebase-report.md,
                              features/<tên>/{brief,spec,plan,verify}.md
reports/roadmap.html          sinh bởi report.py, gitignore
.codegraph/                   index codegraph, gitignore
```

Ba loại thư mục, ba chủ sở hữu: `docs/sources/` của bạn (tool chỉ đọc), `instructions/` cách làm việc (sinh một lần, bạn sửa tay được), `docs/napoleon/` đang ở đâu (chỉ tool ghi). Không có `context/`, `drafts/`, `commands/` ngoài `.claude/`: quy ước nằm ở `instructions/`, code dở nằm ở git branch, lệnh nằm ở `.claude/commands/`.

## Tools

Chạy từ gốc dự án. Mọi tool nhận `--root DIR`.

### `state.py`

```bash
python3 .claude/tools/state.py init
python3 .claude/tools/state.py show [--brief|--json]
python3 .claude/tools/state.py feature add|step|show <tên> [bước]
python3 .claude/tools/state.py task add <feature> "<title>" [--files a,b]
python3 .claude/tools/state.py task start <feature> <id>
python3 .claude/tools/state.py task done <feature> <id> [--skip-tests] [--skip-conform]
python3 .claude/tools/state.py task block <feature> <id> "<lý do>"
python3 .claude/tools/state.py verify <feature> pass|fail [--issue <nhãn>] [--note "..."]
python3 .claude/tools/state.py human <feature> list|tick <n>|tick-all
python3 .claude/tools/state.py followup add <feature> "<việc>" [--source ADR-012] | list [--all] | done <id>
python3 .claude/tools/state.py session note <feature> "<ghi chú>"
```

Ghi `docs/napoleon/state.json` atomic; `session note` append `journal.md`. Tên feature `[a-z0-9-]`. State cũ (version 1) đọc được, tự nâng lên version 2 khi ghi.

`task done` là cổng: chạy `conform.py --files <file của task>` rồi test theo diff (`affected.py`), trượt thì task giữ nguyên trạng thái và in lý do. Xong thì lưu sha HEAD làm mốc diff cho task sau. `--skip-*` ghi thẳng lý do vào `state.json` và hiện trong `/report`.
`feature step <tên> done` chặn khi `verify.md` còn ô trống ngoài mục "Người"; ô trong mục Người chỉ được đếm và nhắc.

### `conform.py`

Soi code theo `instructions/rules.json`. In `path:dòng: rule-id: thông điệp`, exit 1 nếu có vi phạm, 2 nếu rules.json thiếu/hỏng.

| Loại rule | Trường | Bắt gì |
|---|---|---|
| `forbidden-import` | `in`, `forbid[]` | import cấm trong một vùng (domain không import Flutter) |
| `naming` | `in`, `class_regex` | tên class trong file loại X |
| `location` | `pattern`, `must_be_under` | file loại X phải nằm dưới thư mục Y |
| `max-lines` | `in`, `max` | file quá dài |
| `max-comment-ratio` | `in`, `max_ratio`, `min_lines` | quá nhiều comment |
| `max-function-lines` | `in`, `max` | hàm quá dài |
| `max-params` | `in`, `max`, `constructors` | hàm quá nhiều tham số (`constructors: false` để tha data class) |
| `forbidden-pattern` | `in`, `regex`, `allow[]`, `message`, `skip_strings` | hardcode: mã màu, icon bộ khác, API cấm. Luôn bỏ dòng comment |
| `no-sibling-import` | `base`, `allow[]` | feature import feature khác — một rule thay cho N² rule |

Khoá `exclude` (list glob) ở cấp cao nhất loại code sinh khỏi mọi rule; `audit.py` và `affected.py` dùng chung danh sách đó.
Glob kiểu fnmatch; `*` và `**` đều khớp qua `/`, `**/` khớp cả 0 thư mục. Import đọc bằng regex cho Dart, Kotlin, Swift, TS/JS, Python; hàm đọc bằng quét ký tự (`funcs.py`), không AST.

```bash
python3 .claude/tools/conform.py --coverage
```

Soi chính bộ quy ước: dòng trong `conventions.md` chưa gắn `[rule: <id>]` hoặc `[tay]` (lỗi), nhãn trỏ rule không tồn tại (lỗi), rule không khớp file nào hoặc không quy ước nào nhắc tới (cảnh báo).

### `audit.py`

```bash
python3 .claude/tools/audit.py [--source auto|codegraph|scan] [--module-depth 2] [--json]
```

Cycles (Tarjan), phụ thuộc giữa module, vi phạm ranh giới so với bảng "Phụ thuộc cho phép" trong `module-map.md`, dep ngoài, file mồ côi.

Nguồn cạnh file → file:
- `codegraph` (mặc định khi có `.codegraph/codegraph.db`, đã kiểm trên codegraph 1.4): mọi cạnh `calls/references/instantiates/implements/extends` giữa hai node ở hai file khác nhau. Cạnh `imports` của codegraph trỏ vào node import cùng file nên không dùng; node `kind=import` dùng để đếm dep ngoài. Schema đọc lúc chạy, bảng node chọn theo tỉ lệ cạnh resolve được; không nhận dạng được → rơi về `scan`.
- `scan`: regex import. Dart theo đường dẫn và `package:`; Kotlin theo khai báo `package` + symbol; TS tương đối; Python theo module. Swift không có import giữa file cùng module.

Output luôn ghi `source:` và các `ghi chú:` (ngôn ngữ chưa resolve, Kotlin/Swift không tính mồ côi từ scan, dương tính giả mồ côi từ codegraph do DI/expect-actual). Không trộn hai nguồn.

### `affected.py`

```bash
python3 .claude/tools/affected.py [--base HEAD] [--files a,b] [--max-ratio 0.6] [--json]
```

File đổi (git diff + file chưa track) → ai import chúng bắc cầu → file test chạm tới → in lệnh chạy đúng nhóm test đó. Chạy **toàn bộ** khi: không có git hoặc mốc sai, file đổi chưa có trong đồ thị import (file mới), file đổi khớp `full_test_when` trong `toolchain.json` (pubspec, DI, router, theme, l10n), hoặc số test ảnh hưởng vượt `--max-ratio`. `state.py task done` gọi tool này; bước verify không dùng.

### `report.py`

Sinh `reports/roadmap.html` một file, không CDN. Nguồn: `state.json`, `git log`, codegraph, `verify.md`, `audit.py`. Mỗi bảng có dòng "nguồn: …"; thiếu nguồn → "không có dữ liệu". Muốn thêm số → sửa `report.py`, không sửa HTML.
Mục Verify đếm riêng "máy + verifier" và "người chờ bạn", kèm số lần verify mỗi feature; mục "Việc hẹn lại" liệt kê followup đang mở.

## Hooks

Trong `.claude/settings.json`. Chỉ `guard.py` chặn; các hook còn lại luôn exit 0.

| Event | Script | Làm gì |
|---|---|---|
| `PreToolUse` (Bash\|Write\|Edit…) | `guard.py` | **chặn**: ghi file nguồn bằng Bash (`cat >`, `sed -i`, `tee`, python ghi file), và Write/Edit thẳng vào `state.json`. Mở lối: `NAPOLEON_ALLOW_BASH_WRITES=1` |
| `PostToolUse` (Bash\|Grep) | `guard.py --post` | grep tên symbol trong thư mục code → nhắc dùng codegraph. Không chặn |
| `PostToolUse` (Edit\|Write) | `check.sh` | format rồi analyze file vừa sửa theo `toolchain.json`; output trả về Claude qua `additionalContext`. Không có `toolchain.json` → im lặng |
| `Stop` | `codegraph-sync.sh` | có file đổi và có codegraph → `codegraph sync` |
| `SessionStart` | `session-start.sh` | in ≤ 5 dòng từ `state.py show --brief` |

`toolchain.json` do `/start-build` sinh:

```json
{
  "by_ext": {
    ".dart": { "format": "dart format {file}", "analyze": "dart analyze {file}" },
    ".kt":   { "format": "ktlint -F {file}", "analyze": "" }
  },
  "test": "flutter test",
  "build": "flutter build apk --debug"
}
```

## Cập nhật và tuỳ biến

Cập nhật bộ trong dự án:

```bash
~/napoleon/install.sh /đường/dẫn/dự/án --update
```

Đè: commands, skills lõi, agents lõi, tools, templates, `CLAUDE.md`. Không đụng: `settings.json`, `.mcp.json`, `instructions/`, `rules/`, `docs/napoleon/`.

File do `/setup-agents` sinh có dòng `<!-- napoleon:generated -->` ngay sau frontmatter. Chạy lại `/setup-agents` chỉ đè file có dấu này; muốn giữ sửa tay thì xoá dòng đó.

Quy ước có hai tầng:
- **Chung, áp mọi dự án** — khối "Chung" trong [`.claude/templates/conventions.md`](.claude/templates/conventions.md) của repo này. Đổi quan điểm → sửa ở đây, `install.sh --update`, dự án mới tự có; dự án cũ chạy `/retro` để đồng bộ.
- **Riêng dự án** — khối "Theo stack" và "Bổ sung của bạn" trong `instructions/conventions.md`, chốt ở `/start-build`. Máy hoá được → `rules.json` (skill `writing-conventions` có bảng quy ước → loại rule). Thêm loại rule mới: sửa `conform.py` + test.

## Phát triển bộ này

```bash
tests/run.sh
```

Chạy unittest (stdlib) cho 6 tool (`state`, `conform`, `audit`, `affected`, `report`, `funcs`) + `test_docs.py` (frontmatter, độ dài, dấu generated, YAML-safe, nhãn quy ước, agent khai đủ tool MCP) + bash test cho hooks (gồm `guard.py`) và `install.sh`. Fixture: `tests/fixtures/flutter_mini` (6 file Dart, mỗi loại rule một vi phạm, một cycle) và DB codegraph giả.

Quy ước khi sửa bộ:
- Test trước, code sau. Mọi tool, hook, install đều có test chạy được không cần codegraph thật.
- `CLAUDE.md` ≤ 100 dòng; description skill/agent ≤ 3 dòng; description chứa `: ` phải bọc ngoặc kép.
- Không thêm dependency. Không thêm agent nếu không đạt một trong ba tiêu chí.

## Thiết kế

- Spec: [docs/superpowers/specs/2026-11-08-napoleon-design.md](docs/superpowers/specs/2026-11-08-napoleon-design.md)
- Plan triển khai: [docs/superpowers/plans/2026-11-08-napoleon.md](docs/superpowers/plans/2026-11-08-napoleon.md)

Nguồn ý tưởng: [claude-code-ultimate-guide / core](https://github.com/FlorianBruniaux/claude-code-ultimate-guide/tree/main/guide/core) (repository harness, 3 vòng phản hồi, lỗi lặp → chặn bằng máy), [When to fold subagents into your main agent loop](https://claude.com/resources/articles/building-agents-when-to-fold-subagents-into-your-main-agent-loop) (một vòng lặp chính, 3 tiêu chí subagent), [Harnessing Claude's intelligence](https://claude.com/resources/articles/harnessing-claudes-intelligence) (progressive disclosure, hỏi "bỏ được gì"), và harness của dự án Flora AI (evidence có exit code, quick path có ngưỡng).

Ngoài phạm vi v1: đóng gói plugin, `/fix` cho thay đổi nhỏ, eval với golden examples, prune định kỳ, memory chia sẻ team, Codex/Cursor, parse AST.

## License

MIT

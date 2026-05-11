# `.claude/` — Cấu hình Claude Code cho Mu Online Varka bot

Thư mục này định hình cách Claude Code làm việc trên project: agents chuyên trách, skills theo từng task, hooks bảo vệ file nhạy cảm và verify nhẹ, và workflow docs cưỡng chế phát triển từng bước có người dùng xác nhận.

## Cây thư mục

```
.claude/
  README.md                       <-- file này
  settings.json                   <-- đăng ký hooks
  agents/                         <-- 7 subagent chuyên trách
  skills/                         <-- 10 skill task-focused
  hooks/                          <-- 3 PowerShell hook (Windows)
  workflow/                       <-- roadmap, gates, vòng lặp, định tuyến, câu hỏi mở
  logs/                           <-- nơi hook log ghi vào (.gitkeep)
```

## Triết lý 30 giây

1. **Đọc doc trước**, code sau. Mọi gate bắt đầu bằng `docs-review`.
2. **Một gate, một verification command**. Người dùng phải xác nhận trước khi sang gate kế.
3. **Không bao giờ** đụng game memory / packets / hooks / injection / anti-cheat. UI / màn hình / input thuần.
4. **Không hard-code** toạ độ / threshold / template path. Tất cả nằm trong config.
5. **Không clicked-blind**. Helper chỉ bấm khi state đúng. NPC chỉ bấm sau khi hover indicator xác minh.

Toàn bộ chi tiết ở `workflow/test-verify-fix-loop.md` và `workflow/verification-gates.md`.

## Thứ tự gọi đề xuất

Khi user nói "bắt đầu gate N":

1. Skill `docs-review` → tóm tắt doc và đặt câu hỏi nếu thiếu thông tin.
2. Agent `solution-architect` → phá nhỏ thành step tối thiểu khả thi.
3. Skill triển khai gate (`varka-window-discovery`, `capability-test-plan`, …) qua wrapper `incremental-dev-step`.
4. Skill `verification-review` (hoặc agent `code-reviewer`) → kiểm tra trước khi user chạy lệnh.
5. **STOP. User chạy verification command, xác nhận.**
6. Agent `technical-docs-keeper` → cập nhật roadmap + verification log.

## Agents (`.claude/agents/`)

| Agent | Khi nào dùng |
|-------|--------------|
| `solution-architect` | Plan từng gate / step. Không viết code lớn. |
| `windows-automation-engineer` | Win32, capture, focus, input backends. Issue 1, 7, mọi thứ chạm OS. |
| `computer-vision-engineer` | ROI, template matching, hover, helper state, timer. Issue 2, 3, 4, 5. |
| `state-machine-orchestrator` | State machine, scheduler, retry policy, terminal status. Issue 4 (alert), 6. |
| `python-qa-test-engineer` | Verification commands, smoke tests, capability harness. Mọi gate. |
| `technical-docs-keeper` | Sau khi gate được verified: cập nhật doc, log, open questions. |
| `code-reviewer` | Sau khi code xong, trước khi user verify. Có quyền block scope creep / unsafe API. |

## Skills (`.claude/skills/`)

| Skill | Phạm vi |
|-------|---------|
| `session-bootstrap` | **Lượt đầu của mọi conversation.** Nạp context tối thiểu, in briefing ≤30 dòng, định nghĩa quy tắc lazy-load doc cho phần còn lại của session. |
| `docs-review` | Reconnaissance trước mọi gate. Read-only. |
| `incremental-dev-step` | Wrapper cưỡng chế quy trình 9 bước cho mọi step triển khai. |
| `capability-test-plan` | **Gate 2** — Issue 7 capability harness. |
| `varka-window-discovery` | **Gate 1** — Issue 1. |
| `varka-lobby-npc` | **Gate 3** — Issue 2. |
| `varka-popups` | **Gate 4** — Issue 3. |
| `varka-event-helper-monitoring` | **Gate 5** — Issue 4. |
| `varka-enter-lobby` | **Gate 6** — Issue 5. |
| `varka-orchestrator` | **Gate 7** — Issue 6. |
| `verification-review` | Static review trước khi user chạy lệnh verification. |

## Hooks (`.claude/hooks/`)

Đăng ký trong `settings.json`. Tất cả là PowerShell (Windows-native).

| Hook | Sự kiện | Tác dụng |
|------|---------|----------|
| `protect-sensitive-files.ps1` | `PreToolUse` (Edit/Write/MultiEdit/NotebookEdit) | **Block** edit `.env`, credentials, key files, account*.{yaml,json,toml}, asset binary trong `assets/templates/`, screenshot trong `.claude/logs/`. Override bằng env var khi cần. |
| `verify-after-edit.ps1` | `PostToolUse` (Edit/Write/MultiEdit/NotebookEdit) | Chạy `python -m py_compile` cho file `.py` nếu có Python trên PATH. Không bao giờ block. Không chạy lint / typecheck / test full. |
| `log-claude-activity.ps1` | `PostToolUse` (mọi tool quan trọng) | Append một dòng JSONL vào `.claude/logs/activity.jsonl`. Tự rotate khi >5 MB. |

### Override chú thích

- Cho phép edit template asset trong session: `$env:CLAUDE_ALLOW_TEMPLATE_EDIT = '1'` trước khi mở Claude Code.
- Cho phép edit screenshot trong `.claude/logs/`: `$env:CLAUDE_ALLOW_LOG_IMAGE_EDIT = '1'`.

### Ghi chú tương thích

`settings.json` dùng cú pháp hooks chuẩn của Claude Code (`PreToolUse` / `PostToolUse` với `matcher` regex và `hooks[].command`). Nếu bản Claude Code hiện tại của user chưa hỗ trợ phiên bản matcher này, các script vẫn dùng được trực tiếp:

```powershell
'<json payload>' | powershell -NoProfile -ExecutionPolicy Bypass -File .\.claude\hooks\protect-sensitive-files.ps1
```

User có thể chạy `/hooks` trong Claude Code để xem lại danh sách đã đăng ký, hoặc dùng skill `update-config` để chỉnh.

## An toàn (đọc trước khi tự thêm gì)

- **Không bao giờ** thêm hook tự chạy lệnh game / lệnh user-facing destructive.
- **Không** lưu credential / token / cookie / account name dạng sensitive vào repo.
- **Không** commit asset PNG/JPG mới mà chưa hỏi user (hook block bằng default).
- **Không** override `protect-sensitive-files.ps1` bằng cách thêm pattern exception bừa.
- Khi nghi ngờ, mở mục mới trong `workflow/open-questions.md` và hỏi user.

## File đầu tiên nên đọc

1. `workflow/implementation-roadmap.md` — biết đang ở gate nào.
2. `workflow/verification-gates.md` — biết deliverable mỗi gate.
3. `workflow/test-verify-fix-loop.md` — biết quy trình thực thi.
4. `workflow/agent-routing.md` — biết gọi ai cho việc gì.
5. `workflow/open-questions.md` — trả lời các câu hỏi mở để Gate 1 bắt đầu được.

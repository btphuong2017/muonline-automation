---
name: session-bootstrap
description: Use AT THE START of every new conversation about this project (or after a context-compaction event). Loads the minimum context Claude needs — project overview, system boundaries, current gate status, open questions, agent/skill routing — and emits a single short briefing. Defines lazy-load rules so Claude knows which docs to pull in later as the task narrows. Read-only; never modifies project files.
---

# session-bootstrap

## Mục đích
Đảm bảo Claude có "bản đồ project" trong tay trước khi nhận task. Output là một briefing ngắn cho user và một mental model rõ ràng cho Claude về:
- đang ở đâu trong roadmap,
- ai (agent/skill) phụ trách việc gì,
- những gì user còn chưa trả lời,
- file nào cần đọc tiếp khi task chuyển hướng.

## Khi nào gọi
- **Lượt đầu của một conversation mới** trên project này.
- Sau khi context bị compact và Claude mất briefing trước đó.
- Khi user gõ: "tóm tắt", "ôn lại", "where are we", "status?", "/session-bootstrap".
- Khi user yêu cầu một việc lớn (gate / planning) mà Claude chưa biết trạng thái hiện tại.

## Khi nào KHÔNG gọi
- User hỏi một câu rõ ràng và hẹp ("file X dòng Y nghĩa gì?", "sửa typo này"). → Trả lời trực tiếp.
- Đang trong giữa một gate đã briefing rồi, user follow-up.
- Đã chạy `session-bootstrap` trong conversation này và context vẫn còn nguyên.

## Read bắt buộc (luôn, theo thứ tự)
1. `.claude/README.md` — cây thư mục, triết lý 30 giây.
2. `.claude/workflow/implementation-roadmap.md` — gate hiện tại, status, verification log mới nhất.
3. `.claude/workflow/open-questions.md` — câu nào còn chặn forward progress.
4. `.claude/workflow/agent-routing.md` — bảng định tuyến agent/skill.
5. `docs/00-overview.md` — ý đồ project trong một trang.
6. `docs/03-system-boundaries.md` — điều cấm không thương lượng.
7. `docs/agents/01-agent-implementation-rules.md` — kỷ luật mọi agent phải tuân.

## Read tuỳ chọn (chỉ khi gate đang "In progress" hoặc "Waiting for user verification")
Xác định gate đó từ roadmap, rồi đọc thêm doc tương ứng:

| Gate | Doc bổ sung |
|-----:|-------------|
| 1 | `docs/varka-flow/02-issue-1-window-discovery.md` |
| 2 | `docs/varka-flow/08-issue-7-execution-capability-test-plan.md`, `docs/automation/04-background-vs-foreground-strategy.md` |
| 3 | `docs/varka-flow/03-issue-2-lobby-and-npc-click.md` |
| 4 | `docs/varka-flow/04-issue-3-npc-popups.md` |
| 5 | `docs/varka-flow/05-issue-4-event-map-helper-monitoring.md` |
| 6 | `docs/varka-flow/06-issue-5-enter-lobby-flow.md` |
| 7 | `docs/varka-flow/07-issue-6-varka-orchestrator.md`, `docs/varka-flow/10-varka-error-and-retry-policy.md` |

Không đọc trước doc của gate chưa tới.

## Output format (briefing)
Một message Markdown duy nhất, ≤ 30 dòng, theo template:

```
# Briefing

## Project
<1 câu mô tả>

## Trạng thái roadmap
- Gate hiện tại: <N — tên — status>
- Đã Verified: <list hoặc "chưa có">
- Blocked: <list hoặc "không">

## Cần user trả lời để đi tiếp (tối đa 5)
- <câu hỏi #1 từ open-questions.md>
- <câu hỏi #2 ...>

## Boundaries phải nhớ
- <2–3 dòng cô đọng từ docs/03-system-boundaries.md>

## Agent / Skill liên quan đến gate hiện tại
- <list ngắn theo agent-routing.md>

## Tôi có thể bắt đầu ngay bằng
- <gợi ý 1–3 hành động cụ thể, ví dụ: "trả lời câu hỏi mở #1", "khởi động Gate 1 với docs-review">

Yêu cầu cụ thể của bạn?
```

## Quy tắc lazy-load trong suốt conversation
Sau bootstrap, **không** nạp tiếp toàn bộ `docs/`. Nạp khi task khu trú lại:

| Khi user nhắc đến… | Đọc thêm |
|---|---|
| Một gate cụ thể | Gọi skill `docs-review` (bảng map đã có sẵn trong skill đó) |
| Win32 / capture / input | `docs/automation/01-…05-` (chỉ file cần) |
| Vision / template / OCR / hover / timer | `docs/vision/01-…05-` (chỉ file cần) |
| State machine / scheduler / dashboard / lifecycle | `docs/orchestration/01-…04-` |
| Một state name (CHECK_LOBBY, FIND_NPC, START_HELPER…) | `docs/varka-flow/09-varka-state-reference.md` |
| Lỗi, retry, cooldown, terminal status | `docs/varka-flow/10-varka-error-and-retry-policy.md` |
| Test / smoke / regression / failure scenario | `docs/testing/01-…05-` |
| Thuật ngữ lạ | `docs/02-glossary.md` |
| Cấu hình / runtime data | `docs/architecture/04-config-and-runtime-data.md` |

Quy tắc: **đọc đúng file, không đọc cả thư mục**.

## Allowed outputs
- Đúng một briefing theo template trên.
- Câu hỏi một dòng "Yêu cầu cụ thể của bạn?" ở cuối.
- Khi user trả lời, gọi tiếp skill thích hợp (thường là `docs-review` hoặc một skill gate).

## Forbidden outputs
- Sửa bất kỳ file nào trong project (kể cả workflow doc).
- Tự khởi động một gate — đó là việc của `solution-architect` + skill gate.
- Paste nguyên văn các đoạn dài từ docs.
- Briefing dài hơn ~30 dòng.
- Đọc toàn bộ `docs/` "cho chắc". Lazy-load là bắt buộc.
- Bỏ qua `MEMORY.md` của auto-memory (đã được harness load tự động — Claude phải dùng những gì nhớ được khi soạn briefing).

## Verification command
Không có. Output (briefing) chính là verification — user đọc và xác nhận đúng/sai bằng cách trả lời "Yêu cầu cụ thể của bạn?".

## Stop condition
Sau khi in briefing và hỏi câu duy nhất, **STOP**. Không proactively chạy task tiếp theo.

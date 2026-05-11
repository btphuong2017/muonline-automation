# Định tuyến Agent / Skill (Agent Routing)

Bảng này nói rõ với mỗi loại công việc nên dùng agent / skill nào, và theo thứ tự nào.

## Theo Issue / Gate

| Gate | Issue | Skill (làm thật) | Agent chính | Agent phụ |
|-----:|------:|------------------|-------------|-----------|
| 1 | 1 | `varka-window-discovery` | `windows-automation-engineer` | `python-qa-test-engineer`, `code-reviewer` |
| 2 | 7 | `capability-test-plan` | `windows-automation-engineer` | `python-qa-test-engineer`, `code-reviewer` |
| 3 | 2 | `varka-lobby-npc` | `computer-vision-engineer` + `windows-automation-engineer` | `python-qa-test-engineer`, `code-reviewer` |
| 4 | 3 | `varka-popups` | `computer-vision-engineer` | `windows-automation-engineer`, `code-reviewer` |
| 5 | 4 | `varka-event-helper-monitoring` | `computer-vision-engineer` | `state-machine-orchestrator` (cho hệ thống alert), `code-reviewer` |
| 6 | 5 | `varka-enter-lobby` | `windows-automation-engineer` + `computer-vision-engineer` | `code-reviewer` |
| 7 | 6 | `varka-orchestrator` | `state-machine-orchestrator` | `python-qa-test-engineer`, `code-reviewer` |

## Theo loại yêu cầu của user

| User nói gì | Bắt đầu bằng |
|-------------|--------------|
| **(Lượt đầu của một conversation mới)** | `session-bootstrap` — luôn luôn, trừ khi user có yêu cầu rõ và hẹp ngay câu đầu |
| "Tóm tắt", "ôn lại", "where are we", "status?" | `session-bootstrap` |
| "Bắt đầu gate N" | `session-bootstrap` (nếu chưa briefing) → `docs-review` → `solution-architect` → `incremental-dev-step` (wrapping skill của gate đó) |
| "Plan cho việc X" | `solution-architect` |
| "Implement step này" | `incremental-dev-step` |
| "Review trước khi tôi chạy" | `verification-review` skill **hoặc** `code-reviewer` agent |
| "Update doc cho gate vừa xong" | `technical-docs-keeper` |
| "Tôi không biết bắt đầu từ đâu" | `session-bootstrap` → đợi user trả lời câu hỏi mở |
| "Có an toàn không?" | `code-reviewer` (focus: safety section) |
| "Test này fail, sửa giúp" | `python-qa-test-engineer` (root-cause first) → `incremental-dev-step` |

## Quy tắc cứng

1. **Mọi conversation mới PHẢI bắt đầu bằng `session-bootstrap`** trừ khi user có yêu cầu rõ và hẹp ngay câu đầu (vd. "sửa typo dòng X file Y").
2. **Mọi gate triển khai PHẢI bắt đầu bằng `docs-review`** trước khi viết code, kể cả khi developer "chắc chắn" đã biết rồi.
3. **`verification-review` chạy TRƯỚC khi user chạy lệnh verification** — không sau.
4. **`technical-docs-keeper` chạy SAU khi user xác nhận** xong gate.
5. **`code-reviewer` agent có quyền block** một thay đổi vi phạm boundary an toàn (memory / packet / hook / injection / non-game window).
6. **Không có agent nào được phép chạy 2 gate trong cùng một lần** trừ khi user nói rõ.
7. **Nếu một agent thấy việc sang scope của agent khác**, phải dừng và đề xuất chuyển — không tự xử lý.

## Khi nào KHÔNG dùng agent

- Câu hỏi đơn giản về 1 doc → trả lời trực tiếp, không cần agent.
- Lệnh git status, ls, đọc 1 file → trả lời trực tiếp.
- Sửa typo trong workflow doc → trả lời trực tiếp.
- Bất kỳ thứ gì xong dưới 3 step → không cần `incremental-dev-step` formal flow.

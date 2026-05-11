# Cổng xác nhận (Verification Gates)

Mỗi gate phải có **một lệnh CLI** mà người dùng chạy được trong dưới một phút và phải tự xác nhận trước khi sang gate kế. Không bao giờ gộp nhiều gate trong một bước.

Tham chiếu doc tổng: `.claude/workflow/implementation-roadmap.md` và `.claude/workflow/test-verify-fix-loop.md`.

---

## Gate 1 — Window discovery

**Mục tiêu**
- Phát hiện cửa sổ game và parse thông tin nhân vật.

**Deliverable bắt buộc**
- Lệnh dạng `python -m <app> scan-windows` (tên `<app>` do solution-architect chốt khi setup repo).
- File JSON snapshot tại `.claude/logs/discovered_windows.json`.

**Người dùng xác nhận**
- Số lượng cửa sổ phát hiện đúng với số client đang mở.
- Tên nhân vật, level, master level, resets được parse đúng.
- `hwnd`, `pid`, `rect`, `visible`, `minimised` xuất hiện cho mỗi dòng.
- Cửa sổ minimized được đánh dấu rõ.

**Không đi tiếp khi user chưa xác nhận.**

---

## Gate 2 — Capability matrix (Issue 7)

**Mục tiêu**
- Xác định khả năng background / foreground / minimised cho từng năng lực (capture, hotkey, click, hover, helper toggle, timer monitor…).

**Deliverable bắt buộc**
- Lệnh dạng `python -m <app> capability-test` (cộng thêm `--test N` để chạy lẻ một test, `--mode foreground|background|minimized` để chốt mode).
- Output: `capability_matrix.json` + `capability_summary.md` trong `.claude/logs/capability/`.

**Người dùng xác nhận**
- Bảng tóm tắt phản ánh đúng hành vi thực tế của game (ví dụ: nếu user thấy `Ctrl+T` không mở Event Window khi background → ô đó phải là `FAIL`).
- Quyết định mode khuyến nghị (Full background / Hybrid / Full foreground) hợp lý theo `docs/automation/04-background-vs-foreground-strategy.md`.

**Không đi tiếp khi user chưa xác nhận.**

---

## Gate 3 — Lobby + NPC test

**Mục tiêu**
- Phát hiện lobby và thử hover indicator + ALT + click NPC.

**Deliverable bắt buộc**
- Lệnh dạng `python -m <app> test-lobby-npc --char <name>` và `--no-click` để chạy ở chế độ "đọc mà không bấm".

**Người dùng xác nhận**
- Lobby được nhận diện đúng (label "Waiting Room for Imperial Fort", không có timer panel, không có dialog finish).
- Hover indicator xuất hiện trên các candidate đúng.
- ALT + click mở được dialog Popup 1 trên window được chỉ định.
- Không click nhầm sang window khác.

**Không đi tiếp khi user chưa xác nhận.**

---

## Gate 4 — Popup handling test

**Mục tiêu**
- Phát hiện và bấm Popup 1 ("Enter Varka") và Popup 2 ("Enter"); nhận diện dialog "daily limit".

**Deliverable bắt buộc**
- Lệnh dạng `python -m <app> test-varka-popups --char <name>` (tiền điều kiện: Popup 1 đang mở, ví dụ chạy `test-lobby-npc` trước).

**Người dùng xác nhận**
- Click đúng nút "Enter Varka" trên Popup 1.
- Click đúng nút "Enter" trên Popup 2 (bỏ qua Monster Element và Level).
- Khi xuất hiện dialog "daily limit", flow trả về `DONE_BY_GAME_LIMIT` mà không bấm bừa.
- Không bấm "Leave Varka" hoặc "Close".

**Không đi tiếp khi user chưa xác nhận.**

---

## Gate 5 — Event map + helper monitoring test

**Mục tiêu**
- Nhận diện vào event map, bật helper an toàn, parse timer, phát hiện finish/return lobby.

**Deliverable bắt buộc**
- Lệnh dạng `python -m <app> test-event-helper --char <name> --watch <giây>`.
- Có flag `--no-toggle` để chỉ quan sát.

**Người dùng xác nhận**
- Bot **không** bấm helper khi nó đang ở trạng thái Pause (đang chạy).
- Bot bấm Play khi helper đang Off và xác nhận icon đổi sang Pause.
- Timer parse đúng `MM:SS(N)` và mode (`Standby` / `Time Left` / `Exit Waiting Time`).
- Cảnh báo "time < 30s và còn quái" chỉ kêu khi đúng điều kiện, không spam.
- Finish dialog được nhận diện và bấm Exit, hoặc auto-return về lobby được tính là success.

**Không đi tiếp khi user chưa xác nhận.**

---

## Gate 6 — Enter lobby flow test

**Mục tiêu**
- Khi nhân vật ở ngoài lobby, mở Event Window (Ctrl+T), chọn Imperial Guardian, bấm Enter, đợi vào lobby.

**Deliverable bắt buộc**
- Lệnh dạng `python -m <app> test-enter-lobby --char <name>` (kèm `--dry-run`).

**Người dùng xác nhận**
- Phát hiện đúng "ngoài lobby và ngoài event map và không có popup".
- Ctrl+T mở Event Window (foreground hoặc background tuỳ matrix).
- Chọn Imperial Guardian đúng kể cả khi list cuộn.
- Click Enter chỉ khi nút enabled; nếu disabled thì trả `EVENT_ENTER_NOT_AVAILABLE` mà không retry vô tận.
- Crash/disconnect khi đang loading → trả `NEED_USER_LOGIN` và dừng.

**Không đi tiếp khi user chưa xác nhận.**

---

## Gate 7 — Orchestrator dry run

**Mục tiêu**
- Cooperative scheduler trên nhiều nhân vật. Wire-up tất cả các gate trước. Không sửa logic của các gate đã verified.

**Deliverable bắt buộc**
- Lệnh dạng `python -m <app> start-varka --dry-run` và `--smoke`.

**Người dùng xác nhận**
- `--dry-run` chạy không bấm vào game thật, chứng minh được đường đi qua các state, retry-then-cooldown, `DONE_BY_GAME_LIMIT`, `DONE_MAX_RUNS`.
- `--smoke` chỉ tiến đúng một bước per nhân vật trên window thật để kiểm tra fairness và dashboard.
- `NEED_USER_LOGIN` ở một nhân vật làm dừng toàn session.
- Dashboard hiển thị rõ `current_state`, `completed_count`, `retry_count`, `status`, `last_error`.

**Không bao giờ chạy "real full automation" khi user chưa xác nhận `--smoke`.**

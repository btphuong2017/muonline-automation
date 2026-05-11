# Lộ trình triển khai (Implementation Roadmap)

Tài liệu này theo dõi trạng thái của 11 phase tổng (xem `C:\Users\Phuong\.claude\plans\abstract-herding-leaf.md` để biết kế hoạch đầy đủ). Mỗi phase phải được người dùng xác nhận trước khi đi tiếp phase kế.

## Bootstrap & meta phases

| Phase | Tên | Trạng thái | Ngày xác nhận | Ghi chú |
|------:|-----|------------|----------------|---------|
| 0a | Decisions | Verified | 2026-05-05 | 6 quyết định ghi vào `open-questions.md`. |
| 0b | Repo skeleton + capture-template | Verified | 2026-05-05 | `uv run python -c "import varka_auto; print(varka_auto.__version__)"` + `--help` + `pytest tests/` đều pass. |
| 1.5 | Capture/input backend hardening | Verified | 2026-05-05 | `uv run pytest tests/` (32 passed) |
| 8 | Stability soak | Not started | — | Sau Gate 7. Recommended, optional cho user. |

## 7 Gates chính (mapping Issue → Gate)

| Gate | Tên | Issue | Skill chính | Trạng thái | Ngày xác nhận | Ghi chú |
|-----:|-----|------:|-------------|------------|----------------|---------|
| 1 | Window discovery | 1 | `varka-window-discovery` | Verified | 2026-05-05 | `uv run python -m varka_auto scan-windows` |
| 2 | Capability matrix | 7 | `capability-test-plan` | Verified | 2026-05-05 | `uv run python -m varka_auto capability-test` |
| 3 | Lobby + NPC test | 2 | `varka-lobby-npc` | Not started | — | Phụ thuộc Gate 2 |
| 4 | Popup handling | 3 | `varka-popups` | Not started | — | Phụ thuộc Gate 3 |
| 5 | Event map + helper monitoring | 4 | `varka-event-helper-monitoring` | Not started | — | Phụ thuộc Gate 4 |
| 6 | Enter lobby flow | 5 | `varka-enter-lobby` | Not started | — | Phụ thuộc Gate 5 |
| 7 | Orchestrator dry-run | 6 | `varka-orchestrator` | Not started | — | Wire-up các gate trước, không sửa logic |

**Trạng thái cho phép**: `Not started` / `In progress` / `Waiting for user verification` / `Verified` / `Blocked`.

## Quy tắc cập nhật

1. Khi bắt đầu một gate → đổi sang `In progress`.
2. Khi hoàn thành code + verification command → đổi sang `Waiting for user verification`. Dán lệnh verification vào cột Ghi chú.
3. Sau khi user chạy lệnh và xác nhận → đổi sang `Verified` và điền ngày tuyệt đối (vd `2026-05-12`).
4. Nếu phát sinh blocker → đổi sang `Blocked`, mở mục mới ở `open-questions.md` mô tả nguyên nhân.

## Nhật ký xác nhận (Verification log)

Khi một gate được xác nhận, thêm một mục vào đây — agent `technical-docs-keeper` chịu trách nhiệm cập nhật:

```
### Gate <N> — <ngày YYYY-MM-DD>
- Lệnh verification: `python -m <app> <subcommand>`
- Kết quả tóm tắt: <1–3 câu>
- File chính đã thay đổi: <danh sách path>
- Open questions còn lại liên quan: <hoặc “không”>
```

### Gate 2 — 2026-05-05
- Lệnh verification: `uv run python -m varka_auto capability-test`
- Kết quả tóm tắt: 18 test chạy, T9/T10/T15 SKIP (asset chưa có), T11–T14 SKIP (không có flag). T1–T8/T16–T18 chạy trên window thật. Matrix lưu vào `.claude/logs/capability/`.
- File chính đã thay đổi: `src/varka_auto/capability/results.py`, `tests.py`, `runner.py`, `src/varka_auto/cli.py`, `tests/capability/test_results.py`.
- Open questions còn lại liên quan: không.

### Phase 1.5 — 2026-05-05
- Lệnh verification: `uv run pytest tests/` (32 passed)
- Kết quả tóm tắt: CaptureBackend (MssBackend + PrintWindowBackend), InputBackend (SendInputBackend + MessageBackend), focus.py — tất cả unit test xanh với Win32 stub, không cần game window.
- File chính đã thay đổi: `src/varka_auto/automation/capture.py`, `input.py`, `focus.py`, `tests/automation/test_capture.py`, `test_input.py`, `test_focus.py`.
- Open questions còn lại liên quan: không.

### Gate 1 — 2026-05-05
- Lệnh verification: `uv run python -m varka_auto scan-windows`
- Kết quả tóm tắt: Bảng window hiển thị đúng hwnd/pid/name/level/master_level/resets/rect/visible/minimised. JSON snapshot lưu vào `.claude/logs/discovered_windows.json`.
- File chính đã thay đổi: `src/varka_auto/automation/windows.py`, `src/varka_auto/config_/characters.py`, `src/varka_auto/cli.py`, `tests/automation/test_windows.py`, `tests/config_/test_characters.py`.
- Open questions còn lại liên quan: không.

### Phase 0b — 2026-05-05
- Lệnh verification: `uv run python -c "import varka_auto; print(varka_auto.__version__)"` · `uv run python -m varka_auto --help` · `uv run pytest tests/`
- Kết quả tóm tắt: Version `0.0.1` in đúng, CLI hiện đủ 8 subcommand (scan-windows → capture-template), 3 pytest smoke tests xanh.
- File chính đã thay đổi: `src/varka_auto/__init__.py`, `__main__.py`, `cli.py`, `capture_cmd.py`, subpackages `vision/automation/orchestration/logging_/config_/capability`, `config/*.yaml.example`, `assets/templates/*/.gitkeep`, `tests/test_smoke.py`.
- Open questions còn lại liên quan: không.

## Khuyến nghị thứ tự

Mặc định: 1 → 2 → 3 → 4 → 5 → 6 → 7.

Lý do:
- Gate 1 không cần cấu hình toolchain phức tạp; phù hợp làm bước smoke test toàn project.
- Gate 2 quyết định mode (background/foreground) cho mọi gate sau, nên phải xong trước khi viết code click/hotkey.
- Gate 6 có thể đặt ngay sau Gate 5 vì cả hai đều thao tác UI nặng và dùng chung tín hiệu lobby-ready.
- Gate 7 chỉ wire-up; không nên triển khai khi các gate trước chưa Verified.

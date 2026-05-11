# Varka Auto

Bot tự động hóa sự kiện **Varka (Imperial Guardian)** trong Mu Online trên Windows.

Bot sử dụng screenshot + template matching + Windows input API để thao tác giao diện game.
Không đọc memory game, không chỉnh packet, không can thiệp vào game client.

---

## Yêu cầu hệ thống

- Windows 10 / 11
- Python 3.10+
- [uv](https://github.com/astral-sh/uv) — package manager
- Mu Online đang chạy, cửa sổ game **không minimize**, hiển thị tên nhân vật trong title bar

---

## Cài đặt

```bash
# Cài uv nếu chưa có
pip install uv

# Cài dependencies
uv sync
```

---

## Cấu hình

### `config/characters.yaml`

Khai báo danh sách nhân vật bot sẽ quản lý:

```yaml
characters:
  - display_name: PPGL     # khớp với tên trong title bar cửa sổ game
    enabled: true
    max_runs: 10            # số lần chạy event tối đa mỗi phiên

  - display_name: PPDK
    enabled: true
    max_runs: 10

  - display_name: PPDL
    enabled: false          # bỏ qua nhân vật này
    max_runs: 10
```

> `display_name` phải khớp chính xác (case-sensitive) với tên hiển thị trong title bar cửa sổ Mu Online.

### `config/templates.yaml`

Chứa đường dẫn đến các ảnh template dùng cho computer vision. Thường không cần sửa trừ khi giao diện game thay đổi — xem phần [Cập nhật template](#cập-nhật-template) bên dưới.

---

## Chạy bot

```bash
# Chạy thật — bot tự điều hướng từng nhân vật qua toàn bộ flow
uv run python -m varka_auto start-varka --config config/characters.yaml

# Dry-run — mô phỏng state transitions, không gửi input thật vào game
uv run python -m varka_auto start-varka --dry-run --config config/characters.yaml

# Smoke — chạy 1 tick mỗi nhân vật rồi dừng (kiểm tra nhanh)
uv run python -m varka_auto start-varka --smoke --config config/characters.yaml
```

Nhấn **Esc** bất kỳ lúc nào để dừng khẩn cấp.

---

## Luồng tự động

Bot chạy round-robin, mỗi nhân vật được xử lý một bước rồi yield cho nhân vật tiếp theo — các nhân vật không block lẫn nhau.

```
ENTER_LOBBY → CLICK_NPC → HANDLE_POPUPS → RUN_EVENT → WAIT_COMPLETION
     ↑                                                        │
     └────────────────────────────────────────────────────────┘
                       (lặp lại cho run tiếp theo)
```

| State | Mô tả |
|-------|-------|
| `enter_lobby` | Mở Event Window (Ctrl+T) → chọn Imperial Guardian → vào lobby |
| `click_npc` | Tìm và ALT+click NPC trong lobby để mở dialog |
| `handle_popups` | Click **Enter Varka** (Popup 1) → click **Enter** (Popup 2) |
| `run_event` | Chờ vào event map → kích hoạt Varka Helper |
| `wait_completion` | Poll kết quả event mỗi 5s → handle exit dialog nếu có → về lobby |

### Retry & cooldown

- Mỗi state thất bại → retry tối đa **3 lần** (delay 2s/lần)
- Sau 3 lần thất bại → `RETRY_LATER`: cooldown **30s** rồi tự detect lại state hiện tại

### Kết thúc

| Trạng thái | Ý nghĩa |
|-----------|---------|
| `DONE_MAX_RUNS` | Đã chạy đủ `max_runs` lần |
| `DONE_BY_GAME_LIMIT` | Game báo đã đạt giới hạn ngày (daily limit) |
| `NEED_USER_LOGIN` | Không tìm thấy cửa sổ game → **bot dừng toàn bộ** |

---

## Detect state tự động khi khởi động

Khi bắt đầu, bot tự xác định trạng thái hiện tại của từng nhân vật:

- Đang trong event map + helper đang chạy → bắt đầu từ `WAIT_COMPLETION`
- Đang trong event map + helper chưa bật → bắt đầu từ `RUN_EVENT`
- Popup 1 đang mở → bắt đầu từ `HANDLE_POPUPS`
- Đang trong lobby → bắt đầu từ `CLICK_NPC`
- Ngoài lobby → bắt đầu từ `ENTER_LOBBY`

---

## Các lệnh test & debug

Mỗi gate có lệnh test riêng để kiểm tra từng bước trước khi chạy bot đầy đủ.
Tất cả lệnh test đều hỗ trợ `--no-click` để detect-only (không gửi click thật).

### Quét cửa sổ game
```bash
uv run python -m varka_auto scan-windows
```
Hiển thị danh sách cửa sổ Mu Online đang mở: hwnd, tên char, level, rect.

### Kiểm tra capability (foreground/background input)
```bash
uv run python -m varka_auto capability-test --char PPGL
```
Chạy 18 test xác định loại input nào hoạt động với cấu hình hiện tại.

### Test lobby + NPC
```bash
uv run python -m varka_auto test-lobby-npc --char PPGL --no-click   # chỉ detect
uv run python -m varka_auto test-lobby-npc --char PPGL               # ALT+click NPC
```

### Test popup
```bash
uv run python -m varka_auto test-varka-popups --char PPGL --no-click
uv run python -m varka_auto test-varka-popups --char PPGL
```

### Test event helper
```bash
uv run python -m varka_auto test-event-helper --char PPGL --no-click
uv run python -m varka_auto test-event-helper --char PPGL
```

### Test vào lobby từ ngoài
```bash
uv run python -m varka_auto test-enter-lobby --char PPGL --no-click
uv run python -m varka_auto test-enter-lobby --char PPGL
```

---

## Cập nhật template

Nếu giao diện game thay đổi, cần chụp lại template ảnh:

```bash
# Chụp từ cửa sổ game đang chạy (cần game đang hiển thị UI cần chụp)
uv run python -m varka_auto capture-template \
  --char PPGL \
  --group lobby \
  --slug lobby_label \
  --roi 10,20,200,30       # x,y,width,height tính từ góc trên-trái client area

# Cắt template từ debug frame đã lưu trong .claude/logs/
uv run python -m varka_auto extract-template \
  --source .claude/logs/frame_lobby.png \
  --group npc \
  --slug npc_hover \
  --roi 50,100,40,40
```

Các nhóm template (`--group`): `lobby`, `npc`, `popup`, `event`

---

## Chạy tests

```bash
uv run pytest                       # toàn bộ
uv run pytest tests/ -v             # verbose
uv run pytest tests/ --tb=short     # traceback ngắn
```

---

## Lưu ý

- Cửa sổ game **không được minimize** khi bot đang thực hiện click — bot cần capture màn hình thật.
- Bot có thể chạy ở background (cửa sổ game không cần ở foreground liên tục) nhưng cần bring-to-front khi click.
- Debug overlay và log frame được lưu vào `.claude/logs/`.
- Bot tương tác qua UI thuần túy — không vi phạm quy tắc chống cheat ở cấp độ memory/packet.

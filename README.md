# Varka Auto & Harmory Auto

Bot tự động hóa hai tính năng trong Mu Online trên Windows:

- **Varka Auto** — chạy event Imperial Guardian tự động cho nhiều nhân vật xen kẽ
- **Harmory Auto** — click cố định, capture vùng kết quả, so sánh với expected template, lặp cho tới khi match

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

Nếu dùng `compare_method: per_row_ocr`, cần cài thêm Tesseract OCR engine:

```bash
# Windows — cài Tesseract binary
winget install UB-Mannheim.TesseractOCR
# Sau khi cài, thêm vào PATH hoặc set tesseract_cmd trong config/harmory.yaml
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

### `config/harmory.yaml`

Cấu hình cho tính năng Harmory Auto:

```yaml
harmory:
  click_point:
    x: 580          # tọa độ click (client area, tính từ góc trên-trái cửa sổ game)
    y: 336
  result_roi:
    x: 310          # vùng capture kết quả (client area)
    y: 425
    width: 293
    height: 73
  compare_method: per_row_ocr         # per_row_ocr | per_row_pink | template_match | color_mask_template_match
  num_stat_rows: 3                    # số dòng stat trong result panel
  expected_stat_texts:                # per_row_ocr: text OCR mong muốn mỗi row
    - "Defense Increase +50"          # chạy 'harmory ocr-test' để biết đúng format
    - "Damage Reduction +50"
    - "SD Ratio +5"
  threshold: 0.60                     # 0.33=≥1 dòng, 0.60=≥2 dòng, 1.0=tất cả dòng
  click_delay_ms: 4000                # chờ 4s sau click trước khi capture
  max_attempts: null                  # null = retry vô hạn
  stop_hotkey: F12                    # phím dừng bot (F9-F12, Pause, ScrollLock, Insert, Delete, Escape)
  save_debug_screenshot: true
  # ocr_scale: 4                      # upscale factor (tăng lên 6 nếu OCR không nhận được text)
  # tesseract_cmd: "C:/Program Files/Tesseract-OCR/tesseract.exe"
  # expected_template_path: assets/harmory/expected_result.png  # chỉ cần cho per_row_pink / template_match
```

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

## Harmory Auto

Bot click 1 điểm cố định, chờ 4 giây, capture ROI, kiểm tra kết quả, lặp cho tới khi match hoặc user dừng bằng **F12** (hoặc Ctrl+C).

Chỉ chạy cho **1 nhân vật** được chỉ định khi gọi lệnh.

### Cơ chế phát hiện kết quả (`per_row_ocr`)

Bot chia ROI thành `num_stat_rows` dải ngang (mỗi dải = 1 stat). Với mỗi dải, chạy Tesseract OCR để đọc text, sau đó so sánh với `expected_stat_texts` trong config.

Confidence = số dòng match / tổng số dòng:
- `threshold: 0.33` — chỉ cần ≥1 dòng đúng
- `threshold: 0.60` — cần ≥2/3 dòng đúng
- `threshold: 1.0` — tất cả dòng phải đúng

Ưu điểm so với phương pháp màu sắc: không bị ảnh hưởng bởi màu text hay background — chỉ đọc giá trị thực.

### Calibration (lần đầu hoặc sau khi thay đổi giao diện)

**Bước 1** — Kiểm tra ROI đúng vùng:
```bash
uv run python -m varka_auto harmory capture-roi --char PPIK
```
Mở file PNG in ra, kiểm tra có đúng vùng 3 dòng text không. Nếu sai → điều chỉnh `result_roi` trong `config/harmory.yaml`.

**Bước 2** — Lấy text OCR của kết quả mong muốn:
```bash
# Khi game đang hiển thị kết quả mong muốn (tất cả stats đúng):
uv run python -m varka_auto harmory ocr-test --char PPIK
```
Output sẽ in text mỗi dòng. Copy những dòng đó vào `expected_stat_texts` trong `config/harmory.yaml`.

**Bước 3** — Xác nhận so sánh đúng:
```bash
# Khi game đang hiển thị kết quả mong muốn:
uv run python -m varka_auto harmory ocr-test --char PPIK
# → phải in PASS với confidence >= threshold
```

**Bước 4** — Test click đúng điểm:
```bash
uv run python -m varka_auto harmory click-test --char PPIK
```

### Chạy Harmory Auto

```bash
uv run python -m varka_auto harmory run --char PPIK

# Giới hạn số lần thử:
uv run python -m varka_auto harmory run --char PPIK --max-attempts 50
```

Nhấn **F12** hoặc **Ctrl+C** để dừng an toàn.

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

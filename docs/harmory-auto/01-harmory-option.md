ISSUE 1 — Harmory Auto

MỤC TIÊU
Tự động click vào một điểm cố định trong game client, chờ 1 giây, capture một vùng kết quả đã cấu hình sẵn, so sánh với kết quả mong muốn gồm 3 dòng text màu tím cố định. Nếu kết quả khớp thì log success và chờ user. Nếu chưa khớp thì tiếp tục lặp cho tới khi khớp hoặc user tự dừng bot.

PHẠM VI
Chỉ xử lý:
- Chạy cho 1 character duy nhất do user chỉ định khi command chạy.
- Click vào 1 điểm cố định theo client area của cửa sổ game.
- Capture 1 ROI cố định theo client area của cửa sổ game.
- So sánh ROI với expected result.
- Nếu match thì log success và chuyển sang trạng thái chờ user.
- Nếu chưa match thì retry vô hạn cho tới khi match hoặc user stop.

Không xử lý:
- Multi-character loop.
- Orchestrator phức tạp như Varka.
- Tự suy luận nhiều trạng thái game.
- Điều khiển combat.
- Đọc memory/packet/hook/inject.
- OCR toàn màn hình.

FACTS / REQUIREMENTS
- Click point tính theo client area của game window.
- Capture ROI tính theo client area của game window.
- Kết quả mong muốn là 3 dòng text màu tím, nội dung cố định.
- Khi match, bot log success rồi chờ user.
- Nếu chưa match, bot tiếp tục retry cho tới khi match hoặc user tự dừng.
- Action chỉ chạy cho 1 character được chỉ định qua command.

RECOMMENDED APPROACH
Dùng image-based comparison trong ROI.

Vì kết quả mong muốn là 3 dòng text cố định, màu tím, phương án nên ưu tiên là:

1. User cung cấp/capture một ảnh mẫu expected result.
2. Bot capture ROI sau mỗi lần click.
3. Bot so sánh ROI hiện tại với expected template.
4. Nếu confidence >= threshold thì coi là match.
5. Nếu chưa match thì tiếp tục click.

Không nên dùng OCR làm nguồn quyết định chính ở MVP vì:
- Text trong game thường nhỏ.
- Font có viền/anti-aliasing.
- Màu tím trên nền game có thể làm OCR sai.
- Nội dung đã cố định, nên template/image matching đơn giản và ổn định hơn.

Nếu template matching trực tiếp chưa ổn, dùng thêm bước lọc màu tím:
- Crop ROI.
- Mask các pixel thuộc dải màu tím.
- So sánh mask hiện tại với mask expected.
- Hoặc template match trên ảnh đã lọc màu.

STATE MODEL
Harmory Auto chỉ cần state đơn giản:

- INIT
- DISCOVER_CHARACTER_WINDOW
- VALIDATE_CONFIG
- CLICK_TARGET
- WAIT_AFTER_CLICK
- CAPTURE_RESULT_ROI
- COMPARE_RESULT
- SUCCESS_WAIT_USER
- RETRY_LOOP
- USER_STOPPED
- ERROR

FLOW
1. User chạy command với character cụ thể.
2. Bot discover window theo display_name.
3. Bot validate click_point và result_roi.
4. Bot click vào click_point.
5. Bot chờ 1 giây.
6. Bot capture result_roi.
7. Bot compare với expected template.
8. Nếu match:
   - log success
   - lưu screenshot success nếu cần
   - terminal hiển thị SUCCESS
   - bot dừng action và chờ user
9. Nếu không match:
   - log attempt count / confidence
   - quay lại bước click
10. Nếu user stop:
   - dừng loop an toàn
   - log USER_STOPPED

CONFIG NÊN CÓ
harmory:
- character_required: true
- click_point:
  - x
  - y
  - coordinate_mode: client_area
- result_roi:
  - x
  - y
  - width
  - height
  - coordinate_mode: client_area
- expected_template_path
- compare_method:
  - template_match
  - or color_mask_template_match
- threshold
- click_delay_ms: 1000
- max_attempts: null
- stop_hotkey: required
- save_debug_screenshot: true

COMPARE STRATEGY
Option A — Template matching trực tiếp:
- Best nếu text luôn nằm cùng vị trí trong ROI.
- Dễ implement.
- Cần threshold phù hợp, ví dụ 0.85–0.95 tùy ảnh mẫu.

Option B — Purple color mask + template matching:
- Best nếu nền thay đổi nhưng text tím cố định.
- Lọc vùng màu tím trước khi compare.
- Giảm nhiễu từ background.
- Phù hợp nếu 3 dòng text có màu rất đặc trưng.

Option C — OCR:
- Không khuyến nghị làm chính ở MVP.
- Chỉ dùng fallback/debug nếu template matching không đủ ổn.
- Nếu dùng OCR, phải crop ROI, preprocess màu tím, scale up, rồi validate đúng 3 dòng text cố định.

RECOMMENDED MVP DECISION
Bắt đầu với:
- Template matching trực tiếp trên ROI.
- Nếu fail do background nhiễu, chuyển sang purple color mask + template matching.
- Chưa dùng OCR nếu chưa bắt buộc.

COMMANDS CẦN CÓ ĐỂ VERIFY TỪNG BƯỚC
1. Capture ROI test:
   - Mục tiêu: xác nhận ROI đúng vùng 3 dòng text.
   - Output:
     - lưu ảnh ROI ra file
     - in path ảnh
     - in kích thước ROI

2. Compare test:
   - Mục tiêu: xác nhận expected template có match được với ROI hiện tại không.
   - Output:
     - confidence score
     - pass/fail theo threshold
     - lưu debug image nếu fail

3. Click test:
   - Mục tiêu: xác nhận click_point đúng vị trí cần click.
   - Output:
     - click 1 lần
     - không loop
     - log tọa độ client và absolute nếu cần debug

4. Run loop:
   - Mục tiêu: chạy action thật.
   - Flow:
     - click
     - wait 1s
     - capture
     - compare
     - loop tới khi match hoặc user stop

GỢI Ý COMMAND
- harmory capture-roi --char PPIK
- harmory compare --char PPIK
- harmory click-test --char PPIK
- harmory run --char PPIK

SAFETY RULES
- Vì max_attempts là vô hạn, bắt buộc phải có stop mechanism.
- Bot phải cho user dừng bằng terminal hoặc hotkey.
- Không click nếu không tìm thấy đúng game window của character.
- Không click nếu window/client rect không hợp lệ.
- Không click nếu config thiếu click_point hoặc result_roi.
- Không dùng absolute desktop coordinate làm config chính.
- Mỗi attempt nên log attempt number và confidence score.
- Không spam screenshot mỗi attempt; chỉ lưu debug theo interval hoặc khi user stop/fail.

LOGGING / TERMINAL STATUS
Terminal nên hiển thị:
- character
- action = harmory
- attempt count
- last confidence
- threshold
- elapsed time
- status:
  - RUNNING
  - MATCH_FOUND
  - WAIT_USER
  - USER_STOPPED
  - ERROR

Khi match:
- Log success.
- Lưu screenshot ROI match nếu cần.
- Dừng loop.
- Chuyển state = SUCCESS_WAIT_USER.

AGENT REQUIREMENTS
Agent implement cần có skill:
- Python Windows window targeting
- Client-area coordinate conversion
- Screenshot ROI capture
- OpenCV template matching
- Optional color masking for purple text
- CLI command design
- Stop/hotkey handling
- Logging/debug screenshots

DONE CRITERIA
- Command capture-roi lưu đúng vùng ROI.
- Command compare trả về confidence rõ ràng.
- Command click-test click đúng điểm trong client game.
- Command run lặp đúng flow click → wait 1s → capture → compare.
- Khi 3 dòng text tím khớp expected template, bot log success và chờ user.
- Nếu chưa khớp, bot tiếp tục retry.
- User có thể stop bot an toàn bất cứ lúc nào.
# Vòng lặp Test → Verify → Fix

Mọi bước triển khai phải tuân vòng lặp này. Không có ngoại lệ.

## 9 bước bắt buộc

1. **Đọc doc liên quan** đến bước này (chỉ những doc cần thiết — không nuốt toàn bộ `docs/`).
2. **Tuyên bố scope**: 1 đoạn nói rõ cái gì trong scope, cái gì rõ ràng KHÔNG trong scope.
3. **Liệt kê file sẽ tạo / sửa**: bảng `path → mục đích 1 dòng`.
4. **Triển khai thay đổi nhỏ nhất khả thi**.
5. **Chạy check tại chỗ** (lint / typecheck / unit test). Nếu chưa có toolchain, **nói rõ** và đề xuất bổ sung.
6. **Nếu check fail**:
   - Giải thích nguyên nhân.
   - Sửa **chỉ** file liên quan.
   - Chạy lại check.
   - **Không** dùng `--no-verify`, `--skip-checks`, hay tương tự để vượt qua.
7. **Tạo hoặc cập nhật một (1) lệnh CLI verification** mà người dùng sẽ chạy. Document expected output.
8. **Cập nhật `implementation-roadmap.md`**: gate hiện tại → `Waiting for user verification`, dán lệnh verification vào cột Ghi chú.
9. **Dừng**. In ra:
   ```
   Verification command:
     <lệnh>
   Expected output:
     <mô tả>
   STOP. Vui lòng chạy lệnh và xác nhận trước khi sang gate kế.
   ```

## Quy tắc bổ sung

- **Một gate mỗi lần**. Không gộp gate trừ khi user nói rõ.
- **Một verification command mỗi gate**. Không "chạy 5 lệnh để biết nó pass".
- **Smallest viable change**. Refactor và dọn dẹp ngoài scope là việc của lần khác.
- **Không chạy lệnh chạm vào game thật** thay người dùng nếu chưa được phép trong session này.
- **Không thêm dependency mới** trong khi đang ở vòng lặp này — list ra, để user duyệt, rồi mới install.
- **Hard-coded coordinates / thresholds bị cấm**. Dùng config (`docs/agents/01-agent-implementation-rules.md` rule 5).
- **Mọi click phải verify trước khi bấm** (rule 3): hover indicator cho NPC, helper state cho helper, anchor template cho popup.

## Khi check fail và không tự fix được

Mở mục mới ở `open-questions.md`:
```
### <ngày YYYY-MM-DD> — <mô tả ngắn>
- Gate: <N>
- Triệu chứng: <log/error/screenshot path>
- Đã thử: <danh sách>
- Câu hỏi cho user: <cụ thể, có thể trả lời yes/no hoặc bằng 1 câu>
```
Rồi dừng và hỏi user.

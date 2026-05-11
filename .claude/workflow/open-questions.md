# Câu hỏi mở (Open Questions)

Mọi điều chưa rõ trong khi đọc doc hoặc khi triển khai phải được ghi vào đây thay vì đoán bừa.

## Quy ước

- Mỗi mục có ngày tuyệt đối (`YYYY-MM-DD`).
- Khi resolved, **không xoá** — sửa thành `Resolved (Gate N): <câu trả lời>`.
- Mục cũ hơn 30 ngày mà chưa resolve cần được nhắc lại với user.

---

## Tổng kết quyết định Phase 0a (2026-05-05)

| # | Quyết định | Giá trị |
|---|------------|---------|
| 1 | Python package | `varka_auto` |
| 2 | Toolchain | `uv` |
| 3 | Window title regex | default Asteria MU prefix (config-overridable) |
| 4 | Sample characters | `Char1`–`Char5` placeholder; user tự tạo `config/characters.yaml` |
| 5 | Asset templates | tạo bằng `varka-auto capture-template` ở Phase 0b |
| 6 | Default execution mode | `hybrid` |

---

## Câu hỏi từ vòng init `.claude/`

### 2026-05-05 — Tên Python package / app
- **Bối cảnh**: Tất cả các skill viết lệnh dạng `python -m <app> <subcommand>`, nhưng repo chưa có `pyproject.toml` / `src/`.
- **Câu hỏi**: User muốn tên package là gì? Gợi ý: `mu_varka`, `muonline_varka`, hoặc `imperial_guardian_bot`.
- **Tác động**: Quyết định trước khi bắt đầu Gate 1 để CLI command có hình dạng chính thức.
- **Trạng thái**: **Resolved (Phase 0a, 2026-05-05)**: `varka_auto`.

### 2026-05-05 — Toolchain Python (uv / Poetry / pip + venv)
- **Bối cảnh**: Chưa có `pyproject.toml`, `requirements.txt`, `poetry.lock`, hay `uv.lock`. Hook `verify-after-edit.ps1` chạy `python -m py_compile` nếu `python` có trên PATH.
- **Câu hỏi**: User muốn dùng gì để quản lý dependency? Gợi ý: `uv` (nhanh, một file `pyproject.toml`).
- **Tác động**: Định hình cấu trúc repo, hướng dẫn cài đặt cho future setup gate.
- **Trạng thái**: **Resolved (Phase 0a, 2026-05-05)**: `uv` (single `pyproject.toml`, lockfile tự động).

### 2026-05-05 — Game prefix trong window title
- **Bối cảnh**: `docs/varka-flow/02-issue-1-window-discovery.md` ví dụ với `"Asteria MU - Powered by IGCN"`. Có thể server / client của user khác.
- **Câu hỏi**: Prefix chính xác trong title là gì? Có server nào khác cần hỗ trợ song song không?
- **Tác động**: Cần khi viết regex parser cho Gate 1.
- **Trạng thái**: **Resolved (Phase 0a, 2026-05-05)**: dùng default theo doc — `^Asteria MU - Powered by IGCN - Name: \[(?P<name>[^\]]+)\] Level: \[(?P<level>\d+)\] Master Level: \[(?P<master>\d+)\] Resets: \[(?P<resets>\d+)\]$`. Sẽ verify lại trên window thật ở Gate 1; nếu không khớp, user chỉnh regex trong `config/runtime.yaml`.

### 2026-05-05 — Số lượng nhân vật và display name mẫu
- **Bối cảnh**: Doc nói tối đa 5, nhưng số thực tế và tên hiển thị quyết định format `config/characters.yaml`.
- **Câu hỏi**: User cho mẫu file config (không cần password / thông tin nhạy cảm) hoặc list display name.
- **Tác động**: Verification command Gate 1 cần config thật để có ý nghĩa.
- **Trạng thái**: **Resolved (Phase 0a, 2026-05-05)**: `config/characters.yaml.example` dùng placeholder `Char1...Char5`. User sẽ tự tạo `config/characters.yaml` với tên hiển thị thật khi chuẩn bị verify Gate 1 (file thật được hook `protect-sensitive-files.ps1` bảo vệ khỏi auto-edit của Claude).

### 2026-05-05 — Vị trí asset templates và screenshots tham chiếu
- **Bối cảnh**: `docs/vision/03-template-assets-list.md` liệt kê những asset cần. Hiện chưa có thư mục `assets/`.
- **Câu hỏi**: User đã có ảnh template / screenshot tham chiếu chưa, hoặc cần tự chụp khi vào lobby?
- **Tác động**: Vision skill (Gate 3, 4, 5, 6) phụ thuộc trực tiếp.
- **Trạng thái**: **Resolved (Phase 0a, 2026-05-05)**: build subcommand `varka-auto capture-template --char <n> --group <g> --slug <s> --roi x,y,w,h` ở Phase 0b. Mỗi gate vision (3–6) liệt kê template cần crop trước khi chạy. Giải vòng "đoán ROI sai → vision fail".

### 2026-05-05 — Mode chạy mặc định
- **Bối cảnh**: `docs/automation/04-background-vs-foreground-strategy.md` khuyến nghị "hybrid". Nhưng nếu user dùng máy chạy single-monitor thì foreground gây cản trở dùng máy.
- **Câu hỏi**: User ưu tiên mode nào nếu phải chọn (full background / hybrid / full foreground)?
- **Tác động**: Capability test (Gate 2) sẽ vẫn chạy đầy đủ, nhưng kết quả sẽ định hướng mặc định khi orchestrator wire-up (Gate 7).
- **Trạng thái**: **Resolved (Phase 0a, 2026-05-05)**: `hybrid`. Capability matrix (Gate 2) vẫn quyết định cụ thể từng capability dùng background/foreground; `hybrid` chỉ là default chiến lược.

---

(Phần dưới để các câu hỏi phát sinh trong khi triển khai.)

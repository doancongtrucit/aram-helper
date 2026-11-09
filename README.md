# ARAM Helper

Ứng dụng máy tính gợi ý **lõi (augment)** và **trang bị** cho tướng bạn đang chơi trong **ARAM Hỗn Loạn**
(Liên Minh Huyền Thoại). Nguồn dữ liệu: [playaram.gg](https://playaram.gg).

![ARAM Helper](docs/images/main-window.png)

- Tự nhận tướng khi vào trận (Live Client API chính thức của Riot).
- Lõi Kim Cương / Vàng / Bạc (top 8 + xem thêm), combo lõi kèm lý do, build trang bị, giày, phép bổ trợ.
- Đánh dấu lõi đã chọn → gợi ý lõi hợp combo cho lượt sau.
- **Windows**: tự đọc 3 lõi đang được đưa ra trên màn hình, overlay gọn trên game, phím tắt khi đang chơi.
- **macOS**: cửa sổ chính (chưa có đọc màn hình / overlay).

![Overlay trên game](docs/images/overlay-ingame.png)

## Cài đặt
| | |
|---|---|
| **Windows 10/11** | Tải mã nguồn (Code → Download ZIP), giải nén, bấm đúp **`install-windows.bat`** → mở shortcut **ARAM Helper** |
| **macOS 11+** | Tải mã nguồn, mở Terminal tại thư mục: **`bash install-macos.sh`** → mở **ARAM Helper** trong `~/Applications` |

Cần Python 3.10+ (script cài tự kiểm tra và hướng dẫn nếu thiếu).

📖 **Hướng dẫn đầy đủ:** [HUONG_DAN.md](HUONG_DAN.md) – cài đặt, cách dùng, hiệu chỉnh đọc màn hình, overlay,
phím tắt, xử lý sự cố.
🛠 **Phát triển:** [CONTRIBUTING.md](CONTRIBUTING.md) – cấu trúc code, quy tắc, cách chạy test.

## Chạy thủ công
```
python -m venv .venv && .venv\Scripts\activate      # macOS: source .venv/bin/activate
pip install -r requirements.txt
python app.py                  # tuỳ chọn: --no-overlay, --champion yasuo
```

## Nhẹ
Giao diện tkinter (có sẵn trong Python), không cần trình duyệt. Đo trên màn 2560×1440: ~65–80 MB RAM,
CPU ~0 khi ngoài trận, ~6% một nhân khi đang quét trong trận.

## Lưu ý
- App **chỉ đọc** (Live Client API + ảnh chụp màn hình): không đọc/ghi bộ nhớ game, không gửi phím/chuột vào game,
  không tự chọn lõi. Dùng công cụ bên thứ ba do bạn tự cân nhắc theo chính sách hiện hành của Riot.
- Phần đọc màn hình mới được kiểm bằng ảnh giả lập; nếu đọc sai trong game thật, hãy mở issue kèm ảnh chụp
  màn hình lúc chọn lõi.
- Không liên kết với Riot Games.

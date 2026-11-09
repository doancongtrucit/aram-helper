# Guideline phát triển

## Môi trường
```
python -m venv .venv
.venv\Scripts\activate            # macOS: source .venv/bin/activate
pip install -r requirements.txt
python tests/fetch_fixtures.py    # tải trang mẫu playaram.gg cho test (không commit)
python -m unittest discover -s tests -v
python app.py --champion yasuo    # chạy có log trong Terminal
```

## Cấu trúc
| File | Vai trò |
|---|---|
| `app.py` | Khởi động, `Hub` (trạng thái dùng chung: trận, tướng, lõi đã chọn), phím tắt |
| `desktop.py` | Cửa sổ chính (tkinter) |
| `overlay.py` | Overlay trên game (Windows) |
| `advice.py` | Công thức chấm điểm / xếp hạng lõi – nơi duy nhất chứa logic gợi ý |
| `playaram.py` | Tải + tách dữ liệu playaram.gg, cache `data/` |
| `live_client.py` | Đọc Live Client Data API của Riot |
| `screen_scan.py`, `scanner.py`, `ocr.py` | Chụp màn hình, nhận diện icon, OCR, luồng quét nền (Windows) |
| `hotkeys.py` | Phím tắt toàn cục (Windows) |
| `tests/` | Unit test + `synthetic.py`/`bench_scan.py` (ảnh giả lập để đo độ chính xác nhận diện) |

## Quy tắc
1. **Chỉ đọc, không can thiệp game**: không đọc/ghi bộ nhớ game, không gửi phím/chuột vào game, không tự chọn lõi.
   Chỉ dùng Live Client API chính thức và ảnh chụp màn hình.
2. **Tôn trọng playaram.gg**: chỉ đọc trang HTML công khai, **không** gọi `/api/` (robots.txt chặn);
   giữ cache và giãn cách request (`playaram.MIN_INTERVAL`); không commit/đăng lại dữ liệu hay trang HTML của họ
   (`data/`, `tests/fixture_*.html` đã nằm trong `.gitignore`).
3. **Nhẹ**: app chạy song song với game. Giữ numpy 1 luồng (`OPENBLAS_NUM_THREADS=1`), không quét khi không
   trong trận, không thêm thư viện nặng (Qt/Electron/trình duyệt) cho giao diện. Đo lại RAM/CPU khi đổi phần quét.
4. **Đa nền tảng**: code chỉ chạy trên Windows (`ctypes.windll`, WinRT, overlay, phím tắt) phải được chặn bằng
   `sys.platform == "win32"`; cửa sổ chính phải chạy được trên macOS. Gói chỉ Windows ghi marker trong
   `requirements.txt`.
5. **Không đưa dữ liệu cá nhân vào repo**: không commit `data/`, log, ảnh chụp màn hình thật, đường dẫn máy,
   email, IP... Commit bằng email noreply của GitHub.
6. **Test trước khi commit**: `python -m unittest discover -s tests`. Đổi phần nhận diện thì chạy thêm
   `python tests/bench_scan.py 40` và so độ chính xác với trước.
7. Giao diện, thông báo và comment viết **tiếng Việt**; tên biến/hàm tiếng Anh.

## Thêm / sửa
- playaram.gg đổi giao diện → sửa hàm `parse_*` trong `playaram.py`, chạy lại `fetch_fixtures.py` và test.
- Đổi công thức gợi ý → chỉ sửa `advice.py` (cửa sổ chính và overlay cùng dùng), cập nhật `tests/test_advice.py`.
- Phím tắt mới → thêm vào `keys` trong `app.main()` kèm phím dự phòng.

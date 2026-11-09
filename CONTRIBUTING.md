# Guideline phát triển

## Môi trường
```
python -m venv .venv
.venv\Scripts\activate            # macOS: source .venv/bin/activate
pip install -r requirements.txt
python tests/fetch_fixtures.py    # tải trang mẫu cho test (không commit)
python -m unittest discover -s tests -v
python app.py --champion yasuo    # chạy có log trong Terminal
```

## Cấu trúc
| File | Vai trò |
|---|---|
| `app.py` | Khởi động, `Hub` (trạng thái dùng chung: trận, tướng, lõi đã chọn), phím tắt |
| `desktop.py` | Cửa sổ chính (tkinter): 2 cột lõi \| trang bị, tự vừa cửa sổ, zoom, tìm tướng nhanh |
| `settings.py`, `settings_ui.py` | Tuỳ chọn (`data/settings.json`, `on_change` báo các phần đang chạy) + hộp thoại Cài đặt |
| `i18n.py`, `localize.py` | Chuỗi giao diện Anh / Việt (`T("chuỗi tiếng Việt")`) + đổi tên lõi / đồ / tướng theo ngôn ngữ |
| `overlay.py` | Overlay trên game (Windows) |
| `advice.py` | Công thức chấm điểm / xếp hạng lõi – nơi duy nhất chứa logic gợi ý lõi |
| `counter_items.py` | Phân tích đội hình + trang bị địch → 2 dòng gợi ý đồ (luật + danh sách tướng hồi máu / khống chế) |
| `esp32_link.py` | Đẩy tóm tắt trận lên màn ARAM của PC Control Deck (ESP32) qua Wi-Fi UDP; cấu hình `data/esp32.json` |
| `ddragon.py` | Dữ liệu tướng / trang bị / phép chính thức của Riot (Data Dragon vi_VN, en_US), rút gọn, cache `data/ddragon*.json` |
| `playaram.py` | Tải + tách dữ liệu từ trang nguồn, cache `data/` |
| `live_client.py` | Đọc Live Client Data API của Riot |
| `screen_scan.py`, `scanner.py`, `ocr.py` | Chụp màn hình, nhận diện icon, OCR, luồng quét nền (Windows) |
| `hotkeys.py` | Phím tắt toàn cục (Windows) |
| `diag.py` | Log chẩn đoán bộ quét + ảnh vùng quét khi gần khớp / hiệu chỉnh lỗi / Ctrl+Alt+D (`data/debug/`, giữ 30 ảnh) |
| `tests/` | Unit test + `synthetic.py`/`bench_scan.py` (ảnh giả lập để đo độ chính xác nhận diện) |
| `paths.py`, `version.py`, `updater.py` | Thư mục dữ liệu (mã nguồn: `data/`, bản cài: `%LOCALAPPDATA%\ARAM Helper`), số phiên bản, báo bản mới |
| `packaging/`, `tools/build.py`, `.github/workflows/release.yml` | Đóng gói PyInstaller + bộ cài Inno Setup, build tự động khi tạo tag |
| `tools/make_screenshots.py` | Tạo lại ảnh trong `docs/images/` từ dữ liệu mẫu + màn chọn lõi giả lập (không chụp màn hình thật) |

## Quy tắc
1. **Chỉ đọc, không can thiệp game**: không đọc/ghi bộ nhớ game, không gửi phím/chuột vào game, không tự chọn lõi.
   Chỉ dùng Live Client API chính thức và ảnh chụp màn hình.
2. **Tải dữ liệu nhẹ nhàng**: chỉ đọc trang HTML công khai, **không** gọi `/api/` (robots.txt chặn);
   giữ cache và giãn cách request (`playaram.MIN_INTERVAL`); không commit dữ liệu hay trang HTML đã tải
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
7. Giao diện, thông báo và comment viết **tiếng Việt**; tên biến/hàm tiếng Anh. Chuỗi hiện lên giao diện bọc
   trong `T("…")` và thêm bản tiếng Anh vào `i18n.EN` (test `test_settings_i18n` + kiểm tra đủ khoá).

## Thêm / sửa
- Trang nguồn đổi giao diện → sửa hàm `parse_*` trong `playaram.py`, chạy lại `fetch_fixtures.py` và test.
- Đổi công thức gợi ý → chỉ sửa `advice.py` (cửa sổ chính và overlay cùng dùng), cập nhật `tests/test_advice.py`.
- Phím tắt mới → thêm vào `keys` trong `app.main()` kèm phím dự phòng.
- Tuỳ chọn mới → thêm khoá vào `settings.DEFAULTS`, ô điều khiển trong `settings_ui.py`, phần dùng nó đọc
  `settings.get()` (đổi ngay thì đăng ký `settings.on_change`).

## Phát hành bản mới
1. Tăng `__version__` trong `version.py` (vd. `1.2.0`), cập nhật tài liệu nếu cần, commit.
2. Tạo tag cùng số và push: `git tag v1.2.0 && git push origin main v1.2.0`.
3. GitHub Actions (`release.yml`) chạy test, build `Setup.exe` + bản portable (Windows) + `.app` (macOS),
   rồi tạo Release kèm các file. App của người dùng sẽ hiện nút **Có bản mới** trong vòng 1 ngày.

Build thử trên máy (Windows):
```
python -m venv build/venv
buildenv\Scripts\python -m pip install -r requirements.txt pyinstaller
buildenv\Scripts\python tools/build.py        # → dist/ (có Inno Setup 6 thì thêm Setup.exe)
```
Đổi icon: sửa `tools/make_icon.py` rồi chạy lại (tạo `assets/icon.png`, `assets/icon.ico`).

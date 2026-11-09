# Phát triển ARAM Helper

Tài liệu cho người sửa mã nguồn. Người dùng cuối chỉ cần [hướng dẫn sử dụng](docs/USER_GUIDE.md).

## Môi trường

Python 3.10+ (CI dùng 3.13), Windows để chạy đủ tính năng (macOS chỉ có cửa sổ chính).

```
python -m venv .venv
.venv\Scripts\activate                      # macOS: source .venv/bin/activate
pip install -r requirements.txt
python tests/fetch_fixtures.py              # tải trang mẫu cho test (không commit)
python -m unittest discover -s tests -v
python src/app.py --champion yasuo          # chạy từ mã nguồn, log in ra Terminal
```

Tuỳ chọn khi chạy: `--champion <slug>` mở thẳng 1 tướng, `--no-overlay` tắt overlay.
Chạy từ mã nguồn thì dữ liệu nằm ở `data/` trong repo; đặt `ARAM_HELPER_DATA=<thư mục>` để dùng thư mục khác.

## Cấu trúc thư mục

```
aram-helper/
├── src/                 mã nguồn (import phẳng: import advice, import settings…)
├── tests/               unit test, ảnh giả lập (synthetic.py), đo độ chính xác (bench_scan.py)
├── tools/               build.py (đóng gói), make_screenshots.py (ảnh tài liệu), make_icon.py (SVG → PNG / ICO)
├── packaging/           PyInstaller spec, bộ cài Inno Setup
├── assets/              icon app (icon.svg là bản gốc; icon.png / icon.ico xuất bằng tools/make_icon.py)
├── docs/                hướng dẫn sử dụng + ảnh minh hoạ
└── .github/workflows/   build và phát hành tự động
```

| Module (`src/`) | Vai trò |
|---|---|
| `app.py` | Điểm vào, `Hub` (trạng thái dùng chung: trận, tướng, lõi đã chọn), phím tắt |
| `desktop.py` | Cửa sổ chính (tkinter): lõi \| trang bị, zoom, tìm tướng nhanh |
| `overlay.py` | Overlay trên game (Windows) |
| `settings.py`, `settings_ui.py` | Tuỳ chọn (`settings.json`, `on_change`) + hộp thoại Cài đặt |
| `i18n.py`, `localize.py` | Chuỗi giao diện Anh / Việt (`T("chuỗi tiếng Việt")`), đổi tên lõi / đồ / tướng theo ngôn ngữ |
| `advice.py` | Chấm điểm / xếp hạng lõi – nơi duy nhất chứa logic gợi ý lõi |
| `counter_items.py` | Phân tích đội hình + trang bị địch → 2 dòng gợi ý đồ |
| `screen_scan.py`, `scanner.py`, `ocr.py` | Chụp màn hình, nhận diện icon, OCR tên lõi, luồng quét nền (Windows) |
| `playaram.py`, `ddragon.py`, `live_client.py` | Nguồn dữ liệu: playaram.gg, Riot Data Dragon, Live Client Data API |
| `esp32_link.py` | Gửi tóm tắt trận lên màn ARAM của PC Control Deck (UDP) |
| `paths.py`, `version.py`, `updater.py` | Thư mục dữ liệu, số phiên bản, kiểm tra bản mới |
| `hotkeys.py`, `diag.py` | Phím tắt toàn cục (Windows), log + ảnh chẩn đoán bộ quét |

## Quy ước

- **Tên file, thư mục, nhánh, commit: tiếng Anh.** Commit theo [Conventional Commits](https://www.conventionalcommits.org/):
  `feat: …`, `fix: …`, `docs: …`, `refactor: …`, `build: …`, `ci: …`, `test: …`, `chore: …`.
- Tên biến / hàm tiếng Anh. Giao diện và tài liệu người dùng viết tiếng Việt; chuỗi hiện lên giao diện bọc trong
  `T("…")` và thêm bản tiếng Anh vào `i18n.EN`.
- Code chỉ chạy trên Windows (`ctypes.windll`, WinRT, overlay, phím tắt) phải chặn bằng `sys.platform == "win32"`;
  cửa sổ chính phải chạy được trên macOS. Gói chỉ Windows ghi marker trong `requirements.txt`.

## Nguyên tắc

1. **Chỉ đọc, không can thiệp game**: không đọc/ghi bộ nhớ game, không gửi phím/chuột vào game, không tự chọn lõi.
   Chỉ dùng Live Client API chính thức và ảnh chụp màn hình.
2. **Tải dữ liệu nhẹ nhàng**: chỉ đọc trang HTML công khai, **không** gọi `/api/` (robots.txt chặn); giữ cache và
   giãn cách request (`playaram.MIN_INTERVAL`).
3. **Nhẹ**: app chạy song song với game. Giữ numpy 1 luồng, không quét khi không trong trận, không thêm thư viện
   giao diện nặng. Đo lại RAM / CPU khi đổi phần quét.
4. **Không đưa dữ liệu cá nhân vào repo**: không commit `data/`, log, ảnh chụp màn hình thật, đường dẫn máy,
   email, IP… Commit bằng email noreply của GitHub.
5. **Test trước khi commit**: `python -m unittest discover -s tests`. Đổi phần nhận diện thì chạy thêm
   `python tests/bench_scan.py 40` và so độ chính xác với trước.

## Sửa thường gặp

- Trang nguồn đổi giao diện → sửa hàm `parse_*` trong `playaram.py`, chạy lại `fetch_fixtures.py` và test.
- Đổi công thức gợi ý → chỉ sửa `advice.py` (cửa sổ chính, overlay, ESP32 cùng dùng), cập nhật `tests/test_advice.py`.
- Phím tắt mới → thêm vào `keys` trong `app.main()` kèm phím dự phòng.
- Tuỳ chọn mới → thêm khoá vào `settings.DEFAULTS`, ô điều khiển trong `settings_ui.py`; phần dùng nó đọc
  `settings.get()` (cần đổi ngay thì đăng ký `settings.on_change`). File cài đặt chỉ lưu giá trị khác mặc định;
  đổi mặc định cần áp lại cho người dùng cũ thì tăng `settings.VERSION` và xử lý trong `_load()`.
- Ảnh tài liệu → `python tools/make_screenshots.py` (dữ liệu mẫu + màn chọn lõi giả lập, không chụp màn hình thật).

## Build và phát hành

Build thử trên máy (Windows; có Inno Setup 6 thì tạo thêm `Setup.exe`):

```
python -m venv build/venv
build\venv\Scripts\python -m pip install -r requirements.txt pyinstaller
build\venv\Scripts\python tools/build.py            # → dist/
```

Phát hành:

1. Tăng `__version__` trong `src/version.py`, thêm mục mới vào `CHANGELOG.md`, commit.
2. Tạo tag cùng số và push: `git tag -a v1.2.0 -m "ARAM Helper 1.2.0" && git push origin main v1.2.0`.
3. GitHub Actions (`release.yml`) chạy test, build `Setup.exe` + bản portable (Windows) + `.app` (macOS) rồi tạo
   Release. App của người dùng hiện nút **Có bản mới** trong vòng vài giờ.

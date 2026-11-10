# Changelog

Định dạng theo [Keep a Changelog](https://keepachangelog.com/vi/1.1.0/), đánh số theo
[Semantic Versioning](https://semver.org/lang/vi/).

## [1.8.0] – 2026-11-10

### Thêm
- Overlay: món trong **Lối lên đồ** mà bạn đã có trong trận được làm mờ và có huy hiệu **✓ xanh** nhỏ ở góc icon (đọc từ Live Client API của Riot,
  tự cập nhật khi mua / bán đồ).

### Đã đổi
- Overlay gọn hơn: bỏ tỉ lệ thắng của tướng trên thanh tiêu đề, bỏ tiêu đề "ĐÃ CHỌN" (vẫn hiện icon + tên lõi đã
  chọn) và chú thích "viền xanh: món cốt lõi" ở mục Lối lên đồ.
- Độ đậm khung overlay mặc định 70% (trước 74%); máy đang để đúng mặc định cũ tự chuyển sang 70%.

### Đã sửa
- Cập nhật một chạm: kiểm tra lại "đang trong trận" sau hộp xác nhận và trước khi cài (tải xong mà trận đã bắt đầu
  thì chờ hết trận mới cài); chặn bấm cập nhật lần 2 từ Cài đặt khi hộp xác nhận đang mở; Cài đặt chỉ hiện tiến độ
  khi đang tải.
- Kiểm tra cập nhật lỗi mạng không còn xoá thông tin "có bản mới" đã biết (thử lại sau ~10 phút).
- Tải bộ cài: chỉ chấp nhận HTTPS, xoá file tải dở và bộ cài của các bản cũ trong thư mục tạm, kiểm tra số phiên
  bản; thông báo lỗi ngắn gọn, có bản tiếng Anh.

## [1.7.0] – 2026-11-10

### Thêm
- **Cập nhật một chạm** (Windows, bản cài bằng Setup.exe): nút **⬆ Cập nhật lên …** tải bộ cài, kiểm tra mã băm
  SHA-256 (`SHA256SUMS.txt` đăng kèm mỗi bản phát hành), đóng app, cài im lặng rồi tự mở lại. Không cập nhật khi
  đang trong trận. Bản portable / macOS vẫn mở trang tải.
- **Cài đặt → Chung → Kiểm tra cập nhật**: kiểm tra bản mới ngay, không phải chờ.

## [1.6.0] – 2026-11-10

### Đã đổi
- Giao diện **Cài đặt** mới kiểu app gaming: thanh điều hướng bên trái (trang + mục con, bấm để cuộn tới), nội dung chia
  mục, mỗi dòng có mô tả ngắn; công tắc bật / tắt có hiệu ứng trượt, nhóm nút chọn thay cho nút tròn, cuộn chuột mượt.
  Nút ✕ / phím Esc để đóng, **↺ Mặc định** ở đầu trang.
- Thanh trượt mảnh có núm tròn trắng; font chữ toàn app đổi sang **Inter** (đi kèm app, SIL OFL) – chữ tròn,
  dễ đọc như các app chat / gaming. Máy nạp font lỗi thì tự dùng font hệ thống.

### Đã gỡ
- Tính năng gửi màn ARAM lên ESP32 (PC Control Deck): bỏ module, thẻ **ESP32** trong Cài đặt và mục hướng dẫn.
  File `esp32.json` cũ trong thư mục dữ liệu (nếu có) không còn được dùng – xoá được.

## [1.5.0] – 2026-11-09

### Thêm
- **Giữ focus cho game**: nếu một cửa sổ ARAM Helper vô tình lấy focus khỏi game khi đang chơi, app trả focus về
  game ngay (~¼ giây) và ghi vào `app.log` cửa sổ nào đã lấy – gói báo lỗi sẽ chỉ ra nguyên nhân. Người chơi chủ động
  chuyển sang app (Alt+Tab, bấm vào app) thì không bị trả về. Bật / tắt trong Cài đặt → Chung.

### Đã sửa
- Mở app khi game đang chạy làm game mất focus một lần (lúc tạo cửa sổ overlay): giờ trả focus lại ngay.

## [1.4.3] – 2026-11-09

### Đã sửa
- **Bị văng khỏi game sau khi chọn lõi (1 màn hình)**: overlay hiện / ẩn / đưa lên trên cùng bằng lệnh của tkinter
  (deiconify, lift, -topmost) làm overlay lấy focus của game; khi nhãn trên thẻ lõi ẩn đi sau lượt chọn, Windows
  chuyển focus sang cửa sổ chính ARAM Helper nên nó nhảy lên che game. Giờ dùng lệnh Windows không kích hoạt cửa sổ
  (SW_SHOWNOACTIVATE, SWP_NOACTIVATE) – overlay không bao giờ lấy focus của game.

## [1.4.2] – 2026-11-09

### Thay đổi
- Cửa sổ chính chỉ để **xem và tìm kiếm**: bỏ thanh "Lõi đã chọn", bấm thẻ lõi không còn đánh dấu đã chọn, bỏ nhãn
  "hợp combo" và nút "Đã chọn" trong ô gợi ý, tab Combo không tô theo lõi đã chọn. Ghi nhận lõi đã lấy và gợi ý
  combo lúc chọn lõi vẫn chạy trên overlay.

### Đã sửa
- Gợi ý trên overlay nhảy qua lại mỗi giây khi một thẻ lúc đọc được tên (OCR), lúc không ("1 trong N lõi"):
  giữ kết quả đã đọc được tên cho tới khi thẻ đổi thật.
- Cửa sổ chính vẽ lại cả trang (giật / nhảy) mỗi khi đồ của đội địch đổi hoặc ghi nhận lõi mới: giờ chỉ vẽ lại
  khối "đồ theo đội địch".

## [1.4.1] – 2026-11-09

### Thêm
- **Tạo gói báo lỗi** (Cài đặt → Giới thiệu): file zip gồm log, ảnh chẩn đoán, vị trí bảng lõi, cài đặt, thông tin hệ
  thống – tự che đường dẫn thư mục người dùng và địa chỉ IP, không gồm cấu hình ESP32. Kèm mẫu báo lỗi trên GitHub.
- Link tải **luôn trỏ tới bản mới nhất** (`…/releases/latest/download/ARAM-Helper-Setup.exe`) trong README và hướng dẫn;
  mỗi bản phát hành có thêm file tên cố định bên cạnh file kèm số phiên bản. Huy hiệu phiên bản mới nhất / test.

### Phát triển
- Test dùng trang mẫu dựng từ `tests/sample_data.json` (số liệu tự đặt) thay cho trang thật không commit được:
  89/91 test chạy được trên GitHub Actions (trước chỉ ~60%). Thêm workflow chạy test ở mỗi push / pull request;
  bước test báo lỗi nếu quá 2 test bị bỏ qua.
- Phát hành: job macOS có giới hạn thời gian; macOS lỗi / hết máy không còn chặn bản Windows.

## [1.4.0] – 2026-11-09

### Thêm
- **Tự ghi nhận lõi đã chọn**: khi bảng chọn đóng, lõi ở thẻ bạn vừa bấm chuột được đánh dấu đã chọn
  (không cần bấm overlay hay Ctrl+Alt+1/2/3). Tắt trong Cài đặt → Chung.
- **Gợi ý đổi lõi (↻)**: overlay ghi "↻ nên đổi" ở thẻ yếu hơn hẳn mức trung bình của tướng khi nút đổi lõi
  của thẻ đó còn lượt (nhận ra nút đã dùng). Tắt trong Cài đặt → Overlay.
- **Thông tin bản quyền**: LICENSE (All rights reserved), THIRD_PARTY_NOTICES.md, trang **Cài đặt → Giới thiệu**
  (phiên bản, developer, email liên hệ, nguồn dữ liệu, giấy phép), dòng bản quyền ở màn chào, trong file exe, bộ cài
  (trang giấy phép khi cài) và bản macOS.

### Thay đổi
- Thanh trên làm lại theo kiểu app gaming: logo, ô tìm kiếm có kính lúp, chip trạng thái trận, công tắc Overlay,
  nút bánh răng; nút "↩ Tướng trong trận" chỉ hiện khi đang xem tướng khác; thanh trạng thái mảnh ở đáy.

### Đã sửa
- Log chẩn đoán không làm hỏng bộ quét khi cửa sổ dòng lệnh không dùng UTF-8.

## [1.3.0] – 2026-11-09

### Thêm
- **Tự định vị bảng lõi**: không cần bấm phím lần đầu – app ước tính vị trí 3 thẻ lõi theo độ phân giải và tự lưu
  ở lượt chọn đầu tiên.
- Bộ quét và overlay bám theo **cửa sổ game**, đọc được khi game chạy ở màn hình phụ.
- **Đổi phím tắt** trong Cài đặt → Phím tắt (có tác dụng ngay).

### Thay đổi
- Nút "Hiệu chỉnh" đổi thành **⌖ Định vị lõi** (có chú thích khi rê chuột).
- Tần suất quét thích ứng: 0,6 giây khi đang chọn lõi, 1,5 giây khi lâu không có lượt chọn (nhẹ CPU hơn).
- Hộp Cài đặt luôn mở ở giữa cửa sổ chính.
- Lỗi trong giao diện được ghi đủ vào `app.log` và hiện thông báo nhỏ (bấm để mở thư mục dữ liệu) thay vì im lặng.
- Tách cửa sổ chính thành `theme.py`, `widgets.py` và `views/` (tìm kiếm, lõi, trang bị, combo) cho dễ bảo trì.

## [1.2.0] – 2026-11-09

### Đã sửa
- Không gợi ý lõi khi bảng chọn có **lõi kỹ năng của tướng** (icon là kỹ năng riêng của từng tướng):
  ô đó giờ được nhận bằng tên (OCR) trên thẻ.
- Hiệu chỉnh thất bại khi một thẻ là lõi kỹ năng tướng: chỉ cần thấy 2 icon, app tự suy ra thẻ thứ 3;
  không còn bắt nhầm vào chữ mô tả hay thanh dưới màn hình.
- Bản exe không ghi được `app.log`.

### Thay đổi
- Icon mới cho toàn bộ app (cửa sổ, overlay, file exe, bộ cài, shortcut, bản macOS) và màn chào khi chưa vào trận.
- Cửa sổ chính mặc định hiện **6 lõi** mỗi bậc, bấm **Xem thêm** để xem tiếp (vẫn chọn được "Tự vừa cửa sổ").
- Overlay: bỏ tỉ lệ thắng ở phần **Lối lên đồ** cho gọn.
- Kiểm tra bản mới mỗi 6 giờ thay vì mỗi ngày.
- Chỉ phát hành dạng ứng dụng (Setup.exe, portable, .app); bỏ các script cài bằng Python.
- Hướng dẫn sử dụng viết lại, chuyển vào `docs/USER_GUIDE.md`; mã nguồn chuyển vào `src/`.

## [1.1.1] – 2026-11-09

### Thêm
- Phát hành dạng ứng dụng: bộ cài Windows (không cần admin), bản portable, bản macOS; tự build khi tạo tag.
- Icon app, số phiên bản, báo khi có bản mới, nút mở thư mục dữ liệu.

## [1.1.0] – 2026-11-09

### Thêm
- Hộp **Cài đặt** (Chung / Overlay / ESP32), giao diện **Tiếng Việt / English**.
- Bố cục 2 cột lõi | trang bị, phóng to / thu nhỏ, tìm tướng nhanh.
- Gợi ý đồ theo đội hình và trang bị của đội địch.
- Màn ARAM trên ESP32 (PC Control Deck).

[1.8.0]: https://github.com/doancongtrucit/aram-helper/compare/v1.7.0...v1.8.0
[1.7.0]: https://github.com/doancongtrucit/aram-helper/compare/v1.6.0...v1.7.0
[1.6.0]: https://github.com/doancongtrucit/aram-helper/compare/v1.5.0...v1.6.0
[1.5.0]: https://github.com/doancongtrucit/aram-helper/compare/v1.4.3...v1.5.0
[1.4.3]: https://github.com/doancongtrucit/aram-helper/compare/v1.4.2...v1.4.3
[1.4.2]: https://github.com/doancongtrucit/aram-helper/compare/v1.4.1...v1.4.2
[1.4.1]: https://github.com/doancongtrucit/aram-helper/compare/v1.4.0...v1.4.1
[1.4.0]: https://github.com/doancongtrucit/aram-helper/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/doancongtrucit/aram-helper/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/doancongtrucit/aram-helper/compare/v1.1.1...v1.2.0
[1.1.1]: https://github.com/doancongtrucit/aram-helper/releases/tag/v1.1.1
[1.1.0]: https://github.com/doancongtrucit/aram-helper/commits/v1.1.0

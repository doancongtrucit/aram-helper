# Changelog

Định dạng theo [Keep a Changelog](https://keepachangelog.com/vi/1.1.0/), đánh số theo
[Semantic Versioning](https://semver.org/lang/vi/).

## [Chưa phát hành]

### Thêm
- **Tự ghi nhận lõi đã chọn**: khi bảng chọn đóng, lõi ở thẻ bạn vừa bấm chuột được đánh dấu đã chọn
  (không cần bấm overlay hay Ctrl+Alt+1/2/3). Tắt trong Cài đặt → Chung.
- **Gợi ý đổi lõi (↻)**: overlay ghi "↻ nên đổi" ở thẻ yếu hơn hẳn mức trung bình của tướng khi nút đổi lõi
  của thẻ đó còn lượt (nhận ra nút đã dùng). Tắt trong Cài đặt → Overlay.

- **Thông tin bản quyền**: LICENSE (All rights reserved), THIRD_PARTY_NOTICES.md, trang **Cài đặt → Giới thiệu**
  (phiên bản, developer, nguồn dữ liệu, giấy phép), dòng bản quyền ở màn chào, trong file exe, bộ cài
  (trang giấy phép khi cài) và bản macOS.

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

[1.3.0]: https://github.com/doancongtrucit/aram-helper/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/doancongtrucit/aram-helper/compare/v1.1.1...v1.2.0
[1.1.1]: https://github.com/doancongtrucit/aram-helper/releases/tag/v1.1.1
[1.1.0]: https://github.com/doancongtrucit/aram-helper/commits/v1.1.0

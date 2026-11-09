# Changelog

Định dạng theo [Keep a Changelog](https://keepachangelog.com/vi/1.1.0/), đánh số theo
[Semantic Versioning](https://semver.org/lang/vi/).

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

[1.2.0]: https://github.com/doancongtrucit/aram-helper/compare/v1.1.1...v1.2.0
[1.1.1]: https://github.com/doancongtrucit/aram-helper/releases/tag/v1.1.1
[1.1.0]: https://github.com/doancongtrucit/aram-helper/commits/v1.1.0

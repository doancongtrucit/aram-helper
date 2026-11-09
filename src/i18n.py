# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
"""Giao diện Anh / Việt. Chuỗi tiếng Việt là khoá; T("Thắng {wr}", wr=...) trả bản theo ngôn ngữ đang chọn."""
from __future__ import annotations

import settings

EN = {
    # Thanh trên / trạng thái
    "Đang chờ trận…": "Waiting for a game…",
    "Trong trận: {name}": "In game: {name}",
    "Đang xem: {name}": "Viewing: {name}",
    "Tìm tướng hoặc lõi…": "Search champion or augment…",
    "Gõ tên tướng để chuyển nhanh (↑ ↓ Enter), hoặc tên lõi – nhiều lõi cách nhau dấu phẩy, không cần dấu.":
        "Type a champion to switch (↑ ↓ Enter), or augment names – several separated by commas.",
    "Tướng trong trận": "Back to my champion",
    "Bỏ tướng đang xem, quay lại tướng bạn đang chơi": "Stop viewing this champion and go back to the one you play",
    "Định vị lõi": "Locate augments",
    "Tìm vị trí 3 thẻ lõi trên màn hình. Thường app tự làm ở lượt chọn đầu tiên – chỉ cần bấm khi app đọc sai.":
        "Find the 3 augment cards on screen. The app usually does this on the first pick – only needed if it misreads.",
    "Cài đặt": "Settings",
    "Quét màn hình: {s}": "Screen scan: {s}",
    "Định vị lõi sau {n} giây – mở bảng chọn lõi trong game": "Locating augments in {n} s – open the augment choice in game",
    # Tướng
    "Tỉ lệ thắng {wr}%": "Win rate {wr}%",
    "{n} trận": "{n} games",
    "Bản {v}": "Patch {v}",
    "Dữ liệu {n} phút trước": "Data {n} min ago",
    " (cũ, mạng lỗi)": " (old, network error)",
    "Lõi & trang bị": "Augments & items",
    "Combo lõi ({n})": "Augment combos ({n})",
    "Đang tải dữ liệu {name}…": "Loading {name}…",
    "Vào một trận ARAM Hỗn Loạn để app tự nhận tướng, hoặc tìm tướng ở ô tìm kiếm phía trên.":
        "Start an ARAM Mayhem game and the app picks up your champion, or search a champion above.",
    # Lõi
    "Lõi Kim Cương": "Prismatic", "Lõi Vàng": "Gold", "Lõi Bạc": "Silver",
    "Xem thêm ({n})": "More ({n})", "Thu gọn": "Less",
    "Lõi đã chọn:": "Taken:", "Xoá hết": "Clear",
    "hợp combo {t}": "combo {t} fit", "combo {t}": "combo {t}",
    "Không có dữ liệu": "No data",
    "Đọc từ màn hình · ": "From screen · ",
    "Nên chọn:": "Pick:",
    "Ẩn": "Hide",
    "Một trong (icon giống nhau) – bấm lõi bạn đã chọn:": "One of (same icon) – click the one you took:",
    "Đã chọn": "Taken",
    "Thắng {wr}{extra}": "Win {wr}{extra}",
    "chưa có số liệu": "no data",
    " (chung, mọi tướng)": " (all champions)",
    "  ·  +{b} hợp combo {t}": "  ·  +{b} combo {t}",
    # Trang bị
    "Trang bị gợi ý": "Item builds",
    "Viền xanh = 2 món cốt lõi quyết định hướng build.": "Green border = the 2 core items of the build.",
    "Thắng {wr}%": "Win {wr}%",
    "Chọn {pr}%  ·  {n} trận đủ đồ": "Pick {pr}%  ·  {n} full builds",
    "Hay lên cùng:": "Often with:",
    "Chưa có build.": "No builds yet.",
    "Trang bị khác": "Other items", "Giày": "Boots", "Phép bổ trợ": "Summoner spells",
    "Đồ nên lên theo đội hình + trang bị của đội địch": "Items against the enemy team and their items",
    # Combo
    "Chưa có lối chơi / combo cho tướng này.": "No playstyles / combos for this champion yet.",
    "Hạng combo là đánh giá của biên tập viên, không phải tỉ lệ thắng. Bấm vào lõi để đánh dấu đã chọn; combo chứa lõi đã chọn được tô xanh.":
        "Combo tiers are editor ratings, not win rates (descriptions are in Vietnamese). Click an augment to mark it taken; combos with taken augments turn green.",
    "đã có {n}/{m}": "have {n}/{m}",
    "Đồ khuyên dùng:": "Recommended items:",
    # Overlay
    "GỢI Ý – bấm để đánh dấu đã chọn": "PICK – click to mark as taken",
    "COMBO – viền xanh: đang được đưa ra · viền lam: đã có": "COMBO – green: offered · blue: taken",
    "ĐÃ CHỌN": "TAKEN",
    "LỐI LÊN ĐỒ – viền xanh: món cốt lõi": "BUILDS – green: core items",
    "THEO ĐỘI ĐỊCH": "VS ENEMY TEAM",
    "có {n}/{m}": "have {n}/{m}",
    "1 trong {n}": "1 of {n}",
    # Gợi ý đồ theo đội địch
    "{k}/{n} địch hồi máu": "{k}/{n} enemies heal",
    "{k} địch lên giáp": "{k} enemies stack armor",
    "{k} tướng đỡ đòn": "{k} tanks",
    "{k} địch lên kháng phép": "{k} enemies stack MR",
    "{p}% sát thương phép": "{p}% magic damage",
    "{p}% sát thương vật lý": "{p}% physical damage",
    "{k} tướng khống chế cứng": "{k} hard-CC champions",
    "Đội địch": "Enemy team",
    "Địch:": "Enemy:",
    " – giữ build gợi ý": " – keep the suggested build",
    "{p}% phép": "{p}% magic", "{k} hồi máu": "{k} heal", "{k} đỡ đòn": "{k} tank", "{k} khống chế": "{k} CC",
    # Settings
    "Chung": "General", "Overlay": "Overlay", "ESP32": "ESP32",
    "Ngôn ngữ": "Language",
    "Cỡ giao diện": "UI size",
    "Số lõi mỗi bậc": "Augments per tier",
    "Tự vừa cửa sổ": "Fit window",
    "Cửa sổ chính phản ứng khi đang chọn lõi (tô sáng, ô Nên chọn)":
        "Main window reacts to the augment choice (highlight, Pick box)",
    "Tắt: cửa sổ chính giữ nguyên để xem tổng quát, gợi ý chọn lõi chỉ hiện trên overlay / ESP32.":
        "Off: the main window stays as is for an overview; pick suggestions only show on the overlay / ESP32.",
    "Cửa sổ chính luôn nằm trên": "Main window always on top",
    "Bật overlay": "Show overlay",
    "Độ đậm khung": "Panel opacity",
    "Độ đậm nhãn trên thẻ lõi": "Card label opacity",
    "Cỡ overlay": "Overlay size",
    "Bề rộng khung": "Panel width",
    "Vị trí khung": "Panel position",
    "Kéo thả": "Drag",
    "Trên phải": "Top right", "Trên trái": "Top left", "Dưới phải": "Bottom right", "Dưới trái": "Bottom left",
    "Đặt lại vị trí": "Reset position",
    "Nhãn ★ / #2 / #3 trên thẻ lõi": "★ / #2 / #3 labels on augment cards",
    "Chỉ hiện khung khi đang chọn lõi": "Show the panel only during augment choice",
    "Mục hiển thị": "Sections",
    "Gợi ý lõi": "Augment pick", "Combo": "Combo", "Lõi đã chọn": "Taken augments",
    "Lối lên đồ": "Builds", "Theo đội địch": "Vs enemy team",
    "Số lối lên đồ": "Builds shown",
    "Gửi màn ARAM lên ESP32 (PC Control Deck)": "Send the ARAM screen to the ESP32 (PC Control Deck)",
    "Cần file esp32.json trong thư mục dữ liệu – xem docs/USER_GUIDE.md, mục ESP32.": "Needs esp32.json in the data folder – see docs/USER_GUIDE.md, ESP32 section.",
    "Mặc định": "Defaults", "Đóng": "Close",
    "Phím tắt: Ctrl + / Ctrl - / Ctrl 0 đổi cỡ giao diện.": "Shortcuts: Ctrl + / Ctrl - / Ctrl 0 change the UI size.",
    "Overlay chỉ có trên Windows.": "The overlay is Windows only.",
    "Phím tắt": "Hotkeys",
    "Giới thiệu": "About", "Email": "Email", "Phiên bản {v}": "Version {v}", "Developer": "Developer",
    "Trang dự án": "Project page", "Báo lỗi / góp ý": "Report an issue", "Giấy phép": "License",
    "Thành phần mã nguồn mở": "Open-source components", "Nguồn dữ liệu": "Data sources",
    "thống kê lõi, combo, lối lên đồ": "augment, combo and build statistics",
    "tên, icon tướng / trang bị / phép": "champion / item / spell names and icons",
    "icon lõi": "augment icons",
    "↻ nên đổi": "↻ reroll", "↻ nên đổi thẻ này": "↻ reroll this card", " · ↻ nên đổi": " · ↻ reroll",
    "Tự ghi nhận lõi đã chọn (theo cú bấm chuột lên thẻ khi chọn lõi)":
        "Record the augment you pick automatically (from your click on the card)",
    "Gợi ý thẻ nên đổi lõi (↻) khi cả 3 lõi không tốt": "Suggest which card to reroll (↻) when the offer is weak",
    "Đánh dấu lõi ở thẻ 1": "Mark card 1 as taken", "Đánh dấu lõi ở thẻ 2": "Mark card 2 as taken",
    "Đánh dấu lõi ở thẻ 3": "Mark card 3 as taken",
    "Ẩn / hiện overlay": "Show / hide overlay", "Lưu ảnh chẩn đoán": "Save diagnostic image",
    "Bấm vào ô rồi nhấn tổ hợp phím mới (cần Ctrl hoặc Alt, ví dụ Ctrl+Shift+L). Esc: huỷ · Backspace: về mặc định. Phím bị app khác dùng thì app tự dùng phím dự phòng.":
        "Click a box, then press the new key combination (needs Ctrl or Alt, e.g. Ctrl+Shift+L). Esc: cancel · Backspace: default. If another app holds a key, a fallback is used.",
    "bị app khác dùng – đang dùng {k}": "taken by another app – using {k}",
    "Nhấn tổ hợp phím…": "Press keys…",
    "Cần có Ctrl hoặc Alt": "Needs Ctrl or Alt",
    "Trùng với: {a}": "Already used by: {a}",
    "Gợi ý lõi và trang bị cho ARAM Hỗn Loạn": "Augment and item advice for ARAM Mayhem",
    "Có lỗi nhỏ ở giao diện – đã ghi vào app.log. Bấm để mở thư mục dữ liệu.":
        "A small UI error was logged to app.log. Click to open the data folder.",
    "Có bản mới {v}": "Update {v}",
    "Báo khi có bản mới (tự kiểm tra trên GitHub)": "Tell me about new versions (checks GitHub)",
    "Thư mục dữ liệu": "Data folder", "Mở": "Open",
}

# Dòng trạng thái của bộ quét màn hình (scanner.py giữ tiếng Việt, dịch khi hiển thị)
STATUS = {
    "Đang khởi động bộ quét…": "Starting the scanner…",
    "Sẽ định vị bảng lõi sau {n} giây – mở bảng chọn lõi trong game.": "Locating augments in {n} s – open the augment choice in game.",
    "Đang định vị bảng lõi…": "Locating augments…",
    "Đã ghi nhận lõi đã chọn – chờ lượt chọn tiếp theo.": "Pick recorded – waiting for the next augment choice.",
    "Đang tải danh sách lõi và icon (lần đầu mất khoảng 1 phút)…": "Loading augments and icons (about 1 minute the first time)…",
    "Sẵn sàng.": "Ready.",
    "Sẵn sàng – vị trí bảng lõi sẽ tự xác định ở lượt chọn lõi đầu tiên.":
        "Ready – the augment cards will be located automatically on the first pick.",
    "Đang định vị bảng lõi… (khoảng 10 giây)": "Locating augments… (about 10 s)",
    "Ảnh chụp màn hình bị đen: chuyển game sang chế độ Không viền (Borderless) rồi thử lại.":
        "The screenshot is black: switch the game to Borderless and try again.",
    "Không tìm thấy bảng lõi trên màn hình. Thử lại khi bảng chọn lõi đang hiện rõ.":
        "Could not find the augment cards on screen. Try again while the augment choice is fully visible.",
    "Đã định vị bảng lõi – app sẽ tự đọc lõi mỗi khi bảng chọn hiện ra.":
        "Augments located – the app now reads them whenever the choice shows.",
    "Đã thấy bảng chọn lõi.": "Augment choice found.",
    "Đang quét… (chưa thấy bảng chọn lõi · khớp tốt nhất {best})": "Scanning… (no augment choice yet · best match {best})",
    "Đã lưu ảnh chẩn đoán: {name}": "Saved diagnostic image: {name}",
    "Chờ vào trận để quét.": "Waiting for a game to scan.",
    "Không khởi động được bộ quét: {e}": "Could not start the scanner: {e}",
    "Lỗi": "Error",
}
_STATUS_RE: list | None = None


def lang() -> str:
    return settings.get("lang") or "vi"


def T(text: str, **kw) -> str:
    s = EN.get(text, text) if lang() == "en" else text
    return s.format(**kw) if kw else s


def status(text: str) -> str:
    """Dịch dòng trạng thái của bộ quét (có cả phần số / tên chèn vào)."""
    global _STATUS_RE
    if lang() != "en" or not text:
        return text
    if text in STATUS:
        return STATUS[text]
    if _STATUS_RE is None:
        import re
        _STATUS_RE = []
        for vi, en in STATUS.items():
            if "{" in vi:
                pat = re.escape(vi)
                for name in re.findall(r"\{(\w+)\}", vi):
                    pat = pat.replace(re.escape("{" + name + "}"), f"(?P<{name}>.+?)", 1)
                _STATUS_RE.append((re.compile("^" + pat + "$", re.S), en))
    for rx, en in _STATUS_RE:
        m = rx.match(text)
        if m:
            return en.format(**m.groupdict())
    return text


def ddragon_locale() -> str:
    return "en_US" if lang() == "en" else "vi_VN"

"""Màu, font, hằng số bố cục và logo dùng chung cho cửa sổ chính, hộp Cài đặt, overlay."""
from __future__ import annotations

import re
import sys
import unicodedata

import paths


# ---------- giao diện ----------
BG, PANEL, PANEL2, CARD, LINE = "#0b0d14", "#141826", "#1a2031", "#111524", "#262d40"
TEXT, MUTED, DIMTEXT = "#e6e8ef", "#8a91a8", "#4a5066"
GOOD, OKC, BAD, ACCENT = "#3ddc97", "#f5a53a", "#ef6b6b", "#6aa8ff"
HIT_BG, OWNED_BG = "#12291f", "#14223a"
RARITY = [("prismatic", "Lõi Kim Cương", "#c58cff"), ("gold", "Lõi Vàng", "#f0c35a"), ("silver", "Lõi Bạc", "#b9c3d6")]
RARITY_COLOR = {k: c for k, _, c in RARITY}
TIER_COLOR = {"S+": "#ff8a5c", "S": "#ff8a5c", "A": "#f5c451", "B": "#6aa8ff", "C": MUTED, "D": MUTED}
IS_MAC = sys.platform == "darwin"
FONT, MONO = ("Helvetica Neue", "Menlo") if IS_MAC else ("Segoe UI", "Consolas")
LOW_PICK = 1.5
CARD_MIN_W = 172          # bề rộng tối thiểu 1 thẻ lõi (px ở 100%)
CARD_H = 44               # chiều cao thẻ lõi
CARD_GAP = 6
WIDE_MIN = 640            # từ bề rộng này (px ở 100%): 2 cột lõi | trang bị, xem cùng lúc không phải cuộn


_logos: dict = {}


def app_logo(root, size_px: int):
    """Logo app (assets/icon.png) ở cỡ size_px – dùng chung cho cửa sổ chính, hộp Cài đặt, overlay."""
    key = (id(root), size_px)
    if key not in _logos:
        from PIL import Image, ImageTk
        im = Image.open(paths.RES / "assets" / "icon.png").convert("RGBA")
        _logos[key] = ImageTk.PhotoImage(im.resize((size_px, size_px), Image.LANCZOS), master=root)
    return _logos[key]


def fold(s: str) -> str:
    s = unicodedata.normalize("NFD", s.replace("đ", "d").replace("Đ", "D"))
    return re.sub(r"\s+", " ", "".join(c for c in s if unicodedata.category(c) != "Mn").lower()).strip()

# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
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
HIT_BG = "#12291f"
RARITY = [("prismatic", "Lõi Kim Cương", "#c58cff"), ("gold", "Lõi Vàng", "#f0c35a"), ("silver", "Lõi Bạc", "#b9c3d6")]
RARITY_COLOR = {k: c for k, _, c in RARITY}
TIER_COLOR = {"S+": "#ff8a5c", "S": "#ff8a5c", "A": "#f5c451", "B": "#6aa8ff", "C": MUTED, "D": MUTED}
IS_MAC = sys.platform == "darwin"
FONT, MONO = ("Helvetica Neue", "Menlo") if IS_MAC else ("Segoe UI", "Consolas")
# Font giao diện: Inter (SIL OFL, đi kèm trong assets/fonts) – chữ tròn, hiện đại như các app chat / gaming.
# Chữ đậm dùng Inter SemiBold. Máy nào nạp font lỗi thì dùng FONT của hệ điều hành.
UI_FONT, UI_FONT_SEMI = "Inter", "Inter SemiBold"
FONT_FILES = ("Inter-Regular.ttf", "Inter-SemiBold.ttf")
_ui = {"regular": None, "semi": None}
LOW_PICK = 1.5
CARD_MIN_W = 172          # bề rộng tối thiểu 1 thẻ lõi (px ở 100%)
CARD_H = 44               # chiều cao thẻ lõi
CARD_GAP = 6
WIDE_MIN = 640            # từ bề rộng này (px ở 100%): 2 cột lõi | trang bị, xem cùng lúc không phải cuộn


def _register_font_file(path: str) -> bool:
    """Nạp file font chỉ cho tiến trình này (không cài vào máy, không cần quyền quản trị)."""
    import ctypes
    if sys.platform == "win32":
        FR_PRIVATE = 0x10
        return ctypes.windll.gdi32.AddFontResourceExW(ctypes.c_wchar_p(path), FR_PRIVATE, 0) > 0
    if IS_MAC:
        cf = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
        ct = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreText.framework/CoreText")
        cf.CFURLCreateFromFileSystemRepresentation.restype = ctypes.c_void_p
        cf.CFURLCreateFromFileSystemRepresentation.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long,
                                                               ctypes.c_bool]
        ct.CTFontManagerRegisterFontsForURL.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p]
        raw = path.encode("utf-8")
        url = cf.CFURLCreateFromFileSystemRepresentation(None, raw, len(raw), False)
        return bool(url) and bool(ct.CTFontManagerRegisterFontsForURL(url, 1, None))   # 1 = trong tiến trình
    return False


def load_fonts(root) -> bool:
    """Nạp Inter (1 lần mỗi tiến trình) rồi kiểm tra Tk thấy font; trả True nếu dùng được."""
    if _ui["regular"] is not None:
        return _ui["regular"] != FONT
    from tkinter import font as tkfont
    try:
        for name in FONT_FILES:
            _register_font_file(str(paths.RES / "assets" / "fonts" / name))
        fams = set(tkfont.families(root))
    except Exception:
        fams = set()
    if UI_FONT in fams:
        _ui["regular"] = UI_FONT
        _ui["semi"] = (UI_FONT_SEMI, "normal") if UI_FONT_SEMI in fams else (UI_FONT, "bold")
    else:
        _ui["regular"], _ui["semi"] = FONT, (FONT, "bold")
    return _ui["regular"] != FONT


def family(bold: bool = False, mono: bool = False) -> tuple[str, str]:
    """(họ font, độ đậm) cho tkinter – Inter nếu đã nạp, không thì font hệ thống."""
    if mono:
        return MONO, "bold" if bold else "normal"
    if _ui["regular"] is None:
        return FONT, "bold" if bold else "normal"
    return _ui["semi"] if bold else (_ui["regular"], "normal")


def font(size: int, bold: bool = False, mono: bool = False) -> tuple:
    fam, weight = family(bold, mono)
    return (fam, size, weight)


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

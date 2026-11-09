# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
"""Vùng màn hình của cửa sổ game (Windows): bộ quét và overlay bám theo game, kể cả khi game ở màn hình phụ.

Toạ độ trả về là điểm ảnh thật trên màn hình ảo (có thể âm nếu màn hình phụ nằm bên trái màn hình chính).
Không thấy cửa sổ game (chưa vào trận, game thu nhỏ, macOS) → dùng màn hình chính.
"""
from __future__ import annotations

import sys
import time

_cache: tuple[float, tuple[int, int, int, int]] | None = None
CACHE_S = 2.0
MIN_SIZE = 320                  # nhỏ hơn thế coi như không phải cửa sổ game đang chơi


def _dpi_aware():
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass


def primary() -> tuple[int, int, int, int]:
    """(x, y, w, h) của màn hình chính."""
    import ctypes
    _dpi_aware()
    u = ctypes.windll.user32
    return 0, 0, u.GetSystemMetrics(0), u.GetSystemMetrics(1)


def virtual_screen() -> tuple[int, int, int, int]:
    """(x, y, w, h) bao trọn mọi màn hình – để giữ overlay không trôi ra ngoài."""
    import ctypes
    _dpi_aware()
    u = ctypes.windll.user32
    return u.GetSystemMetrics(76), u.GetSystemMetrics(77), u.GetSystemMetrics(78), u.GetSystemMetrics(79)


def _find_game() -> tuple[int, int, int, int] | None:
    import ctypes
    from ctypes import wintypes
    _dpi_aware()
    u = ctypes.windll.user32
    hwnd = u.FindWindowW("RiotWindowClass", None) or u.FindWindowW(None, "League of Legends (TM) Client")
    if not hwnd or u.IsIconic(hwnd) or not u.IsWindowVisible(hwnd):
        return None
    r = wintypes.RECT()
    if not u.GetClientRect(hwnd, ctypes.byref(r)):
        return None
    pt = wintypes.POINT(0, 0)
    u.ClientToScreen(hwnd, ctypes.byref(pt))
    w, h = r.right - r.left, r.bottom - r.top
    if w < MIN_SIZE or h < MIN_SIZE:
        return None
    return pt.x, pt.y, w, h


def rect(force: bool = False) -> tuple[int, int, int, int]:
    """(x, y, w, h) vùng client của cửa sổ game; không có thì màn hình chính. Nhớ 2 giây (gọi mỗi lần quét)."""
    global _cache
    if sys.platform != "win32":
        return 0, 0, 0, 0
    now = time.time()
    if not force and _cache and now - _cache[0] < CACHE_S:
        return _cache[1]
    try:
        r = _find_game() or primary()
    except Exception:
        r = primary()
    _cache = (now, r)
    return r

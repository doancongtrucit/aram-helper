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


# ---------- chế độ Toàn màn hình ----------
# League ở chế độ Toàn màn hình (exclusive) chiếm riêng màn hình: overlay bị game che nhưng VẪN nhận cú bấm, nên
# bấm chọn lõi trúng overlay vô hình → game thu nhỏ, người chơi văng ra desktop. Overlay chỉ hiện khi Không viền.
FS_CACHE_S = 3.0
QUNS_RUNNING_D3D_FULL_SCREEN = 3
_fs_cache: tuple[float, bool] | None = None


def window_mode(cfg_text: str) -> int | None:
    """WindowMode trong [General] của game.cfg: 0 Toàn màn hình, 1 Cửa sổ, 2 Không viền; None nếu không có."""
    section = ""
    for line in cfg_text.splitlines():
        line = line.strip()
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip().lower()
        elif section == "general" and "=" in line:
            key, _, val = line.partition("=")
            if key.strip().lower() == "windowmode":
                try:
                    return int(val.strip())
                except ValueError:
                    return None
    return None


def _game_cfg_paths(exe: str) -> list[str]:
    """game.cfg nằm ở <League>/Config; exe game ở <League>/Game/League of Legends.exe."""
    import os
    d = os.path.dirname(exe)
    return [os.path.join(os.path.dirname(d), "Config", "game.cfg"), os.path.join(d, "Config", "game.cfg")]


def _game_exe() -> str | None:
    import ctypes
    from ctypes import wintypes
    u, k = ctypes.windll.user32, ctypes.windll.kernel32
    u.FindWindowW.restype = wintypes.HWND
    hwnd = u.FindWindowW("RiotWindowClass", None)
    if not hwnd:
        return None
    pid = wintypes.DWORD()
    u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    k.OpenProcess.restype = wintypes.HANDLE
    h = k.OpenProcess(0x1000, False, pid.value)          # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return None
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(1024)
        if k.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return buf.value
    finally:
        k.CloseHandle(h)
    return None


def _d3d_fullscreen() -> bool:
    """Windows báo đang có app D3D chiếm toàn màn hình (exclusive)."""
    import ctypes
    state = ctypes.c_int(0)
    if ctypes.windll.shell32.SHQueryUserNotificationState(ctypes.byref(state)) != 0:
        return False
    return state.value == QUNS_RUNNING_D3D_FULL_SCREEN


def _cfg_fullscreen() -> bool:
    exe = _game_exe()
    if not exe:
        return False
    for p in _game_cfg_paths(exe):
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                return window_mode(f.read()) == 0
        except OSError:
            continue
    return False


def exclusive_fullscreen(force: bool = False) -> bool:
    """True khi League đang ở chế độ Toàn màn hình (đọc game.cfg của game đang chạy, hoặc Windows báo D3D
    toàn màn hình). Nhớ 3 giây. Không đọc / ghi gì vào game ngoài file cài đặt game.cfg."""
    global _fs_cache
    if sys.platform != "win32":
        return False
    now = time.time()
    if not force and _fs_cache and now - _fs_cache[0] < FS_CACHE_S:
        return _fs_cache[1]
    try:
        fs = _d3d_fullscreen() or _cfg_fullscreen()
    except Exception:
        fs = False
    _fs_cache = (now, fs)
    return fs

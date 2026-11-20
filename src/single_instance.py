# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
"""Chỉ cho chạy một ARAM Helper mỗi phiên đăng nhập (Windows).

Mở thêm lần nữa (vd. app đã tự mở cùng Windows và nằm dưới khay, rồi bấm lối tắt ở Start menu) thì bản mới
không chạy: nó gọi bản đang chạy hiện cửa sổ lên rồi thoát. Hai bản cùng lúc = 2 overlay chồng nhau, 2 bộ quét,
phím tắt chỉ chạy ở 1 bản và cả 2 cùng ghi file cài đặt.
"""
from __future__ import annotations

import sys
import time

MUTEX = "Local\\ARAMHelper.SingleInstance"
ERROR_ALREADY_EXISTS = 183
_handle = None                     # giữ mutex suốt đời tiến trình (Windows tự giải phóng khi thoát)


def acquire(name: str = MUTEX) -> bool:
    """True nếu đây là bản duy nhất (đã giữ mutex). Ngoài Windows luôn True."""
    global _handle
    if sys.platform != "win32":
        return True
    import ctypes
    from ctypes import wintypes as wt
    k = ctypes.windll.kernel32
    k.CreateMutexW.argtypes = [wt.LPVOID, wt.BOOL, wt.LPCWSTR]
    k.CreateMutexW.restype = wt.HANDLE
    h = k.CreateMutexW(None, False, name)
    if not h:
        return True                    # không tạo được mutex: thà chạy còn hơn không mở được app
    if k.GetLastError() == ERROR_ALREADY_EXISTS:
        k.CloseHandle(h)
        return False
    _handle = h
    return True


def release():
    global _handle
    if _handle and sys.platform == "win32":
        import ctypes
        ctypes.windll.kernel32.CloseHandle(_handle)
    _handle = None


def wake_existing(timeout: float = 3.0) -> bool:
    """Bảo bản đang chạy hiện cửa sổ chính (giả lập bấm vào biểu tượng khay). True nếu tìm thấy bản đó."""
    if sys.platform != "win32":
        return False
    import ctypes
    from ctypes import wintypes as wt
    import tray
    u = ctypes.windll.user32
    u.FindWindowW.restype = wt.HWND
    u.FindWindowW.argtypes = [wt.LPCWSTR, wt.LPCWSTR]
    u.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
    end = time.time() + timeout
    while True:                        # bản kia có thể vừa mở, chưa kịp tạo biểu tượng khay
        hwnd = u.FindWindowW(tray.Tray.CLASS, None)
        if hwnd:
            u.AllowSetForegroundWindow(-1)          # ASFW_ANY: cho bản kia được đưa cửa sổ lên trước
            u.PostMessageW(hwnd, tray.WM_TRAY, 1, tray.WM_LBUTTONUP)
            return True
        main = u.FindWindowW(None, "ARAM Helper")       # bản kia không có biểu tượng khay: hiện thẳng cửa sổ
        if main:
            u.ShowWindow(main, 9)                       # SW_RESTORE
            u.SetForegroundWindow(main)
            return True
        if time.time() >= end:
            return False
        time.sleep(0.2)

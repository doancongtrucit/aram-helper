# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
"""Biểu tượng ở khay hệ thống (Windows), viết bằng Win32 qua ctypes – không thêm thư viện.

Chạy ở luồng riêng có vòng nhận thông điệp. Không gọi Tk từ luồng này: mọi cú bấm được đưa vào hàng đợi
`events` ("open" | "settings" | "quit"), cửa sổ chính đọc hàng đợi bằng root.after.
"""
from __future__ import annotations

import atexit
import ctypes
import queue
import sys
import threading
from ctypes import wintypes as wt

IS_WINDOWS = sys.platform == "win32"

WM_DESTROY, WM_CLOSE, WM_NULL, WM_COMMAND = 0x0002, 0x0010, 0x0000, 0x0111
WM_LBUTTONUP, WM_LBUTTONDBLCLK, WM_RBUTTONUP, WM_CONTEXTMENU = 0x0202, 0x0203, 0x0205, 0x007B
WM_TRAY = 0x8000 + 1                                   # WM_APP + 1
NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_INFO = 0x1, 0x2, 0x4, 0x10
NIIF_INFO, NIIF_NOSOUND = 0x1, 0x10
MF_STRING, MF_SEPARATOR, MF_DEFAULT = 0x0, 0x800, 0x1000
TPM_RIGHTBUTTON, TPM_RETURNCMD, TPM_NONOTIFY = 0x2, 0x100, 0x80
IMAGE_ICON, LR_LOADFROMFILE, LR_DEFAULTSIZE = 1, 0x10, 0x40
IDI_APPLICATION = 32512
CMD_OPEN, CMD_SETTINGS, CMD_QUIT = 1, 2, 3

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", wt.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", wt.HINSTANCE), ("hIcon", wt.HICON),
                ("hCursor", wt.HANDLE), ("hbrBackground", wt.HBRUSH), ("lpszMenuName", wt.LPCWSTR),
                ("lpszClassName", wt.LPCWSTR)]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("hWnd", wt.HWND), ("uID", wt.UINT), ("uFlags", wt.UINT),
                ("uCallbackMessage", wt.UINT), ("hIcon", wt.HICON), ("szTip", wt.WCHAR * 128),
                ("dwState", wt.DWORD), ("dwStateMask", wt.DWORD), ("szInfo", wt.WCHAR * 256),
                ("uVersion", wt.UINT), ("szInfoTitle", wt.WCHAR * 64), ("dwInfoFlags", wt.DWORD),
                ("guidItem", ctypes.c_byte * 16), ("hBalloonIcon", wt.HICON)]


def _api():
    u, s, k = ctypes.windll.user32, ctypes.windll.shell32, ctypes.windll.kernel32
    u.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
    u.DefWindowProcW.restype = LRESULT
    u.CreateWindowExW.argtypes = [wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD, ctypes.c_int, ctypes.c_int,
                                  ctypes.c_int, ctypes.c_int, wt.HWND, wt.HMENU, wt.HINSTANCE, wt.LPVOID]
    u.CreateWindowExW.restype = wt.HWND
    u.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
    u.RegisterClassW.restype = wt.ATOM
    u.LoadImageW.argtypes = [wt.HINSTANCE, wt.LPCWSTR, wt.UINT, ctypes.c_int, ctypes.c_int, wt.UINT]
    u.LoadImageW.restype = wt.HANDLE
    u.LoadIconW.argtypes = [wt.HINSTANCE, wt.LPVOID]
    u.LoadIconW.restype = wt.HICON
    u.CreatePopupMenu.restype = wt.HMENU
    u.AppendMenuW.argtypes = [wt.HMENU, wt.UINT, ctypes.c_size_t, wt.LPCWSTR]
    u.TrackPopupMenu.argtypes = [wt.HMENU, wt.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.HWND, wt.LPVOID]
    u.TrackPopupMenu.restype = ctypes.c_int
    u.DestroyMenu.argtypes = [wt.HMENU]
    u.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
    u.SetForegroundWindow.argtypes = [wt.HWND]
    u.DestroyWindow.argtypes = [wt.HWND]
    u.SetMenuDefaultItem.argtypes = [wt.HMENU, wt.UINT, wt.UINT]
    s.Shell_NotifyIconW.argtypes = [wt.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
    k.GetModuleHandleW.restype = wt.HMODULE
    return u, s, k


class Tray:
    """tray = Tray(tip, icon_path, labels); tray.start(); … tray.events.get_nowait() → "open" / "settings" / "quit"."""

    CLASS = "ARAMHelperTray"

    def __init__(self, tooltip: str, icon_path: str | None = None, labels: dict | None = None):
        self.tooltip = tooltip[:127]
        self.icon_path = icon_path
        self.labels = {"open": "Open", "settings": "Settings", "quit": "Quit", **(labels or {})}
        self.events: queue.Queue = queue.Queue()
        self.hwnd = None
        self._nid = None
        self._ready = threading.Event()
        self._proc = None
        self._taskbar_msg = 0

    # ----- dùng từ luồng giao diện -----
    def start(self, wait: float = 2.0) -> bool:
        if not IS_WINDOWS:
            return False
        threading.Thread(target=self._run, daemon=True, name="tray").start()
        self._ready.wait(wait)
        if self.hwnd:
            atexit.register(self.stop)
        return bool(self.hwnd)

    def set_labels(self, labels: dict):
        self.labels.update(labels)

    def notify(self, title: str, text: str):
        """Bong bóng thông báo cạnh khay (Windows 10/11 hiện thành thông báo nhỏ)."""
        if not self._nid:
            return
        n = self._nid
        n.uFlags = NIF_INFO
        n.szInfoTitle, n.szInfo = title[:63], text[:255]
        n.dwInfoFlags = NIIF_INFO | NIIF_NOSOUND
        _api()[1].Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(n))

    def stop(self):
        """Gỡ biểu tượng ngay (không để lại icon 'ma' sau khi thoát) rồi đóng luồng."""
        if self._nid:
            _api()[1].Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._nid))
            self._nid = None
        if self.hwnd:
            _api()[0].PostMessageW(self.hwnd, WM_CLOSE, 0, 0)

    # ----- luồng khay -----
    def _icon(self, u, hinst):
        if self.icon_path:
            h = u.LoadImageW(None, self.icon_path, IMAGE_ICON, 0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE)
            if h:
                return h
        return u.LoadIconW(None, ctypes.c_void_p(IDI_APPLICATION))

    def _add(self):
        n = self._nid
        n.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        return _api()[1].Shell_NotifyIconW(NIM_ADD, ctypes.byref(n))

    def _menu(self, hwnd):
        u = _api()[0]
        m = u.CreatePopupMenu()
        u.AppendMenuW(m, MF_STRING, CMD_OPEN, self.labels["open"])
        u.AppendMenuW(m, MF_STRING, CMD_SETTINGS, self.labels["settings"])
        u.AppendMenuW(m, MF_SEPARATOR, 0, None)
        u.AppendMenuW(m, MF_STRING, CMD_QUIT, self.labels["quit"])
        u.SetMenuDefaultItem(m, CMD_OPEN, 0)
        pt = wt.POINT()
        u.GetCursorPos(ctypes.byref(pt))
        u.SetForegroundWindow(hwnd)            # bắt buộc, không thì menu không tự đóng khi bấm ra ngoài
        cmd = u.TrackPopupMenu(m, TPM_RIGHTBUTTON | TPM_RETURNCMD | TPM_NONOTIFY, pt.x, pt.y, 0, hwnd, None)
        u.PostMessageW(hwnd, WM_NULL, 0, 0)
        u.DestroyMenu(m)
        return {CMD_OPEN: "open", CMD_SETTINGS: "settings", CMD_QUIT: "quit"}.get(cmd)

    def _wndproc(self, hwnd, msg, wp, lp):
        u = _api()[0]
        try:
            if msg == WM_TRAY:
                ev = lp & 0xFFFF
                if ev in (WM_LBUTTONUP, WM_LBUTTONDBLCLK):
                    self.events.put("open")
                elif ev in (WM_RBUTTONUP, WM_CONTEXTMENU):
                    what = self._menu(hwnd)
                    if what:
                        self.events.put(what)
                return 0
            if msg == self._taskbar_msg and self._nid:      # Explorer khởi động lại → gắn lại biểu tượng
                self._add()
                return 0
            if msg == WM_CLOSE:
                u.DestroyWindow(hwnd)
                return 0
            if msg == WM_DESTROY:
                if self._nid:
                    _api()[1].Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._nid))
                    self._nid = None
                u.PostQuitMessage(0)
                return 0
        except Exception as e:                # không để lỗi Python làm sập vòng thông điệp
            print("tray:", repr(e))
        return u.DefWindowProcW(hwnd, msg, wp, lp)

    def _run(self):
        try:
            u, _s, k = _api()
            hinst = k.GetModuleHandleW(None)
            self._proc = WNDPROC(self._wndproc)       # giữ tham chiếu: callback bị thu gom là sập app
            wc = WNDCLASSW(lpfnWndProc=self._proc, hInstance=hinst, lpszClassName=self.CLASS)
            u.RegisterClassW(ctypes.byref(wc))           # đã đăng ký (lần chạy trước trong cùng tiến trình) cũng không sao
            self._taskbar_msg = u.RegisterWindowMessageW("TaskbarCreated")
            hwnd = u.CreateWindowExW(0, self.CLASS, self.CLASS, 0, 0, 0, 0, 0, None, None, hinst, None)
            if not hwnd:
                raise OSError(f"CreateWindowExW lỗi {k.GetLastError()}")
            n = NOTIFYICONDATAW()
            n.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
            n.hWnd, n.uID, n.uCallbackMessage = hwnd, 1, WM_TRAY
            n.hIcon = self._icon(u, hinst)
            n.szTip = self.tooltip
            self._nid = n
            if not self._add():
                raise OSError("Shell_NotifyIconW(NIM_ADD) thất bại")
            self.hwnd = hwnd
        except Exception as e:
            print("tray: không tạo được biểu tượng khay –", repr(e))
            self._ready.set()
            return
        self._ready.set()
        msg = wt.MSG()
        while u.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            u.TranslateMessage(ctypes.byref(msg))
            u.DispatchMessageW(ctypes.byref(msg))
        self.hwnd = None

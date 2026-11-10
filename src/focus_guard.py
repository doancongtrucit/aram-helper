# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
"""Giữ focus cho game (Windows): nếu một cửa sổ của ARAM Helper VÔ TÌNH lấy focus khỏi game, trả focus lại ngay
và ghi vào app.log để biết nguyên nhân.

"Vô tình" = không có phím / chuột nào trong ~0,4 giây trước đó. Người chơi chủ động chuyển sang app (Alt+Tab, bấm
vào app trên thanh tác vụ) luôn có thao tác ngay lúc đó, nên không bị trả về game. Chỉ đọc trạng thái cửa sổ của
Windows; không đọc / gửi gì vào game.
"""
from __future__ import annotations

import os
import sys
import threading
import time

POLL = 0.25
USER_INPUT_MS = 400          # có phím / chuột trong khoảng này trước lúc đổi focus → coi là người chơi chủ động
GAME_CLASS = "RiotWindowClass"


OVERLAY_TITLE = "ARAM Helper overlay"


def decide(prev_is_game: bool, now_is_ours: bool, idle_ms: int, now_is_overlay: bool = False) -> str | None:
    """'return' = trả focus về game; 'user' = người chơi tự chuyển sang app; None = không liên quan.

    Overlay lấy focus thì luôn trả về game, kể cả ngay sau cú bấm: bấm lên overlay (chọn lõi, kéo khung) không bao giờ
    là ý muốn rời game."""
    if not (prev_is_game and now_is_ours):
        return None
    if now_is_overlay:
        return "return"
    return "user" if idle_ms < USER_INPUT_MS else "return"


class FocusGuard:
    def __init__(self, in_game_fn, log=print, enabled_fn=lambda: True):
        self.in_game_fn, self.log, self.enabled_fn = in_game_fn, log, enabled_fn
        self.returned = 0

    def start(self):
        if sys.platform == "win32":
            threading.Thread(target=self._loop, daemon=True, name="focus-guard").start()

    def _loop(self):
        import ctypes
        from ctypes import wintypes as wt
        u, k = ctypes.windll.user32, ctypes.windll.kernel32
        u.GetForegroundWindow.restype = wt.HWND
        u.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
        u.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
        u.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
        u.SetForegroundWindow.argtypes = [wt.HWND]

        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", wt.UINT), ("dwTime", wt.DWORD)]

        me = os.getpid()
        game_hwnd = None
        prev = None

        def cls(h):
            b = ctypes.create_unicode_buffer(128)
            u.GetClassNameW(h, b, 128)
            return b.value

        def ours(h):
            pid = wt.DWORD()
            u.GetWindowThreadProcessId(h, ctypes.byref(pid))
            return pid.value == me

        def idle_ms():
            li = LASTINPUTINFO(ctypes.sizeof(LASTINPUTINFO), 0)
            u.GetLastInputInfo(ctypes.byref(li))
            return (k.GetTickCount() - li.dwTime) & 0xFFFFFFFF

        while True:
            time.sleep(POLL)
            try:
                if not self.in_game_fn():
                    prev = None
                    continue
                fg = u.GetForegroundWindow()
                if fg and cls(fg) == GAME_CLASS:
                    game_hwnd = fg
                if fg != prev:
                    is_ours = bool(fg) and ours(fg)
                    name = ""
                    if is_ours:
                        t = ctypes.create_unicode_buffer(128)
                        u.GetWindowTextW(fg, t, 128)
                        name = t.value or cls(fg)
                    what = decide(prev is not None and prev == game_hwnd, is_ours, idle_ms(),
                                  now_is_overlay=name == OVERLAY_TITLE)
                    if what:
                        if what == "return" and self.enabled_fn() and game_hwnd:
                            u.SetForegroundWindow(game_hwnd)
                            self.returned += 1
                            self.log(f"giữ focus: '{name}' vô tình lấy focus của game → đã trả về game")
                            fg = game_hwnd
                        elif what == "user":
                            self.log(f"giữ focus: người chơi tự chuyển sang '{name}'")
                    prev = fg
            except Exception as e:      # không để luồng phụ làm hỏng app
                self.log(f"giữ focus: lỗi {e!r}")
                time.sleep(2)

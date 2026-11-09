# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
"""Ghi nhận lõi người chơi chọn: trong lúc bảng chọn lõi đang hiện, xem cú bấm chuột trái rơi vào thẻ nào.

Chỉ đọc vị trí con trỏ và trạng thái nút chuột của Windows (GetCursorPos / GetAsyncKeyState) – không đọc
hay gửi gì vào game, không cài hook. Chỉ chạy khi bảng chọn lõi đang hiện; ngoài lúc đó luồng chỉ ngủ.
"""
from __future__ import annotations

import sys
import threading
import time

POLL = 0.04          # 25 lần/giây: một cú bấm chuột thường dài 80–150 ms nên không bị lỡ
IDLE = 0.3


class ClickWatcher:
    def __init__(self):
        self.lock = threading.Lock()
        self.rects: list[tuple[int, int, int, int]] | None = None     # (x0, y0, x1, y1) từng thẻ, toạ độ màn hình
        self.last: tuple[int, float] | None = None                   # (thẻ, thời điểm) của cú bấm cuối
        self._thread = None

    def watch(self, rects):
        with self.lock:
            self.rects = list(rects)
        if sys.platform == "win32" and self._thread is None:
            self._thread = threading.Thread(target=self._loop, daemon=True, name="pick-watch")
            self._thread.start()

    def stop(self):
        with self.lock:
            self.rects = None

    def take(self, since: float) -> int | None:
        """Thẻ được bấm cuối cùng kể từ `since` (rồi xoá); None nếu không bấm thẻ nào."""
        with self.lock:
            last, self.last = self.last, None
        return last[0] if last and last[1] >= since else None

    @staticmethod
    def slot_at(rects, x: int, y: int) -> int | None:
        for i, (x0, y0, x1, y1) in enumerate(rects or []):
            if x0 <= x <= x1 and y0 <= y <= y1:
                return i
        return None

    def _loop(self):
        import ctypes
        from ctypes import wintypes
        u = ctypes.windll.user32
        pt = wintypes.POINT()
        was_down = False
        while True:
            with self.lock:
                rects = self.rects
            if not rects:
                was_down = False
                time.sleep(IDLE)
                continue
            down = bool(u.GetAsyncKeyState(0x01) & 0x8000)        # VK_LBUTTON
            if down and not was_down and u.GetCursorPos(ctypes.byref(pt)):
                i = self.slot_at(rects, pt.x, pt.y)
                if i is not None:
                    with self.lock:
                        self.last = (i, time.time())
            was_down = down
            time.sleep(POLL)

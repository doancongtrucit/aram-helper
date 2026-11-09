"""Phím tắt toàn cục trên Windows (RegisterHotKey) – hoạt động cả khi game đang được chọn.

    hotkeys.start({"calibrate": (["ctrl+alt+a", "ctrl+alt+k"], fn), ...})

Mỗi việc có danh sách phím ưu tiên: phím đầu tiên đăng ký được sẽ được dùng (app khác có thể đã
chiếm một tổ hợp). Phím thực tế nằm trong ACTIVE, vd. {"calibrate": "Ctrl+Alt+K"}.
"""
from __future__ import annotations

import threading
import traceback

MODS = {"alt": 0x1, "ctrl": 0x2, "shift": 0x4, "win": 0x8}
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312

ACTIVE: dict[str, str | None] = {}
_ready = threading.Event()


def _parse(combo: str) -> tuple[int, int]:
    *mods, key = combo.lower().split("+")
    m = MOD_NOREPEAT
    for x in mods:
        m |= MODS[x]
    return m, ord(key.upper())


def pretty(combo: str | None) -> str:
    return "+".join(p.capitalize() if len(p) > 1 else p.upper() for p in combo.split("+")) if combo else "(không có)"


def label(name: str) -> str:
    return pretty(ACTIVE.get(name))


def start(mapping: dict[str, tuple[list[str], callable]], log=print, wait: float = 2.0) -> dict[str, str | None]:
    def loop():
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
        except Exception:
            _ready.set()
            return
        handlers, hid = {}, 0
        for name, (combos, fn) in mapping.items():
            ACTIVE[name] = None
            for combo in combos:
                hid += 1
                mods, vk = _parse(combo)
                if user32.RegisterHotKey(None, hid, mods, vk):
                    handlers[hid] = fn
                    ACTIVE[name] = combo
                    break
            if ACTIVE[name] is None:
                log(f"Không đăng ký được phím tắt cho '{name}' ({', '.join(combos)} đều bị app khác dùng).")
            elif ACTIVE[name] != combos[0]:
                log(f"{pretty(combos[0])} đang bị app khác dùng → dùng {pretty(ACTIVE[name])} thay thế.")
        _ready.set()
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            if msg.message == WM_HOTKEY and msg.wParam in handlers:
                try:
                    handlers[msg.wParam]()
                except Exception:
                    traceback.print_exc()

    threading.Thread(target=loop, daemon=True, name="hotkeys").start()
    _ready.wait(wait)
    return dict(ACTIVE)

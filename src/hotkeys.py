"""Phím tắt toàn cục trên Windows (RegisterHotKey) – hoạt động cả khi game đang được chọn.

    hotkeys.start({"calibrate": (["ctrl+alt+a", "ctrl+alt+k"], fn), ...})
    hotkeys.update("calibrate", ["ctrl+shift+l", "ctrl+alt+a"])     # đổi phím lúc đang chạy

Mỗi việc có danh sách phím ưu tiên: phím đầu tiên đăng ký được sẽ được dùng (app khác có thể đã
chiếm một tổ hợp). Phím thực tế nằm trong ACTIVE, vd. {"calibrate": "ctrl+alt+k"}.
RegisterHotKey gắn với luồng đã đăng ký, nên mọi lần đăng ký lại đều chạy trên luồng phím tắt.
"""
from __future__ import annotations

import threading
import traceback

MODS = {"alt": 0x1, "ctrl": 0x2, "shift": 0x4, "win": 0x8}
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
WM_APP_RELOAD = 0x8000 + 1
KEYS = {f"f{i}": 0x6F + i for i in range(1, 13)}          # F1–F12

# Phím mặc định + phím dự phòng (khi app khác đã chiếm); phím người dùng chọn trong Cài đặt đứng đầu danh sách
DEFAULTS = {
    "calibrate": ["ctrl+alt+a", "ctrl+alt+k", "ctrl+alt+shift+a"],
    "pick1": ["ctrl+alt+1", "ctrl+alt+shift+1"],
    "pick2": ["ctrl+alt+2", "ctrl+alt+shift+2"],
    "pick3": ["ctrl+alt+3", "ctrl+alt+shift+3"],
    "overlay": ["ctrl+alt+o", "ctrl+alt+shift+o"],
    "diagnose": ["ctrl+alt+d", "ctrl+alt+shift+d"],
}

ACTIVE: dict[str, str | None] = {}
_mapping: dict[str, tuple[list[str], callable]] = {}
_ready = threading.Event()
_thread_id: int | None = None
_log = print


def parse(combo: str) -> tuple[int, int]:
    """'ctrl+alt+a' → (modifiers, virtual-key). ValueError nếu không hợp lệ."""
    *mods, key = combo.lower().replace(" ", "").split("+")
    m = MOD_NOREPEAT
    for x in mods:
        if x not in MODS:
            raise ValueError(f"phím bổ trợ lạ: {x}")
        m |= MODS[x]
    if key in KEYS:
        vk = KEYS[key]
    elif len(key) == 1 and key.isalnum():
        vk = ord(key.upper())
    else:
        raise ValueError(f"phím lạ: {key}")
    return m, vk


def valid(combo: str) -> bool:
    """Tổ hợp dùng được làm phím tắt toàn cục: có Ctrl hoặc Alt (tránh chặn phím khi đang gõ / chơi)."""
    try:
        parse(combo)
    except (ValueError, IndexError):
        return False
    mods = combo.lower().split("+")[:-1]
    return "ctrl" in mods or "alt" in mods


def combos_for(name: str, custom: str | None) -> list[str]:
    """Phím người dùng chọn (nếu hợp lệ) rồi tới phím mặc định / dự phòng, không trùng."""
    out = []
    for c in ([custom] if custom and valid(custom) else []) + DEFAULTS.get(name, []):
        if c not in out:
            out.append(c)
    return out


def pretty(combo: str | None) -> str:
    return "+".join(p.capitalize() if len(p) > 1 else p.upper() for p in combo.split("+")) if combo else "(không có)"


def label(name: str) -> str:
    return pretty(ACTIVE.get(name))


def _register_all(user32) -> dict[int, callable]:
    """Huỷ hết rồi đăng ký lại theo _mapping. Chạy trên luồng phím tắt."""
    for hid in range(1, 64):
        user32.UnregisterHotKey(None, hid)
    handlers, hid = {}, 0
    for name, (combos, fn) in _mapping.items():
        ACTIVE[name] = None
        for combo in combos:
            hid += 1
            try:
                mods, vk = parse(combo)
            except (ValueError, IndexError):
                continue
            if user32.RegisterHotKey(None, hid, mods, vk):
                handlers[hid] = fn
                ACTIVE[name] = combo
                break
        if ACTIVE[name] is None:
            _log(f"Không đăng ký được phím tắt cho '{name}' ({', '.join(combos)} đều bị app khác dùng).")
        elif ACTIVE[name] != combos[0]:
            _log(f"{pretty(combos[0])} đang bị app khác dùng → dùng {pretty(ACTIVE[name])} thay thế.")
    return handlers


def start(mapping: dict[str, tuple[list[str], callable]], log=print, wait: float = 2.0) -> dict[str, str | None]:
    global _log
    _log = log
    _mapping.update(mapping)

    def loop():
        global _thread_id
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            _thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        except Exception:
            _ready.set()
            return
        handlers = _register_all(user32)
        _ready.set()
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            if msg.message == WM_APP_RELOAD:
                handlers = _register_all(user32)
                _ready.set()
            elif msg.message == WM_HOTKEY and msg.wParam in handlers:
                try:
                    handlers[msg.wParam]()
                except Exception:
                    traceback.print_exc()

    threading.Thread(target=loop, daemon=True, name="hotkeys").start()
    _ready.wait(wait)
    return dict(ACTIVE)


def update(name: str, combos: list[str], wait: float = 1.0) -> str | None:
    """Đổi danh sách phím của 1 việc lúc đang chạy; trả phím thực tế đăng ký được."""
    if name not in _mapping or _thread_id is None:
        return ACTIVE.get(name)
    _mapping[name] = (combos, _mapping[name][1])
    _ready.clear()
    import ctypes
    ctypes.windll.user32.PostThreadMessageW(_thread_id, WM_APP_RELOAD, 0, 0)
    _ready.wait(wait)
    return ACTIVE.get(name)

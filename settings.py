"""Tuỳ chọn của app (data/settings.json). Đổi ở hộp Settings → áp dụng ngay, các phần đăng ký on_change được báo."""
from __future__ import annotations

import json
import threading
from pathlib import Path

import paths

PATH = paths.DATA / "settings.json"

DEFAULTS = {
    # Chung
    "lang": "vi",                 # vi | en – giao diện + tên lõi/đồ/tướng
    "ui_zoom": 1.0,               # 0.7 – 1.6, phím Ctrl + / Ctrl - / Ctrl 0
    "top_n": 0,                   # số lõi mỗi bậc; 0 = tự vừa cửa sổ (không phải cuộn)
    "app_follow_offer": False,    # cửa sổ chính phản ứng khi bảng chọn lõi hiện ra (tô sáng + ô Nên chọn)
    "always_on_top": False,
    # Overlay
    "overlay": True,
    "ov_opacity": 0.74,
    "ov_badge_opacity": 0.84,
    "ov_scale": 1.0,              # 0.7 – 1.6
    "ov_width": 272,              # px ở tỉ lệ 100%
    "ov_badges": True,            # nhãn ★ / #2 / #3 trên thẻ lõi
    "ov_only_offer": False,       # chỉ hiện khung khi đang chọn lõi
    "ov_show_offer": True,
    "ov_show_combo": True,
    "ov_show_owned": True,
    "ov_show_build": True,
    "ov_show_counter": True,
    "ov_builds": 3,
    "ov_corner": "custom",        # top-right | top-left | bottom-right | bottom-left | custom (kéo thả)
    # ESP32 (PC Control Deck)
    "esp32": True,
    # Cập nhật: mỗi ngày hỏi GitHub 1 lần xem có bản mới không (chỉ báo, không tự tải)
    "check_updates": True,
}

_lock = threading.Lock()
_values: dict | None = None
_listeners: list = []


def _load() -> dict:
    global _values
    if _values is None:
        _values = dict(DEFAULTS)
        try:
            saved = json.loads(PATH.read_text(encoding="utf-8"))
            _values.update({k: v for k, v in saved.items() if k in DEFAULTS})
        except Exception:
            pass
    return _values


def get(key: str):
    with _lock:
        return _load().get(key, DEFAULTS.get(key))


def all_values() -> dict:
    with _lock:
        return dict(_load())


def set_many(changes: dict, save: bool = True):
    with _lock:
        v = _load()
        changed = {k: val for k, val in changes.items() if k in DEFAULTS and v.get(k) != val}
        v.update(changed)
        if save and changed:
            PATH.parent.mkdir(parents=True, exist_ok=True)
            PATH.write_text(json.dumps(v, ensure_ascii=False, indent=1), encoding="utf-8")
    for fn in list(_listeners):
        if changed:
            try:
                fn(changed)
            except Exception as e:
                print("settings listener:", repr(e))
    return changed


def set(key: str, value):  # noqa: A001 – API ngắn gọn: settings.set("lang", "en")
    return set_many({key: value})


def reset(keys=None):
    return set_many({k: DEFAULTS[k] for k in (keys or DEFAULTS)})


def on_change(fn):
    _listeners.append(fn)


def _reset_for_tests(path: Path):
    """Dùng trong test: trỏ sang file tạm và xoá bộ nhớ đệm."""
    global PATH, _values
    PATH, _values = path, None
    _listeners.clear()

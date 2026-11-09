# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
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
    "top_n": 6,                   # số lõi mỗi bậc (bấm "Xem thêm" để mở đủ); 0 = tự vừa cửa sổ
    "app_follow_offer": False,    # cửa sổ chính phản ứng khi bảng chọn lõi hiện ra (tô sáng + ô Nên chọn)
    "always_on_top": False,
    "auto_pick": True,
    "focus_guard": True,          # app vô tình lấy focus khi đang chơi → tự trả focus về game            # tự ghi nhận lõi đã chọn theo cú bấm chuột lên thẻ khi bảng chọn đóng
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
    "reroll_hint": True,          # gợi ý thẻ nên bấm đổi lõi (↻)
    "ov_corner": "custom",        # top-right | top-left | bottom-right | bottom-left | custom (kéo thả)
    # ESP32 (PC Control Deck)
    "esp32": True,
    # Phím tắt toàn cục (Windows); phím dự phòng nằm trong hotkeys.DEFAULTS
    "hk_calibrate": "ctrl+alt+a",
    "hk_pick1": "ctrl+alt+1",
    "hk_pick2": "ctrl+alt+2",
    "hk_pick3": "ctrl+alt+3",
    "hk_overlay": "ctrl+alt+o",
    "hk_diagnose": "ctrl+alt+d",
    # Cập nhật: hỏi GitHub xem có bản mới không (chỉ báo, không tự tải)
    "check_updates": True,
}

VERSION = 2                       # tăng khi đổi giá trị mặc định cần áp lại cho file cũ
_lock = threading.Lock()
_values: dict | None = None
_listeners: list = []


def _load() -> dict:
    global _values
    if _values is None:
        _values = dict(DEFAULTS)
        try:
            saved = json.loads(PATH.read_text(encoding="utf-8"))
            if saved.get("_v", 1) < 2:
                saved.pop("top_n", None)          # bản cũ lưu cả giá trị mặc định cũ (tự vừa cửa sổ)
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
            # chỉ lưu giá trị khác mặc định → đổi mặc định ở bản sau vẫn có tác dụng
            keep = {k: val for k, val in v.items() if val != DEFAULTS.get(k)}
            PATH.write_text(json.dumps({"_v": VERSION, **keep}, ensure_ascii=False, indent=1), encoding="utf-8")
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

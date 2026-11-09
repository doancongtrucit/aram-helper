# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
"""Gói báo lỗi: gom log, ảnh chẩn đoán, vị trí bảng lõi, cài đặt và thông tin hệ thống vào 1 file zip
để người dùng đính kèm khi báo lỗi trên GitHub.

Bảo vệ thông tin cá nhân: che đường dẫn thư mục người dùng, tên đăng nhập Windows và địa chỉ IP trong log;
KHÔNG đưa cấu hình khác hay dữ liệu tải về (cache, icon) vào gói. Ảnh chẩn đoán là ảnh màn hình game
lúc chọn lõi – người dùng được báo trước khi tạo gói.
"""
from __future__ import annotations

import getpass
import json
import os
import platform
import re
import sys
import time
import zipfile
from pathlib import Path

import paths

INCLUDE = ["app.log", "app.log.1", "calibration.json", "overlay.json", "settings.json", "update.json"]
MAX_DEBUG = 12                       # ảnh chẩn đoán mới nhất (mỗi ảnh kèm file .json)
_IP = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def _secrets() -> list[str]:
    """Chuỗi cần che: thư mục người dùng, tên đăng nhập."""
    out = [str(Path.home()), str(Path.home()).replace("\\", "/")]
    try:
        out.append(getpass.getuser())
    except Exception:
        pass
    return sorted({s for s in out if s and len(s) > 2}, key=len, reverse=True)


def sanitize(text: str) -> str:
    """Che đường dẫn / tên người dùng / địa chỉ IP (trừ 127.0.0.1) trong nội dung chữ."""
    for s in _secrets():
        text = re.sub(re.escape(s), "~" if ("\\" in s or "/" in s) else "<user>", text, flags=re.I)
    return _IP.sub(lambda m: m.group(0) if m.group(0).startswith("127.") else "x.x.x.x", text)


def system_info(extra: dict | None = None) -> dict:
    from version import __version__
    info = {
        "app_version": __version__,
        "frozen": paths.FROZEN,
        "os": platform.platform(),
        "python": sys.version.split()[0],
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    if sys.platform == "win32":
        try:
            import game_window
            info["game_area"] = list(game_window.rect(force=True))
            info["virtual_screen"] = list(game_window.virtual_screen())
        except Exception as e:
            info["game_area"] = f"lỗi: {e!r}"
        try:
            import ocr
            info["ocr_installed"] = ocr.installed()
        except Exception:
            info["ocr_installed"] = False
        try:
            import hotkeys
            info["hotkeys"] = dict(hotkeys.ACTIVE)
        except Exception:
            pass
    info.update(extra or {})
    return info


def default_dir() -> Path:
    """Desktop nếu có (dễ tìm để đính kèm), không thì thư mục dữ liệu."""
    for d in (Path(os.environ.get("USERPROFILE", Path.home())) / "Desktop", Path.home() / "Desktop"):
        if d.is_dir():
            return d
    return paths.DATA


def make_bundle(dest_dir: Path | None = None, extra: dict | None = None) -> Path:
    """Tạo file zip báo lỗi; trả đường dẫn file."""
    dest_dir = Path(dest_dir or default_dir())
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = dest_dir / f"ARAM-Helper-bug-report-{time.strftime('%Y%m%d-%H%M%S')}.zip"
    data = paths.DATA
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("system.json", sanitize(json.dumps(system_info(extra), ensure_ascii=False, indent=1, default=str)))
        for name in INCLUDE:
            f = data / name
            if f.is_file():
                z.writestr(name, sanitize(f.read_text(encoding="utf-8", errors="replace")))
        debug = data / "debug"
        if debug.is_dir():
            pngs = sorted(debug.glob("*.png"), key=lambda p: p.stat().st_mtime)[-MAX_DEBUG:]
            for png in pngs:
                z.write(png, f"debug/{png.name}")
                meta = png.with_suffix(".json")
                if meta.is_file():
                    z.writestr(f"debug/{meta.name}", sanitize(meta.read_text(encoding="utf-8", errors="replace")))
        z.writestr("README.txt", "ARAM Helper – gói báo lỗi.\n"
                                 "Đính kèm file zip này khi mở issue: https://github.com/doancongtrucit/aram-helper/issues\n"
                                 "Đã che đường dẫn thư mục người dùng và địa chỉ IP; không gồm dữ liệu tải về.\n")
    return out


def reveal(path: Path):
    """Mở thư mục và chọn sẵn file (Windows Explorer); hệ khác thì mở thư mục."""
    import subprocess
    if sys.platform == "win32":
        subprocess.Popen(["explorer", "/select,", str(path)])
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path.parent)])

# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
"""Gói báo lỗi: gom log, ảnh chẩn đoán, vị trí bảng lõi, cài đặt và thông tin hệ thống vào 1 file zip
để người dùng đính kèm khi báo lỗi trên GitHub.

Bảo vệ thông tin cá nhân: che đường dẫn thư mục người dùng, tên đăng nhập Windows và địa chỉ IP trong log;
KHÔNG đưa cấu hình khác hay dữ liệu tải về (cache, icon) vào gói. Ảnh chẩn đoán chỉ giữ vùng quanh 3 thẻ lõi:
ảnh chụp cả màn hình (định vị thất bại, phím chẩn đoán) được cắt trước khi cho vào gói – không lộ khung chat,
tên người chơi hay bảng điểm. Người dùng được báo trước khi tạo gói.
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


def crop_box(w: int, h: int, info: dict) -> tuple[int, int, int, int]:
    """Vùng giữ lại của ảnh chẩn đoán (x0, y0, x1, y1).

    Ảnh đã là vùng quét (có "origin") → giữ nguyên. Ảnh cả màn hình → vùng quanh 3 thẻ lõi theo vị trí bảng lõi
    trong file .json, không có thì dải giữa màn hình nơi bảng chọn lõi hiện (bỏ chat, bảng điểm, tên người chơi)."""
    if "origin" in info:
        return 0, 0, w, h
    c = info.get("calibration") or {}
    try:
        sx, sy = w / c["width"], h / c["height"]
        s = c["size"] * sx
        xs = [p[0] * sx for p in c["centers"]]
        ys = [p[1] * sy for p in c["centers"]]
        box = (int(min(xs) - 1.5 * s), int(min(ys) - 1.4 * s), int(max(xs) + 1.5 * s), int(max(ys) + 3.1 * s))
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        box = (int(w * 0.2), int(h * 0.1), int(w * 0.8), int(h * 0.62))
    x0, y0, x1, y1 = max(0, box[0]), max(0, box[1]), min(w, box[2]), min(h, box[3])
    if x1 - x0 < 16 or y1 - y0 < 16:
        return int(w * 0.2), int(h * 0.1), int(w * 0.8), int(h * 0.62)
    return x0, y0, x1, y1


def card_area_png(path: Path, info: dict) -> bytes:
    """PNG đã cắt chỉ còn vùng thẻ lõi (xem crop_box)."""
    import io
    from PIL import Image
    with Image.open(path) as im:
        box = crop_box(im.width, im.height, info)
        out = io.BytesIO()
        im.crop(box).save(out, "PNG")
        return out.getvalue()


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
                meta = png.with_suffix(".json")
                info = {}
                if meta.is_file():
                    text = meta.read_text(encoding="utf-8", errors="replace")
                    z.writestr(f"debug/{meta.name}", sanitize(text))
                    try:
                        info = json.loads(text)
                    except ValueError:
                        pass
                try:
                    z.writestr(f"debug/{png.name}", card_area_png(png, info))
                except Exception as e:                  # ảnh hỏng: bỏ qua, không đưa ảnh gốc vào gói
                    z.writestr(f"debug/{png.name}.skipped.txt", f"không đọc được ảnh: {e!r}")
        z.writestr("README.txt", "ARAM Helper – gói báo lỗi.\n"
                                 "Đính kèm file zip này khi mở issue: https://github.com/doancongtrucit/aram-helper/issues\n"
                                 "Đã che đường dẫn thư mục người dùng và địa chỉ IP; ảnh chỉ giữ vùng thẻ lõi; "
                                 "không gồm dữ liệu tải về.\n")
    return out


def reveal(path: Path):
    """Mở thư mục và chọn sẵn file (Windows Explorer); hệ khác thì mở thư mục."""
    import subprocess
    if sys.platform == "win32":
        subprocess.Popen(["explorer", "/select,", str(path)])
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path.parent)])

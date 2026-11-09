"""Nơi app lưu dữ liệu (cache, icon, hiệu chỉnh, cài đặt, log).

- Chạy từ mã nguồn (python app.py): thư mục data/ cạnh code, như trước.
- Chạy bản exe / .app đã đóng gói: thư mục người dùng, giữ nguyên khi cài bản mới hoặc gỡ cài đặt
    Windows: %LOCALAPPDATA%\\ARAM Helper     macOS: ~/Library/Application Support/ARAM Helper
- Bản exe có file portable.txt cạnh ARAM Helper.exe: lưu vào data/ cạnh exe (chép cả thư mục sang máy khác).
- Biến môi trường ARAM_HELPER_DATA ghi đè tất cả (dùng khi thử nghiệm).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "ARAM Helper"
FROZEN = bool(getattr(sys, "frozen", False))
# bản exe: thư mục chứa exe; mã nguồn: gốc repo (src/ nằm ngay dưới)
APP_DIR = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent.parent


def _data_dir() -> Path:
    env = os.environ.get("ARAM_HELPER_DATA")
    if env:
        return Path(env)
    if not FROZEN or (APP_DIR / "portable.txt").exists():
        return APP_DIR / "data"
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home())   # Windows luôn có LOCALAPPDATA
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / APP_NAME


DATA = _data_dir()
# File đi kèm app (icon...): bản exe nằm trong thư mục giải nén của PyInstaller, bản mã nguồn nằm cạnh code
RES = Path(getattr(sys, "_MEIPASS", APP_DIR))

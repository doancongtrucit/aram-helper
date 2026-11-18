# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
"""Mở app cùng Windows: giá trị "ARAM Helper" trong HKCU\\...\\Run (chạy kèm --minimized → nằm sẵn dưới khay).

Bộ cài cũ (≤ 1.8.3) tạo lối tắt trong thư mục Startup; migrate() đổi lối tắt đó sang khoá Run để chỉ còn một chỗ.
Chỉ Windows; nơi khác mọi hàm đều trả False / không làm gì.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import paths

IS_WINDOWS = sys.platform == "win32"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE = paths.APP_NAME
FLAG = "--minimized"


def supported() -> bool:
    return IS_WINDOWS


def command() -> str:
    """Lệnh Windows chạy khi đăng nhập: bản exe → exe; mã nguồn → pythonw app.py (không mở cửa sổ dòng lệnh)."""
    if paths.FROZEN:
        return f'"{sys.executable}" {FLAG}'
    exe = Path(sys.executable)
    pyw = exe.with_name("pythonw.exe")
    return f'"{pyw if pyw.exists() else exe}" "{paths.APP_DIR / "src" / "app.py"}" {FLAG}'


def _legacy_shortcut() -> Path | None:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / f"{paths.APP_NAME}.lnk"


def _read() -> str | None:
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            return winreg.QueryValueEx(k, VALUE)[0]
    except OSError:
        return None


def is_enabled() -> bool:
    if not IS_WINDOWS:
        return False
    lnk = _legacy_shortcut()
    return bool(_read()) or bool(lnk and lnk.exists())


def set_enabled(on: bool) -> bool:
    """Bật / tắt. Trả về trạng thái thật sau khi đổi (False nếu không ghi được registry)."""
    if not IS_WINDOWS:
        return False
    import winreg
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            if on:
                winreg.SetValueEx(k, VALUE, 0, winreg.REG_SZ, command())
            else:
                try:
                    winreg.DeleteValue(k, VALUE)
                except FileNotFoundError:
                    pass
    except OSError as e:
        print("autostart:", repr(e))
    if not on:
        lnk = _legacy_shortcut()
        if lnk:
            lnk.unlink(missing_ok=True)
    return is_enabled()


def migrate():
    """Lối tắt Startup của bộ cài cũ → khoá Run (có --minimized); khoá Run trỏ sai chỗ (đã chuyển thư mục) → sửa lại."""
    if not IS_WINDOWS:
        return
    lnk = _legacy_shortcut()
    cur = _read()
    if lnk and lnk.exists():
        set_enabled(True)
        lnk.unlink(missing_ok=True)
    elif cur and paths.FROZEN and cur != command() and not _target_exists(cur):
        set_enabled(True)


def _target_exists(cmd: str) -> bool:
    exe = cmd.split('"')[1] if cmd.startswith('"') else cmd.split(" ")[0]
    return Path(exe).exists()


def launched_at_login() -> bool:
    return FLAG in sys.argv

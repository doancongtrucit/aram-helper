# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
"""Cập nhật từ GitHub Releases.

- Kiểm tra bản mới (tối đa 4 lần / ngày, hoặc khi bấm Kiểm tra cập nhật trong Cài đặt).
- Bản cài bằng Setup.exe (Windows): cập nhật một chạm – tải bộ cài, so mã băm SHA-256 với SHA256SUMS.txt của
  bản phát hành, chạy bộ cài im lặng (/RELAUNCH=1 → mở lại app sau khi cài). Không khớp mã băm thì không cài.
- Bản portable / macOS / chạy từ mã nguồn: chỉ báo + mở trang tải.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

import paths
import settings
from version import __version__

REPO = "doancongtrucit/aram-helper"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES = f"https://github.com/{REPO}/releases/latest"
DOWNLOAD = f"https://github.com/{REPO}/releases/download"
SETUP = "ARAM-Helper-Setup.exe"
SUMS = "SHA256SUMS.txt"
STATE = paths.DATA / "update.json"
EVERY = 6 * 3600          # hỏi GitHub tối đa 4 lần / ngày
UA = {"User-Agent": f"ARAM-Helper/{__version__}"}


class UpdateError(Exception):
    pass


def parse(v: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", v or "")
    return tuple(int(n) for n in nums[:3]) or (0,)


def newer(latest: str, current: str = __version__) -> bool:
    return parse(latest) > parse(current)


def _load() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _fetch_latest() -> dict:
    req = urllib.request.Request(API, headers={**UA, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=8) as r:
        data = json.load(r)
    return {"version": data.get("tag_name", ""), "url": data.get("html_url") or RELEASES}


def status(force: bool = False) -> tuple[str, dict | None]:
    """("new", info) có bản mới · ("latest", None) đang dùng bản mới nhất · ("error", None) không hỏi được GitHub."""
    st = _load()
    if not force and time.time() - st.get("checked", 0) < EVERY:
        latest, ok = st.get("latest"), True
    else:
        try:
            latest, ok = _fetch_latest(), True
        except Exception:
            latest, ok = None, False
        try:
            STATE.parent.mkdir(parents=True, exist_ok=True)
            STATE.write_text(json.dumps({"checked": time.time(), "latest": latest}), encoding="utf-8")
        except OSError:
            pass
    if latest and newer(latest.get("version", "")):
        return "new", latest
    return ("latest" if ok else "error"), None


def check(force: bool = False) -> dict | None:
    """{"version", "url"} nếu có bản mới hơn bản đang chạy, ngược lại None. Lỗi mạng → None (thử lại sau)."""
    return status(force)[1]


def check_async(callback):
    """Chạy ở luồng nền; callback(info) chỉ được gọi khi có bản mới."""
    def run():
        if not settings.get("check_updates"):
            return
        info = check()
        if info:
            callback(info)
    threading.Thread(target=run, daemon=True, name="update-check").start()


# ---------- cập nhật một chạm (Windows, bản cài bằng Setup.exe) ----------
def can_self_update(exe: str | None = None) -> bool:
    """Chỉ bản đã cài bằng bộ cài (có trình gỡ cài đặt cạnh file exe) mới tự cập nhật được."""
    if sys.platform != "win32" or (exe is None and not getattr(sys, "frozen", False)):
        return False
    return (Path(exe or sys.executable).parent / "unins000.exe").exists()


def parse_sums(text: str) -> dict[str, str]:
    """Đọc SHA256SUMS.txt (định dạng của sha256sum): '<hex>  <tên file>' hoặc '<hex> *<tên file>'."""
    out = {}
    for line in text.splitlines():
        m = re.match(r"^([0-9a-fA-F]{64})\s+\*?(.+?)\s*$", line)
        if m:
            out[m.group(2)] = m.group(1).lower()
    return out


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _download(url: str, dest: Path, progress=None, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    part = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(req, timeout=timeout) as r, open(part, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = r.read(1 << 16)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if progress:
                progress(done, total)
    part.replace(dest)


def _read_url(url: str, timeout=15) -> str:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read(1 << 20).decode("utf-8", "replace")


def update_dir() -> Path:
    return Path(tempfile.gettempdir()) / "aram-helper-update"


def prepare(version: str, progress=None) -> Path:
    """Tải bộ cài của bản `version` (vd. 'v1.7.0') và kiểm tra mã băm; trả đường dẫn file đã kiểm tra."""
    base = f"{DOWNLOAD}/{version}"
    try:
        sums = parse_sums(_read_url(f"{base}/{SUMS}"))
    except Exception as e:
        raise UpdateError(f"không tải được {SUMS}: {e}") from e
    want = sums.get(SETUP)
    if not want:
        raise UpdateError(f"{SUMS} không có {SETUP}")
    folder = update_dir()
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / f"ARAM-Helper-{version.lstrip('v')}-Setup.exe"
    if not (dest.exists() and sha256(dest) == want):        # đã tải đủ lần trước thì dùng lại
        try:
            _download(f"{base}/{SETUP}", dest, progress)
        except Exception as e:
            raise UpdateError(f"tải bộ cài lỗi: {e}") from e
        got = sha256(dest)
        if got != want:
            dest.unlink(missing_ok=True)
            raise UpdateError("mã băm bộ cài không khớp – đã huỷ")
    return dest


def install_command(setup: Path) -> list[str]:
    log = paths.DATA / "update-install.log"
    return [str(setup), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS", "/RELAUNCH=1",
            f"/LOG={log}"]


def launch_installer(setup: Path):
    """Chạy bộ cài tách khỏi app (app thoát ngay sau đó; bộ cài mở lại app khi xong)."""
    flags = 0x00000008 | 0x00000200            # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(install_command(setup), creationflags=flags, close_fds=True)

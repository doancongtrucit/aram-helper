"""Kiểm tra bản mới trên GitHub Releases (tối đa 1 lần / ngày). Chỉ báo + mở trang tải, không tự tải hay cài."""
from __future__ import annotations

import json
import re
import threading
import time
import urllib.request

import paths
import settings
from version import __version__

REPO = "doancongtrucit/aram-helper"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES = f"https://github.com/{REPO}/releases/latest"
STATE = paths.DATA / "update.json"
EVERY = 6 * 3600          # hỏi GitHub tối đa 4 lần / ngày


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


def check(force: bool = False) -> dict | None:
    """{"version", "url"} nếu có bản mới hơn bản đang chạy, ngược lại None. Lỗi mạng → None (thử lại hôm sau)."""
    st = _load()
    if not force and time.time() - st.get("checked", 0) < EVERY:
        latest = st.get("latest")
    else:
        latest = None
        try:
            req = urllib.request.Request(API, headers={"User-Agent": f"ARAM-Helper/{__version__}",
                                                       "Accept": "application/vnd.github+json"})
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.load(r)
            latest = {"version": data.get("tag_name", ""), "url": data.get("html_url") or RELEASES}
        except Exception:
            pass
        try:
            STATE.parent.mkdir(parents=True, exist_ok=True)
            STATE.write_text(json.dumps({"checked": time.time(), "latest": latest}), encoding="utf-8")
        except OSError:
            pass
    if latest and newer(latest.get("version", "")):
        return latest
    return None


def check_async(callback):
    """Chạy ở luồng nền; callback(info) chỉ được gọi khi có bản mới."""
    def run():
        if not settings.get("check_updates"):
            return
        info = check()
        if info:
            callback(info)
    threading.Thread(target=run, daemon=True, name="update-check").start()

"""Đọc Live Client Data API mà client LoL mở trên máy khi đang trong trận.

https://127.0.0.1:2999/liveclientdata/... — chứng chỉ tự ký của Riot nên tắt kiểm tra SSL
(chỉ áp dụng cho địa chỉ localhost này). Chỉ đọc, không can thiệp game.
"""
from __future__ import annotations

import json
import ssl
import urllib.request

LIVE = "https://127.0.0.1:2999/liveclientdata"
_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE


def _get(path: str):
    with urllib.request.urlopen(LIVE + path, context=_ctx, timeout=2) as r:
        return json.loads(r.read().decode("utf-8"))


def _same_player(p: dict, active: str) -> bool:
    active = active.lower()
    names = {
        str(p.get("riotId", "")).lower(),
        str(p.get("summonerName", "")).lower(),
        f"{p.get('riotIdGameName', '')}#{p.get('riotIdTagLine', '')}".lower(),
        str(p.get("riotIdGameName", "")).lower(),
    }
    return active in names or active.split("#")[0] in names


def current_game() -> dict:
    """Trả về {'in_game': False} nếu không có trận, ngược lại thông tin tướng của mình."""
    try:
        active = _get("/activeplayername")
        players = _get("/playerlist")
        stats = _get("/gamestats")
    except Exception:
        return {"in_game": False}

    me = next((p for p in players if _same_player(p, active)), None)
    if me is None:
        return {"in_game": True, "error": "Không xác định được tướng của bạn", "player": active}
    return {
        "in_game": True,
        "player": active,
        "champion_raw": me.get("rawChampionName", ""),
        "champion_name": me.get("championName", ""),
        "game_mode": stats.get("gameMode"),
        "game_time": stats.get("gameTime"),
    }

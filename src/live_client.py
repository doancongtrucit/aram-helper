# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
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
    my_team = me.get("team")
    return {
        "in_game": True,
        "player": active,
        "champion_raw": me.get("rawChampionName", ""),
        "champion_name": me.get("championName", ""),
        "team": my_team,
        "my_items": _player_brief(me)["items"],
        # Đội địch: thông tin này đều xem được trên bảng điểm (phím Tab) trong game
        "enemies": [_player_brief(p) for p in players if my_team and p.get("team") and p.get("team") != my_team],
        "game_mode": stats.get("gameMode"),
        "game_time": stats.get("gameTime"),
    }


def _player_brief(p: dict) -> dict:
    raw = str(p.get("rawChampionName", ""))
    return {
        "champion_raw": raw,
        "champion_name": p.get("championName", ""),
        "slug": "".join(ch for ch in raw.replace("game_character_displayname_", "").lower() if ch.isalnum()),
        "level": p.get("level"),
        "items": [int(it["itemID"]) for it in p.get("items") or [] if isinstance(it, dict) and it.get("itemID")],
    }

"""Dữ liệu tướng / trang bị chính thức của Riot (Data Dragon, bản tiếng Việt), rút gọn chỉ giữ trường cần dùng.

Cache ở data/ddragon.json, kiểm tra phiên bản mới mỗi 24 giờ. Mạng lỗi thì dùng bản đã lưu.
"""
from __future__ import annotations

import json
import re
import threading
import time
import urllib.request
from pathlib import Path

import paths

CDN = "https://ddragon.leagueoflegends.com"
CACHE = paths.DATA / "ddragon.json"
CHECK_EVERY = 24 * 3600
ARAM_MAP = "12"
KEEP_PREFIX = ("12", "22")
SCHEMA = 3                 # tăng khi đổi cách rút gọn → tải lại
UA = {"User-Agent": "aram-helper/1.0 (personal use)"}

_lock = threading.Lock()


def _get_json(url: str):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def _strip(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).strip()


def trim(version: str, champions: dict, items: dict) -> dict:
    """Rút gọn champion.json + item.json (vi_VN) – tách riêng để test không cần mạng."""
    champs = {}
    for c in champions.values():
        info = c.get("info", {})
        champs[c["id"].lower()] = {"name": c["name"], "tags": c.get("tags", []),
                                   "attack": info.get("attack", 0), "magic": info.get("magic", 0),
                                   "defense": info.get("defense", 0)}
    out_items = {}
    for k, v in items.items():
        # Mã 6 số: chỉ giữ nhóm 12xxxx / 22xxxx (món riêng của chế độ ARAM); 77xxxx, 99xxxx là món chế độ khác
        if len(k) > 4 and k[:2] not in KEEP_PREFIX:
            continue
        gold = v.get("gold", {})
        if not (v.get("maps", {}).get(ARAM_MAP) and gold.get("purchasable")) or v.get("requiredAlly"):
            continue
        tags = v.get("tags", [])
        boots = "Boots" in tags
        final = not v.get("into") and gold.get("total", 0) >= 2000
        if not (final or (boots and gold.get("total", 0) >= 900)):
            continue
        desc = _strip(v.get("description", ""))
        st = v.get("stats", {})
        out_items[k] = {"name": v["name"], "tags": tags, "gold": gold.get("total", 0), "boots": boots,
                        "armor": st.get("FlatArmorMod", 0), "mr": st.get("FlatSpellBlockMod", 0),
                        "antiheal": "Vết Thương Sâu" in desc or "Grievous" in desc}
    # Tên mọi món dùng được trên ARAM (kể cả món ghép) – để đổi tên theo ngôn ngữ
    names = {k: v["name"] for k, v in items.items() if v.get("maps", {}).get(ARAM_MAP)}
    return {"version": version, "schema": SCHEMA, "checked": time.time(), "champions": champs, "items": out_items,
            "item_names": names}


def trim_spells(spells: dict) -> dict:
    """Phép bổ trợ: khoá = id viết thường bỏ chữ 'summoner' (SummonerFlash → flash)."""
    return {k.lower().replace("summoner", ""): v["name"] for k, v in spells.items()}


def _download(locale: str) -> dict:
    version = _get_json(f"{CDN}/api/versions.json")[0]
    champs = _get_json(f"{CDN}/cdn/{version}/data/{locale}/champion.json")["data"]
    items = _get_json(f"{CDN}/cdn/{version}/data/{locale}/item.json")["data"]
    out = trim(version, champs, items)
    try:
        out["spells"] = trim_spells(_get_json(f"{CDN}/cdn/{version}/data/{locale}/summoner.json")["data"])
    except Exception:
        out["spells"] = {}
    out["locale"] = locale
    return out


_cache: dict[str, dict] = {}


def _path(locale: str) -> Path:
    return CACHE if locale == "vi_VN" else CACHE.with_name(f"ddragon_{locale}.json")


def get(locale: str = "vi_VN") -> dict | None:
    """Dữ liệu đã rút gọn theo ngôn ngữ (vi_VN / en_US), lưu riêng từng file. None nếu chưa từng tải được."""
    with _lock:
        data = _cache.get(locale)
        path = _path(locale)
        if data is None and path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                data = None
        if data is None or time.time() - data.get("checked", 0) > CHECK_EVERY or data.get("schema") != SCHEMA:
            try:
                latest = _get_json(f"{CDN}/api/versions.json")[0]
                if data is None or latest != data.get("version") or data.get("schema") != SCHEMA:
                    data = _download(locale)
                else:
                    data["checked"] = time.time()
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass                       # mạng lỗi: dùng bản cũ nếu có
        if data is not None:
            _cache[locale] = data
        return data


def item_icon(item_id, version: str) -> str:
    return f"{CDN}/cdn/{version}/img/item/{item_id}.png"

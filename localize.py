"""Đổi dữ liệu tướng (lấy từ trang tiếng Việt – bản đầy đủ nhất, có combo) sang tiếng Anh theo id.

- Tên lõi: tier list tiếng Anh của trang nguồn (cùng id lõi).
- Tên tướng / trang bị / phép bổ trợ: Data Dragon en_US.
- Nhãn kiểu build: bảng nhỏ STYLE_EN.
Phần mô tả combo / mẹo do biên tập viên viết chỉ có tiếng Việt nên giữ nguyên.
"""
from __future__ import annotations

import copy
import re

STYLE_EN = {
    "Chí mạng": "Crit", "Tốc đánh / đòn đánh": "Attack speed / on-hit", "Tốc đánh": "Attack speed",
    "Đấu sĩ AD": "AD fighter", "Đấu sĩ": "Fighter", "Pháp sư": "Mage", "Sát thủ": "Assassin", "Đỡ đòn": "Tank",
    "Hỗ trợ": "Support", "Sát lực": "Lethality", "Sức mạnh phép": "Ability power", "Xuyên giáp": "Armor pen",
    "Xuyên phép": "Magic pen", "Hút máu": "Lifesteal", "Máu": "Health", "Hồi chiêu": "Ability haste",
    "Kỹ năng": "Abilities", "Đòn đánh": "On-hit", "Giáp": "Armor", "Kháng phép": "Magic resist",
}
SPELL_ALIAS = {"mark": "snowball"}          # tên ảnh trên trang nguồn → id Data Dragon


def _style(text: str) -> str:
    parts = [p.strip() for p in re.split(r",", text or "")]
    return ", ".join(STYLE_EN.get(p, p) for p in parts if p)


def _item_id_from_icon(url: str | None) -> str | None:
    m = re.search(r"/item/[^/]+/(\d+)\.png", url or "")
    return m.group(1) if m else None


def _spell_key(url: str | None) -> str | None:
    m = re.search(r"summoner_(\w+)\.png", url or "")
    return SPELL_ALIAS.get(m.group(1), m.group(1)) if m else None


def champion(champ: dict | None, lang: str, aug_names: dict[int, str], dd: dict | None) -> dict | None:
    """Bản sao đã đổi tên sang `lang` (chỉ hỗ trợ "en"); "vi" trả nguyên bản."""
    if not champ or lang == "vi" or not dd:
        return champ
    c = copy.deepcopy(champ)
    items = dd.get("item_names", {})
    spells = dd.get("spells", {})
    c["name"] = dd.get("champions", {}).get(c.get("slug", ""), {}).get("name", c.get("name"))

    def aug(a):
        a["name"] = aug_names.get(a.get("id"), a.get("name"))

    def item(it):
        k = str(it.get("id") or _item_id_from_icon(it.get("icon")) or "")
        if k in items:
            it["name"] = items[k]
        elif _spell_key(it.get("icon")) in spells:
            it["name"] = spells[_spell_key(it.get("icon"))]

    for lst in (c.get("augments") or {}).values():
        for a in lst:
            aug(a)
    for s in c.get("playstyles") or []:
        for cb in s.get("combos", []):
            for a in cb.get("augments", []):
                aug(a)
        for it in s.get("items", []):
            item(it)
    for b in c.get("builds") or []:
        style, _, key_item = (b.get("name") or "").partition(" · ")     # "Chí mạng · Mũi Tên Yun Tal"
        old = {id(it): it.get("name") for it in b.get("items", [])}
        for it in b.get("items", []) + b.get("boots", []) + b.get("spells", []):
            item(it)
        for w in b.get("with", []):
            item(w)
        # món đặc trưng trong tên build: tìm theo tên gốc tiếng Việt rồi lấy tên mới
        key_en = next((it["name"] for it in b.get("items", []) if old.get(id(it)) == key_item), key_item)
        b["name"] = f"{_style(style)} · {key_en}" if key_item else _style(style)
        b["style"] = _style(b.get("style", ""))
    for key in ("other_items", "boots"):
        for r in c.get(key) or []:
            k = _item_id_from_icon((r.get("icons") or [None])[0])
            if k in items:
                r["name"] = items[k]
    for r in c.get("spells") or []:
        names = [spells.get(_spell_key(u)) for u in r.get("icons") or []]
        if names and all(names):
            r["name"] = " + ".join(names)
    return c


def catalog(cat: dict[int, dict], lang: str, aug_names: dict[int, str]) -> dict[int, dict]:
    if lang == "vi" or not aug_names:
        return cat
    return {k: dict(v, name=aug_names.get(k, v["name"])) for k, v in cat.items()}

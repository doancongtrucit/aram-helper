"""Phân tích đội hình + trang bị đội địch → 2 gợi ý trang bị ngắn gọn.

Luật kinh nghiệm (không phải thống kê theo đội hình):
- ≥2 tướng địch hồi máu mạnh            → món giảm hồi máu (Vết Thương Sâu)
- nhiều tướng đỡ đòn / địch lên giáp     → xuyên giáp (tướng AD) · địch lên kháng phép → xuyên phép (tướng AP)
- sát thương địch nghiêng hẳn về phép   → món kháng phép · nghiêng về vật lý → món giáp
- ≥3 tướng khống chế cứng                → giày kháng hiệu ứng
Món được chọn theo kiểu tướng của bạn (suy ra từ build gợi ý), ưu tiên món tướng đó hay lên (có tỉ lệ thắng).
"""
from __future__ import annotations

from i18n import T

# Tướng hồi máu mạnh (id Data Dragon viết thường)
HEALERS = {
    "aatrox", "vladimir", "soraka", "yuumi", "sona", "nami", "seraphine", "milio", "taric", "warwick", "drmundo",
    "sylas", "swain", "fiddlesticks", "briar", "olaf", "illaoi", "trundle", "volibear", "nasus", "gwen", "maokai",
    "zac", "kayn", "belveth", "udyr", "senna", "rakan", "alistar", "nunu", "ekko", "renekton", "rengar",
    "tahmkench", "xinzhao", "samira", "darius",
}
# Tướng có khống chế cứng đáng kể (hất tung, choáng, trói, kéo...)
HARD_CC = {
    "leona", "nautilus", "amumu", "malphite", "sejuani", "ashe", "morgana", "lissandra", "zyra", "alistar", "rell",
    "thresh", "blitzcrank", "braum", "maokai", "rammus", "sion", "zac", "nami", "chogath", "annie", "lux", "neeko",
    "seraphine", "ornn", "galio", "jarvaniv", "vi", "monkeyking", "kennen", "diana", "orianna", "pantheon",
    "skarner", "poppy", "veigar", "fiddlesticks", "warwick", "yasuo", "sona", "bard", "taric", "janna", "xerath",
    "varus", "twistedfate", "zilean", "sett", "volibear", "nunu", "gragas", "ksante", "rakan", "ambessa",
}
ARMOR_STACK = 60      # 1 tướng địch có ≥ mức giáp này từ trang bị = đang lên giáp
MR_STACK = 50


def my_class(champion: dict, items: dict) -> str:
    """Kiểu tướng của bạn theo build gợi ý: crit / fighter / ap / tank."""
    tags: dict[str, int] = {}
    for b in (champion.get("builds") or [])[:2]:
        for it in b.get("items", []):
            for t in items.get(str(it.get("id")), {}).get("tags", []):
                tags[t] = tags.get(t, 0) + 1
    ap, ad, crit = tags.get("SpellDamage", 0), tags.get("Damage", 0), tags.get("CriticalStrike", 0)
    # Cân theo tỉ lệ (có món lai, vd. Nghi Thức Suy Vong vừa Chí mạng vừa Sức mạnh phép)
    if ap >= 2 and ap > ad + crit / 2:
        return "ap"
    if crit >= 2:
        return "crit"
    if ad >= 2:
        return "fighter"
    if tags.get("Armor", 0) + tags.get("SpellBlock", 0) >= 2:
        return "tank"
    return "ap" if ap > ad else "fighter"


def team_profile(enemies: list[dict], dd: dict) -> dict:
    champs, items = dd["champions"], dd["items"]
    phys = magic = 0.0
    healers, tanks, cc, armor_stack, mr_stack = [], [], [], [], []
    for e in enemies:
        c = champs.get(e.get("slug", ""), {})
        name = c.get("name") or e.get("champion_name") or e.get("slug", "?")
        a, m = c.get("attack", 5), c.get("magic", 5)
        phys += a / max(1, a + m)
        magic += m / max(1, a + m)
        if e.get("slug") in HEALERS:
            healers.append(name)
        if "Tank" in c.get("tags", []) or c.get("defense", 0) >= 8:
            tanks.append(name)
        if e.get("slug") in HARD_CC:
            cc.append(name)
        own = [items.get(str(i), {}) for i in e.get("items", [])]
        if sum(i.get("armor", 0) for i in own) >= ARMOR_STACK:
            armor_stack.append(name)
        if sum(i.get("mr", 0) for i in own) >= MR_STACK:
            mr_stack.append(name)
    n = max(1, len(enemies))
    return {"n": len(enemies), "ap_share": magic / max(1e-6, phys + magic), "healers": healers, "tanks": tanks,
            "cc": cc, "armor_stack": armor_stack, "mr_stack": mr_stack, "per": n}


def _needs(p: dict, cls: str) -> list[dict]:
    """Nhu cầu trang bị theo hồ sơ đội địch, kèm mức độ và lý do ngắn."""
    out = []
    n = p["n"]
    if len(p["healers"]) >= 2:
        out.append({"need": "antiheal", "sev": 2 + len(p["healers"]),
                    "why": T("{k}/{n} địch hồi máu", k=len(p["healers"]), n=n)})
    if cls in ("crit", "fighter"):
        k = len(set(p["tanks"]) | set(p["armor_stack"]))
        if k >= 2:
            why = T("{k} địch lên giáp", k=len(p["armor_stack"])) if p["armor_stack"] else T("{k} tướng đỡ đòn", k=len(p["tanks"]))
            out.append({"need": "armorpen", "sev": 1.5 * k, "why": why})
    if cls == "ap":
        k = len(set(p["tanks"]) | set(p["mr_stack"]))
        if k >= 2:
            why = T("{k} địch lên kháng phép", k=len(p["mr_stack"])) if p["mr_stack"] else T("{k} tướng đỡ đòn", k=len(p["tanks"]))
            out.append({"need": "magicpen", "sev": 1.5 * k, "why": why})
    ap = p["ap_share"]
    if ap >= 0.6:
        out.append({"need": "mr", "sev": (ap - 0.5) * 12, "why": T("{p}% sát thương phép", p=round(ap * 100))})
    elif ap <= 0.4:
        out.append({"need": "armor", "sev": (0.5 - ap) * 12, "why": T("{p}% sát thương vật lý", p=round((1 - ap) * 100))})
    if len(p["cc"]) >= 3:
        out.append({"need": "tenacity", "sev": len(p["cc"]), "why": T("{k} tướng khống chế cứng", k=len(p["cc"]))})
    return sorted(out, key=lambda x: -x["sev"])


def _fits(item: dict, cls: str, need: str) -> bool:
    t = set(item["tags"])
    if need == "tenacity":
        return item["boots"] and "Tenacity" in t
    if item["boots"]:
        return False
    if need == "antiheal":
        ok = item["antiheal"]
    elif need == "armorpen":
        ok = "ArmorPenetration" in t
    elif need == "magicpen":
        ok = "MagicPenetration" in t
    elif need == "mr":
        ok = "SpellBlock" in t
    else:
        ok = "Armor" in t
    if not ok:
        return False
    if cls == "crit":
        return "CriticalStrike" in t or ("Damage" in t and "Health" not in t)
    if cls == "fighter":
        return "Damage" in t
    if cls == "ap":
        return "SpellDamage" in t
    return "Health" in t and "Damage" not in t and "SpellDamage" not in t        # tank


def suggest(champion: dict, enemies: list[dict], dd: dict, my_items: list[int] = (), limit: int = 2) -> list[dict]:
    """Tối đa `limit` gợi ý: {item_id, name, icon, why}. Rỗng nếu chưa có dữ liệu đội địch."""
    if not enemies or not dd or not champion:
        return []
    items = dd["items"]
    cls = my_class(champion, items)
    prof = team_profile(enemies, dd)
    # Món tướng này hay lên (có tỉ lệ thắng thật) được ưu tiên
    known: dict[str, float] = {}
    for b in champion.get("builds") or []:
        for it in b.get("items", []) + b.get("boots", []):
            if it.get("id"):
                known.setdefault(str(it["id"]), 0.0)
                known[str(it["id"])] = max(known[str(it["id"])], (b.get("winrate") or 50) + 1)
    by_name = {v["name"]: k for k, v in items.items()}
    for r in (champion.get("other_items") or []) + (champion.get("boots") or []):
        k = by_name.get(r.get("name"))
        if k:
            known[k] = max(known.get(k, 0), r.get("winrate") or 50)
    have = {str(i) for i in my_items}
    needs = _needs(prof, cls)
    out, used, covered = [], set(), set()
    for nd in needs:
        if nd["need"] in covered:
            continue
        cands = [(k, v) for k, v in items.items() if k not in have and k not in used and _fits(v, cls, nd["need"])]
        if not cands:
            continue
        k, v = max(cands, key=lambda kv: (kv[0] in known, known.get(kv[0], 0), -kv[1]["gold"]))
        used.add(k)
        why = nd["why"]
        # Giày kháng hiệu ứng có kháng phép: gộp luôn nhu cầu kháng phép vào cùng 1 dòng
        if nd["need"] == "tenacity" and "SpellBlock" in v["tags"]:
            mr = next((x for x in needs if x["need"] == "mr"), None)
            if mr:
                covered.add("mr")
                why += " · " + mr["why"]
        out.append({"item_id": int(k), "name": v["name"], "why": why, "need": nd["need"],
                    "icon": f"https://ddragon.leagueoflegends.com/cdn/{dd['version']}/img/item/{k}.png"})
        if len(out) >= limit:
            break
    return out


def two_lines(champion: dict, enemies: list[dict], dd: dict, my_items: list[int] = ()) -> list[dict]:
    """Đúng 2 dòng để hiển thị: tối đa 2 món gợi ý; thiếu thì thêm dòng tóm tắt đội địch (không có icon)."""
    if not enemies or not dd or not champion:
        return []
    lines = suggest(champion, enemies, dd, my_items, limit=2)
    if len(lines) < 2:
        s = summary(enemies, dd)
        lines.append({"item_id": None, "icon": None, "name": T("Đội địch"),
                      "why": s + ("" if lines else T(" – giữ build gợi ý"))})
    return lines[:2]


def summary(enemies: list[dict], dd: dict) -> str:
    """1 dòng tóm tắt đội địch, vd. '62% phép · 2 hồi máu · 2 đỡ đòn · 3 khống chế'."""
    if not enemies or not dd:
        return ""
    p = team_profile(enemies, dd)
    parts = [T("{p}% phép", p=round(p["ap_share"] * 100))]
    for key, label in (("healers", "{k} hồi máu"), ("tanks", "{k} đỡ đòn"), ("cc", "{k} khống chế")):
        if p[key]:
            parts.append(T(label, k=len(p[key])))
    return " · ".join(parts)

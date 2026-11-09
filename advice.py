"""Chấm điểm lõi và xếp hạng gợi ý (dùng chung cho cửa sổ chính và overlay).

Điểm = tỉ lệ thắng của lõi với tướng này
       (thiếu thì: tỉ lệ thắng chung tướng + (tỉ lệ thắng chung của lõi - 50))
       + thưởng nếu hợp combo với lõi đã chọn: S +4, A +3, B +2, C +1.
"""
from __future__ import annotations

TIER_BONUS = {"S": 4, "A": 3, "B": 2, "C": 1}


def _rank(t):
    return TIER_BONUS.get(t or "", 0)


def combos(champion: dict) -> list[dict]:
    return [c for s in champion.get("playstyles", []) for c in s.get("combos", [])]


def combo_fit(champion: dict, owned: set[int]) -> dict[int, str]:
    """id lõi → hạng combo tốt nhất mà lõi đó tạo được cùng một lõi đã chọn."""
    fit: dict[int, str] = {}
    for c in combos(champion):
        ids = [a["id"] for a in c["augments"]]
        if not any(i in owned for i in ids):
            continue
        for i in ids:
            if i not in owned and _rank(c["tier"]) > _rank(fit.get(i)):
                fit[i] = c["tier"]
    return fit


def champ_augments(champion: dict) -> dict[int, dict]:
    return {a["id"]: a for items in champion.get("augments", {}).values() for a in items}


def score(aug_id: int, champion: dict, catalog: dict[int, dict], owned: set[int],
          _cache: dict | None = None) -> dict:
    ch = champ_augments(champion) if _cache is None else _cache["ch"]
    fit = combo_fit(champion, owned) if _cache is None else _cache["fit"]
    base = champion.get("winrate") or 50.0
    a = ch.get(aug_id)
    g = catalog.get(aug_id, {})
    name = (a or g).get("name", f"#{aug_id}")
    if a and a.get("winrate") is not None:
        wr, src, shown = a["winrate"], "tướng", a["winrate"]
    elif g.get("winrate") is not None:
        wr, src, shown = base + (g["winrate"] - 50), "chung", g["winrate"]
    else:
        wr, src, shown = base, None, None
    tier = fit.get(aug_id)
    return {"id": aug_id, "name": name, "icon": (a or g).get("icon"), "winrate": shown, "source": src,
            "fit": tier, "score": round(wr + _rank(tier), 2)}


def offer_combos(champion: dict, offered: list[int], owned: set[int], limit: int = 3) -> list[dict]:
    """Combo lõi liên quan tới các lõi đang được đưa ra để chọn.

    Mỗi combo: {tier, augments: [{id, name, offered, owned}], offered: [id], owned_count}.
    Ưu tiên combo hoàn thành được với lõi đã có, rồi hạng combo cao, rồi có nhiều lõi đang được đưa ra."""
    offered_set = set(offered)
    seen, out = set(), []
    for c in combos(champion):
        ids = tuple(a["id"] for a in c["augments"])
        hit = [i for i in ids if i in offered_set]
        if not hit or ids in seen:
            continue
        seen.add(ids)
        out.append({
            "tier": c["tier"],
            "augments": [{"id": a["id"], "name": a["name"], "offered": a["id"] in offered_set,
                          "owned": a["id"] in owned} for a in c["augments"]],
            "offered": hit,
            "owned_count": sum(i in owned for i in ids),
        })
    out.sort(key=lambda c: (-c["owned_count"], -_rank(c["tier"]), -len(c["offered"])))
    return out[:limit]


def rank_offer(slots: list[list[int]], champion: dict, catalog: dict[int, dict], owned: set[int]) -> list[dict]:
    """slots: 3 ô, mỗi ô là danh sách id ứng viên. Trả về mỗi ô {slot, best, candidates, rank}
    theo thứ tự ô gốc; rank 1 = nên chọn."""
    cache = {"ch": champ_augments(champion), "fit": combo_fit(champion, owned)}
    out = []
    for i, cands in enumerate(slots):
        scored = sorted((score(c, champion, catalog, owned, cache) for c in cands), key=lambda s: -s["score"])
        if scored:
            out.append({"slot": i, "best": scored[0], "candidates": scored})
    for r, item in enumerate(sorted(out, key=lambda o: -o["best"]["score"]), start=1):
        item["rank"] = r
    return out

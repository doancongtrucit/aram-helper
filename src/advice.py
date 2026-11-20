# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
"""Chấm điểm lõi và xếp hạng gợi ý (dùng chung cho cửa sổ chính và overlay).

Điểm = tỉ lệ thắng của lõi với tướng này, kéo về mức kỳ vọng khi lõi có ít trận
       (thiếu thì: tỉ lệ thắng chung tướng + (tỉ lệ thắng chung của lõi - 50))
       + thưởng nếu hợp combo với lõi đã chọn: S +4, A +3, B +2, C +1.

Kéo về mức kỳ vọng (trung bình có trọng số kiểu Bayes): lõi hiếm, vài chục trận thắng 70 % chưa chắc tốt hơn lõi
phổ biến hàng nghìn trận thắng 56 %. Số trận ước tính = tỉ lệ chọn × số trận của tướng; PRIOR_GAMES trận "ảo"
mang tỉ lệ thắng kỳ vọng (tỉ lệ chung của lõi quy về tướng này). Lõi nhiều trận gần như không đổi.
"""
from __future__ import annotations

TIER_BONUS = {"S": 4, "A": 3, "B": 2, "C": 1}
PRIOR_GAMES = 150


def est_games(aug: dict, champion: dict) -> float | None:
    """Số trận ước tính của lõi với tướng: tỉ lệ chọn (%) × số trận của tướng. Thiếu số liệu → None."""
    pr, games = aug.get("pickrate"), champion.get("games")
    if pr is None or not games:
        return None
    return max(0.0, pr) / 100.0 * games


def shrink(wr: float, games: float | None, prior: float, k: float = PRIOR_GAMES) -> float:
    """Tỉ lệ thắng sau khi kéo về prior theo số trận (games=None: giữ nguyên)."""
    if games is None:
        return wr
    return (games * wr + k * prior) / (games + k)


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
        prior = base + (g["winrate"] - 50) if g.get("winrate") is not None else base
        wr, src, shown = shrink(a["winrate"], est_games(a, champion), prior), "tướng", a["winrate"]
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


REROLL_MARGIN = 1.0     # điểm dưới tỉ lệ thắng chung của tướng bao nhiêu thì đáng đổi lõi


def reroll_hint(ranked: list[dict], champion: dict, rerolls: list | None) -> int | None:
    """Thẻ nên bấm đổi lõi (↻): thẻ yếu nhất còn lượt đổi, không phải lõi nên chọn, và điểm thấp hơn
    tỉ lệ thắng chung của tướng ít nhất REROLL_MARGIN. Không có thì None."""
    if not ranked or not rerolls:
        return None
    base = champion.get("winrate") or 50.0
    pool = [r for r in ranked if r["rank"] != 1 and r["slot"] < len(rerolls) and rerolls[r["slot"]]]
    if not pool:
        return None
    worst = min(pool, key=lambda r: r["best"]["score"])
    return worst["slot"] if worst["best"]["score"] < base - REROLL_MARGIN else None

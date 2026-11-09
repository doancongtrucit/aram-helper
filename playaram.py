"""Lấy và cache dữ liệu lõi (augment) theo tướng từ playaram.gg.

Không dùng /api/ của trang (robots.txt chặn). Chỉ đọc HTML trang tướng công khai,
mỗi trang tối đa 1 lần / CACHE_TTL, cách nhau tối thiểu MIN_INTERVAL giây.
"""
from __future__ import annotations

import html
import json
import re
import threading
import time
import urllib.request
from pathlib import Path

import paths

BASE = "https://playaram.gg"
USER_AGENT = "aram-helper/0.1 (personal use)"
CACHE_DIR = paths.DATA
CACHE_TTL = 12 * 3600          # giây
MIN_INTERVAL = 2.0             # giây giữa 2 request tới playaram.gg
SCHEMA = 2                     # tăng khi đổi cấu trúc JSON để bỏ cache cũ

RARITY_LABEL = {"prismatic": "Kim Cương", "gold": "Vàng", "silver": "Bạc"}

_lock = threading.Lock()
_last_request = 0.0


def _get(path: str) -> str:
    """GET một trang playaram.gg, có giãn cách giữa các request."""
    global _last_request
    with _lock:
        wait = MIN_INTERVAL - (time.time() - _last_request)
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(BASE + path, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.read().decode("utf-8")
        finally:
            _last_request = time.time()


def slugify(raw: str) -> str:
    """'MonkeyKing' / 'game_character_displayname_DrMundo' -> 'monkeyking' / 'drmundo'."""
    raw = raw.replace("game_character_displayname_", "")
    return re.sub(r"[^a-z0-9]", "", raw.lower())


def _pct(s: str) -> float:
    return float(s.replace("%", "").strip())


def _text(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def parse_champion_list(page: str) -> list[str]:
    return sorted(set(re.findall(r'href="/tuong/([a-z0-9-]+)"', page)))


def parse_champion_page(page: str, slug: str) -> dict:
    """Tách thông tin tướng + lõi theo bậc từ HTML trang /tuong/<slug>."""
    def find(pattern: str, default: str = "") -> str:
        m = re.search(pattern, page, re.S)
        return _text(m.group(1)) if m else default

    head_icon = re.search(r'<img src="([^"]+)"[^>]*class="cb-head__icon"', page)
    games = find(r'class="sp-stat cb-head__games">([^<]+)<', "0").replace(".", "").replace(",", "")
    data = {
        "slug": slug,
        "name": find(r'class="crumbs__current">([^<]+)<', slug),
        "icon": BASE + head_icon.group(1) if head_icon else None,
        "tier": find(r'class="cb-tier[^"]*">([^<]+)<'),
        "winrate": _pct(find(r'class="sp-stat cb-head__wr">([^<]+)<', "0")),
        "games": int(games) if games.isdigit() else 0,
        "patch": find(r"<dt>Phiên bản</dt><dd>([^<]+)</dd>"),
        "updated": (re.search(r'<time datetime="([^"]+)"', page) or [None, None])[1],
        "augments": {},
        "schema": SCHEMA,
    }

    start = page.find('id="build-core-options"')
    if start < 0:
        raise ValueError(f"Không tìm thấy bảng lõi trong trang {slug} (trang có thể đã đổi giao diện)")
    section = page[start:]
    for block in re.finditer(r'<div class="cb-rarity cb-rarity--(\w+)">(.*?)</ul>', section, re.S):
        rarity, body = block.group(1), block.group(2)
        items = []
        for li in re.finditer(r"<li[^>]*data-tooltip-id=\"(\d+)\"[^>]*>(.*?)</li>", body, re.S):
            aug_id, inner = li.group(1), li.group(2)
            img = re.search(r'<img src="([^"]+)"', inner)
            name = re.search(r'class="cb-core__name">(.*?)</span>', inner, re.S)
            wr = re.search(r'cb-stats__wr">([^<]+)<', inner)
            pr = re.findall(r'class="sp-stat[^"]*">([\d.,]+%)<', inner)
            if not (name and wr):
                continue
            items.append({
                "id": int(aug_id),
                "name": _text(name.group(1)),
                "icon": BASE + img.group(1) if img else None,
                "winrate": _pct(wr.group(1)),
                "pickrate": _pct(pr[-1]) if len(pr) >= 2 else None,
            })
        data["augments"][rarity] = items
    if not data["augments"]:
        raise ValueError(f"Bảng lõi của {slug} rỗng (trang có thể đã đổi giao diện)")

    # Các phần dưới là phụ: lỗi ở đây không làm hỏng bảng lõi.
    for key, fn in (("builds", _parse_builds), ("playstyles", _parse_playstyles),
                    ("other_items", lambda p: _parse_rows(p, "Trang bị khác")),
                    ("boots", lambda p: _parse_rows(p, "Giày tốt nhất")),
                    ("spells", lambda p: _parse_rows(p, "Phép bổ trợ tốt nhất"))):
        try:
            data[key] = fn(page)
        except Exception:
            data[key] = []
    return data


# ---------- trang bị, lối chơi, combo ----------

def _rich_text(s: str) -> str:
    """HTML đoạn mô tả -> chữ thường; phím kỹ năng <kbd>Q</kbd> -> ' (Q)'."""
    s = re.sub(r'<kbd[^>]*>([^<]*)</kbd>', r" (\1)", s)
    s = re.sub(r"</p>\s*<p[^>]*>", "\n", s)
    return re.sub(r"[ \t]+", " ", _text(s)).strip()


def _section(page: str, title_prefix: str) -> str:
    m = re.search(r'<h2 class="cb-section__title">' + re.escape(title_prefix), page)
    if not m:
        return ""
    end = page.find("<h2", m.end())
    return page[m.start(): end if end > 0 else len(page)]


def _abs(src: str | None) -> str | None:
    return BASE + src if src and src.startswith("/") else src


def _stats(s: str) -> tuple[float | None, float | None]:
    wr = re.search(r'cb-stats__wr">([\d.]+)%', s)
    pk = re.search(r'cb-stats__pick">([\d.]+)%', s)
    return (float(wr.group(1)) if wr else None, float(pk.group(1)) if pk else None)


def _slots(ul_html: str) -> list[dict]:
    out = []
    for li in re.finditer(r'<li class="bt-slot([^"]*)">(.*?)</li>', ul_html, re.S):
        img = re.search(r'<img src="([^"]+)"', li.group(2))
        tid = re.search(r'data-tooltip-id="(\d+)"', li.group(2))
        name = re.search(r'class="bt-slot__name">([^<]*)<', li.group(2))
        out.append({
            "id": int(tid.group(1)) if tid else None,
            "name": _text(name.group(1)) if name else "",
            "icon": _abs(img.group(1)) if img else None,
            "core": "bt-slot--core" in li.group(1),
            "boot": "bt-slot--boot" in li.group(1),
        })
    return out


def _panels(section: str, prefix: str) -> list[str]:
    parts = re.split(r'<div role="tabpanel" id="' + prefix + r'-panel-\d+"', section)
    return parts[1:]


def _parse_builds(page: str) -> list[dict]:
    builds = []
    for p in _panels(_section(page, "Build trang bị"), "build"):
        strips = re.findall(r'<ul class="bt-strip bt-strip--(\w+)">(.*?)</ul>', p, re.S)
        items = [s for kind, ul in strips if kind == "items" for s in _slots(ul)]
        extra = [s for kind, ul in strips if kind == "extra" for s in _slots(ul)]
        kpis = re.findall(r'class="sp-stat bt-kpi[^"]*">([^<]+)<', p)
        withs = []
        for opt in re.finditer(r'<span class="cb-opt">(.*?)</span></span></span>', p, re.S):
            img = re.search(r'<img src="([^"]+)" alt="([^"]*)"', opt.group(1))
            wr, pk = _stats(opt.group(1))
            if img:
                withs.append({"name": _text(img.group(2)), "icon": _abs(img.group(1)), "winrate": wr, "pickrate": pk})
        name = re.search(r'class="bt-panel__name">(.*?)</h3>', p, re.S)
        sub = re.search(r'class="bt-panel__sub">(.*?)</p>', p, re.S)
        builds.append({
            "name": _text(name.group(1)) if name else "",
            "style": _text(sub.group(1)) if sub else "",
            "winrate": _pct(kpis[0]) if len(kpis) > 0 else None,
            "pickrate": _pct(kpis[1]) if len(kpis) > 1 else None,
            "games": int(re.sub(r"\D", "", kpis[2]) or 0) if len(kpis) > 2 else None,
            "items": items,
            "boots": [s for s in extra if s["boot"]],
            "spells": [s for s in extra if not s["boot"]],
            "with": withs,
        })
    return builds


def _parse_playstyles(page: str) -> list[dict]:
    section = _section(page, "Lối chơi")
    tab_tiers = re.findall(r'role="tab"[^>]*>.*?class="cb-tier cb-tier--\w+">([^<]+)<', section, re.S)
    styles = []
    for i, p in enumerate(_panels(section, "playstyle")):
        name = re.search(r'class="bt-panel__name">(.*?)</h3>', p, re.S)
        desc = re.search(r'class="bt-panel__sub">(.*?)</div>', p, re.S)
        combos = []
        for c in re.finditer(r'<li class="ps-combo ps-tier--(\w+)">(.*?)</li>\s*(?=<li class="ps-combo|</ul>)', p, re.S):
            body = c.group(2)
            head = body[: body.find('class="ps-combo__name"')]
            augs = [{"id": int(i_), "name": _text(alt), "rarity": rar, "icon": _abs(src)}
                    for src, alt, i_, rar in re.findall(
                        r'<img src="([^"]+)" alt="([^"]*)"[^>]*data-tooltip-id="(\d+)"[^>]*class="ps-aug ps-aug--(\w+)"', head)]
            text = re.search(r'<div class="ps-text">(.*?)</div>', body, re.S)
            tier = re.search(r'class="cb-tier[^"]*">([^<]+)<', head)
            combos.append({
                "tier": tier.group(1) if tier else c.group(1).upper(),
                "augments": augs,
                "why": _rich_text(text.group(1)) if text else "",
            })
        items_ul = re.search(r'<ul aria-label="Đồ khuyên dùng"[^>]*>(.*?)</ul>', p, re.S)
        tips = []
        for t in re.finditer(r'<li class="ps-tip">(.*?)</li>', p, re.S):
            title = re.search(r'class="ps-tip__title">(.*?)</p>', t.group(1), re.S)
            text = re.search(r'<div class="ps-text">(.*?)</div>', t.group(1), re.S)
            tips.append({"title": _text(title.group(1)) if title else "",
                         "text": _rich_text(text.group(1)) if text else ""})
        link = re.search(r'<a href="(/loi-choi/[^"]+)" class="ps-more"', p)
        styles.append({
            "name": _text(name.group(1)) if name else "",
            "tier": tab_tiers[i] if i < len(tab_tiers) else "",
            "description": _rich_text(desc.group(1)) if desc else "",
            "combos": combos,
            "items": _slots(items_ul.group(1)) if items_ul else [],
            "tips": tips,
            "url": BASE + link.group(1) if link else None,
        })
    return styles


def _parse_rows(page: str, title_prefix: str) -> list[dict]:
    rows = []
    for li in re.finditer(r'<li class="cb-row">(.*?)</li>', _section(page, title_prefix), re.S):
        body = li.group(1)
        name = re.search(r'class="cb-row__name">([^<]*)<', body)
        wr, pk = _stats(body)
        rows.append({
            "name": _text(name.group(1)) if name else "",
            "icons": [_abs(s) for s in re.findall(r'<img src="([^"]+)"', body)],
            "winrate": wr, "pickrate": pk,
        })
    return rows


def _cache_path(name: str) -> Path:
    return CACHE_DIR / f"{name}.json"


_mem: dict[str, dict] = {}     # bản trong RAM: khỏi đọc + parse file JSON mỗi lần hỏi


def _read_cache(name: str, ttl: float) -> dict | None:
    obj = _mem.get(name)
    if obj is None:
        p = _cache_path(name)
        if not p.exists():
            return None
        obj = json.loads(p.read_text(encoding="utf-8"))
        _mem[name] = obj
    if time.time() - obj.get("fetched_at", 0) > ttl:
        return None
    return obj


def _write_cache(name: str, obj: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    obj["fetched_at"] = time.time()
    _cache_path(name).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    _mem[name] = obj


def _stale_cache(name: str) -> dict | None:
    """Cache cũ (quá hạn) vẫn dùng được khi mạng lỗi."""
    return _read_cache(name, float("inf"))


def icon_asset_path(url: str | None) -> str | None:
    """'.../media/game-asset/assets/ux/kiwi/augments/icons/x_large.png' -> 'assets/ux/kiwi/augments/icons/x_large.png'."""
    if not url:
        return None
    m = re.search(r"/media/game-asset/(assets/.+?\.png)", url)
    return m.group(1).lower() if m else None


def parse_augment_catalog(page: str) -> list[dict]:
    """Toàn bộ lõi ARAM Hỗn Loạn từ /loi-aram-hon-loan (tier chung, tỉ lệ thắng chung)."""
    out = []
    pos = [(m.start(), m.group(1)) for m in re.finditer(r'<h2 aria-label="(?:Bậc|Tier) ([^"]+)"', page)]
    for li in re.finditer(r'<li data-core-name="[^"]*" data-core-rarity="(\w+)" data-core-cats="([^"]*)" '
                          r'data-tooltip-id="(\d+)"[^>]*>(.*?)</li>', page, re.S):
        rarity, cats, aug_id, body = li.groups()
        tier = next((t for p, t in reversed(pos) if p < li.start()), None)
        img = re.search(r'<img src="([^"]+)"', body)
        name = re.search(r'class="core-card__name">(.*?)</span>', body, re.S)
        wr = re.search(r'core-card__wr">([\d.]+)%', body)
        pk = re.search(r'core-card__pick">([\d.]+)%', body)
        out.append({
            "id": int(aug_id),
            "name": _text(name.group(1)) if name else str(aug_id),
            "rarity": rarity,
            "cats": cats.split(),
            "tier": tier,
            "winrate": float(wr.group(1)) if wr else None,
            "pickrate": float(pk.group(1)) if pk else None,
            "icon": BASE + img.group(1) if img else None,
            "asset": icon_asset_path(img.group(1) if img else None),
        })
    if not out:
        raise ValueError("Không đọc được danh sách lõi (trang có thể đã đổi giao diện)")
    return out


def get_augment_catalog(force: bool = False, lang: str = "vi") -> list[dict]:
    """Tier list lõi; lang = "en" lấy bản tiếng Anh (cùng id lõi, tên tiếng Anh)."""
    name = "_augments" if lang == "vi" else f"_augments_{lang}"
    if not force:
        cached = _read_cache(name, 24 * 3600)
        if cached and cached.get("schema") == SCHEMA:
            return cached["augments"]
    try:
        augs = parse_augment_catalog(_get("/loi-aram-hon-loan" if lang == "vi" else f"/{lang}/loi-aram-hon-loan"))
        _write_cache(name, {"augments": augs, "schema": SCHEMA})
        return augs
    except Exception:
        stale = _stale_cache(name)
        if stale:
            return stale["augments"]
        raise


def get_champion_list() -> list[str]:
    cached = _read_cache("_champions", 24 * 3600)
    if cached:
        return cached["slugs"]
    try:
        slugs = parse_champion_list(_get("/tuong"))
        _write_cache("_champions", {"slugs": slugs})
        return slugs
    except Exception:
        stale = _stale_cache("_champions")
        if stale:
            return stale["slugs"]
        raise


def get_champion(slug: str, force: bool = False) -> dict:
    slug = slugify(slug)
    name = f"champ_{slug}"
    if not force:
        cached = _read_cache(name, CACHE_TTL)
        if cached and cached.get("schema") == SCHEMA:
            return cached
    try:
        data = parse_champion_page(_get(f"/tuong/{slug}"), slug)
        _write_cache(name, data)
        return data
    except Exception:
        stale = _stale_cache(name)
        if stale:
            stale["stale"] = True
            return stale
        raise


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    d = get_champion(sys.argv[1] if len(sys.argv) > 1 else "yasuo", force=True)
    print(d["name"], d["tier"], d["winrate"], d["patch"])
    for r, items in d["augments"].items():
        print(f"-- {RARITY_LABEL.get(r, r)}")
        for a in items[:5]:
            print(f"   {a['name']:<30} {a['winrate']:6.2f}%  {a['pickrate']}%")

# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
"""Dựng trang HTML mẫu (cùng cấu trúc trang nguồn) từ tests/sample_data.json để test parser và mọi phần dùng dữ liệu.

Số liệu và chữ trong sample_data.json đều tự đặt cho test – không phải dữ liệu của trang nguồn; chỉ id, tên và icon
của lõi / trang bị là dữ liệu game. Nhờ vậy test chạy được ở mọi nơi (kể cả GitHub Actions) mà không phải tải trang.
"""
from __future__ import annotations

import json
from html import escape
from pathlib import Path

SAMPLE = json.loads((Path(__file__).parent / "sample_data.json").read_text(encoding="utf-8"))
CHAMPION = SAMPLE["champion"]
CATALOG = SAMPLE["catalog"]


def _slot(it: dict, cls: str = "") -> str:
    tid = f' data-tooltip-id="{it["id"]}"' if it.get("id") else ""
    return (f'<li class="bt-slot{cls}"><img src="{it["icon"]}" alt=""{tid}>'
            f'<span class="bt-slot__name">{escape(it["name"])}</span></li>')


def champion_page(c: dict = CHAMPION) -> str:
    out = [
        "<html><body>",
        f'<nav><span class="crumbs__current">{escape(c["name"])}</span></nav>',
        f'<img src="{c["icon"]}" alt="" class="cb-head__icon">',
        f'<span class="cb-tier cb-tier--x">{c["tier"]}</span>',
        f'<span class="sp-stat cb-head__wr">{c["winrate"]:.2f}%</span>',
        f'<span class="sp-stat cb-head__games">{c["games"]:,}</span>'.replace(",", "."),
        f'<dl><dt>Phiên bản</dt><dd>{c["patch"]}</dd></dl><time datetime="{c["updated"]}"></time>',
        '<section id="build-core-options">',
    ]
    for rarity, items in c["augments"].items():
        out.append(f'<div class="cb-rarity cb-rarity--{rarity}"><ul>')
        for a in items:
            out.append(f'<li class="cb-core" data-tooltip-id="{a["id"]}"><img src="{a["icon"]}" alt="">'
                       f'<span class="cb-core__name">{escape(a["name"])}</span>'
                       f'<span class="sp-stat cb-stats__wr">{a["winrate"]:.2f}%</span>'
                       f'<span class="sp-stat cb-stats__pick">{a["pickrate"]}%</span></li>')
        out.append("</ul></div>")
    out.append("</section>")

    out.append('<h2 class="cb-section__title">Build trang bị</h2>')
    for k, b in enumerate(c["builds"]):
        out.append(f'<div role="tabpanel" id="build-panel-{k}">'
                   f'<h3 class="bt-panel__name">{escape(b["name"])}</h3><p class="bt-panel__sub">{escape(b["style"])}</p>'
                   f'<span class="sp-stat bt-kpi">{b["winrate"]:.2f}%</span>'
                   f'<span class="sp-stat bt-kpi">{b["pickrate"]}%</span>'
                   f'<span class="sp-stat bt-kpi">{b["games"]} trận</span>')
        out.append('<ul class="bt-strip bt-strip--items">'
                   + "".join(_slot(i, " bt-slot--core" if i["core"] else "") for i in b["items"]) + "</ul>")
        out.append('<ul class="bt-strip bt-strip--extra">' + "".join(_slot(i, " bt-slot--boot") for i in b["boots"])
                   + "".join(_slot(s) for s in b["spells"]) + "</ul>")
        for w in b["with"]:
            out.append(f'<span class="cb-opt"><img src="{w["icon"]}" alt="{escape(w["name"])}"><span>'
                       f'<span class="cb-stats__wr">{w["winrate"]:.2f}%</span> '
                       f'<span class="cb-stats__pick">{w["pickrate"]}%</span></span></span>')
        out.append("</div>")

    out.append('<h2 class="cb-section__title">Lối chơi</h2><div role="tablist">')
    for s in c["playstyles"]:
        out.append(f'<button role="tab"><span class="cb-tier cb-tier--x">{s["tier"]}</span>{escape(s["name"])}</button>')
    out.append("</div>")
    for k, s in enumerate(c["playstyles"]):
        out.append(f'<div role="tabpanel" id="playstyle-panel-{k}"><h3 class="bt-panel__name">{escape(s["name"])}</h3>'
                   f'<div class="bt-panel__sub"><p>{escape(s["description"])}</p></div><ul>')
        for cb in s["combos"]:
            imgs = "".join(f'<img src="{a["icon"]}" alt="{escape(a["name"])}" data-tooltip-id="{a["id"]}" '
                           f'class="ps-aug ps-aug--{a["rarity"]}">' for a in cb["augments"])
            out.append(f'<li class="ps-combo ps-tier--{cb["tier"].lower().replace("+", "p")}">'
                       f'<div class="ps-combo__head"><span class="cb-tier cb-tier--x">{cb["tier"]}</span>{imgs}</div>'
                       f'<p class="ps-combo__name">combo</p><div class="ps-text"><p>{cb["why"]}</p></div></li>')
        out.append("</ul>")
        if s["items"]:
            out.append('<ul aria-label="Đồ khuyên dùng">' + "".join(_slot(i) for i in s["items"]) + "</ul>")
        if s["tips"]:
            out.append("<ul>" + "".join(f'<li class="ps-tip"><p class="ps-tip__title">{escape(t["title"])}</p>'
                                        f'<div class="ps-text"><p>{escape(t["text"])}</p></div></li>'
                                        for t in s["tips"]) + "</ul>")
        if s["url"]:
            out.append(f'<a href="{s["url"]}" class="ps-more">Xem thêm</a>')
        out.append("</div>")

    for title, rows in (("Trang bị khác", c["other_items"]), ("Giày tốt nhất", c["boots"]),
                        ("Phép bổ trợ tốt nhất", c["spells"])):
        out.append(f'<h2 class="cb-section__title">{title}</h2><ul>')
        for r in rows:
            out.append('<li class="cb-row">' + "".join(f'<img src="{i}" alt="">' for i in r["icons"])
                       + f'<span class="cb-row__name">{escape(r["name"])}</span>'
                       f'<span class="cb-stats__wr">{r["winrate"]:.2f}%</span>'
                       f'<span class="cb-stats__pick">{r["pickrate"]}%</span></li>')
        out.append("</ul>")
    out.append("<h2>end</h2></body></html>")
    return "\n".join(out)


def catalog_page(catalog: list[dict] = CATALOG) -> str:
    out, tier = ["<html><body>"], None
    for a in catalog:
        if a["tier"] != tier:
            tier = a["tier"]
            out.append(f'<h2 aria-label="Bậc {tier}">Bậc {tier}</h2>')
        out.append(f'<ul><li data-core-name="{escape(a["name"])}" data-core-rarity="{a["rarity"]}" '
                   f'data-core-cats="{" ".join(a["cats"])}" data-tooltip-id="{a["id"]}" class="core-card">'
                   f'<img src="{a["icon"]}" alt=""><span class="core-card__name">{escape(a["name"])}</span>'
                   f'<span class="core-card__wr">{a["winrate"]}%</span>'
                   f'<span class="core-card__pick">{a["pickrate"]}%</span></li></ul>')
    out.append("</body></html>")
    return "\n".join(out)

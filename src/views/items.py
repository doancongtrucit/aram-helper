# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
"""Cột trang bị: đồ theo đội địch, lối lên đồ, trang bị khác, giày, phép."""
from __future__ import annotations

import tkinter as tk

from i18n import T
from theme import BG, PANEL, LINE, TEXT, MUTED, GOOD, OKC


class ItemsMixin:
    """Cột trang bị: đồ theo đội địch, lối lên đồ, trang bị khác, giày, phép."""

    def _render_counter(self, root, lines, pane_w):
        if not lines:
            return
        box = tk.Frame(root, bg=PANEL, highlightthickness=1, highlightbackground=OKC, padx=self.S(10), pady=self.S(5))
        box.pack(fill="x", padx=(0, self.S(6)), pady=(0, self.S(8)))
        self.label(box, T("Đồ nên lên theo đội hình + trang bị của đội địch"), 8, MUTED).pack(anchor="w")
        for line in lines[:2]:
            row = tk.Frame(box, bg=PANEL, pady=self.S(1))
            row.pack(fill="x")
            if line.get("icon"):
                self.icon(row, line["icon"], 22, tip=line["name"]).pack(side="left")
                self.label(row, line["name"], 9, OKC, True).pack(side="left", padx=(self.S(6), self.S(5)))
            self.label(row, self._fit(line["why"], pane_w // 2, 9), 9, MUTED if line.get("icon") else TEXT).pack(side="left")

    # ----- trang bị (gọn) -----
    def _render_items(self, root, c, pane_w):
        head = tk.Frame(root, bg=BG)
        head.pack(fill="x", padx=(0, self.S(6)))
        self.label(head, T("Trang bị gợi ý"), 11, TEXT, True).pack(side="left")
        hint = self._fit(T("Viền xanh = 2 món cốt lõi quyết định hướng build."), pane_w - self.S(150), 8)
        if len(hint) > 12:
            self.label(head, hint, 8, MUTED).pack(side="left", padx=self.S(8))
        for b in c.get("builds") or []:
            card = tk.Frame(root, bg=PANEL, highlightthickness=1, highlightbackground=LINE, padx=self.S(8), pady=self.S(5))
            card.pack(fill="x", padx=(0, self.S(6)), pady=(self.S(4), 0))
            top = tk.Frame(card, bg=PANEL)
            top.pack(fill="x")
            self.label(top, T("Thắng {wr}%", wr=b.get("winrate", "?")), 9, GOOD, True).pack(side="right")
            self.label(top, self._fit(b.get("name", ""), pane_w - self.S(120), 9, True), 9, TEXT, True).pack(side="left")
            sub = T("Chọn {pr}%  ·  {n} trận đủ đồ", pr=b.get("pickrate", "?"), n=b.get("games", "?")) \
                + (f"  ·  {b['style']}" if b.get("style") else "")
            self.label(card, self._fit(sub, pane_w - self.S(30), 8), 8, MUTED).pack(anchor="w")
            row = tk.Frame(card, bg=PANEL)
            row.pack(anchor="w", pady=(self.S(3), 0))
            big, small = b.get("items", []), b.get("boots", []) + b.get("spells", [])
            unit = (pane_w - self.S(34)) / max(1.0, len(big) + 0.8 * len(small)) / self.scale
            size = int(max(18, min(30, unit - 6)))
            for it in big:
                self._item_icon(row, it, size)
            tk.Frame(row, bg=PANEL, width=self.S(6)).pack(side="left")
            for it in small:
                self._item_icon(row, it, int(size * 0.8))
            if b.get("with"):
                w = tk.Frame(card, bg=PANEL)
                w.pack(anchor="w", pady=(self.S(3), 0))
                self.label(w, T("Hay lên cùng:"), 8, MUTED).pack(side="left")
                for x in b["with"]:
                    self.icon(w, x.get("icon"), 18, tip=x["name"]).pack(side="left", padx=(self.S(5), self.S(2)))
                    self.label(w, f"{x.get('winrate') or ''}%", 8, MUTED).pack(side="left")
        if not c.get("builds"):
            self.label(root, T("Chưa có build."), 10, MUTED).pack(anchor="w")

        lists = tk.Frame(root, bg=BG)
        lists.pack(fill="x", padx=(0, self.S(6)), pady=(self.S(8), self.S(4)))
        ncol = 3 if pane_w >= self.S(560) else 1
        for k in range(ncol):
            lists.grid_columnconfigure(k, weight=1, uniform="l")
        col_w = pane_w // ncol - self.S(16)
        for k, (title, rows) in enumerate(((T("Trang bị khác"), c.get("other_items")), (T("Giày"), c.get("boots")),
                                           (T("Phép bổ trợ"), c.get("spells")))):
            box = tk.Frame(lists, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
            box.grid(row=k // ncol, column=k % ncol, sticky="nsew", padx=self.S(2), pady=self.S(2))
            self.label(box, title, 9, TEXT, True).pack(anchor="w", padx=self.S(8), pady=(self.S(4), self.S(2)))
            for r in rows or []:
                line = tk.Frame(box, bg=PANEL, padx=self.S(8), pady=self.S(1))
                line.pack(fill="x")
                for src in r.get("icons", []):
                    self.icon(line, src, 18, tip=r["name"]).pack(side="left", padx=(0, self.S(2)))
                self.label(line, f"{r.get('pickrate', '?')}%", 7, MUTED, mono=True).pack(side="right")
                self.label(line, f"{r.get('winrate', '?')}%", 8, TEXT, True, mono=True).pack(side="right", padx=self.S(4))
                self.label(line, self._fit(r["name"], col_w - self.S(110), 8), 8, TEXT, anchor="w").pack(side="left", padx=self.S(4))
            tk.Frame(box, bg=PANEL, height=self.S(4)).pack()

    def _item_icon(self, parent, it, size):
        border = tk.Frame(parent, bg=GOOD if it.get("core") else PANEL, padx=self.S(1), pady=self.S(1))
        border.pack(side="left", padx=(0, self.S(3)))
        self.icon(border, it.get("icon"), size, tip=it.get("name", "")).pack()

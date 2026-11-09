# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
"""Tab Combo lõi: lối chơi, combo kèm lý do, đồ khuyên dùng, mẹo."""
from __future__ import annotations

import tkinter as tk

from i18n import T
from theme import PANEL, PANEL2, LINE, TEXT, MUTED, RARITY_COLOR, TIER_COLOR


class CombosMixin:
    """Tab Combo lõi: lối chơi, combo kèm lý do, đồ khuyên dùng, mẹo."""

    def _render_combos(self, root, c, st, wrap):
        styles = c.get("playstyles") or []
        if not styles:
            self.label(root, T("Chưa có lối chơi / combo cho tướng này."), 11, MUTED).pack(pady=self.S(40))
            return
        self.label(root, T("Hạng combo là đánh giá của biên tập viên, không phải tỉ lệ thắng."),
                   8, MUTED, wraplength=wrap, justify="left").pack(anchor="w", pady=(self.S(2), self.S(8)))
        for s in styles:
            card = tk.Frame(root, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
            card.pack(fill="x", padx=(0, self.S(10)), pady=(0, self.S(10)))
            head = tk.Frame(card, bg=PANEL, padx=self.S(10), pady=self.S(6))
            head.pack(fill="x")
            if s.get("tier"):
                self.badge(head, s["tier"], TIER_COLOR.get(s["tier"], MUTED)).pack(side="left", padx=(0, self.S(8)))
            self.label(head, s["name"], 10, TEXT, True, wraplength=wrap, justify="left").pack(side="left")
            if s.get("description"):
                self.label(card, s["description"], 9, "#c9cddb", wraplength=wrap, justify="left",
                           padx=self.S(10)).pack(anchor="w", pady=(0, self.S(6)))
            for cb in s.get("combos", []):
                bg = PANEL
                tk.Frame(card, bg=LINE, height=1).pack(fill="x")
                row = tk.Frame(card, bg=bg, padx=self.S(10), pady=self.S(6))
                row.pack(fill="x")
                line = tk.Frame(row, bg=bg)
                line.pack(anchor="w")
                self.badge(line, cb["tier"], TIER_COLOR.get(cb["tier"], MUTED)).pack(side="left", padx=(0, self.S(8)))
                for k, a in enumerate(cb["augments"]):
                    if k:
                        self.label(line, "+", 10, MUTED).pack(side="left", padx=self.S(3))
                    chip = tk.Frame(line, bg=PANEL2, padx=self.S(4), pady=self.S(1))
                    chip.pack(side="left")
                    self.icon(chip, a["id"], 18).pack(side="left")
                    self.label(chip, a["name"], 9, RARITY_COLOR.get(a.get("rarity"), TEXT)).pack(side="left", padx=self.S(4))
                if cb.get("why"):
                    self.label(row, cb["why"], 9, "#c9cddb", wraplength=wrap, justify="left").pack(anchor="w", pady=(self.S(3), 0))
            if s.get("items"):
                tk.Frame(card, bg=LINE, height=1).pack(fill="x")
                row = tk.Frame(card, bg=PANEL, padx=self.S(10), pady=self.S(6))
                row.pack(fill="x")
                self.label(row, T("Đồ khuyên dùng:"), 9, MUTED).pack(side="left", padx=(0, self.S(8)))
                for it in s["items"]:
                    self._item_icon(row, it, 30)
            if s.get("tips"):
                tk.Frame(card, bg=LINE, height=1).pack(fill="x")
                tips = tk.Frame(card, bg=PANEL, padx=self.S(10), pady=self.S(6))
                tips.pack(fill="x")
                for t in s["tips"]:
                    self.label(tips, f"•  {t['title']}. {t['text']}", 9, "#c9cddb", wraplength=wrap,
                               justify="left").pack(anchor="w", pady=self.S(1))

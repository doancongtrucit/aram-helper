# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
"""Bảng lõi 3 bậc, thẻ lõi, tô sáng khi tìm / khi đang chọn lõi, ô Nên chọn."""
from __future__ import annotations

import tkinter as tk

import advice
import settings
from i18n import T
from theme import (
    BG, PANEL, PANEL2, CARD, LINE, TEXT, MUTED, DIMTEXT, GOOD, OKC, BAD, HIT_BG, RARITY,
    TIER_COLOR, LOW_PICK, CARD_MIN_W, CARD_H, CARD_GAP, fold)


class AugmentsMixin:
    """Bảng lõi 3 bậc, thẻ lõi, tô sáng khi tìm / khi đang chọn lõi, ô Nên chọn."""

    def _per_tier(self, pane_w, pane_h) -> tuple[int, int]:
        """(số cột, số lõi mỗi bậc). top_n = 0: tự vừa chiều cao để 3 bậc không phải cuộn."""
        cols = max(1, (pane_w - self.S(8)) // self.S(CARD_MIN_W))
        n = int(settings.get("top_n") or 0)
        if n <= 0:
            head, step = self._meas or (self.S(52), self.S(CARD_H + CARD_GAP + 8))
            avail = pane_h - 3 * head - (self.S(150) if self._follow_offer() else 0)
            rows = max(1, int(avail // (3 * step)))
            n = min(16, max(cols, cols * rows))
        return cols, n

    def _measure(self) -> bool:
        """Đo chiều cao thật của tiêu đề bậc và 1 hàng thẻ (font / DPI khác nhau). True nếu khác lần trước."""
        try:
            sec, rows = self._secs[0]
            card = next(c for c in self.cards.values() if c["rarity"] == RARITY[0][0] and c["w"].winfo_manager())
            step = card["w"].winfo_height() + self.S(CARD_GAP)
            head = sec.winfo_height() + self.S(8) - rows * step
        except (StopIteration, IndexError, tk.TclError):
            return False
        if step <= 4 or head <= 0:
            return False
        old, self._meas = self._meas, (head, step)
        return old is None or abs(old[0] - head) > 2 or abs(old[1] - step) > 2

    def _follow_offer(self) -> bool:
        return bool(settings.get("app_follow_offer"))

    def _render_augments(self, root, champ, st, pane_w, pane_h):
        self.advice_box = tk.Frame(root, bg=BG)
        self.advice_box.pack(fill="x", padx=(0, self.S(6)))
        # Cửa sổ chính chỉ để xem và tìm: không theo lõi đã chọn trong trận (việc đó ở overlay)
        any_tier = {}
        for c in advice.combos(champ):
            for a in c["augments"]:
                if advice.TIER_BONUS.get(c["tier"], 0) > advice.TIER_BONUS.get(any_tier.get(a["id"]), 0):
                    any_tier[a["id"]] = c["tier"]
        base = champ.get("winrate") or 50
        cols, top_n = self._per_tier(pane_w, pane_h)
        self._auto_n = (cols, top_n)
        self._secs = []
        card_w = (pane_w - self.S(8)) / cols
        self._name_w = max(self.S(50), int(card_w - self.S(76)))
        for key, title, color in RARITY:
            items = champ.get("augments", {}).get(key, [])
            more, open_ = len(items) - top_n, key in self.expanded
            sec = tk.Frame(root, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
            sec.pack(fill="x", pady=(0, self.S(8)), padx=(0, self.S(6)))
            head = tk.Frame(sec, bg=PANEL, padx=self.S(10), pady=self.S(4))
            head.pack(fill="x")
            self.label(head, T(title), 10, color, True).pack(side="left")
            if more > 0:
                self.button(head, T("Thu gọn") if open_ else T("Xem thêm ({n})", n=more),
                            lambda k=key: self._toggle_more(k), 8).pack(side="right")
            body = tk.Frame(sec, bg=PANEL, padx=self.S(4), pady=self.S(4))
            body.pack(fill="x")
            for c in range(cols):
                body.grid_columnconfigure(c, weight=1, uniform="card")
            shown = len(items) if open_ else min(len(items), top_n)
            self._secs.append((sec, -(-shown // cols)))
            for i, a in enumerate(items):
                card = self._aug_card(body, a, i, color, base, any_tier.get(a["id"]))
                card["extra"], card["rarity"], card["pos"] = i >= top_n, key, (i // cols, i % cols)
                self.cards[a["id"]] = card
                if not card["extra"] or open_:
                    card["w"].grid(row=card["pos"][0], column=card["pos"][1], sticky="nsew",
                                   padx=self.S(CARD_GAP // 2), pady=self.S(CARD_GAP // 2))
            if not items:
                self.label(body, T("Không có dữ liệu"), 10, MUTED).grid(row=0, column=0)

    def _toggle_more(self, key):
        self.expanded.symmetric_difference_update({key})
        self._full_sig = None

    def _aug_card(self, parent, a, i, color, base, any_tier):
        outer = tk.Frame(parent, bg=color)                       # viền trái màu theo bậc
        inner = tk.Frame(outer, bg=CARD, padx=self.S(6), pady=self.S(3))
        inner.pack(fill="both", expand=True, padx=(self.S(2), 0))
        frame = tk.Frame(inner, bg="#0b0e18", highlightthickness=1, highlightbackground=color, padx=self.S(2), pady=self.S(2))
        frame.pack(side="left")
        self.icon(frame, a["id"], 30).pack()
        right = tk.Frame(inner, bg=CARD)
        right.pack(side="left", fill="x", expand=True, padx=(self.S(8), 0))
        top = tk.Frame(right, bg=CARD)
        top.pack(fill="x")
        self.label(top, f"{i + 1}", 7, MUTED).pack(side="left")
        name = self.label(top, self._fit(a["name"], self._name_w, 9, True), 9, TEXT, True, anchor="w")
        name.pack(side="left", padx=(self.S(3), 0), fill="x", expand=True)
        stats = tk.Frame(right, bg=CARD)
        stats.pack(fill="x")
        wr = a.get("winrate") or 0
        wcol = GOOD if wr >= base + 2 else OKC if wr >= base - 1 else BAD
        self.label(stats, f"{wr:.2f}%", 9, wcol, True, mono=True).pack(side="left")
        low = a.get("pickrate") is not None and a["pickrate"] < LOW_PICK
        self.label(stats, f"{a.get('pickrate', '?')}%{'*' if low else ''}", 8, MUTED, mono=True).pack(side="left", padx=self.S(6))
        roomy = self._name_w >= self.S(150)        # thẻ hẹp: nhãn combo rút gọn còn "◆A"
        if any_tier:
            self.badge(stats, T("combo {t}", t=any_tier) if roomy else f"◆{any_tier}",
                       TIER_COLOR.get(any_tier, MUTED)).pack(side="left")
        card = {"w": outer, "inner": inner, "name": name, "color": color, "fold": fold(a["name"])}
        self._style_card(card, "normal")
        return card

    def _style_card(self, card, state):
        bg = HIT_BG if state == "hit" else CARD
        edge = GOOD if state == "hit" else card["color"]
        card["w"].configure(bg=edge)

        def paint(w):
            if isinstance(w, (tk.Frame, tk.Label)) and w["bg"] in (CARD, HIT_BG):
                w.configure(bg=bg)
            for ch in w.winfo_children():
                paint(ch)
        paint(card["inner"])
        card["name"].configure(fg=DIMTEXT if state == "dim" else TEXT)

    # ----- cập nhật nhẹ: tìm kiếm (+ bảng lõi đọc từ màn hình nếu bật) -----
    def _light_update(self):
        st = self._st
        champ = st.get("champion")
        if not champ or self.tab != "aug" or self.advice_box is None:
            return
        text = self.search_text()
        terms = [] if self.champion_matches(text) else [t.strip() for t in fold(text).split(",") if t.strip()]
        adv = st.get("advice") if self._follow_offer() else None    # mặc định: cửa sổ chính giữ nguyên
        sig = (tuple(terms), repr([(a["slot"], [c["id"] for c in a["candidates"]]) for a in adv or []]))
        if sig == self._light_sig:
            return
        self._light_sig = sig
        offer_ids = {c["id"] for a in adv or [] for c in a["candidates"]}
        hits = [i for i, c in self.cards.items() if any(t in c["fold"] for t in terms)] if terms else []
        active = bool(terms or offer_ids)
        for i, c in self.cards.items():
            hit = i in offer_ids or i in hits
            self._style_card(c, "hit" if hit else "dim" if active else "normal")
            if c["extra"]:   # lõi ngoài top N đang được tìm / đọc ra thì vẫn hiện
                if hit or c["rarity"] in self.expanded:
                    c["w"].grid(row=c["pos"][0], column=c["pos"][1], sticky="nsew",
                                padx=self.S(CARD_GAP // 2), pady=self.S(CARD_GAP // 2))
                else:
                    c["w"].grid_remove()
        for w in self.advice_box.winfo_children():
            w.destroy()
        if adv:
            self._advice(adv, "offer")
        elif terms:
            cat = self.hub.catalog()
            ids = list(dict.fromkeys(hits + [i for i, a in cat.items() if any(t in fold(a["name"]) for t in terms)]))[:6]
            if ids:
                self._advice(advice.rank_offer([[i] for i in ids], champ, cat, set()), "search")

    def _advice(self, ranked, source):
        box = tk.Frame(self.advice_box, bg=PANEL, highlightthickness=1, highlightbackground=GOOD,
                       padx=self.S(10), pady=self.S(6))
        box.pack(fill="x", pady=(0, self.S(8)))
        rows = sorted(ranked, key=lambda r: r["rank"])
        head = tk.Frame(box, bg=PANEL)
        head.pack(fill="x")
        self.label(head, (T("Đọc từ màn hình · ") if source == "offer" else "") + T("Nên chọn:"), 9, TEXT).pack(side="left")
        self.label(head, rows[0]["best"]["name"], 9, GOOD, True).pack(side="left", padx=self.S(4))
        if source == "offer" and self.scanner:
            self.button(head, T("Ẩn"), self.scanner.mark_hidden, 8).pack(side="right")
        for r in rows:
            b = r["best"]
            row = tk.Frame(box, bg=PANEL, pady=self.S(2))
            row.pack(fill="x")
            self.icon(row, b["id"], 24).pack(side="left")
            mid = tk.Frame(row, bg=PANEL)
            mid.pack(side="left", fill="x", expand=True, padx=self.S(8))
            if len(r["candidates"]) > 1:
                self.label(mid, T("Một trong (icon giống nhau):"), 8, MUTED).pack(anchor="w")
                line = tk.Frame(mid, bg=PANEL)
                line.pack(anchor="w")
                for c in r["candidates"]:
                    chip = tk.Frame(line, bg=PANEL2, padx=self.S(4), pady=self.S(1))
                    chip.pack(side="left", padx=(0, self.S(4)), pady=self.S(2))
                    self.icon(chip, c["id"], 16).pack(side="left")
                    self.label(chip, c["name"], 8).pack(side="left", padx=self.S(3))
            else:
                self.label(mid, b["name"], 9, GOOD if r["rank"] == 1 else TEXT, r["rank"] == 1).pack(anchor="w")
            wr = (T("chưa có số liệu") if b["winrate"] is None
                  else f"{b['winrate']}%" + (T(" (chung, mọi tướng)") if b["source"] == "chung" else ""))
            extra = T("  ·  +{b} hợp combo {t}", b=advice.TIER_BONUS[b["fit"]], t=b["fit"]) if b.get("fit") else ""
            if r.get("reroll"):
                extra += T(" · ↻ nên đổi")
            self.label(mid, T("Thắng {wr}{extra}", wr=wr, extra=extra), 8, OKC if r.get("reroll") else MUTED).pack(anchor="w")

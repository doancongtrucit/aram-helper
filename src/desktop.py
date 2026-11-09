"""Cửa sổ chính ARAM Helper (tkinter – có sẵn trong Python, nhẹ RAM).

Tab "Lõi & trang bị": cửa sổ rộng → 2 cột (lõi bên trái, trang bị bên phải), mỗi cột cuộn riêng; "Tự vừa cửa sổ"
chọn số lõi mỗi bậc theo chiều cao để không phải cuộn dù cửa sổ to/nhỏ hay zoom (Ctrl + / Ctrl - / Ctrl 0).
Tab "Combo lõi": lối chơi, combo lõi kèm lý do, đồ khuyên dùng, mẹo.
Ô tìm kiếm: gõ tên tướng → danh sách chọn nhanh (↑ ↓ Enter); gõ tên lõi → tô sáng lõi.
Mặc định cửa sổ chính KHÔNG đổi khi bảng chọn lõi hiện ra (gợi ý ở overlay / ESP32) – bật lại trong Cài đặt.
"""
from __future__ import annotations

import sys
import threading
import time
import tkinter as tk
from tkinter import ttk

import i18n
import paths
import settings
import updater
from i18n import T
from theme import (
    BG, PANEL, PANEL2, LINE, TEXT, MUTED, DIMTEXT, GOOD, OKC, BAD, ACCENT, TIER_COLOR, IS_MAC, FONT, MONO,
    WIDE_MIN, app_logo)
from widgets import Images, Scroll, Tooltip
from views.augments import AugmentsMixin
from views.combos import CombosMixin
from views.items import ItemsMixin
from views.search import SearchMixin


# ---------- cửa sổ chính ----------
class App(SearchMixin, AugmentsMixin, ItemsMixin, CombosMixin):
    def __init__(self, root: tk.Tk, hub, scanner=None, overlay=None):
        self.root, self.hub, self.scanner, self.overlay = root, hub, scanner, overlay
        # Windows: 96 dpi = 100%; macOS Tk báo 72 dpi nhưng màn Retina đã tự nhân → giữ tỉ lệ 1
        self.base_scale = 1.0 if IS_MAC else root.winfo_fpixels("1i") / 96.0
        self.img = Images(root, self.base_scale)
        self.tooltip = Tooltip(self)
        self.tab = "aug"
        self.expanded: set[str] = set()
        self.cards: dict[int, dict] = {}
        self.advice_box = None
        self._full_sig = self._light_sig = None
        self._st: dict = {}
        self._fonts: dict = {}
        self._size = (0, 0)
        self._champs: list[tuple[str, str, str]] = []   # (slug, tên hiển thị, tên bỏ dấu)
        self._popup = None
        self._settings_dlg = None
        self._meas = None              # (cao tiêu đề bậc, cao 1 hàng thẻ) đo được – để tự vừa cửa sổ
        self._auto_n = None
        self._fit_args = (800, 600)
        self._secs = []

        root.title("ARAM Helper")
        root.configure(bg=BG)
        self._set_icon()
        self._update_info = None
        self._apply_zoom()
        root.geometry(f"{self.S(1280)}x{self.S(820)}")
        root.minsize(640, 420)
        root.attributes("-topmost", bool(settings.get("always_on_top")))
        for seq, step in (("<Control-equal>", 1), ("<Control-plus>", 1), ("<Control-KP_Add>", 1),
                          ("<Control-minus>", -1), ("<Control-KP_Subtract>", -1), ("<Control-Key-0>", 0)):
            root.bind(seq, lambda e, s=step: self._zoom_step(s))
        root.bind_all("<MouseWheel>", self._wheel)
        root.report_callback_exception = self._on_ui_error      # lỗi trong callback: ghi log + báo nhẹ
        root.bind("<Configure>", self._on_root_configure, add="+")
        settings.on_change(lambda ch: root.after(0, self._on_settings, ch))
        self._style()
        self._build()
        threading.Thread(target=self._load_champion_list, daemon=True).start()
        updater.check_async(lambda info: root.after(0, self._show_update, info))
        root.after(200, self._poll)

    def _set_icon(self):
        try:
            if not IS_MAC and (paths.RES / "assets" / "icon.ico").exists():
                self.root.iconbitmap(default=str(paths.RES / "assets" / "icon.ico"))
            self._icon_img = tk.PhotoImage(file=str(paths.RES / "assets" / "icon.png"))
            self.root.iconphoto(True, self._icon_img)
        except (tk.TclError, OSError):
            pass

    def _show_update(self, info):
        """Có bản mới trên GitHub: hiện nút nhỏ ở thanh trên, bấm để mở trang tải."""
        self._update_info = info
        if getattr(self, "update_slot", None) is None or not self.update_slot.winfo_exists():
            return
        for w in self.update_slot.winfo_children():
            w.destroy()
        import webbrowser
        b = self.button(self.update_slot, "⬆ " + T("Có bản mới {v}", v=info["version"]),
                        lambda: webbrowser.open(info["url"]), 9, primary=True)
        b.pack(side="left")

    # ----- tỉ lệ / font -----
    def _apply_zoom(self):
        self.zoom = max(0.6, min(1.8, float(settings.get("ui_zoom") or 1.0)))
        self.scale = self.base_scale * self.zoom
        self.img.scale = self.scale

    def S(self, px) -> int:
        return int(round(px * self.scale))

    def f(self, size, bold=False, mono=False):
        return (MONO if mono else FONT, max(6, int(round(size * self.zoom))), "bold" if bold else "normal")

    def _zoom_step(self, step):
        z = 1.0 if step == 0 else round(min(1.6, max(0.7, self.zoom + 0.1 * step)), 2)
        settings.set("ui_zoom", z)

    def _on_settings(self, changed: dict):
        if "lang" in changed or "ui_zoom" in changed:
            self._rebuild()
            if "lang" in changed:
                threading.Thread(target=self._load_champion_list, daemon=True).start()
        elif {"top_n", "app_follow_offer"} & set(changed):
            self._full_sig = None
        if "always_on_top" in changed:
            self.root.attributes("-topmost", bool(changed["always_on_top"]))

    def _rebuild(self):
        """Đổi ngôn ngữ / cỡ chữ: dựng lại toàn bộ cửa sổ (giữ các cửa sổ con như overlay, Cài đặt)."""
        self._hide_popup()
        self.tooltip.hide()
        for w in self.root.winfo_children():
            if not isinstance(w, tk.Toplevel):
                w.destroy()
        self._fonts = {}
        self._meas = None
        self._apply_zoom()
        self._style()
        self._build()
        self._full_sig = self._light_sig = None

    def _style(self):
        st = ttk.Style(self.root)
        st.theme_use("clam")
        st.configure("Vertical.TScrollbar", background=PANEL2, troughcolor=BG, bordercolor=BG, arrowcolor=MUTED,
                     lightcolor=PANEL2, darkcolor=PANEL2)

    # ----- widget nhỏ -----
    def label(self, parent, text="", size=10, color=TEXT, bold=False, bg=None, mono=False, **kw):
        return tk.Label(parent, text=text, fg=color, bg=bg or parent["bg"], font=self.f(size, bold, mono), **kw)

    def button(self, parent, text, cmd, size=10, primary=False):
        b = tk.Label(parent, text=text, fg="#05261a" if primary else TEXT, bg=GOOD if primary else PANEL2,
                     font=self.f(size, primary), padx=self.S(9), pady=self.S(3), cursor="hand2")
        b.bind("<Button-1>", lambda e: cmd())
        if not primary:
            b.bind("<Enter>", lambda e: b.configure(bg=LINE))
            b.bind("<Leave>", lambda e: b.configure(bg=PANEL2))
        return b

    def icon(self, parent, src, size, bg=None, tip=""):
        lb = tk.Label(parent, bg=bg or parent["bg"], bd=0)
        self.img.set(lb, src, size)
        if tip:
            self.tooltip.bind(lb, tip)
        return lb

    def badge(self, parent, text, color, filled=False):
        return tk.Label(parent, text=text, fg="#062" if filled else color, bg=color if filled else parent["bg"],
                        font=self.f(7, True), padx=self.S(3), highlightthickness=1, highlightbackground=color)

    def _fit(self, text, width_px, size, bold=False):
        """Cắt chữ cho vừa bề rộng, thêm '…' (Label của tkinter tự cắt cụt không có dấu)."""
        from tkinter import font as tkfont
        key = (size, bold, self.zoom)
        if key not in self._fonts:
            self._fonts[key] = tkfont.Font(family=FONT, size=max(6, int(round(size * self.zoom))),
                                           weight="bold" if bold else "normal")
        f = self._fonts[key]
        if f.measure(text) <= width_px:
            return text
        while text and f.measure(text + "…") > width_px:
            text = text[:-1]
        return text.rstrip() + "…"

    @staticmethod
    def bind_tree(widget, fn):
        widget.bind("<Button-1>", lambda e: fn())
        widget.configure(cursor="hand2")
        for ch in widget.winfo_children():
            App.bind_tree(ch, fn)

    def _wheel(self, e):
        """Cuộn vùng nằm dưới con trỏ (có 2 vùng cuộn song song khi cửa sổ rộng)."""
        w = self.root.winfo_containing(e.x_root, e.y_root)
        while w is not None and not hasattr(w, "_scroll"):
            w = w.master
        if w is not None:
            step = -e.delta if IS_MAC else int(-e.delta / 40)
            w._scroll.canvas.yview_scroll(step, "units")

    # ----- khung cố định -----
    def _build(self):
        top = tk.Frame(self.root, bg=BG, padx=self.S(12), pady=self.S(6))
        top.pack(fill="x")
        self.dot = tk.Canvas(top, width=self.S(12), height=self.S(12), bg=BG, highlightthickness=0)
        self.dot.pack(side="left")
        self._dot = self.dot.create_oval(1, 1, self.S(11), self.S(11), fill=MUTED, outline="")
        self.status = self.label(top, T("Đang chờ trận…"), 10, TEXT, True)
        self.status.pack(side="left", padx=(self.S(6), self.S(12)))

        self.search_var = tk.StringVar()
        self.search = tk.Entry(top, textvariable=self.search_var, bg=PANEL, fg=TEXT, insertbackground=TEXT,
                               relief="flat", font=self.f(10), highlightthickness=1, highlightbackground=LINE,
                               highlightcolor=ACCENT)
        self.search.pack(side="left", fill="x", expand=True, ipady=self.S(3))
        self._placeholder(self.search, self.search_var,
                          T("Tìm tướng hoặc lõi (không cần dấu, nhiều lõi cách nhau dấu phẩy)…"))
        self.search_var.trace_add("write", lambda *_: self.root.after(80, self._on_search))
        self.search.bind("<Down>", lambda e: self._popup_move(1))
        self.search.bind("<Up>", lambda e: self._popup_move(-1))
        self.search.bind("<Return>", lambda e: self._popup_pick())
        self.search.bind("<FocusOut>", lambda e: self.root.after(200, self._hide_popup), add="+")

        self.update_slot = tk.Frame(top, bg=BG)
        self.update_slot.pack(side="left", padx=(self.S(8), 0))
        if self._update_info:
            self.root.after(0, self._show_update, self._update_info)
        self.button(top, T("Tự động"), self._auto).pack(side="left", padx=(self.S(8), self.S(4)))
        self.button(top, "⚙ " + T("Cài đặt"), self.open_settings).pack(side="left", padx=self.S(4))
        if self.overlay:
            self.ov_var = tk.BooleanVar(value=self.overlay.visible)
            tk.Checkbutton(top, text="Overlay", variable=self.ov_var, command=self._toggle_overlay,
                           bg=BG, fg=TEXT, selectcolor=PANEL, activebackground=BG, activeforeground=TEXT,
                           font=self.f(10)).pack(side="left", padx=self.S(4))

        bar2 = tk.Frame(self.root, bg=BG, padx=self.S(12))
        bar2.pack(fill="x")
        self.scan_lbl = self.label(bar2, "", 9, MUTED, anchor="w")
        self.scan_lbl.pack(side="left", fill="x", expand=True)
        if self.scanner:
            self.button(bar2, T("Hiệu chỉnh"), lambda: self.scanner.request_calibration(5), 9).pack(side="right")

        headrow = tk.Frame(self.root, bg=BG, padx=self.S(12), pady=self.S(4))
        headrow.pack(fill="x")
        self.tabs = tk.Frame(headrow, bg=BG)
        self.tabs.pack(side="right", anchor="s")
        self.head = tk.Frame(headrow, bg=BG)
        self.head.pack(side="left", fill="x", expand=True)
        tk.Frame(self.root, bg=LINE, height=1).pack(fill="x", padx=self.S(12))
        self.owned_bar = tk.Frame(self.root, bg=BG, padx=self.S(12))
        self.owned_bar.pack(fill="x")
        self.body = tk.Frame(self.root, bg=BG)
        self.body.pack(fill="both", expand=True, padx=(self.S(12), self.S(4)), pady=(self.S(4), self.S(6)))

    def _placeholder(self, entry, var, text):
        def show(_=None):
            if not var.get():
                entry.configure(fg=DIMTEXT)
                var.set(text)

        def hide(_=None):
            if var.get() == text:
                var.set("")
                entry.configure(fg=TEXT)
        entry.bind("<FocusIn>", hide)
        entry.bind("<FocusOut>", show, add="+")
        entry.bind("<Escape>", lambda e: (self._hide_popup(), var.set(""), self.root.focus()))
        entry._ph_text = text
        show()

    def search_text(self) -> str:
        v = self.search_var.get()
        return "" if v == getattr(self.search, "_ph_text", None) else v

    def _toggle_overlay(self):
        self.overlay.set_visible(self.ov_var.get())
        settings.set("overlay", bool(self.ov_var.get()))

    # ----- vòng cập nhật -----
    def _on_root_configure(self, e):
        if e.widget is not self.root:
            return
        size = (self.root.winfo_width() // self.S(40), self.root.winfo_height() // self.S(40))
        if size != self._size:
            self._size = size
            self._full_sig = None

    def _poll(self):
        try:
            st = self.hub.state()
            self._st = st
            self._update_bars(st)
            champ = st.get("champion")
            full = ((champ or {}).get("slug"), (champ or {}).get("fetched_at"), (champ or {}).get("name"), self.tab,
                    tuple(sorted(self.expanded)), tuple(st.get("owned", [])), self._size, st.get("focus"),
                    repr(st.get("counter")), i18n.lang())
            if full != self._full_sig:
                self._full_sig = full
                self._render(st)
            self._light_update()
        except Exception:       # không để giao diện chết vì 1 lỗi
            self._on_ui_error(*sys.exc_info())
        self.root.after(700, self._poll)

    def _update_bars(self, st):
        game, scan = st.get("game", {}), st.get("scan") or {}
        if self.overlay and self.ov_var.get() != self.overlay.visible:   # bật/tắt bằng phím tắt
            self.ov_var.set(self.overlay.visible)
        self.dot.itemconfigure(self._dot, fill=GOOD if game.get("in_game") else MUTED)
        champ = st.get("champion") or {}
        if game.get("in_game"):
            txt = T("Trong trận: {name}", name=champ.get("name") or game.get("champion_name") or "?")
        elif st.get("focus"):
            txt = T("Đang xem: {name}", name=champ.get("name") or st["focus"])
        else:
            txt = T("Đang chờ trận…")
        self.status.configure(text=txt)
        if scan.get("error"):
            s, col = scan["error"], OKC
        elif scan.get("calibrating_in") is not None:
            s = (T("Hiệu chỉnh sau {n} giây – mở bảng chọn lõi trong game", n=int(scan["calibrating_in"]) + 1)
                 if scan["calibrating_in"] > 0 else scan.get("status", ""))
            col = OKC
        else:
            s = scan.get("status", "")
            col = GOOD if (scan.get("offer") or {}).get("visible") else MUTED if scan.get("calibrated") else OKC
        self.scan_lbl.configure(text=T("Quét màn hình: {s}", s=i18n.status(s)) if s else "", fg=col)

    # ----- vẽ lại toàn bộ (đổi tướng / tab / lõi đã chọn / kích thước / ngôn ngữ) -----
    def _render(self, st):
        champ = st.get("champion")
        keep_y = {}
        for name in ("_left", "_right", "_single"):
            sc = getattr(self, name, None)
            if sc is not None and sc.winfo_exists() and not getattr(self, "_scroll_top", False):
                keep_y[name] = sc.canvas.yview()[0]
        if (champ or {}).get("slug") != getattr(self, "_last_slug", None):
            keep_y = {}
        self._last_slug, self._scroll_top = (champ or {}).get("slug"), False
        self.tooltip.hide()
        for w in self.head.winfo_children() + self.tabs.winfo_children() + self.body.winfo_children():
            w.destroy()
        self._left = self._right = self._single = None
        self.cards, self.advice_box, self._light_sig = {}, None, None
        self._render_owned(st)
        if not champ:
            msg = (T("Đang tải dữ liệu {name}…", name=st["focus"]) if st.get("focus") and not st.get("error")
                   else st.get("error") or T("Vào một trận ARAM Hỗn Loạn để app tự nhận tướng, hoặc tìm tướng ở ô tìm kiếm phía trên."))
            self._render_welcome(msg)
            return
        self._render_head(champ)
        self._render_tabs(champ)
        self.root.update_idletasks()
        W = max(self.body.winfo_width(), self.S(500))
        H = max(self.body.winfo_height(), self.S(300))
        if self.tab == "aug":
            if W >= self.S(WIDE_MIN):
                self.body.grid_columnconfigure(0, weight=3, uniform="pane")
                self.body.grid_columnconfigure(1, weight=2, uniform="pane")
                self.body.grid_rowconfigure(0, weight=1)
                self._left, self._right = Scroll(self.body, self.S(30)), Scroll(self.body, self.S(30))
                self._left.grid(row=0, column=0, sticky="nsew", padx=(0, self.S(8)))
                self._right.grid(row=0, column=1, sticky="nsew")
                left_w = int(W * 3 / 5) - self.S(26)
                right_w = int(W * 2 / 5) - self.S(18)
                self._fit_args = (left_w, H)
                self._render_augments(self._left.inner, champ, st, left_w, H)
                self._render_counter(self._right.inner, st.get("counter") or [], right_w)
                self._render_items(self._right.inner, champ, right_w)
            else:
                self._single = Scroll(self.body, self.S(30))
                self._single.pack(fill="both", expand=True)
                self._fit_args = (W - self.S(26), H)
                self._render_augments(self._single.inner, champ, st, W - self.S(26), H)
                self._render_counter(self._single.inner, st.get("counter") or [], W - self.S(26))
                self._render_items(self._single.inner, champ, W - self.S(26))
        else:
            self._single = Scroll(self.body, self.S(30))
            self._single.pack(fill="both", expand=True)
            self._render_combos(self._single.inner, champ, st, W - self.S(40))
        self.root.update_idletasks()
        if (self.tab == "aug" and int(settings.get("top_n") or 0) <= 0 and self._measure()
                and not getattr(self, "_refit", False)):
            # lần đầu / đổi cỡ chữ: số đo thật khác ước lượng → vẽ lại 1 lần cho vừa khít
            cols, n = self._per_tier(*self._fit_args)
            if (cols, n) != self._auto_n:
                self._refit = True
                try:
                    self._render(st)
                finally:
                    self._refit = False
                return
        for name, y in keep_y.items():
            sc = getattr(self, name, None)
            if sc is not None:
                sc.canvas.yview_moveto(y)

    def _render_welcome(self, msg):
        """Màn chào khi chưa có tướng: logo, tên app, giới thiệu ngắn."""
        from version import __version__
        box = tk.Frame(self.body, bg=BG)
        box.place(relx=0.5, rely=0.42, anchor="center")
        try:
            tk.Label(box, image=app_logo(self.root, self.S(128)), bg=BG).pack()
        except Exception:
            pass
        self.label(box, "ARAM Helper", 22, TEXT, True).pack(pady=(self.S(10), 0))
        self.label(box, T("Gợi ý lõi và trang bị cho ARAM Hỗn Loạn") + f"  ·  v{__version__}", 10, MUTED).pack()
        self.label(box, msg, 11, OKC if self._st.get("error") else TEXT, wraplength=self.S(620),
                   justify="center").pack(pady=(self.S(18), 0))

    def _render_head(self, c):
        self.icon(self.head, c.get("icon"), 40).pack(side="left", padx=(0, self.S(10)))
        box = tk.Frame(self.head, bg=BG)
        box.pack(side="left")
        row = tk.Frame(box, bg=BG)
        row.pack(anchor="w")
        self.label(row, c.get("name", ""), 15, TEXT, True).pack(side="left")
        self.label(row, c.get("tier", ""), 15, TIER_COLOR.get(c.get("tier"), OKC), True).pack(side="left", padx=self.S(6))
        meta = "   ·   ".join([T("Tỉ lệ thắng {wr}%", wr=c.get("winrate")),
                               T("{n} trận", n=f"{c.get('games', 0):,}".replace(",", ".")),
                               T("Bản {v}", v=c.get("patch", "?"))])
        if c.get("fetched_at"):
            meta += "   ·   " + T("Dữ liệu {n} phút trước", n=int((time.time() - c["fetched_at"]) / 60))
            meta += T(" (cũ, mạng lỗi)") if c.get("stale") else ""
        self.label(box, meta, 8, MUTED).pack(anchor="w")

    def _render_tabs(self, c):
        n = sum(len(s.get("combos", [])) for s in c.get("playstyles", []))
        for key, text in (("aug", T("Lõi & trang bị")), ("combo", T("Combo lõi ({n})", n=n))):
            on = self.tab == key
            t = tk.Label(self.tabs, text=text, fg=TEXT if on else MUTED, bg=BG, font=self.f(10, True),
                         padx=self.S(10), pady=self.S(4), cursor="hand2")
            t.pack(side="left")
            if on:
                tk.Frame(t, bg=ACCENT, height=self.S(2)).place(relx=0, rely=1, relwidth=1, anchor="sw")
            t.bind("<Button-1>", lambda e, k=key: self._set_tab(k))

    def _set_tab(self, k):
        if k != self.tab:
            self._scroll_top = True
        self.tab = k
        self._full_sig = None

    def _render_owned(self, st):
        for w in self.owned_bar.winfo_children():
            w.destroy()
        ids = st.get("owned", [])
        champ = st.get("champion")
        if not champ or not ids:
            self.owned_bar.configure(pady=0)
            return
        self.owned_bar.configure(pady=self.S(3))
        self.label(self.owned_bar, T("Lõi đã chọn:"), 9, MUTED).pack(side="left", padx=(0, self.S(6)))
        names = self._names(champ)
        for i in ids:
            chip = tk.Frame(self.owned_bar, bg=PANEL2, padx=self.S(4), pady=self.S(1))
            chip.pack(side="left", padx=self.S(3))
            self.icon(chip, i, 18).pack(side="left")
            self.label(chip, names.get(i, f"#{i}"), 9).pack(side="left", padx=self.S(4))
            x = self.label(chip, "✕", 9, MUTED, cursor="hand2")
            x.pack(side="left")
            x.bind("<Button-1>", lambda e, i=i: self._own(remove=i))
        self.button(self.owned_bar, T("Xoá hết"), lambda: self._own(clear=True), 8).pack(side="left", padx=self.S(8))

    def _names(self, champ) -> dict[int, str]:
        names = {i: a["name"] for i, a in self.hub.catalog().items()}
        for items in champ.get("augments", {}).values():
            for a in items:
                names[a["id"]] = a["name"]
        return names

    def _own(self, **kw):
        slug = (self._st.get("champion") or {}).get("slug")
        if slug:
            self.hub.update_owned(slug, **kw)
            if kw.get("add") and self.scanner:
                self.scanner.mark_hidden()
            self._full_sig = None

    # ----- lỗi giao diện -----
    def _on_ui_error(self, exc, val, tb):
        """Lỗi trong giao diện: ghi đủ vào app.log, hiện 1 thông báo nhỏ (tối đa 1 lần / 30 giây)."""
        import traceback
        print("Lỗi giao diện:\n" + "".join(traceback.format_exception(exc, val, tb)), end="", flush=True)
        now = time.time()
        if now - getattr(self, "_last_error_toast", 0) > 30:
            self._last_error_toast = now
            self.toast(T("Có lỗi nhỏ ở giao diện – đã ghi vào app.log. Bấm để mở thư mục dữ liệu."),
                       paths.open_data_folder)

    def toast(self, text, on_click=None, ms=8000):
        """Thông báo nhỏ ở góc dưới phải, tự ẩn sau ms; bấm vào thì gọi on_click."""
        old = getattr(self, "_toast_w", None)
        if old is not None and old.winfo_exists():
            old.destroy()
        lb = tk.Label(self.root, text=text, bg="#3a1d24", fg=TEXT, font=self.f(9), padx=self.S(12), pady=self.S(6),
                      highlightthickness=1, highlightbackground=BAD, cursor="hand2" if on_click else "")
        lb.place(relx=1, rely=1, x=-self.S(16), y=-self.S(16), anchor="se")

        def click(_e):
            lb.destroy()
            if on_click:
                on_click()
        lb.bind("<Button-1>", click)
        self.root.after(ms, lambda: lb.winfo_exists() and lb.destroy())
        self._toast_w = lb

    # ----- Cài đặt -----
    def open_settings(self):
        if self._settings_dlg is not None and self._settings_dlg.win.winfo_exists():
            self._settings_dlg.win.lift()
            return
        import settings_ui
        self._settings_dlg = settings_ui.SettingsDialog(self)

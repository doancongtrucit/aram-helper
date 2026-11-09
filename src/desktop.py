# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
"""Cửa sổ chính ARAM Helper (tkinter – có sẵn trong Python, nhẹ RAM).

Tab "Lõi & trang bị": cửa sổ rộng → 2 cột (lõi bên trái, trang bị bên phải), mỗi cột cuộn riêng; "Tự vừa cửa sổ"
chọn số lõi mỗi bậc theo chiều cao để không phải cuộn dù cửa sổ to/nhỏ hay zoom (Ctrl + / Ctrl - / Ctrl 0).
Tab "Combo lõi": lối chơi, combo lõi kèm lý do, đồ khuyên dùng, mẹo.
Ô tìm kiếm: gõ tên tướng → danh sách chọn nhanh (↑ ↓ Enter); gõ tên lõi → tô sáng lõi.
Mặc định cửa sổ chính KHÔNG đổi khi bảng chọn lõi hiện ra (gợi ý ở overlay) – bật lại trong Cài đặt.
"""
from __future__ import annotations

import sys
import threading
import time
import tkinter as tk
from tkinter import ttk

import about
import i18n
import paths
import settings
import theme
import updater
from i18n import T
from theme import (
    BG, PANEL, PANEL2, LINE, TEXT, MUTED, DIMTEXT, GOOD, OKC, BAD, ACCENT, TIER_COLOR, IS_MAC,
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
        theme.load_fonts(root)                  # Inter đi kèm app (font hệ thống nếu nạp lỗi)
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
        """Có bản mới trên GitHub: nút ở thanh trên – bản cài: cập nhật một chạm; bản khác: mở trang tải."""
        self._update_info = info
        if getattr(self, "update_slot", None) is None or not self.update_slot.winfo_exists():
            return
        for w in self.update_slot.winfo_children():
            w.destroy()
        text = T("Cập nhật lên {v}", v=info["version"]) if updater.can_self_update() \
            else T("Có bản mới {v}", v=info["version"])
        self._update_btn = self.button(self.update_slot, "⬆ " + text, lambda: self.start_update(info), 9, primary=True)
        self._update_btn.pack(side="left")
        self._update_text = "⬆ " + text

    # ----- cập nhật một chạm -----
    def start_update(self, info):
        """Tải bộ cài bản mới (kiểm tra mã băm), đóng app, cài im lặng, bộ cài tự mở lại app."""
        import webbrowser
        if not updater.can_self_update():
            webbrowser.open(info["url"])
            return
        if getattr(self, "_updating", False):
            return
        if (self._st.get("game") or {}).get("in_game"):
            self.toast(T("Đang trong trận – cập nhật sau khi hết trận nhé."))
            return
        from tkinter import messagebox
        if not messagebox.askyesno(
                T("Cập nhật ARAM Helper"),
                T("Cập nhật lên {v}?\n\nApp tải bộ cài (khoảng 45 MB), đóng lại, cài bản mới rồi tự mở lại. "
                  "Cài đặt và dữ liệu được giữ nguyên.", v=info["version"]), parent=self.root):
            return
        self._updating = True
        self._update_note(T("Đang tải bản cập nhật…"))
        job = {"pct": None, "done": None}          # luồng tải ghi vào, luồng giao diện đọc (không gọi Tk từ luồng phụ)

        def progress(done, total):
            if total:
                job["pct"] = done * 100 // total

        def run():
            try:
                job["done"] = ("ok", updater.prepare(info["version"], progress))
            except Exception as e:
                job["done"] = ("err", e)

        def watch(last=None):
            if job["done"]:
                kind, val = job["done"]
                return self._update_install(val) if kind == "ok" else self._update_failed(val)
            if job["pct"] is not None and job["pct"] != last:
                self._update_note(T("Đang tải… {p}%", p=job["pct"]))
            self.root.after(150, watch, job["pct"])
        threading.Thread(target=run, daemon=True, name="update-download").start()
        watch()

    def _update_note(self, text):
        """Hiện tiến độ trên nút cập nhật và trong Cài đặt (nếu đang mở)."""
        b = getattr(self, "_update_btn", None)
        if b is not None and b.winfo_exists():
            b.configure(text="⬇ " + text)
        dlg = self._settings_dlg
        if dlg is not None and dlg.win.winfo_exists():
            dlg.update_note(text)

    def _update_failed(self, e):
        import diag
        self._updating = False
        diag.log(f"cập nhật: lỗi {e}")
        b = getattr(self, "_update_btn", None)
        if b is not None and b.winfo_exists():
            b.configure(text=getattr(self, "_update_text", ""))
        self._update_note_reset(T("Cập nhật lỗi: {e}", e=e))
        self.toast(T("Cập nhật lỗi: {e}", e=e))

    def _update_note_reset(self, text):
        dlg = self._settings_dlg
        if dlg is not None and dlg.win.winfo_exists():
            dlg.update_note(text)

    def _update_install(self, path):
        import diag
        self._update_note(T("Đang cài – app sẽ tự mở lại…"))
        try:
            updater.launch_installer(path)
        except Exception as e:
            self._update_failed(e)
            return
        diag.log(f"cập nhật: chạy bộ cài {path.name}, đóng app")
        self.root.after(400, self.root.destroy)

    # ----- tỉ lệ / font -----
    def _apply_zoom(self):
        self.zoom = max(0.6, min(1.8, float(settings.get("ui_zoom") or 1.0)))
        self.scale = self.base_scale * self.zoom
        self.img.scale = self.scale

    def S(self, px) -> int:
        return int(round(px * self.scale))

    def f(self, size, bold=False, mono=False):
        return theme.font(max(6, int(round(size * self.zoom))), bold, mono)

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
            fam, weight = theme.family(bold)
            self._fonts[key] = tkfont.Font(family=fam, size=max(6, int(round(size * self.zoom))), weight=weight)
        f = self._fonts[key]
        if f.measure(text) <= width_px:
            return text
        while text and f.measure(text + "…") > width_px:
            text = text[:-1]
        return text.rstrip() + "…"

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
        """Bố cục kiểu app gaming: thanh trên (logo · tìm kiếm · trạng thái · công tắc · cài đặt),
        thanh trạng thái mảnh ở đáy (bộ quét · Định vị lõi · phiên bản)."""
        S = self.S
        top = tk.Frame(self.root, bg=PANEL, padx=S(14), pady=S(8))
        top.pack(fill="x")
        tk.Frame(self.root, bg=LINE, height=1).pack(fill="x")

        # trái: thương hiệu
        brand = tk.Frame(top, bg=PANEL)
        brand.pack(side="left")
        try:
            tk.Label(brand, image=app_logo(self.root, S(26)), bg=PANEL).pack(side="left")
        except Exception:
            pass
        self.label(brand, "ARAM Helper", 12, TEXT, True).pack(side="left", padx=(S(8), 0))

        # phải (xếp từ mép phải vào): cài đặt · overlay · trạng thái trận · quay lại tướng trong trận · cập nhật
        self.settings_btn = self._icon_button(top, "⚙", self.open_settings, T("Cài đặt"))
        self.settings_btn.pack(side="right")
        if self.overlay:
            self.ov_var = tk.BooleanVar(value=self.overlay.visible)
            self.ov_toggle = self._toggle(top, "Overlay", self.ov_var, self._toggle_overlay)
            self.ov_toggle.pack(side="right", padx=(0, S(10)))
        chip = tk.Frame(top, bg=PANEL2, padx=S(10), pady=S(5), highlightthickness=1, highlightbackground=LINE)
        chip.pack(side="right", padx=(0, S(10)))
        self.chip = chip
        self.dot = tk.Canvas(chip, width=S(10), height=S(10), bg=PANEL2, highlightthickness=0)
        self.dot.pack(side="left")
        self._dot = self.dot.create_oval(1, 1, S(9), S(9), fill=MUTED, outline="")
        self.status = self.label(chip, T("Đang chờ trận…"), 9, TEXT, True)
        self.status.pack(side="left", padx=(S(6), 0))
        self.back_btn = self.button(top, "↩ " + T("Tướng trong trận"), self._auto, 9)
        self.tooltip.bind(self.back_btn, T("Bỏ tướng đang xem, quay lại tướng bạn đang chơi"))
        self.update_slot = tk.Frame(top, bg=PANEL)
        self.update_slot.pack(side="right", padx=(0, S(10)))
        if self._update_info:
            self.root.after(0, self._show_update, self._update_info)

        # giữa: tìm kiếm có biểu tượng kính lúp
        box = tk.Frame(top, bg=BG, highlightthickness=1, highlightbackground=LINE, highlightcolor=ACCENT,
                       padx=S(8))
        box.pack(side="left", fill="x", expand=True, padx=(S(24), S(16)))
        self.search_box = box
        glass = tk.Canvas(box, width=S(16), height=S(16), bg=BG, highlightthickness=0)
        glass.create_oval(S(2), S(2), S(11), S(11), outline=MUTED, width=max(1, S(2)))
        glass.create_line(S(10), S(10), S(14), S(14), fill=MUTED, width=max(1, S(2)), capstyle="round")
        glass.pack(side="left")
        self.search_var = tk.StringVar()
        self.search = tk.Entry(box, textvariable=self.search_var, bg=BG, fg=TEXT, insertbackground=TEXT,
                               relief="flat", font=self.f(10), highlightthickness=0)
        self.search.pack(side="left", fill="x", expand=True, ipady=S(5), padx=(S(8), 0))
        self._placeholder(self.search, self.search_var, T("Tìm tướng hoặc lõi…"))
        self.tooltip.bind(self.search, T("Gõ tên tướng để chuyển nhanh (↑ ↓ Enter), hoặc tên lõi – nhiều lõi cách nhau dấu phẩy, không cần dấu."))
        self.search.bind("<FocusIn>", lambda e: box.configure(highlightbackground=ACCENT), add="+")
        self.search.bind("<FocusOut>", lambda e: box.configure(highlightbackground=LINE), add="+")
        self.search_var.trace_add("write", lambda *_: self.root.after(80, self._on_search))
        self.search.bind("<Down>", lambda e: self._popup_move(1))
        self.search.bind("<Up>", lambda e: self._popup_move(-1))
        self.search.bind("<Return>", lambda e: self._popup_pick())
        self.search.bind("<FocusOut>", lambda e: self.root.after(200, self._hide_popup), add="+")
        for w in (box, glass):
            w.bind("<Button-1>", lambda e: self.search.focus_set())

        # đáy: thanh trạng thái
        from version import __version__
        bar = tk.Frame(self.root, bg=PANEL, padx=S(12), pady=S(3))
        bar.pack(side="bottom", fill="x")
        tk.Frame(self.root, bg=LINE, height=1).pack(side="bottom", fill="x")
        self.scan_dot = tk.Canvas(bar, width=S(8), height=S(8), bg=PANEL, highlightthickness=0)
        self.scan_dot.pack(side="left")
        self._scan_dot = self.scan_dot.create_oval(1, 1, S(7), S(7), fill=MUTED, outline="")
        self.scan_lbl = self.label(bar, "", 8, MUTED, anchor="w")
        self.scan_lbl.pack(side="left", fill="x", expand=True, padx=(S(6), 0))
        self.label(bar, f"v{__version__}", 8, DIMTEXT).pack(side="right")
        if self.scanner:
            loc = self.label(bar, "⌖ " + T("Định vị lõi"), 8, ACCENT, cursor="hand2")
            loc.pack(side="right", padx=(0, S(14)))
            loc.bind("<Button-1>", lambda e: self.scanner.request_calibration(5))
            loc.bind("<Enter>", lambda e: loc.configure(fg=TEXT))
            loc.bind("<Leave>", lambda e: loc.configure(fg=ACCENT))
            self.tooltip.bind(loc, T("Tìm vị trí 3 thẻ lõi trên màn hình. Thường app tự làm ở lượt chọn đầu tiên – chỉ cần bấm khi app đọc sai."))

        headrow = tk.Frame(self.root, bg=BG, padx=self.S(12), pady=self.S(4))
        headrow.pack(fill="x")
        self.tabs = tk.Frame(headrow, bg=BG)
        self.tabs.pack(side="right", anchor="s")
        self.head = tk.Frame(headrow, bg=BG)
        self.head.pack(side="left", fill="x", expand=True)
        tk.Frame(self.root, bg=LINE, height=1).pack(fill="x", padx=self.S(12))
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

    # ----- nút kiểu app gaming -----
    def _icon_button(self, parent, glyph, cmd, tip):
        """Nút vuông chỉ có biểu tượng (kèm chú thích khi rê chuột)."""
        bg = parent["bg"]
        b = tk.Label(parent, text=glyph, fg=MUTED, bg=bg, font=self.f(14), width=2, cursor="hand2")
        b.bind("<Button-1>", lambda e: cmd())
        b.bind("<Enter>", lambda e: b.configure(fg=TEXT, bg=PANEL2))
        b.bind("<Leave>", lambda e: b.configure(fg=MUTED, bg=bg))
        self.tooltip.bind(b, tip)
        return b

    def _toggle(self, parent, text, var, on_change):
        """Công tắc gạt: chữ + rãnh bo tròn, bật = xanh."""
        S, bg = self.S, parent["bg"]
        f = tk.Frame(parent, bg=bg, cursor="hand2")
        lb = self.label(f, text, 9, TEXT, bg=bg)
        lb.pack(side="left", padx=(0, S(6)))
        w, h = S(30), S(16)
        cv = tk.Canvas(f, width=w, height=h, bg=bg, highlightthickness=0, cursor="hand2")
        cv.pack(side="left")

        def draw():
            cv.delete("all")
            on = bool(var.get())
            col = GOOD if on else LINE
            r = h / 2
            cv.create_oval(0, 0, h, h, fill=col, outline="")
            cv.create_oval(w - h, 0, w, h, fill=col, outline="")
            cv.create_rectangle(r, 0, w - r, h, fill=col, outline="")
            kx = w - h + S(2) if on else S(2)
            cv.create_oval(kx, S(2), kx + h - S(4), h - S(2), fill="#ffffff" if on else MUTED, outline="")

        def flip(_e=None):
            var.set(not var.get())
            draw()
            on_change()
        for w_ in (f, lb, cv):
            w_.bind("<Button-1>", flip)
        f.redraw = draw
        draw()
        return f

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
                    tuple(sorted(self.expanded)), self._size, st.get("focus"), i18n.lang())
            if full != self._full_sig:
                self._full_sig = full
                self._render(st)
            self._refresh_counter(st)
            self._light_update()
        except Exception:       # không để giao diện chết vì 1 lỗi
            self._on_ui_error(*sys.exc_info())
        self.root.after(700, self._poll)

    def _update_bars(self, st):
        game, scan = st.get("game", {}), st.get("scan") or {}
        if self.overlay and self.ov_var.get() != self.overlay.visible:   # bật/tắt bằng phím tắt
            self.ov_var.set(self.overlay.visible)
            self.ov_toggle.redraw()
        in_game = bool(game.get("in_game"))
        self.dot.itemconfigure(self._dot, fill=GOOD if in_game else ACCENT if st.get("focus") else MUTED)
        self.chip.configure(highlightbackground=GOOD if in_game and not st.get("focus") else LINE)
        if st.get("focus") and not self.back_btn.winfo_manager():      # đang xem tướng khác → nút quay lại
            self.back_btn.pack(side="right", padx=(0, self.S(10)), before=self.update_slot)
        elif not st.get("focus") and self.back_btn.winfo_manager():
            self.back_btn.pack_forget()
        champ = st.get("champion") or {}
        if game.get("in_game"):
            txt = T("Trong trận: {name}", name=game.get("champion_name") or champ.get("name") or "?")
        elif st.get("focus"):
            txt = T("Đang xem: {name}", name=champ.get("name") or st["focus"])
        else:
            txt = T("Đang chờ trận…")
        self.status.configure(text=txt)
        if scan.get("error"):
            s, col = scan["error"], OKC
        elif scan.get("calibrating_in") is not None:
            s = (T("Định vị lõi sau {n} giây – mở bảng chọn lõi trong game", n=int(scan["calibrating_in"]) + 1)
                 if scan["calibrating_in"] > 0 else scan.get("status", ""))
            col = OKC
        else:
            s = scan.get("status", "")
            col = GOOD if (scan.get("offer") or {}).get("visible") else MUTED if scan.get("calibrated") else OKC
        self.scan_lbl.configure(text=T("Quét màn hình: {s}", s=i18n.status(s)) if s else "", fg=col)
        self.scan_dot.itemconfigure(self._scan_dot, fill=col)

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
                self._counter_slot(self._right.inner, right_w)
                self._render_items(self._right.inner, champ, right_w)
            else:
                self._single = Scroll(self.body, self.S(30))
                self._single.pack(fill="both", expand=True)
                self._fit_args = (W - self.S(26), H)
                self._render_augments(self._single.inner, champ, st, W - self.S(26), H)
                self._counter_slot(self._single.inner, W - self.S(26))
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
        foot = self.label(self.body, about.COPYRIGHT + "  ·  " + T("Giới thiệu"), 8, DIMTEXT, cursor="hand2")
        foot.place(relx=0.5, rely=1.0, y=-self.S(10), anchor="s")
        foot.bind("<Button-1>", lambda e: self.open_settings("about"))

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
    def open_settings(self, page=None):
        if self._settings_dlg is not None and self._settings_dlg.win.winfo_exists():
            if page:
                self._settings_dlg._go(page)
            self._settings_dlg.center()
            self._settings_dlg.win.lift()
            self._settings_dlg.win.focus_force()
            return
        import settings_ui
        self._settings_dlg = settings_ui.SettingsDialog(self)
        if page:
            self._settings_dlg._go(page)

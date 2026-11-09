"""Cửa sổ chính ARAM Helper (tkinter – có sẵn trong Python, nhẹ RAM).

Tab "Lõi & trang bị": cửa sổ rộng → 2 cột (lõi bên trái, trang bị bên phải), mỗi cột cuộn riêng; "Tự vừa cửa sổ"
chọn số lõi mỗi bậc theo chiều cao để không phải cuộn dù cửa sổ to/nhỏ hay zoom (Ctrl + / Ctrl - / Ctrl 0).
Tab "Combo lõi": lối chơi, combo lõi kèm lý do, đồ khuyên dùng, mẹo.
Ô tìm kiếm: gõ tên tướng → danh sách chọn nhanh (↑ ↓ Enter); gõ tên lõi → tô sáng lõi.
Mặc định cửa sổ chính KHÔNG đổi khi bảng chọn lõi hiện ra (gợi ý ở overlay / ESP32) – bật lại trong Cài đặt.
"""
from __future__ import annotations

import hashlib
import queue
import re
import sys
import threading
import time
import tkinter as tk
import unicodedata
import urllib.request
from tkinter import ttk

import advice
import hotkeys
import i18n
import playaram
import settings
from i18n import T

# ---------- giao diện ----------
BG, PANEL, PANEL2, CARD, LINE = "#0b0d14", "#141826", "#1a2031", "#111524", "#262d40"
TEXT, MUTED, DIMTEXT = "#e6e8ef", "#8a91a8", "#4a5066"
GOOD, OKC, BAD, ACCENT = "#3ddc97", "#f5a53a", "#ef6b6b", "#6aa8ff"
HIT_BG, OWNED_BG = "#12291f", "#14223a"
RARITY = [("prismatic", "Lõi Kim Cương", "#c58cff"), ("gold", "Lõi Vàng", "#f0c35a"), ("silver", "Lõi Bạc", "#b9c3d6")]
RARITY_COLOR = {k: c for k, _, c in RARITY}
TIER_COLOR = {"S+": "#ff8a5c", "S": "#ff8a5c", "A": "#f5c451", "B": "#6aa8ff", "C": MUTED, "D": MUTED}
IS_MAC = sys.platform == "darwin"
FONT, MONO = ("Helvetica Neue", "Menlo") if IS_MAC else ("Segoe UI", "Consolas")
LOW_PICK = 1.5
CARD_MIN_W = 172          # bề rộng tối thiểu 1 thẻ lõi (px ở 100%)
CARD_H = 44               # chiều cao thẻ lõi
CARD_GAP = 6
WIDE_MIN = 640            # từ bề rộng này (px ở 100%): 2 cột lõi | trang bị, xem cùng lúc không phải cuộn
IMG_DIR = playaram.CACHE_DIR / "img"
ICON_DIR = playaram.CACHE_DIR / "icons"


def fold(s: str) -> str:
    s = unicodedata.normalize("NFD", s.replace("đ", "d").replace("Đ", "D"))
    return re.sub(r"\s+", " ", "".join(c for c in s if unicodedata.category(c) != "Mn").lower()).strip()


# ---------- ảnh (tải nền, cache đĩa + RAM) ----------
class Images:
    """Icon lõi lấy từ data/icons/<id>.png; icon trang bị / tướng / phép tải 1 lần từ nguồn dữ liệu rồi cache."""

    def __init__(self, root: tk.Tk, scale: float):
        self.root, self.scale = root, scale
        self.mem: dict = {}
        self.waiting: dict = {}
        self.blank: dict = {}
        self.jobs: queue.Queue = queue.Queue()
        self.done: queue.Queue = queue.Queue()
        self.listeners: list = []          # gọi khi có ảnh mới tải xong (overlay vẽ lại)
        threading.Thread(target=self._worker, daemon=True, name="images").start()
        self.root.after(80, self._pump)

    def px(self, size: int) -> int:
        return max(8, int(round(size * self.scale)))

    def set(self, widget, src, size: int):
        """src: id lõi (int) hoặc URL ảnh. Gán ảnh cho Label ngay nếu đã có, không thì tải nền."""
        if src is None:
            return
        k = (src, self.px(size))
        if k in self.mem:
            widget.configure(image=self.mem[k])
            return
        widget.configure(image=self._blank(k[1]))
        lst = self.waiting.setdefault(k, [])
        lst.append(widget)
        if len(lst) == 1:
            self.jobs.put(k)

    def photo(self, src, size: int):
        """Cho Canvas: trả PhotoImage nếu đã có, không thì tải nền (xong sẽ gọi listeners) và trả None."""
        if src is None:
            return None
        k = (src, self.px(size))
        if k in self.mem:
            return self.mem[k]
        if k not in self.waiting:
            self.waiting[k] = []
            self.jobs.put(k)
        return None

    def _blank(self, px):
        if px not in self.blank:
            self.blank[px] = tk.PhotoImage(width=px, height=px)
        return self.blank[px]

    def _worker(self):
        from PIL import Image
        IMG_DIR.mkdir(parents=True, exist_ok=True)
        while True:
            k = self.jobs.get()
            src, px = k
            img = None
            try:
                if isinstance(src, int):
                    path = ICON_DIR / f"{src}.png"
                else:
                    path = IMG_DIR / (hashlib.sha1(src.encode()).hexdigest()[:16] + ".img")
                    if not path.exists():
                        req = urllib.request.Request(src, headers={"User-Agent": playaram.USER_AGENT,
                                                                   "Accept": "image/png,image/*"})
                        with urllib.request.urlopen(req, timeout=15) as r:
                            path.write_bytes(r.read())
                with Image.open(path) as im:
                    img = im.convert("RGBA").resize((px, px), Image.LANCZOS)
            except Exception:
                img = None
            self.done.put((k, img))

    def _pump(self):
        got = False
        try:
            from PIL import ImageTk
            while True:
                k, img = self.done.get_nowait()
                widgets = self.waiting.pop(k, [])
                if img is None:
                    continue
                photo = ImageTk.PhotoImage(img)
                self.mem[k] = photo
                got = True
                for w in widgets:
                    try:
                        w.configure(image=photo)
                    except tk.TclError:      # widget đã bị vẽ lại
                        pass
        except queue.Empty:
            pass
        if got:
            for fn in self.listeners:
                fn()
        self.root.after(80, self._pump)



# ---------- vùng cuộn ----------
class Scroll(tk.Frame):
    """Khung cuộn dọc. Cuộn chuột được xử lý chung (App._wheel): cuộn đúng vùng nằm dưới con trỏ."""

    def __init__(self, parent, step: int):
        super().__init__(parent, bg=BG)
        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0, bd=0, yscrollincrement=step)
        self.bar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.bar.set)
        self.bar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.canvas, bg=BG)
        self.inner._scroll = self
        self.canvas._scroll = self
        self._win = self.canvas.create_window(0, 0, window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))

    def clear(self):
        for w in self.inner.winfo_children():
            w.destroy()


class Tooltip:
    """Chú thích nhỏ khi rê chuột (tên món dưới icon)."""

    def __init__(self, app):
        self.app, self.win = app, None

    def bind(self, widget, text: str):
        if text:
            widget.bind("<Enter>", lambda e: self.show(e, text), add="+")
            widget.bind("<Leave>", lambda e: self.hide(), add="+")

    def show(self, e, text):
        self.hide()
        w = tk.Toplevel(self.app.root)
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        tk.Label(w, text=text, bg=PANEL2, fg=TEXT, font=self.app.f(9), padx=6, pady=2,
                 highlightthickness=1, highlightbackground=LINE).pack()
        w.geometry(f"+{e.x_root + 12}+{e.y_root + 16}")
        self.win = w

    def hide(self):
        if self.win is not None:
            try:
                self.win.destroy()
            except tk.TclError:
                pass
            self.win = None


# ---------- cửa sổ chính ----------
class App:
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
        self._apply_zoom()
        root.geometry(f"{self.S(1280)}x{self.S(820)}")
        root.minsize(640, 420)
        root.attributes("-topmost", bool(settings.get("always_on_top")))
        for seq, step in (("<Control-equal>", 1), ("<Control-plus>", 1), ("<Control-KP_Add>", 1),
                          ("<Control-minus>", -1), ("<Control-KP_Subtract>", -1), ("<Control-Key-0>", 0)):
            root.bind(seq, lambda e, s=step: self._zoom_step(s))
        root.bind_all("<MouseWheel>", self._wheel)
        root.bind("<Configure>", self._on_root_configure, add="+")
        settings.on_change(lambda ch: root.after(0, self._on_settings, ch))
        self._style()
        self._build()
        threading.Thread(target=self._load_champion_list, daemon=True).start()
        root.after(200, self._poll)

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

    # ----- tìm tướng nhanh -----
    def _load_champion_list(self):
        try:
            slugs = playaram.get_champion_list()
        except Exception:
            slugs = []
        names = {}
        try:
            import ddragon
            dd = ddragon.get(i18n.ddragon_locale())
            names = {k: v["name"] for k, v in (dd or {}).get("champions", {}).items()}
        except Exception:
            pass
        champs = [(s, names.get(s, s.capitalize()), fold(names.get(s, s))) for s in slugs]
        self._champs = sorted(champs, key=lambda c: c[2])

    def champion_matches(self, text: str, limit: int = 8) -> list[tuple[str, str]]:
        t = fold(text).strip()
        if not t or "," in t:
            return []
        flat = t.replace(" ", "")
        starts = [c for c in self._champs if c[2].startswith(t) or c[0].startswith(flat)]
        inside = [c for c in self._champs if c not in starts and (t in c[2] or flat in c[0])]
        return [(slug, name) for slug, name, _ in (starts + inside)[:limit]]

    def _on_search(self):
        text = self.search_text()
        matches = self.champion_matches(text)
        try:
            focused = self.root.focus_get() is self.search
        except (KeyError, tk.TclError):     # Tk lỗi 'popdown' khi focus nằm ở menu/combobox
            focused = False
        if matches and focused:
            self._show_popup(matches)
        else:
            self._hide_popup()
        self._light_update()

    def _show_popup(self, matches):
        if self._popup is None:
            win = tk.Toplevel(self.root)
            win.overrideredirect(True)
            win.attributes("-topmost", True)
            lb = tk.Listbox(win, bg=PANEL, fg=TEXT, selectbackground=ACCENT, selectforeground="#06121f",
                            font=self.f(10), relief="flat", highlightthickness=1, highlightbackground=LINE,
                            activestyle="none")
            lb.pack(fill="both", expand=True)
            lb.bind("<ButtonRelease-1>", lambda e: self._popup_pick())
            self._popup = (win, lb)
        win, lb = self._popup
        lb.delete(0, "end")
        self._popup_slugs = [s for s, _ in matches]
        for slug, name in matches:
            lb.insert("end", f"  {name}")
        lb.selection_clear(0, "end")
        lb.selection_set(0)
        x, y = self.search.winfo_rootx(), self.search.winfo_rooty() + self.search.winfo_height()
        h = len(matches) * self.S(22) + 4
        win.geometry(f"{self.search.winfo_width()}x{h}+{x}+{y}")
        lb.configure(height=len(matches))

    def _hide_popup(self):
        if self._popup is not None:
            try:
                self._popup[0].destroy()
            except tk.TclError:
                pass
            self._popup = None

    def _popup_move(self, step):
        if self._popup is None:
            return
        lb = self._popup[1]
        cur = lb.curselection()
        i = (cur[0] if cur else -1) + step
        i = max(0, min(lb.size() - 1, i))
        lb.selection_clear(0, "end")
        lb.selection_set(i)
        lb.see(i)
        return "break"

    def _popup_pick(self):
        if self._popup is None:
            return
        cur = self._popup[1].curselection()
        slug = self._popup_slugs[cur[0] if cur else 0]
        self._hide_popup()
        self.search_var.set("")
        self.root.focus()
        self.hub.set_focus(slug)
        self._scroll_top = True
        return "break"

    def _auto(self):
        self.hub.set_focus(None)
        self._scroll_top = True

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
        except Exception as e:  # không để giao diện chết vì 1 lỗi
            print("ui:", repr(e))
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
            self.label(self.body, msg, 11, MUTED, wraplength=self.S(700)).pack(pady=self.S(60))
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

    # ----- lõi -----
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
        owned = set(st.get("owned", []))
        fit = advice.combo_fit(champ, owned)
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
                card = self._aug_card(body, a, i, color, base, fit.get(a["id"]), any_tier.get(a["id"]), a["id"] in owned)
                card["extra"], card["rarity"], card["pos"] = i >= top_n, key, (i // cols, i % cols)
                self.cards[a["id"]] = card
                if not card["extra"] or open_ or card["owned"]:
                    card["w"].grid(row=card["pos"][0], column=card["pos"][1], sticky="nsew",
                                   padx=self.S(CARD_GAP // 2), pady=self.S(CARD_GAP // 2))
            if not items:
                self.label(body, T("Không có dữ liệu"), 10, MUTED).grid(row=0, column=0)

    def _toggle_more(self, key):
        self.expanded.symmetric_difference_update({key})
        self._full_sig = None

    def _aug_card(self, parent, a, i, color, base, fit, any_tier, owned):
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
        if fit:
            self.badge(stats, T("hợp combo {t}", t=fit) if roomy else f"◆{fit}", GOOD, filled=True).pack(side="left")
        elif any_tier:
            self.badge(stats, T("combo {t}", t=any_tier) if roomy else f"◆{any_tier}",
                       TIER_COLOR.get(any_tier, MUTED)).pack(side="left")
        card = {"w": outer, "inner": inner, "name": name, "color": color, "fold": fold(a["name"]), "owned": owned}
        self.bind_tree(outer, lambda: self._own(toggle=a["id"]))
        self._style_card(card, "owned" if owned else "normal")
        return card

    def _style_card(self, card, state):
        bg = {"hit": HIT_BG, "owned": OWNED_BG}.get(state, CARD)
        edge = {"hit": GOOD, "owned": ACCENT}.get(state, card["color"])
        card["w"].configure(bg=edge)

        def paint(w):
            if isinstance(w, (tk.Frame, tk.Label)) and w["bg"] in (CARD, HIT_BG, OWNED_BG):
                w.configure(bg=bg)
            for ch in w.winfo_children():
                paint(ch)
        paint(card["inner"])
        card["name"].configure(fg=DIMTEXT if state == "dim" else TEXT)

    # ----- cập nhật nhẹ: tìm kiếm (+ bảng lõi đọc từ màn hình nếu bật) -----
    def _light_update(self, from_search=False):
        st = self._st
        champ = st.get("champion")
        if not champ or self.tab != "aug" or self.advice_box is None:
            return
        text = self.search_text()
        terms = [] if self.champion_matches(text) else [t.strip() for t in fold(text).split(",") if t.strip()]
        adv = st.get("advice") if self._follow_offer() else None    # mặc định: cửa sổ chính giữ nguyên
        sig = (tuple(terms), repr([(a["slot"], [c["id"] for c in a["candidates"]]) for a in adv or []]),
               tuple(st.get("owned", [])))
        if sig == self._light_sig:
            return
        self._light_sig = sig
        offer_ids = {c["id"] for a in adv or [] for c in a["candidates"]}
        hits = [i for i, c in self.cards.items() if any(t in c["fold"] for t in terms)] if terms else []
        active = bool(terms or offer_ids)
        for i, c in self.cards.items():
            hit = i in offer_ids or i in hits
            self._style_card(c, "hit" if hit else "owned" if c["owned"] else "dim" if active else "normal")
            if c["extra"]:   # lõi ngoài top N đang được tìm / đọc ra / đã chọn thì vẫn hiện
                if hit or c["owned"] or c["rarity"] in self.expanded:
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
                self._advice(advice.rank_offer([[i] for i in ids], champ, cat, set(st.get("owned", []))), "search")

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
                self.label(mid, T("Một trong (icon giống nhau) – bấm lõi bạn đã chọn:"), 8, MUTED).pack(anchor="w")
                line = tk.Frame(mid, bg=PANEL)
                line.pack(anchor="w")
                for c in r["candidates"]:
                    chip = tk.Frame(line, bg=PANEL2, padx=self.S(4), pady=self.S(1))
                    chip.pack(side="left", padx=(0, self.S(4)), pady=self.S(2))
                    self.icon(chip, c["id"], 16).pack(side="left")
                    self.label(chip, c["name"], 8).pack(side="left", padx=self.S(3))
                    self.bind_tree(chip, lambda c=c: self._pick_aug(c["id"], source))
            else:
                self.label(mid, b["name"], 9, GOOD if r["rank"] == 1 else TEXT, r["rank"] == 1).pack(anchor="w")
            wr = (T("chưa có số liệu") if b["winrate"] is None
                  else f"{b['winrate']}%" + (T(" (chung, mọi tướng)") if b["source"] == "chung" else ""))
            extra = T("  ·  +{b} hợp combo {t}", b=advice.TIER_BONUS[b["fit"]], t=b["fit"]) if b.get("fit") else ""
            self.label(mid, T("Thắng {wr}{extra}", wr=wr, extra=extra), 8, MUTED).pack(anchor="w")
            if len(r["candidates"]) == 1:
                self.button(row, T("Đã chọn"), lambda i=b["id"]: self._pick_aug(i, source), 8,
                            primary=r["rank"] == 1).pack(side="right")

    def _pick_aug(self, aug_id, source):
        self._own(add=aug_id)
        if source == "search":
            self.search_var.set("")
            self.search.event_generate("<FocusOut>")

    # ----- đồ theo đội địch (2 dòng) -----
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

    # ----- tab Combo -----
    def _render_combos(self, root, c, st, wrap):
        owned = set(st.get("owned", []))
        styles = c.get("playstyles") or []
        if not styles:
            self.label(root, T("Chưa có lối chơi / combo cho tướng này."), 11, MUTED).pack(pady=self.S(40))
            return
        self.label(root, T("Hạng combo là đánh giá của biên tập viên, không phải tỉ lệ thắng. Bấm vào lõi để đánh dấu đã chọn; combo chứa lõi đã chọn được tô xanh."),
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
            combos = sorted(s.get("combos", []), key=lambda x: -sum(a["id"] in owned for a in x["augments"]))
            for cb in combos:
                n = sum(a["id"] in owned for a in cb["augments"])
                bg = "#132a20" if n else PANEL
                tk.Frame(card, bg=LINE, height=1).pack(fill="x")
                row = tk.Frame(card, bg=bg, padx=self.S(10), pady=self.S(6))
                row.pack(fill="x")
                line = tk.Frame(row, bg=bg)
                line.pack(anchor="w")
                self.badge(line, cb["tier"], TIER_COLOR.get(cb["tier"], MUTED)).pack(side="left", padx=(0, self.S(8)))
                for k, a in enumerate(cb["augments"]):
                    if k:
                        self.label(line, "+", 10, MUTED).pack(side="left", padx=self.S(3))
                    have = a["id"] in owned
                    chip = tk.Frame(line, bg=PANEL2, padx=self.S(4), pady=self.S(1), highlightthickness=1,
                                    highlightbackground=ACCENT if have else PANEL2)
                    chip.pack(side="left")
                    self.icon(chip, a["id"], 18).pack(side="left")
                    self.label(chip, a["name"], 9, RARITY_COLOR.get(a.get("rarity"), TEXT)).pack(side="left", padx=self.S(4))
                    self.bind_tree(chip, lambda i=a["id"]: self._own(toggle=i))
                if n:
                    self.label(line, T("đã có {n}/{m}", n=n, m=len(cb["augments"])), 9, GOOD).pack(side="left", padx=self.S(8))
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

    # ----- Cài đặt -----
    def open_settings(self):
        if self._settings_dlg is not None and self._settings_dlg.win.winfo_exists():
            self._settings_dlg.win.lift()
            return
        import settings_ui
        self._settings_dlg = settings_ui.SettingsDialog(self)

"""Cửa sổ chính ARAM Helper (tkinter – có sẵn trong Python, nhẹ RAM).

Tab "Lõi": 3 hàng Kim Cương / Vàng / Bạc (top 8 + Xem thêm), bên dưới là Trang bị gợi ý.
Tab "Combo lõi": lối chơi, combo lõi kèm lý do, đồ khuyên dùng, mẹo.
Bấm vào lõi để đánh dấu đã chọn. Khi bộ quét đọc được 3 lõi trên màn hình, ô "Nên chọn" hiện ở đầu tab Lõi.
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
import playaram

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
TOP_N, LOW_PICK = 8, 1.5
CARD_W = 232
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
    def __init__(self, parent, step: int):
        super().__init__(parent, bg=BG)
        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0, bd=0, yscrollincrement=step)
        self.bar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.bar.set)
        self.bar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.canvas, bg=BG)
        self._win = self.canvas.create_window(0, 0, window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._wheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def _wheel(self, e):
        # Windows: delta = ±120 mỗi nấc; macOS: delta nhỏ (±1..±10)
        step = -e.delta if IS_MAC else int(-e.delta / 40)
        self.canvas.yview_scroll(step, "units")

    def clear(self):
        for w in self.inner.winfo_children():
            w.destroy()


# ---------- cửa sổ chính ----------
class App:
    def __init__(self, root: tk.Tk, hub, scanner=None, overlay=None):
        self.root, self.hub, self.scanner, self.overlay = root, hub, scanner, overlay
        # Windows: 96 dpi = 100%; macOS Tk báo 72 dpi nhưng màn Retina đã tự nhân → giữ tỉ lệ 1
        self.scale = 1.0 if IS_MAC else root.winfo_fpixels("1i") / 96.0
        self.img = Images(root, self.scale)
        self.tab = "aug"
        self.expanded: set[str] = set()
        self.cards: dict[int, dict] = {}
        self.advice_box = None
        self._full_sig = self._light_sig = None
        self._st: dict = {}
        self._width = 0
        self._fonts: dict = {}
        self._name_w = 200

        root.title("ARAM Helper")
        root.configure(bg=BG)
        root.geometry(f"{self.S(1240)}x{self.S(860)}")
        root.minsize(self.S(760), self.S(520))
        self._style()
        self._build()
        threading.Thread(target=self._load_champion_list, daemon=True).start()
        root.after(200, self._poll)

    def S(self, px) -> int:
        return int(round(px * self.scale))

    def f(self, size, bold=False, mono=False):
        return (MONO if mono else FONT, size, "bold" if bold else "normal")

    def _style(self):
        st = ttk.Style(self.root)
        st.theme_use("clam")
        st.configure("TCombobox", fieldbackground=PANEL, background=PANEL2, foreground=TEXT, arrowcolor=TEXT,
                     bordercolor=LINE, lightcolor=PANEL, darkcolor=PANEL, selectbackground=PANEL2)
        st.map("TCombobox", fieldbackground=[("readonly", PANEL)], foreground=[("readonly", TEXT)])
        st.configure("Vertical.TScrollbar", background=PANEL2, troughcolor=BG, bordercolor=BG, arrowcolor=MUTED,
                     lightcolor=PANEL2, darkcolor=PANEL2)
        self.root.option_add("*TCombobox*Listbox.background", PANEL)
        self.root.option_add("*TCombobox*Listbox.foreground", TEXT)
        self.root.option_add("*TCombobox*Listbox.selectBackground", PANEL2)

    # ----- widget nhỏ -----
    def label(self, parent, text="", size=10, color=TEXT, bold=False, bg=None, mono=False, **kw):
        return tk.Label(parent, text=text, fg=color, bg=bg or parent["bg"], font=self.f(size, bold, mono), **kw)

    def button(self, parent, text, cmd, size=10, primary=False):
        b = tk.Label(parent, text=text, fg="#05261a" if primary else TEXT, bg=GOOD if primary else PANEL2,
                     font=self.f(size, primary), padx=self.S(10), pady=self.S(4), cursor="hand2")
        b.bind("<Button-1>", lambda e: cmd())
        if not primary:
            b.bind("<Enter>", lambda e: b.configure(bg=LINE))
            b.bind("<Leave>", lambda e: b.configure(bg=PANEL2))
        return b

    def icon(self, parent, src, size, bg=None):
        lb = tk.Label(parent, bg=bg or parent["bg"], bd=0)
        self.img.set(lb, src, size)
        return lb

    def badge(self, parent, text, color, filled=False):
        return tk.Label(parent, text=text, fg="#062" if filled else color, bg=color if filled else parent["bg"],
                        font=self.f(8, True), padx=self.S(4), highlightthickness=1, highlightbackground=color)

    def _fit(self, text, width_px, size, bold=False):
        """Cắt chữ cho vừa bề rộng, thêm '…' (Label của tkinter tự cắt cụt không có dấu)."""
        from tkinter import font as tkfont
        key = (size, bold)
        if key not in self._fonts:
            self._fonts[key] = tkfont.Font(family=FONT, size=size, weight="bold" if bold else "normal")
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

    # ----- khung cố định -----
    def _build(self):
        top = tk.Frame(self.root, bg=BG, padx=self.S(14), pady=self.S(8))
        top.pack(fill="x")
        self.dot = tk.Canvas(top, width=self.S(12), height=self.S(12), bg=BG, highlightthickness=0)
        self.dot.pack(side="left")
        self._dot = self.dot.create_oval(1, 1, self.S(11), self.S(11), fill=MUTED, outline="")
        self.status = self.label(top, "Đang chờ trận…", 10, TEXT, True)
        self.status.pack(side="left", padx=(self.S(6), self.S(14)))

        self.search_var = tk.StringVar()
        self.search = tk.Entry(top, textvariable=self.search_var, bg=PANEL, fg=TEXT, insertbackground=TEXT,
                               relief="flat", font=self.f(10), highlightthickness=1, highlightbackground=LINE,
                               highlightcolor=ACCENT)
        self.search.pack(side="left", fill="x", expand=True, ipady=self.S(4))
        self._placeholder(self.search, self.search_var, "Gõ tên lõi (không cần dấu), nhiều lõi cách nhau dấu phẩy…")
        self.search_var.trace_add("write", lambda *_: self.root.after(120, self._light_update, True))

        self.pick_var = tk.StringVar()
        self.pick = ttk.Combobox(top, textvariable=self.pick_var, width=16, font=self.f(10))
        self.pick.pack(side="left", padx=(self.S(10), self.S(4)), ipady=self.S(2))
        self.pick.bind("<<ComboboxSelected>>", lambda e: self._pick())
        self.pick.bind("<Return>", lambda e: self._pick())
        self.pick.bind("<KeyRelease>", self._filter_pick)
        self.button(top, "Tự động", self._auto).pack(side="left", padx=self.S(4))
        if self.overlay:
            self.ov_var = tk.BooleanVar(value=True)
            tk.Checkbutton(top, text="Overlay", variable=self.ov_var, command=lambda: self.overlay.set_visible(self.ov_var.get()),
                           bg=BG, fg=TEXT, selectcolor=PANEL, activebackground=BG, activeforeground=TEXT,
                           font=self.f(10)).pack(side="left", padx=self.S(6))

        bar2 = tk.Frame(self.root, bg=BG, padx=self.S(14))
        bar2.pack(fill="x")
        self.scan_lbl = self.label(bar2, "", 9, MUTED, anchor="w")
        self.scan_lbl.pack(side="left", fill="x", expand=True)
        if self.scanner:
            self.button(bar2, "Hiệu chỉnh", lambda: self.scanner.request_calibration(5), 9).pack(side="right")

        self.head = tk.Frame(self.root, bg=BG, padx=self.S(14), pady=self.S(8))
        self.head.pack(fill="x")
        self.tabs = tk.Frame(self.root, bg=BG, padx=self.S(14))
        self.tabs.pack(fill="x")
        tk.Frame(self.root, bg=LINE, height=1).pack(fill="x", padx=self.S(14))
        self.owned_bar = tk.Frame(self.root, bg=BG, padx=self.S(14), pady=self.S(6))
        self.owned_bar.pack(fill="x")
        self.scroll = Scroll(self.root, self.S(30))
        self.scroll.pack(fill="both", expand=True, padx=(self.S(14), 0), pady=(0, self.S(8)))
        self.scroll.canvas.bind("<Configure>", self._on_resize, add="+")

    def _placeholder(self, entry, var, text):
        def show(_=None):
            if not var.get():
                entry.configure(fg=DIMTEXT)
                var.set(text)
                entry._ph = True

        def hide(_=None):
            if getattr(entry, "_ph", False):
                entry._ph = False
                var.set("")
                entry.configure(fg=TEXT)
        entry.bind("<FocusIn>", hide)
        entry.bind("<FocusOut>", show)
        entry.bind("<Escape>", lambda e: (var.set(""), self.root.focus()))
        entry._ph_text = text
        show()

    def search_text(self) -> str:
        v = self.search_var.get()
        return "" if v == getattr(self.search, "_ph_text", None) else v

    # ----- chọn tướng -----
    def _load_champion_list(self):
        try:
            self._champs = playaram.get_champion_list()
            self.root.after(0, lambda: self.pick.configure(values=self._champs))
        except Exception:
            self._champs = []

    def _filter_pick(self, e):
        if e.keysym in ("Return", "Down", "Up", "Escape"):
            return
        t = fold(self.pick_var.get()).replace(" ", "")
        self.pick.configure(values=[c for c in getattr(self, "_champs", []) if t in c] if t else getattr(self, "_champs", []))

    def _pick(self):
        v = self.pick_var.get().strip()
        if v:
            self.hub.set_focus(v)
            self.root.focus()

    def _auto(self):
        self.pick_var.set("")
        self.hub.set_focus(None)

    # ----- vòng cập nhật -----
    def _on_resize(self, e):
        if abs(e.width - self._width) > self.S(40):
            self._width = e.width
            self._full_sig = None

    def _poll(self):
        try:
            st = self.hub.state()
            self._st = st
            self._update_bars(st)
            champ = st.get("champion")
            full = (champ or {}).get("slug"), (champ or {}).get("fetched_at"), self.tab, tuple(sorted(self.expanded)), \
                tuple(st.get("owned", [])), self._cols(), st.get("focus")
            if full != self._full_sig:
                self._full_sig = full
                self._render(st)
            self._light_update()
        except Exception as e:  # không để giao diện chết vì 1 lỗi
            print("ui:", repr(e))
        self.root.after(700, self._poll)

    def _cols(self):
        w = self._width or self.scroll.canvas.winfo_width()
        return max(1, (w - self.S(30)) // self.S(CARD_W))

    def _update_bars(self, st):
        game, scan = st.get("game", {}), st.get("scan") or {}
        if self.overlay and self.ov_var.get() != self.overlay.visible:   # bật/tắt bằng phím tắt
            self.ov_var.set(self.overlay.visible)
        self.dot.itemconfigure(self._dot, fill=GOOD if game.get("in_game") else MUTED)
        champ = st.get("champion") or {}
        if champ.get("slug") and self.root.focus_get() is not self.pick and self.pick_var.get() != champ["slug"]:
            self.pick_var.set(champ["slug"])        # ô chọn tướng luôn hiện tướng đang xem
        if game.get("in_game"):
            txt = f"Trong trận: {game.get('champion_name') or '?'}"
        elif st.get("focus"):
            txt = f"Đang xem: {st['focus']}"
        else:
            txt = "Đang chờ trận…"
        self.status.configure(text=txt)
        if scan.get("error"):
            s, col = scan["error"], OKC
        elif scan.get("calibrating_in") is not None:
            s, col = (f"Hiệu chỉnh sau {int(scan['calibrating_in']) + 1} giây – mở bảng chọn lõi trong game"
                      if scan["calibrating_in"] > 0 else scan.get("status", "")), OKC
        else:
            s, col = scan.get("status", ""), (GOOD if (scan.get("offer") or {}).get("visible") else
                                              MUTED if scan.get("calibrated") else OKC)
        self.scan_lbl.configure(text=("Quét màn hình: " + s) if s else "", fg=col)

    # ----- vẽ lại toàn bộ (đổi tướng / tab / lõi đã chọn / kích thước) -----
    def _render(self, st):
        champ = st.get("champion")
        y = self.scroll.canvas.yview()[0]
        if getattr(self, "_scroll_top", False) or (champ or {}).get("slug") != getattr(self, "_last_slug", None):
            y, self._scroll_top = 0.0, False         # đổi tab / đổi tướng: về đầu trang
        self._last_slug = (champ or {}).get("slug")
        for w in self.head.winfo_children() + self.tabs.winfo_children():
            w.destroy()
        self.scroll.clear()
        self.cards, self.advice_box = {}, None
        self._light_sig = None
        self._render_owned(st)
        if not champ:
            msg = (f"Đang tải dữ liệu {st['focus']}…" if st.get("focus") and not st.get("error")
                   else st.get("error") or "Vào một trận ARAM Hỗn Loạn để app tự nhận tướng, hoặc chọn tướng ở ô bên phải trên cùng.")
            self.label(self.scroll.inner, msg, 11, MUTED, wraplength=self.S(700)).pack(pady=self.S(60))
            return
        self._render_head(champ)
        self._render_tabs(champ)
        if self.tab == "aug":
            self._render_augments(champ, st)
            self._render_items(champ)
        else:
            self._render_combos(champ, st)
        self.root.update_idletasks()
        self.scroll.canvas.yview_moveto(y)

    def _render_head(self, c):
        self.icon(self.head, c.get("icon"), 60).pack(side="left", padx=(0, self.S(12)))
        box = tk.Frame(self.head, bg=BG)
        box.pack(side="left")
        row = tk.Frame(box, bg=BG)
        row.pack(anchor="w")
        self.label(row, c.get("name", ""), 18, TEXT, True).pack(side="left")
        self.label(row, c.get("tier", ""), 18, TIER_COLOR.get(c.get("tier"), OKC), True).pack(side="left", padx=self.S(8))
        meta = f"Tỉ lệ thắng {c.get('winrate')}%   ·   {c.get('games', 0):,} trận   ·   Bản {c.get('patch', '?')}"
        if c.get("fetched_at"):
            ago = int((time.time() - c["fetched_at"]) / 60)
            meta += f"   ·   Dữ liệu {ago} phút trước{' (cũ, mạng lỗi)' if c.get('stale') else ''}"
        self.label(box, meta.replace(",", "."), 9, MUTED).pack(anchor="w")

    def _render_tabs(self, c):
        n = sum(len(s.get("combos", [])) for s in c.get("playstyles", []))
        for key, text in (("aug", "Lõi & trang bị"), ("combo", f"Combo lõi ({n})")):
            on = self.tab == key
            t = tk.Label(self.tabs, text=text, fg=TEXT if on else MUTED, bg=BG, font=self.f(10, True),
                         padx=self.S(12), pady=self.S(6), cursor="hand2")
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
        if not champ:
            return
        if not ids:
            hint = f" (trong game: {hotkeys.label('pick1')}/2/3)" if hotkeys.ACTIVE.get("pick1") else ""
            self.label(self.owned_bar, f"Bấm vào lõi bạn đã chọn để app gợi ý lõi hợp combo cho lượt sau{hint}.",
                       9, MUTED).pack(side="left")
            return
        self.label(self.owned_bar, "Lõi đã chọn:", 9, MUTED).pack(side="left", padx=(0, self.S(6)))
        names = self._names(champ)
        for i in ids:
            chip = tk.Frame(self.owned_bar, bg=PANEL2, padx=self.S(4), pady=self.S(2))
            chip.pack(side="left", padx=self.S(3))
            self.icon(chip, i, 20).pack(side="left")
            self.label(chip, names.get(i, f"#{i}"), 9).pack(side="left", padx=self.S(4))
            x = self.label(chip, "✕", 9, MUTED, cursor="hand2")
            x.pack(side="left")
            x.bind("<Button-1>", lambda e, i=i: self._own(remove=i))
        self.button(self.owned_bar, "Xoá hết", lambda: self._own(clear=True), 9).pack(side="left", padx=self.S(8))

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

    # ----- tab Lõi -----
    def _section(self, parent, title, color=TEXT, right=None):
        sec = tk.Frame(parent, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        sec.pack(fill="x", pady=(0, self.S(12)), padx=(0, self.S(14)))
        head = tk.Frame(sec, bg=PANEL, padx=self.S(12), pady=self.S(8))
        head.pack(fill="x")
        self.label(head, title, 11, color, True).pack(side="left")
        if right:
            right(head).pack(side="right")
        tk.Frame(sec, bg=LINE, height=1).pack(fill="x")
        body = tk.Frame(sec, bg=PANEL, padx=self.S(10), pady=self.S(10))
        body.pack(fill="x")
        return body

    def _render_augments(self, champ, st):
        root = self.scroll.inner
        self.advice_box = tk.Frame(root, bg=BG)
        self.advice_box.pack(fill="x", padx=(0, self.S(14)))
        owned = set(st.get("owned", []))
        fit = advice.combo_fit(champ, owned)
        any_tier = {}
        for c in advice.combos(champ):
            for a in c["augments"]:
                if advice.TIER_BONUS.get(c["tier"], 0) > advice.TIER_BONUS.get(any_tier.get(a["id"]), 0):
                    any_tier[a["id"]] = c["tier"]
        base = champ.get("winrate") or 50
        cols = self._cols()
        # chỗ cho tên lõi trong thẻ = bề rộng thẻ - icon - số thứ tự - lề
        card_w = ((self._width or self.scroll.canvas.winfo_width()) - self.S(60)) / cols
        self._name_w = max(self.S(60), int(card_w - self.S(100)))
        for key, title, color in RARITY:
            items = champ.get("augments", {}).get(key, [])
            more = len(items) - TOP_N
            open_ = key in self.expanded
            right = (lambda h, k=key, o=open_, m=more: self.button(h, "Thu gọn" if o else f"Xem thêm ({m})",
                                                                   lambda: self._toggle_more(k), 9)) if more > 0 else None
            body = self._section(root, title, color, right)
            for c in range(cols):
                body.grid_columnconfigure(c, weight=1, uniform="card")
            for i, a in enumerate(items):
                card = self._aug_card(body, a, i, color, base, fit.get(a["id"]), any_tier.get(a["id"]), a["id"] in owned)
                card["extra"], card["rarity"] = i >= TOP_N, key
                card["pos"] = (i // cols, i % cols)
                self.cards[a["id"]] = card
                if not card["extra"] or open_ or card["owned"]:
                    card["w"].grid(row=card["pos"][0], column=card["pos"][1], sticky="nsew", padx=self.S(4), pady=self.S(4))
            if not items:
                self.label(body, "Không có dữ liệu", 10, MUTED).grid(row=0, column=0)

    def _toggle_more(self, key):
        self.expanded.symmetric_difference_update({key})
        self._full_sig = None

    def _aug_card(self, parent, a, i, color, base, fit, any_tier, owned):
        outer = tk.Frame(parent, bg=color)                       # viền trái màu theo bậc
        inner = tk.Frame(outer, bg=CARD, padx=self.S(8), pady=self.S(6))
        inner.pack(fill="both", expand=True, padx=(self.S(2), 0))
        frame = tk.Frame(inner, bg="#0b0e18", highlightthickness=1, highlightbackground=color, padx=self.S(3), pady=self.S(3))
        frame.pack(side="left")
        self.icon(frame, a["id"], 38).pack()
        right = tk.Frame(inner, bg=CARD)
        right.pack(side="left", fill="x", expand=True, padx=(self.S(10), 0))
        top = tk.Frame(right, bg=CARD)
        top.pack(fill="x")
        self.label(top, f"{i + 1}", 8, MUTED).pack(side="left")
        name = self.label(top, self._fit(a["name"], self._name_w, 10, True), 10, TEXT, True, anchor="w")
        name.pack(side="left", padx=(self.S(4), 0), fill="x", expand=True)
        stats = tk.Frame(right, bg=CARD)
        stats.pack(fill="x")
        wr = a.get("winrate") or 0
        wcol = GOOD if wr >= base + 2 else OKC if wr >= base - 1 else BAD
        self.label(stats, f"{wr:.2f}%", 11, wcol, True, mono=True).pack(side="left")
        low = a.get("pickrate") is not None and a["pickrate"] < LOW_PICK
        self.label(stats, f"{a.get('pickrate', '?')}%{'*' if low else ''}", 9, MUTED, mono=True).pack(side="left", padx=self.S(8))
        if fit:
            self.badge(stats, f"hợp combo {fit}", GOOD, filled=True).pack(side="left")
        elif any_tier:
            self.badge(stats, f"combo {any_tier}", TIER_COLOR.get(any_tier, MUTED)).pack(side="left")
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

    # ----- cập nhật nhẹ: tìm kiếm + bảng lõi đọc từ màn hình -----
    def _light_update(self, from_search=False):
        st = self._st
        champ = st.get("champion")
        if not champ or self.tab != "aug" or self.advice_box is None:
            return
        terms = [t.strip() for t in fold(self.search_text()).split(",") if t.strip()]
        adv = st.get("advice")
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
            state = "hit" if hit else "owned" if c["owned"] else "dim" if active else "normal"
            self._style_card(c, state)
            if c["extra"]:   # lõi ngoài top 8 đang được tìm / đọc ra / đã chọn thì vẫn hiện
                if hit or c["owned"] or c["rarity"] in self.expanded:
                    c["w"].grid(row=c["pos"][0], column=c["pos"][1], sticky="nsew", padx=self.S(4), pady=self.S(4))
                else:
                    c["w"].grid_remove()
        # ô gợi ý
        for w in self.advice_box.winfo_children():
            w.destroy()
        if adv:
            self._advice(adv, "offer")
        elif terms:
            cat = self.hub.catalog()
            ids = list(dict.fromkeys(hits + [i for i, a in cat.items() if any(t in fold(a["name"]) for t in terms)]))[:8]
            if ids:
                ranked = advice.rank_offer([[i] for i in ids], champ, cat, set(st.get("owned", [])))
                self._advice(ranked, "search")

    def _advice(self, ranked, source):
        box = tk.Frame(self.advice_box, bg=PANEL, highlightthickness=1, highlightbackground=GOOD,
                       padx=self.S(12), pady=self.S(8))
        box.pack(fill="x", pady=(0, self.S(12)))
        rows = sorted(ranked, key=lambda r: r["rank"])
        head = tk.Frame(box, bg=PANEL)
        head.pack(fill="x")
        self.label(head, ("Đọc từ màn hình · " if source == "offer" else "") + "Nên chọn:", 10, TEXT).pack(side="left")
        self.label(head, rows[0]["best"]["name"], 10, GOOD, True).pack(side="left", padx=self.S(4))
        if source == "offer" and self.scanner:
            self.button(head, "Ẩn", self.scanner.mark_hidden, 9).pack(side="right")
        for r in rows:
            b = r["best"]
            row = tk.Frame(box, bg=PANEL, pady=self.S(4))
            row.pack(fill="x")
            self.icon(row, b["id"], 30).pack(side="left")
            mid = tk.Frame(row, bg=PANEL)
            mid.pack(side="left", fill="x", expand=True, padx=self.S(10))
            if len(r["candidates"]) > 1:
                self.label(mid, "Một trong (icon giống nhau) – bấm lõi bạn đã chọn:", 9, MUTED).pack(anchor="w")
                line = tk.Frame(mid, bg=PANEL)
                line.pack(anchor="w")
                for c in r["candidates"]:
                    chip = tk.Frame(line, bg=PANEL2, padx=self.S(4), pady=self.S(1))
                    chip.pack(side="left", padx=(0, self.S(4)), pady=self.S(2))
                    self.icon(chip, c["id"], 18).pack(side="left")
                    self.label(chip, c["name"], 9).pack(side="left", padx=self.S(3))
                    self.bind_tree(chip, lambda c=c: self._pick_aug(c["id"], source))
            else:
                self.label(mid, b["name"], 10, GOOD if r["rank"] == 1 else TEXT, r["rank"] == 1).pack(anchor="w")
            wr = "chưa có số liệu" if b["winrate"] is None else f"{b['winrate']}%" + (" (chung, mọi tướng)" if b["source"] == "chung" else "")
            extra = f"  ·  +{advice.TIER_BONUS[b['fit']]} hợp combo {b['fit']}" if b.get("fit") else ""
            self.label(mid, f"Thắng {wr}{extra}", 9, MUTED).pack(anchor="w")
            if len(r["candidates"]) == 1:
                self.button(row, "Đã chọn", lambda i=b["id"]: self._pick_aug(i, source), 9,
                            primary=r["rank"] == 1).pack(side="right")

    def _pick_aug(self, aug_id, source):
        self._own(add=aug_id)
        if source == "search":
            self.search_var.set("")
            self.search.event_generate("<FocusOut>")

    # ----- trang bị -----
    def _render_items(self, c):
        root = self.scroll.inner
        self.label(root, "Trang bị gợi ý", 13, TEXT, True).pack(anchor="w", pady=(self.S(8), self.S(2)))
        self.label(root, "Viền xanh = 2 món cốt lõi quyết định hướng build.", 9, MUTED).pack(anchor="w", pady=(0, self.S(8)))
        grid = tk.Frame(root, bg=BG)
        grid.pack(fill="x", padx=(0, self.S(14)))
        builds = c.get("builds") or []
        w = self._width or self.scroll.canvas.winfo_width()
        ncol = 3 if w >= self.S(1050) else 2 if w >= self.S(680) else 1
        for k in range(ncol):
            grid.grid_columnconfigure(k, weight=1, uniform="b")
        for i, b in enumerate(builds):
            card = tk.Frame(grid, bg=PANEL, highlightthickness=1, highlightbackground=LINE, padx=self.S(12), pady=self.S(10))
            card.grid(row=i // ncol, column=i % ncol, sticky="nsew", padx=self.S(4), pady=self.S(4))
            self.label(card, b["name"], 10, TEXT, True).pack(anchor="w")
            k = tk.Frame(card, bg=PANEL)
            k.pack(anchor="w", pady=self.S(2))
            self.label(k, f"Thắng {b.get('winrate', '?')}%", 10, GOOD, True).pack(side="left")
            self.label(k, f"Chọn {b.get('pickrate', '?')}%  ·  {b.get('games', '?')} trận đủ đồ", 9, MUTED).pack(side="left", padx=self.S(8))
            if b.get("style"):
                self.label(card, b["style"], 9, MUTED).pack(anchor="w")
            for group in (b.get("items", []), b.get("boots", []) + b.get("spells", [])):
                row = tk.Frame(card, bg=PANEL)
                row.pack(anchor="w", pady=(self.S(6), 0))
                for it in group:
                    self._item(row, it)
            if b.get("with"):
                w = tk.Frame(card, bg=PANEL)
                w.pack(anchor="w", pady=(self.S(6), 0))
                self.label(w, "Hay lên cùng:", 9, MUTED).pack(side="left")
                for x in b["with"]:
                    self.icon(w, x.get("icon"), 22).pack(side="left", padx=(self.S(6), self.S(2)))
                    self.label(w, f"{x['name']} {x.get('winrate') or ''}%", 9, MUTED).pack(side="left")
        if not builds:
            self.label(grid, "Chưa có build.", 10, MUTED).grid(row=0, column=0)

        lists = tk.Frame(root, bg=BG)
        lists.pack(fill="x", padx=(0, self.S(14)), pady=(self.S(8), self.S(16)))
        for k in range(3):
            lists.grid_columnconfigure(k, weight=1, uniform="l")
        for k, (title, rows) in enumerate((("Trang bị khác", c.get("other_items")), ("Giày", c.get("boots")),
                                           ("Phép bổ trợ", c.get("spells")))):
            box = tk.Frame(lists, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
            box.grid(row=0, column=k, sticky="nsew", padx=self.S(4))
            self.label(box, title, 10, TEXT, True).pack(anchor="w", padx=self.S(12), pady=self.S(8))
            for r in rows or []:
                line = tk.Frame(box, bg=PANEL, padx=self.S(12), pady=self.S(3))
                line.pack(fill="x")
                for src in r.get("icons", []):
                    self.icon(line, src, 26).pack(side="left", padx=(0, self.S(3)))
                self.label(line, r["name"], 9, TEXT, anchor="w").pack(side="left", padx=self.S(6), fill="x", expand=True)
                self.label(line, f"{r.get('winrate', '?')}%", 9, TEXT, True, mono=True).pack(side="left")
                self.label(line, f"{r.get('pickrate', '?')}%", 8, MUTED, mono=True).pack(side="left", padx=(self.S(6), 0))
            tk.Frame(box, bg=PANEL, height=self.S(6)).pack()

    def _item(self, parent, it):
        cell = tk.Frame(parent, bg=PANEL, width=self.S(70))
        cell.pack(side="left", padx=(0, self.S(4)), anchor="n")
        border = tk.Frame(cell, bg=GOOD if it.get("core") else PANEL, padx=self.S(2), pady=self.S(2))
        border.pack()
        self.icon(border, it.get("icon"), 40).pack()
        self.label(cell, it.get("name", ""), 8, MUTED, wraplength=self.S(68), justify="center").pack()

    # ----- tab Combo -----
    def _render_combos(self, c, st):
        root = self.scroll.inner
        owned = set(st.get("owned", []))
        styles = c.get("playstyles") or []
        if not styles:
            self.label(root, "Chưa có lối chơi / combo cho tướng này.", 11, MUTED).pack(pady=self.S(40))
            return
        self.label(root, "Hạng combo là đánh giá của biên tập viên, không phải tỉ lệ thắng. "
                   "Bấm vào lõi để đánh dấu đã chọn; combo chứa lõi đã chọn được tô xanh.", 9, MUTED,
                   wraplength=self.S(900), justify="left").pack(anchor="w", pady=(self.S(4), self.S(10)))
        wrap = max(self.S(400), (self._width or self.S(1000)) - self.S(80))
        for s in styles:
            card = tk.Frame(root, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
            card.pack(fill="x", padx=(0, self.S(14)), pady=(0, self.S(12)))
            head = tk.Frame(card, bg=PANEL, padx=self.S(12), pady=self.S(8))
            head.pack(fill="x")
            if s.get("tier"):
                self.badge(head, s["tier"], TIER_COLOR.get(s["tier"], MUTED)).pack(side="left", padx=(0, self.S(8)))
            self.label(head, s["name"], 11, TEXT, True, wraplength=wrap, justify="left").pack(side="left")
            if s.get("description"):
                self.label(card, s["description"], 9, "#c9cddb", wraplength=wrap, justify="left",
                           padx=self.S(12)).pack(anchor="w", pady=(0, self.S(8)))
            combos = sorted(s.get("combos", []), key=lambda x: -sum(a["id"] in owned for a in x["augments"]))
            for cb in combos:
                n = sum(a["id"] in owned for a in cb["augments"])
                bg = "#132a20" if n else PANEL
                tk.Frame(card, bg=LINE, height=1).pack(fill="x")
                row = tk.Frame(card, bg=bg, padx=self.S(12), pady=self.S(8))
                row.pack(fill="x")
                line = tk.Frame(row, bg=bg)
                line.pack(anchor="w")
                self.badge(line, cb["tier"], TIER_COLOR.get(cb["tier"], MUTED)).pack(side="left", padx=(0, self.S(8)))
                for k, a in enumerate(cb["augments"]):
                    if k:
                        self.label(line, "+", 10, MUTED).pack(side="left", padx=self.S(3))
                    have = a["id"] in owned
                    chip = tk.Frame(line, bg=PANEL2, padx=self.S(4), pady=self.S(2), highlightthickness=1,
                                    highlightbackground=ACCENT if have else PANEL2)
                    chip.pack(side="left")
                    self.icon(chip, a["id"], 20).pack(side="left")
                    self.label(chip, a["name"], 9, RARITY_COLOR.get(a.get("rarity"), TEXT)).pack(side="left", padx=self.S(4))
                    self.bind_tree(chip, lambda i=a["id"]: self._own(toggle=i))
                if n:
                    self.label(line, f"đã có {n}/{len(cb['augments'])}", 9, GOOD).pack(side="left", padx=self.S(8))
                if cb.get("why"):
                    self.label(row, cb["why"], 9, "#c9cddb", wraplength=wrap, justify="left").pack(anchor="w", pady=(self.S(4), 0))
            if s.get("items"):
                tk.Frame(card, bg=LINE, height=1).pack(fill="x")
                row = tk.Frame(card, bg=PANEL, padx=self.S(12), pady=self.S(8))
                row.pack(fill="x")
                self.label(row, "Đồ khuyên dùng:", 9, MUTED).pack(side="left", anchor="n", padx=(0, self.S(8)))
                for it in s["items"]:
                    self._item(row, it)
            if s.get("tips"):
                tk.Frame(card, bg=LINE, height=1).pack(fill="x")
                tips = tk.Frame(card, bg=PANEL, padx=self.S(12), pady=self.S(8))
                tips.pack(fill="x")
                for t in s["tips"]:
                    self.label(tips, f"•  {t['title']}. {t['text']}", 9, "#c9cddb", wraplength=wrap,
                               justify="left").pack(anchor="w", pady=self.S(1))

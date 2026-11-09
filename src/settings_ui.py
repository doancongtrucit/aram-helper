# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
"""Hộp thoại Cài đặt kiểu "app gaming": thanh điều hướng bên trái (trang + mục con), nội dung bên phải chia mục,
mỗi dòng = tên + mô tả bên trái, điều khiển bên phải (công tắc trượt, nút chọn, thanh trượt).

Mọi thay đổi áp dụng ngay (settings.set → các phần đăng ký tự cập nhật). Đổi trang chỉ dựng lại phần nội dung;
cuộn bằng chuột / bấm mục con cuộn mượt (có gia tốc giảm dần).
"""
from __future__ import annotations

import sys
import tkinter as tk
from tkinter import ttk

import about
import paths
import settings
from i18n import T

CORNERS = [("custom", "Kéo thả"), ("top-right", "Trên phải"), ("top-left", "Trên trái"),
           ("bottom-right", "Dưới phải"), ("bottom-left", "Dưới trái")]
HOTKEYS = [("calibrate", "Định vị lõi"), ("pick1", "Đánh dấu lõi ở thẻ 1"), ("pick2", "Đánh dấu lõi ở thẻ 2"),
           ("pick3", "Đánh dấu lõi ở thẻ 3"), ("overlay", "Ẩn / hiện overlay"), ("diagnose", "Lưu ảnh chẩn đoán")]
# Windows: mã phím ảo (event.keycode) → tên phím dùng trong hotkeys.parse
_VK = {**{65 + i: chr(97 + i) for i in range(26)}, **{48 + i: str(i) for i in range(10)},
       **{111 + i: f"f{i}" for i in range(1, 13)}}
SECTIONS = [("offer", "Gợi ý lõi"), ("combo", "Combo"), ("owned", "Lõi đã chọn"),
            ("build", "Lối lên đồ"), ("counter", "Theo đội địch")]
TOP_N = [("0", "Tự vừa"), ("4", "4"), ("6", "6"), ("8", "8"), ("10", "10"), ("12", "12")]

# Bảng màu riêng của hộp thoại (nền theme.BG / PANEL của app)
SIDE, CONTENT = "#0e1119", "#141927"
NAV_HOVER, NAV_ACTIVE = "#1b2132", "#252d42"
BTN, BTN_HOVER, SEG_ON = "#232a3d", "#2f3852", "#3a4669"
SW_OFF, KNOB = "#4a5168", "#ffffff"
SIDE_W, WIN_W, WIN_H = 236, 920, 640       # px ở cỡ 100%
FRAME_MS, ANIM_FRAMES = 12, 9


def _mix(c1: str, c2: str, t: float) -> str:
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


_switch_imgs: dict = {}


def _switch_img(root, w: int, h: int, bg: str, on: str, step: int, steps: int):
    """Ảnh công tắc (khử răng cưa bằng vẽ to gấp 4 rồi thu nhỏ) ở vị trí step/steps – dùng làm các khung chuyển động."""
    key = (id(root), w, h, bg, on, step, steps)
    if key not in _switch_imgs:
        from PIL import Image, ImageDraw, ImageTk
        k, t = 4, step / steps
        W, H = w * k, h * k
        track = _mix(SW_OFF, on, t)
        im = Image.new("RGBA", (W, H), bg)
        dr = ImageDraw.Draw(im)
        dr.rounded_rectangle((0, 0, W - 1, H - 1), radius=H // 2, fill=track)
        pad = 3 * k
        d = H - 2 * pad
        x = pad + (W - 2 * pad - d) * t
        dr.ellipse((x, pad, x + d, pad + d), fill=KNOB)
        cx, cy, r, lw = x + d / 2, pad + d / 2, d * 0.22, max(2, int(1.8 * k))
        if t >= 0.5:      # ✓ khi bật, ✕ khi tắt – như các app chat / gaming quen thuộc
            dr.line((cx - r, cy, cx - r * 0.25, cy + r * 0.75, cx + r, cy - r * 0.7), fill=track, width=lw, joint="curve")
        else:
            dr.line((cx - r * 0.8, cy - r * 0.8, cx + r * 0.8, cy + r * 0.8), fill=track, width=lw)
            dr.line((cx - r * 0.8, cy + r * 0.8, cx + r * 0.8, cy - r * 0.8), fill=track, width=lw)
        _switch_imgs[key] = ImageTk.PhotoImage(im.resize((w, h), Image.LANCZOS), master=root)
    return _switch_imgs[key]


class Switch(tk.Label):
    """Công tắc bật / tắt có hiệu ứng trượt. Đổi giá trị biến (kể cả từ _sync) → tự chạy hiệu ứng."""
    STEPS = 6

    def __init__(self, parent, var: tk.BooleanVar, on_toggle, S, on_color):
        super().__init__(parent, bg=parent["bg"], bd=0, cursor="hand2")
        self.var, self.size, self.on_color = var, (S(42), S(24)), on_color
        self.pos = self.STEPS if var.get() else 0
        self._job = None
        self.bind("<Button-1>", lambda e: on_toggle(not self.var.get()))
        var.trace_add("write", lambda *_: self._animate())
        self._draw()

    def _draw(self):
        w, h = self.size
        self.configure(image=_switch_img(self.winfo_toplevel(), w, h, self["bg"], self.on_color, self.pos, self.STEPS))

    def _animate(self):
        if self._job:
            self.after_cancel(self._job)
            self._job = None
        try:
            target = self.STEPS if self.var.get() else 0
        except tk.TclError:
            return
        if not self.winfo_exists() or self.pos == target:
            return
        self.pos += 1 if target > self.pos else -1
        self._draw()
        self._job = self.after(FRAME_MS + 4, self._animate)


_knob_imgs: dict = {}


def _knob_img(root, d: int, bg: str):
    """Núm tròn trắng khử răng cưa (kèm bóng mờ nhẹ) cho thanh trượt."""
    key = (id(root), d, bg)
    if key not in _knob_imgs:
        from PIL import Image, ImageDraw, ImageFilter, ImageTk
        k = 4
        D = d * k
        im = Image.new("RGBA", (D, D), bg)
        shadow = Image.new("L", (D, D), 0)
        ImageDraw.Draw(shadow).ellipse((k, 2 * k, D - k, D - 1), fill=110)
        im.paste(Image.new("RGBA", (D, D), "#000000"), (0, 0), shadow.filter(ImageFilter.GaussianBlur(k)))
        ImageDraw.Draw(im).ellipse((k, k, D - 2 * k, D - 2 * k), fill=KNOB)
        _knob_imgs[key] = ImageTk.PhotoImage(im.resize((d, d), Image.LANCZOS), master=root)
    return _knob_imgs[key]


class Slider(tk.Canvas):
    """Thanh trượt mảnh: phần đã kéo tô màu, núm tròn trắng. Bấm / kéo bất kỳ đâu trên thanh để đổi giá trị."""

    def __init__(self, parent, var: tk.DoubleVar, lo, hi, step, cast, on_move, on_release, length, S, color):
        self.knob = S(20)
        super().__init__(parent, width=length, height=self.knob + S(4), bg=parent["bg"], highlightthickness=0,
                         bd=0, cursor="hand2")
        self.var, self.lo, self.hi, self.step, self.cast = var, lo, hi, step, cast
        self.on_move, self.on_release, self.length, self.color = on_move, on_release, length, color
        self.track = max(3, S(4))
        self._img = _knob_img(self.winfo_toplevel(), self.knob, parent["bg"])
        self.bind("<Button-1>", self._drag)
        self.bind("<B1-Motion>", self._drag)
        self.bind("<ButtonRelease-1>", lambda e: self.on_release(self._value(e.x)))
        var.trace_add("write", lambda *_: self.winfo_exists() and self._draw())
        self._draw()

    def _x(self, v) -> float:
        r = self.knob / 2
        t = (float(v) - self.lo) / (self.hi - self.lo) if self.hi > self.lo else 0
        return r + max(0.0, min(1.0, t)) * (self.length - 2 * r)

    def _value(self, x):
        r = self.knob / 2
        t = max(0.0, min(1.0, (x - r) / max(1, self.length - 2 * r)))
        v = self.lo + round(t * (self.hi - self.lo) / self.step) * self.step
        return self.cast(round(v)) if self.cast is int else round(v, 2)

    def _drag(self, e):
        v = self._value(e.x)
        if v != self.var.get():
            self.on_move(v)

    def _draw(self):
        self.delete("all")
        try:
            x = self._x(self.var.get())
        except tk.TclError:
            return
        r, cy, w = self.knob / 2, int(self["height"]) / 2, self.track
        self.create_line(r, cy, self.length - r, cy, fill=SW_OFF, width=w, capstyle="round")
        self.create_line(r, cy, x, cy, fill=self.color, width=w, capstyle="round")
        self.create_image(x, cy, image=self._img)


class SettingsDialog:
    def __init__(self, app):
        import theme as d
        self.app, self.d = app, d
        self.page = "general"
        self.win = tk.Toplevel(app.root)
        self.win.configure(bg=CONTENT)
        self.win.resizable(False, False)
        self.win.transient(app.root)
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        self.win.bind("<Escape>", self._on_escape)
        self.win.bind("<MouseWheel>", self._on_wheel)
        self._listener = lambda ch: self.win.after(0, self._on_change, ch)
        settings.on_change(self._listener)
        self._capture = None
        self._scroll_job = None
        self._build()

    # ----- vị trí / đóng -----
    def center(self):
        """Đặt hộp thoại giữa cửa sổ chính (gọi mỗi lần mở / dựng lại)."""
        a, w = self.app.root, self.win
        w.update_idletasks()
        W, H = self._size
        # geometry đặt góc khung ngoài; trừ viền + thanh tiêu đề để phần nội dung nằm đúng giữa
        bx, by = max(0, w.winfo_rootx() - w.winfo_x()), max(0, w.winfo_rooty() - w.winfo_y())
        x = a.winfo_rootx() + (a.winfo_width() - W) // 2 - bx
        y = a.winfo_rooty() + (a.winfo_height() - H) // 2 - by
        sw, sh = w.winfo_screenwidth(), w.winfo_screenheight()
        x, y = min(max(0, x), max(0, sw - W)), min(max(0, y), max(0, sh - H - by))
        w.geometry(f"{W}x{H}+{x}+{y}")
        if not getattr(self, "_recentered", False):          # lần đầu: chưa biết cỡ thanh tiêu đề → đặt lại 1 lần
            self._recentered = True
            w.after(60, self.center)

    def close(self):
        try:
            settings._listeners.remove(self._listener)
        except ValueError:
            pass
        self.win.destroy()

    def _on_escape(self, _=None):
        if self._capture:
            return self._end_capture()
        self.close()
        return "break"

    def _on_change(self, ch):
        if not self.win.winfo_exists():
            return
        if "lang" in ch or "ui_zoom" in ch:     # chữ / cỡ chữ đổi → dựng lại hộp thoại
            self._build()
        else:
            self._sync()

    # ----- khung -----
    def _pages(self):
        pages = [("general", "⚙", T("Chung")), ("overlay", "▣", T("Overlay"))]
        if sys.platform == "win32":
            pages.append(("hotkeys", "⌨", T("Phím tắt")))
        return [(T("Cài đặt ứng dụng"), pages), (T("Hỗ trợ"), [("about", "ⓘ", T("Giới thiệu"))])]

    def _build(self):
        """Dựng cả hộp thoại (lần đầu, đổi ngôn ngữ / cỡ chữ)."""
        a = self.app
        self._sub_labels, self._sections = [], []
        for w in self.win.winfo_children():
            w.destroy()
        self.win.title("ARAM Helper – " + T("Cài đặt"))
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        self._size = (min(a.S(WIN_W), sw - 40), min(a.S(WIN_H), sh - 80))
        self.side = tk.Frame(self.win, bg=SIDE, width=a.S(SIDE_W))
        self.side.pack(side="left", fill="y")
        self.side.pack_propagate(False)
        tk.Frame(self.win, bg=self.d.LINE, width=1).pack(side="left", fill="y")
        main = tk.Frame(self.win, bg=CONTENT)
        main.pack(side="left", fill="both", expand=True)

        # thanh tiêu đề trang: tên trang · Mặc định · ✕
        self.head = tk.Frame(main, bg=CONTENT, height=a.S(52))
        self.head.pack(fill="x")
        self.head.pack_propagate(False)
        tk.Frame(main, bg=self.d.LINE, height=1).pack(fill="x")

        # vùng cuộn
        wrap = tk.Frame(main, bg=CONTENT)
        wrap.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(wrap, bg=CONTENT, highlightthickness=0, bd=0)
        self.sb = ttk.Scrollbar(wrap, orient="vertical", command=self._scroll_cmd)
        self.canvas.configure(yscrollcommand=self._on_scrolled)
        self.sb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.body_w = self._size[0] - a.S(SIDE_W) - a.S(20) - 2 * a.S(44)
        self.inner = tk.Frame(self.canvas, bg=CONTENT)
        self._win_id = self.canvas.create_window(a.S(44), 0, window=self.inner, anchor="nw", width=self.body_w)
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=(0, 0, 0, self.inner.winfo_reqheight() + a.S(40))))
        self.center()
        self._render_page()

    def _render_page(self):
        """Đổi trang: chỉ dựng lại nội dung + thanh bên, về đầu trang."""
        a, d = self.app, self.d
        self._end_capture(refresh=False)
        self.vars: dict[str, tk.Variable] = {}
        self._sections: list[tuple[str, tk.Widget]] = []
        self._hk_buttons = {}
        self._wraps = []
        for w in self.inner.winfo_children():
            w.destroy()
        for w in self.head.winfo_children():
            w.destroy()
        self.body = self.inner
        tk.Frame(self.inner, bg=CONTENT, height=a.S(12)).pack()
        getattr(self, "_page_" + self.page)()
        tk.Frame(self.inner, bg=CONTENT, height=a.S(24)).pack()
        self._fit_wraps()                     # cũng cập nhật vị trí các mục → tô đúng mục con ở đầu trang

        title = dict((k, t) for _, items in self._pages() for k, _, t in items).get(self.page, "")
        a.label(self.head, title, 12, d.TEXT, True, bg=CONTENT).pack(side="left", padx=a.S(24))
        close = a.label(self.head, "✕", 13, d.MUTED, bg=CONTENT, cursor="hand2", padx=a.S(10))
        close.pack(side="right", padx=(0, a.S(12)))
        close.bind("<Button-1>", lambda e: self.close())
        self._hover(close, CONTENT, NAV_HOVER, fg=(d.MUTED, d.TEXT))
        if self.page != "about":
            reset = self._btn(self.head, "↺ " + T("Mặc định"), self._defaults, bg=CONTENT, hover=NAV_HOVER, fg=d.MUTED)
            reset.pack(side="right", padx=a.S(4))

        self.canvas.yview_moveto(0)
        self._scroll_pos = 0.0
        self._render_nav()
        self.win.after(80, self._mark_subnav)      # tô lại khi các mục đã có vị trí thật

    def _render_nav(self):
        a, d = self.app, self.d
        self._sub_labels = []
        for w in self.side.winfo_children():
            w.destroy()
        from version import __version__
        top = tk.Frame(self.side, bg=SIDE, padx=a.S(16), pady=a.S(18))
        top.pack(fill="x")
        try:
            tk.Label(top, image=d.app_logo(a.root, a.S(40)), bg=SIDE).pack(side="left", padx=(0, a.S(10)))
        except Exception:
            pass
        box = tk.Frame(top, bg=SIDE)
        box.pack(side="left")
        a.label(box, about.APP_NAME, 11, d.TEXT, True, bg=SIDE).pack(anchor="w")
        a.label(box, T("Phiên bản {v}", v=__version__), 8, d.MUTED, bg=SIDE).pack(anchor="w")

        self._sub_labels = []
        for group, items in self._pages():
            a.label(self.side, group.upper(), 7, d.MUTED, True, bg=SIDE).pack(
                anchor="w", padx=a.S(22), pady=(a.S(12), a.S(4)))
            for key, icon, text in items:
                on = key == self.page
                bg = NAV_ACTIVE if on else SIDE
                row = tk.Frame(self.side, bg=bg, cursor="hand2", padx=a.S(10), pady=a.S(7))
                row.pack(fill="x", padx=a.S(12), pady=a.S(1))
                ic = a.label(row, icon, 11, d.TEXT if on else d.MUTED, bg=bg, width=2)
                ic.pack(side="left")
                tx = a.label(row, text, 10, d.TEXT if on else d.MUTED, on, bg=bg)
                tx.pack(side="left", padx=(a.S(6), 0))
                for w in (row, ic, tx):
                    w.bind("<Button-1>", lambda e, k=key: self._go(k))
                if not on:
                    self._hover_group(row, (ic, tx), SIDE, NAV_HOVER)
                elif self._sections:
                    self._render_subnav()

        foot = tk.Frame(self.side, bg=SIDE, padx=a.S(18), pady=a.S(14))
        foot.pack(side="bottom", fill="x")
        a.label(foot, about.COPYRIGHT, 7, d.DIMTEXT, bg=SIDE, wraplength=a.S(SIDE_W - 36), justify="left").pack(anchor="w")
        self._mark_subnav()

    def _render_subnav(self):
        """Mục con của trang đang mở (như Account Info / Password & Security) – bấm để cuộn tới."""
        a, d = self.app, self.d
        box = tk.Frame(self.side, bg=SIDE)
        box.pack(fill="x", padx=(a.S(30), a.S(12)), pady=(a.S(2), a.S(6)))
        for i, (text, _) in enumerate(self._sections):
            row = tk.Frame(box, bg=SIDE, cursor="hand2")
            row.pack(fill="x")
            bar = tk.Frame(row, bg=d.LINE, width=a.S(2))
            bar.pack(side="left", fill="y")
            lb = a.label(row, text, 9, d.MUTED, bg=SIDE, padx=a.S(12), pady=a.S(5), cursor="hand2")
            lb.pack(side="left")
            for w in (row, lb):
                w.bind("<Button-1>", lambda e, k=i: self._jump(k))
                w.bind("<Enter>", lambda e, l=lb: l.configure(fg=d.TEXT))
                w.bind("<Leave>", lambda e, k=i: self._mark_subnav())
            self._sub_labels.append((bar, lb))

    def _mark_subnav(self):
        """Tô mục con đang nằm ở đầu vùng xem."""
        if not getattr(self, "_sub_labels", None) or not self.win.winfo_exists():
            return
        cur = self._current_section()
        for i, (bar, lb) in enumerate(self._sub_labels):
            if not lb.winfo_exists():         # đang dựng lại thanh bên
                return
            on = i == cur
            bar.configure(bg=self.d.TEXT if on else self.d.LINE)
            lb.configure(fg=self.d.TEXT if on else self.d.MUTED)

    def _current_section(self) -> int:
        if not self._sections:
            return 0
        top = self.canvas.canvasy(0) + self.app.S(60)
        cur = 0
        for i, (_, w) in enumerate(self._sections):
            y = w.winfo_y() if w.winfo_exists() else 0
            if i and y == 0:                  # mục chưa được xếp chỗ (vừa dựng xong) → bỏ qua
                continue
            if y <= top:
                cur = i
        if self._scroll_pos >= 0.999 and self._max_scroll() > 0:     # cuộn hết: mục cuối
            cur = len(self._sections) - 1
        return cur

    def _go(self, key):
        if key == self.page and getattr(self, "_sections", None) is not None:
            return self._scroll_to(0)
        self.page = key
        self._render_page()

    # ----- cuộn mượt -----
    def _max_scroll(self) -> int:
        return max(0, self.inner.winfo_reqheight() + self.app.S(40) - self.canvas.winfo_height())

    def _on_scrolled(self, lo, hi):
        self.sb.set(lo, hi)
        total = self._max_scroll()
        self._scroll_pos = (self.canvas.canvasy(0) / total) if total else 0.0
        self._mark_subnav()

    def _scroll_cmd(self, *args):
        if self._scroll_job:
            self.win.after_cancel(self._scroll_job)
            self._scroll_job = None
        self.canvas.yview(*args)

    def _on_wheel(self, e):
        if not hasattr(self, "canvas") or not self.canvas.winfo_exists():
            return
        steps = -e.delta / (1 if self.d.IS_MAC else 120)
        base = getattr(self, "_scroll_target", None)
        if self._scroll_job is None or base is None:
            base = self.canvas.canvasy(0)
        self._scroll_to(base + steps * self.app.S(90))

    def _jump(self, i):
        if 0 <= i < len(self._sections):
            self._scroll_to(self._sections[i][1].winfo_y() - self.app.S(8))

    def _scroll_to(self, y):
        """Cuộn tới y (px) với gia tốc giảm dần."""
        total = self._max_scroll()
        y = max(0, min(total, y))
        self._scroll_target = y
        if self._scroll_job:
            self.win.after_cancel(self._scroll_job)
        start = self.canvas.canvasy(0)

        def frame(i=1):
            t = i / ANIM_FRAMES
            ease = 1 - (1 - t) ** 3
            pos = start + (y - start) * ease
            self.canvas.yview_moveto(pos / (total + self.canvas.winfo_height()) if total else 0)
            if i < ANIM_FRAMES:
                self._scroll_job = self.win.after(FRAME_MS, frame, i + 1)
            else:
                self._scroll_job = None
        frame()

    # ----- mặc định / đồng bộ -----
    def _defaults(self):
        keys = {"general": ["lang", "ui_zoom", "top_n", "app_follow_offer", "always_on_top", "check_updates", "auto_pick", "focus_guard"],
                "overlay": [k for k in settings.DEFAULTS if k.startswith("ov_") or k in ("overlay", "reroll_hint")],
                "hotkeys": ["hk_" + k for k, _ in HOTKEYS]}[self.page]
        settings.reset(keys)

    def _sync(self):
        """Đồng bộ ô điều khiển với giá trị hiện tại (vd. bật overlay bằng phím tắt)."""
        for key, var in self.vars.items():
            v = settings.get(key)
            try:
                cur = var.get()
                if isinstance(var, tk.StringVar):
                    cur, v = str(cur), str(v)
                elif isinstance(var, tk.BooleanVar):
                    v = bool(v)
                if cur != v:
                    var.set(v)
            except tk.TclError:
                pass
        self._hk_refresh()

    # ----- khối dựng giao diện -----
    def _hover(self, w, bg, hover_bg, fg=None):
        def on(_):
            w.configure(bg=hover_bg, **({"fg": fg[1]} if fg else {}))

        def off(_):
            w.configure(bg=bg, **({"fg": fg[0]} if fg else {}))
        w.bind("<Enter>", on)
        w.bind("<Leave>", off)

    def _hover_group(self, frame, children, bg, hover_bg):
        def paint(c, fg):
            for w in (frame, *children):
                w.configure(bg=c)
            for w in children:
                w.configure(fg=fg)

        def leave(e):
            x, y = frame.winfo_pointerxy()
            if frame.winfo_containing(x, y) not in (frame, *children):
                paint(bg, self.d.MUTED)
        for w in (frame, *children):
            w.bind("<Enter>", lambda e: paint(hover_bg, self.d.TEXT))
            w.bind("<Leave>", leave)

    def _btn(self, parent, text, cmd, primary=False, bg=None, hover=None, fg=None):
        a, d = self.app, self.d
        bg = bg or (d.GOOD if primary else BTN)
        hover = hover or ("#5ae6ab" if primary else BTN_HOVER)
        b = tk.Label(parent, text=text, bg=bg, fg=fg or ("#05261a" if primary else d.TEXT), font=a.f(9, True),
                     padx=a.S(14), pady=a.S(6), cursor="hand2")
        b.bind("<Button-1>", lambda e: cmd())
        self._hover(b, bg, hover)
        return b

    def _section(self, title, first=False):
        """Tiêu đề mục (kèm đường kẻ phía trên, trừ mục đầu). Mục được thêm vào thanh bên để bấm cuộn tới."""
        a, d = self.app, self.d
        box = tk.Frame(self.inner, bg=CONTENT)
        box.pack(fill="x")
        if self._sections and not first:
            tk.Frame(box, bg=d.LINE, height=1).pack(fill="x", pady=(a.S(18), a.S(24)))
        a.label(box, title, 15, d.TEXT, True, bg=CONTENT).pack(anchor="w", pady=(a.S(4), a.S(10)))
        self._sections.append((title, box))
        return box

    def _row(self, label, desc=None, below=False):
        """Một dòng: tên (+ mô tả mờ) bên trái; trả về khung đặt điều khiển (bên phải, hoặc ngay dưới nếu below)."""
        a, d = self.app, self.d
        row = tk.Frame(self.inner, bg=CONTENT, pady=a.S(9))
        row.pack(fill="x")
        row.columnconfigure(0, weight=1)
        left = tk.Frame(row, bg=CONTENT)
        left.grid(row=0, column=0, sticky="w")
        a.label(left, label, 10, d.TEXT, True, bg=CONTENT).pack(anchor="w")
        row.desc = None
        if desc is not None:
            row.desc = a.label(left, desc, 9, d.MUTED, bg=CONTENT, justify="left",
                               wraplength=self.body_w - (0 if below else a.S(250)))
            row.desc.pack(anchor="w", pady=(a.S(2), 0))
        ctl = tk.Frame(row, bg=CONTENT)
        if below:
            ctl.grid(row=1, column=0, columnspan=2, sticky="w", pady=(a.S(8), 0))
        else:
            ctl.grid(row=0, column=1, sticky="e", padx=(a.S(16), 0))
            if row.desc is not None:
                self._wraps.append((row.desc, ctl))
        return ctl

    def _fit_wraps(self):
        """Mô tả xuống dòng vừa chỗ trống bên trái điều khiển (điều khiển rộng như nhóm nút thì mô tả hẹp lại)."""
        self.inner.update_idletasks()
        for desc, ctl in self._wraps:
            desc.configure(wraplength=max(self.app.S(160), self.body_w - ctl.winfo_reqwidth() - self.app.S(32)))

    def _note(self, text):
        self.app.label(self.inner, text, 9, self.d.MUTED, bg=CONTENT, wraplength=self.body_w, justify="left").pack(
            anchor="w", pady=(self.app.S(2), self.app.S(8)))

    def _check(self, key, label, desc=None):
        var = tk.BooleanVar(value=bool(settings.get(key)))
        self.vars[key] = var
        ctl = self._row(label, desc)
        Switch(ctl, var, lambda v: (var.set(v), settings.set(key, v)), self.app.S, self.d.GOOD).pack()
        return var

    def _segmented(self, parent, var, options, on_pick, multi=None):
        """Nhóm nút chọn liền nhau; multi = {value: BooleanVar} để chọn nhiều."""
        a, d = self.app, self.d
        box = tk.Frame(parent, bg=BTN, padx=a.S(3), pady=a.S(3))
        cells = []

        def paint(*_):
            for value, cell in cells:
                try:
                    on = multi[value].get() if multi else str(var.get()) == value
                except tk.TclError:
                    return
                cell.configure(bg=SEG_ON if on else BTN, fg=d.TEXT if on else d.MUTED,
                               font=a.f(9, on))
                cell.on = on
        for value, text in options:
            cell = tk.Label(box, text=text, bg=BTN, fg=d.MUTED, font=a.f(9), padx=a.S(11), pady=a.S(4),
                            cursor="hand2")
            cell.pack(side="left", padx=(0, a.S(2)))
            cell.bind("<Button-1>", lambda e, v=value: on_pick(v))
            cell.bind("<Enter>", lambda e, c=cell: (not getattr(c, "on", False)) and c.configure(bg=BTN_HOVER, fg=d.TEXT))
            cell.bind("<Leave>", lambda e: paint())
            cells.append((value, cell))
        for v in ([var] if var is not None else []) + list((multi or {}).values()):
            v.trace_add("write", paint)
        paint()
        return box

    def _choice(self, key, label, options, desc=None, cast=str, below=False):
        var = tk.StringVar(value=str(settings.get(key)))
        self.vars[key] = var
        ctl = self._row(label, desc, below)

        def pick(v):
            var.set(v)
            settings.set(key, cast(v))
        self._segmented(ctl, var, options, pick).pack(side="left")
        return ctl

    def _slider(self, key, label, lo, hi, step, fmt="{:.0%}", live=True, cast=float, desc=None):
        """Thanh trượt. live=False: chỉ áp dụng khi nhả chuột (đổi cỡ giao diện dựng lại cả cửa sổ)."""
        a, d = self.app, self.d
        ctl = self._row(label, desc, below=True)
        var = tk.DoubleVar(value=float(settings.get(key)))
        self.vars[key] = var
        val = a.label(ctl, "", 9, d.TEXT, True, bg=CONTENT, width=7, anchor="e")

        def show(*_):
            if val.winfo_exists():
                val.configure(text=fmt.format(cast(var.get()) if cast is int else var.get()))

        def moved(v):
            var.set(v)
            if live:
                settings.set(key, v)

        def released(v):
            if not live:
                settings.set(key, v)
        var.trace_add("write", show)
        Slider(ctl, var, lo, hi, step, cast, moved, released, self.body_w - a.S(80), a.S, d.ACCENT).pack(side="left")
        val.pack(side="left", padx=(a.S(12), 0))
        show()
        return ctl

    # ----- các trang -----
    def _page_general(self):
        a = self.app
        self._section(T("Giao diện"))
        self._choice("lang", T("Ngôn ngữ"), [("vi", "Tiếng Việt"), ("en", "English")],
                     desc=T("Giao diện, tên lõi, trang bị và tướng"))
        self._slider("ui_zoom", T("Cỡ giao diện"), 0.7, 1.6, 0.1, live=False,
                     desc=T("Phím tắt: Ctrl + / Ctrl - / Ctrl 0 đổi cỡ giao diện."))
        n = str(int(settings.get("top_n") or 0))
        opts = [(v, T(t)) for v, t in TOP_N]
        if n not in dict(TOP_N):
            opts.append((n, n))
        self._choice("top_n", T("Số lõi mỗi bậc"), opts, cast=int,
                     desc=T("Số lõi hiện sẵn ở mỗi bậc, bấm Xem thêm để xem tiếp. Tự vừa: theo chiều cao cửa sổ."))

        self._section(T("Cửa sổ chính"))
        self._check("app_follow_offer", T("Phản ứng khi đang chọn lõi"),
                    T("Tô sáng lõi và hiện ô Nên chọn. Tắt: cửa sổ chính giữ nguyên để xem tổng quát, "
                      "gợi ý chọn lõi chỉ hiện trên overlay."))
        self._check("always_on_top", T("Cửa sổ chính luôn nằm trên"))

        if sys.platform == "win32":
            self._section(T("Trong trận"))
            self._check("auto_pick", T("Tự ghi nhận lõi đã chọn"), T("Theo cú bấm chuột lên thẻ khi chọn lõi."))
            self._check("focus_guard", T("Giữ focus cho game"),
                        T("App vô tình lấy focus khi đang chơi thì trả lại game ngay và ghi vào log."))

        self._section(T("Cập nhật & dữ liệu"))
        from version import __version__
        ctl = self._row(T("Phiên bản {v}", v=__version__), T("Bấm để kiểm tra bản mới trên GitHub."))
        self._upd_desc = ctl.master.grid_slaves(row=0, column=0)[0].winfo_children()[-1]
        self._upd_ctl = ctl
        self._btn(ctl, T("Kiểm tra cập nhật"), self._check_update).pack()
        if getattr(a, "_update_info", None):
            self._show_new(a._update_info)
        self._check("check_updates", T("Báo khi có bản mới"), T("Tự kiểm tra bản phát hành trên GitHub."))
        ctl = self._row(T("Thư mục dữ liệu"), a._fit(str(paths.DATA), self.body_w - a.S(260), 9))
        self._btn(ctl, T("Mở"), paths.open_data_folder).pack()

    # ----- cập nhật -----
    def update_note(self, text):
        """Dòng trạng thái cập nhật (app gọi khi đang tải / cài)."""
        w = getattr(self, "_upd_desc", None)
        if w is not None and w.winfo_exists():
            w.configure(text=text)

    def _check_update(self):
        import threading
        import updater
        self.update_note(T("Đang kiểm tra…"))

        box = {}

        def run():
            box["res"] = updater.status(force=True)

        def watch():
            if not self.win.winfo_exists():
                return
            if "res" in box:
                return self._update_result(*box["res"])
            self.win.after(150, watch)
        threading.Thread(target=run, daemon=True, name="update-check-now").start()
        watch()

    def _update_result(self, state, info):
        if not self.win.winfo_exists():
            return
        if state == "new":
            self.app._show_update(info)
            self._show_new(info)
        elif state == "latest":
            self.update_note(T("Bạn đang dùng bản mới nhất."))
        else:
            self.update_note(T("Không kết nối được GitHub – thử lại sau."))

    def _show_new(self, info):
        import updater
        ctl = getattr(self, "_upd_ctl", None)
        if ctl is None or not ctl.winfo_exists():
            return
        auto = updater.can_self_update()
        self.update_note(T("Có bản mới {v}.", v=info["version"]) + ("" if auto else " " + T(
            "Bản portable / macOS không tự cập nhật được – mở trang tải.")))
        for w in ctl.winfo_children():
            w.destroy()
        self._btn(ctl, T("Cập nhật ngay") if auto else T("Mở trang tải"), lambda: self.app.start_update(info),
                  primary=True).pack()

    def _page_overlay(self):
        a = self.app
        self._section(T("Overlay"))
        self._check("overlay", T("Bật overlay"), T("Khung gợi ý và nhãn trên thẻ lõi nằm trên game."))
        self._check("ov_only_offer", T("Chỉ hiện khung khi đang chọn lõi"))
        if not a.overlay:
            self._note(T("Overlay chỉ có trên Windows."))

        self._section(T("Hiển thị"))
        self._slider("ov_opacity", T("Độ đậm khung"), 0.3, 1.0, 0.02)
        self._slider("ov_badge_opacity", T("Độ đậm nhãn trên thẻ lõi"), 0.3, 1.0, 0.02)
        self._slider("ov_scale", T("Cỡ overlay"), 0.7, 1.6, 0.1)
        self._slider("ov_width", T("Bề rộng khung"), 220, 420, 10, fmt="{} px", cast=int)

        self._section(T("Vị trí"))
        ctl = self._choice("ov_corner", T("Vị trí khung"), [(k, T(t)) for k, t in CORNERS],
                           desc=T("Kéo thả: giữ chuột trên thanh tiêu đề overlay để di chuyển."), below=True)
        if a.overlay:
            self._btn(ctl, T("Đặt lại vị trí"), a.overlay.reset_position).pack(side="left", padx=a.S(10))

        self._section(T("Nội dung"))
        self._check("ov_badges", T("Nhãn ★ / #2 / #3 trên thẻ lõi"))
        self._check("reroll_hint", T("Gợi ý đổi lõi (↻)"), T("Chỉ thẻ nên bấm đổi khi cả 3 lõi đều không tốt."))
        multi = {}
        for key, _ in SECTIONS:
            v = tk.BooleanVar(value=bool(settings.get("ov_show_" + key)))
            self.vars["ov_show_" + key] = multi[key] = v
        ctl = self._row(T("Mục hiển thị"), T("Bấm để bật / tắt từng mục trong khung overlay."), below=True)

        def flip(k):
            multi[k].set(not multi[k].get())
            settings.set("ov_show_" + k, multi[k].get())
        self._segmented(ctl, None, [(k, T(t)) for k, t in SECTIONS], flip, multi=multi).pack(side="left")
        self._choice("ov_builds", T("Số lối lên đồ"), [("1", "1"), ("2", "2"), ("3", "3")], cast=int)

    def _page_hotkeys(self):
        """Đổi phím tắt: bấm vào ô rồi nhấn tổ hợp mới (cần Ctrl hoặc Alt). Esc huỷ, Backspace về mặc định."""
        import hotkeys
        a, d = self.app, self.d
        self._section(T("Phím tắt"))
        self._note(T("Bấm vào ô rồi nhấn tổ hợp phím mới (cần Ctrl hoặc Alt, ví dụ Ctrl+Shift+L). "
                     "Esc: huỷ · Backspace: về mặc định. Phím bị app khác dùng thì app tự dùng phím dự phòng."))
        for name, text in HOTKEYS:
            ctl = self._row(T(text), "")
            b = tk.Label(ctl, text=hotkeys.pretty(settings.get("hk_" + name)), bg=BTN, fg=d.TEXT, font=a.f(9, True),
                         width=18, padx=a.S(8), pady=a.S(5), cursor="hand2", highlightthickness=1,
                         highlightbackground=BTN)
            b.pack()
            b.bind("<Button-1>", lambda e, n=name: self._start_capture(n))
            self._hover(b, BTN, BTN_HOVER)
            note = ctl.master.grid_slaves(row=0, column=0)[0].winfo_children()[-1]
            note.configure(fg=d.OKC)
            self._hk_buttons[name] = (b, note)
        self._hk_refresh()

    def _hk_refresh(self):
        """Hiện phím thực tế đang dùng nếu khác phím đã chọn (bị app khác chiếm)."""
        import hotkeys
        for name, (b, note) in getattr(self, "_hk_buttons", {}).items():
            if not b.winfo_exists():
                return
            if name == self._capture:
                continue
            want, got = settings.get("hk_" + name), hotkeys.ACTIVE.get(name)
            b.configure(text=hotkeys.pretty(want), highlightbackground=BTN)
            note.configure(text="" if name not in hotkeys.ACTIVE or got == want
                           else T("bị app khác dùng – đang dùng {k}", k=hotkeys.pretty(got)))

    def _start_capture(self, name):
        if self._capture:
            self._end_capture(refresh=False)
        b, note = self._hk_buttons[name]
        self._capture = name
        b.configure(text=T("Nhấn tổ hợp phím…"), highlightbackground=self.d.ACCENT)
        note.configure(text="")
        self.win.focus_force()
        self.win.bind("<KeyPress>", self._on_capture_key)

    def _on_capture_key(self, e):
        import hotkeys
        name = self._capture
        if not name:
            return
        b, note = self._hk_buttons[name]
        if e.keysym == "Escape":
            return self._end_capture()
        if e.keysym == "BackSpace":
            settings.set("hk_" + name, settings.DEFAULTS["hk_" + name])
            return self._end_capture()
        key = _VK.get(e.keycode)
        if key is None:                      # mới nhấn phím bổ trợ (Ctrl/Alt/Shift) – chờ phím chính
            return "break"
        mods = [m for m, bit in (("ctrl", 0x4), ("alt", 0x20000), ("shift", 0x1)) if e.state & bit]
        combo = "+".join(mods + [key])
        if not hotkeys.valid(combo):
            note.configure(text=T("Cần có Ctrl hoặc Alt"))
            return "break"
        clash = [n for n, _ in HOTKEYS if n != name and settings.get("hk_" + n) == combo]
        if clash:
            note.configure(text=T("Trùng với: {a}", a=T(dict(HOTKEYS)[clash[0]])))
            return "break"
        settings.set("hk_" + name, combo)
        return self._end_capture()

    def _end_capture(self, refresh=True):
        self._capture = None
        try:
            self.win.unbind("<KeyPress>")
        except tk.TclError:
            pass
        if refresh:
            self._hk_refresh()
            self.win.after(1200, self._hk_refresh)    # chờ luồng phím tắt đăng ký lại xong
        return "break"

    def _page_about(self):
        """Giới thiệu: phiên bản, bản quyền, developer, nguồn dữ liệu, giấy phép."""
        import webbrowser
        from version import __version__
        a, d = self.app, self.d
        hero = tk.Frame(self.inner, bg=d.PANEL2, padx=a.S(20), pady=a.S(18))
        hero.pack(fill="x", pady=(0, a.S(8)))
        try:
            tk.Label(hero, image=d.app_logo(a.root, a.S(72)), bg=d.PANEL2).pack(side="left", padx=(0, a.S(16)))
        except Exception:
            pass
        box = tk.Frame(hero, bg=d.PANEL2)
        box.pack(side="left")
        a.label(box, about.APP_NAME, 18, d.TEXT, True).pack(anchor="w")
        a.label(box, T("Phiên bản {v}", v=__version__) + "  ·  " + T("Gợi ý lõi và trang bị cho ARAM Hỗn Loạn"),
                9, d.MUTED).pack(anchor="w")
        a.label(box, about.COPYRIGHT, 9, d.TEXT).pack(anchor="w", pady=(a.S(6), 0))

        def link(parent, text, fn):
            lb = a.label(parent, text, 10, d.ACCENT, bg=CONTENT, cursor="hand2")
            lb.bind("<Button-1>", lambda e: fn())
            self._hover(lb, CONTENT, CONTENT, fg=(d.ACCENT, "#9cc6ff"))
            return lb

        self._section(T("Liên hệ"))
        link(self._row(T("Developer")), about.DEVELOPER, lambda: webbrowser.open(about.DEVELOPER_URL)).pack()
        link(self._row(T("Email")), about.EMAIL, lambda: webbrowser.open("mailto:" + about.EMAIL)).pack()

        self._section(T("Hỗ trợ"))
        self._btn(self._row(T("Tạo gói báo lỗi"), T("Gom log + ảnh chẩn đoán vào 1 file zip để đính kèm khi báo lỗi")),
                  "🧰 " + T("Tạo gói"), self._bug_report, primary=True).pack()
        self._btn(self._row(T("Báo lỗi / góp ý"), T("Mở mẫu báo lỗi trên GitHub Issues.")), T("Mở"),
                  lambda: webbrowser.open(about.ISSUES_URL + "/new/choose")).pack()
        self._btn(self._row(T("Trang dự án")), T("Mở"), lambda: webbrowser.open(about.REPO_URL)).pack()
        self._btn(self._row(T("Giấy phép")), T("Xem"), lambda: self._show_file("LICENSE", T("Giấy phép"))).pack()
        self._btn(self._row(T("Thành phần mã nguồn mở")), T("Xem"),
                  lambda: self._show_file("THIRD_PARTY_NOTICES.md", T("Thành phần mã nguồn mở"))).pack()

        self._section(T("Nguồn dữ liệu"))
        for name, url, what in about.DATA_SOURCES:
            link(self._row(name, T(what)), "↗", lambda u=url: webbrowser.open(u)).pack()
        a.label(self.inner, about.RIOT_DISCLAIMER, 8, d.DIMTEXT, bg=CONTENT, wraplength=self.body_w,
                justify="left").pack(anchor="w", pady=(a.S(16), 0))

    def _bug_report(self, confirm: bool = True):
        """Tạo gói báo lỗi (zip) ra Desktop; hỏi trước vì có ảnh màn hình game lúc chọn lõi."""
        from tkinter import messagebox
        import report
        if confirm and not messagebox.askokcancel(
                T("Tạo gói báo lỗi"),
                T("Gói gồm: log của app, tối đa 12 ảnh chẩn đoán gần nhất (ảnh màn hình game lúc chọn lõi), vị trí "
                  "bảng lõi, cài đặt và thông tin hệ thống.\n\nĐường dẫn thư mục máy và địa chỉ IP được che."
                  "\n\nTạo file zip ra Desktop?"), parent=self.win):
            return None
        try:
            hub = getattr(self.app, "hub", None)
            st = hub.state() if hub else {}
            scan = st.get("scan") or {}
            extra = {"in_game": (st.get("game") or {}).get("in_game"), "scan_status": scan.get("status"),
                     "scan_error": scan.get("error"), "calibrated": scan.get("calibrated")}
            path = report.make_bundle(extra=extra)
        except Exception as e:
            if confirm:
                messagebox.showerror(T("Tạo gói báo lỗi"), repr(e), parent=self.win)
            return None
        if confirm:
            report.reveal(path)
            self.app.toast(T("Đã tạo {f} – đính kèm file này khi báo lỗi.", f=path.name))
        return path

    def _show_file(self, name, title):
        """Xem LICENSE / THIRD_PARTY_NOTICES ngay trong app (file đi kèm bản cài)."""
        d, a = self.d, self.app
        try:
            text = (paths.RES / name).read_text(encoding="utf-8")
        except OSError:
            text = f"{name}: {about.REPO_URL}"
        w = tk.Toplevel(self.win)
        w.title(f"{about.APP_NAME} – {title}")
        w.configure(bg=d.BG)
        w.transient(self.win)
        t = tk.Text(w, bg=d.PANEL, fg=d.TEXT, font=a.f(9, mono=True), wrap="word", relief="flat",
                    padx=a.S(12), pady=a.S(10), width=96, height=30, highlightthickness=0)
        t.insert("1.0", text)
        t.configure(state="disabled")
        t.pack(fill="both", expand=True, padx=a.S(8), pady=a.S(8))
        a.button(w, T("Đóng"), w.destroy, 9, primary=True).pack(side="right", padx=a.S(8), pady=(0, a.S(8)))
        w.update_idletasks()
        x = self.win.winfo_rootx() + (self.win.winfo_width() - w.winfo_reqwidth()) // 2
        w.geometry(f"+{max(0, x)}+{max(0, self.win.winfo_rooty() - a.S(40))}")
        return w

# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
"""Điều khiển vẽ tay của hộp thoại Cài đặt: công tắc trượt có hiệu ứng (Switch) và thanh trượt (Slider).

Tách khỏi settings_ui.py (chỉ còn bố cục các trang). Ảnh công tắc / núm được dựng bằng Pillow ở độ phân giải gấp 4
rồi thu nhỏ – viền mượt, không răng cưa – và lưu lại theo cỡ + màu để dùng chung.
"""
from __future__ import annotations

import tkinter as tk

SW_OFF, KNOB = "#4a5168", "#ffffff"
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

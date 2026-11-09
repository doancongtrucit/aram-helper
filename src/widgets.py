# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
"""Widget dùng chung: tải ảnh nền (cache đĩa + RAM), vùng cuộn, tooltip."""
from __future__ import annotations

import hashlib
import queue
import threading
import tkinter as tk
import urllib.request
from tkinter import ttk

import playaram
from theme import BG, PANEL2, LINE, TEXT


IMG_DIR = playaram.CACHE_DIR / "img"
ICON_DIR = playaram.CACHE_DIR / "icons"


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
        w.title("ARAM Helper tooltip")
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

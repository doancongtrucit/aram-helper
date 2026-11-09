"""Overlay trên game: gọn, nền mờ, bấm được mà không cướp focus của game.

- Khung nhỏ (mặc định góc phải trên, kéo thanh tiêu đề để di chuyển – app nhớ vị trí):
  tướng, 3 lõi đang được đưa ra (xếp hạng, có icon), lõi đã chọn, build đồ chính.
  Nút ▾/▸ thu gọn còn 1 dòng, nút ✕ ẩn (phím tắt hoặc ô "Overlay" trong cửa sổ chính để hiện lại).
- Khi bảng chọn lõi hiện ra: nhãn nhỏ ngay trên từng thẻ lõi (★ = nên chọn).
- Bấm vào dòng gợi ý / nhãn trên thẻ = đánh dấu đã chọn lõi đó (giống phím Ctrl+Alt+1/2/3).
- Overlay bị loại khỏi ảnh chụp màn hình (SetWindowDisplayAffinity) để không làm nhiễu bộ quét lõi.

Chỉ vẽ lên màn hình, không đọc/ghi bộ nhớ game, không gửi phím/chuột vào game.
Game phải ở chế độ Không viền (Borderless) hoặc Cửa sổ thì overlay mới nằm trên được.
"""
from __future__ import annotations

import ctypes
import json
import os
import time
import tkinter as tk
from tkinter import font as tkfont

from advice import TIER_BONUS
from hotkeys import label

KEY = "#010203"                 # màu "trong suốt" (góc bo tròn)
BG = "#0d111c"
BG_HOVER = "#1b2236"
LINE = "#2a3147"
TEXT = "#eef0f6"
MUTED = "#8c93aa"
GOOD = "#3ddc97"
GOOD_BG = "#123a2a"
OK = "#f5a53a"
TIER_COLOR = {"S+": "#ff8a5c", "S": "#ff8a5c", "A": "#f5c451", "B": "#6aa8ff", "C": MUTED, "D": MUTED}
FONT = "Segoe UI"
PANEL_ALPHA = 0.86              # nền mờ: nhìn xuyên được game nhưng chữ vẫn rõ
BADGE_ALPHA = 0.92
SHOW_IN_CAPTURE = os.environ.get("ARAM_OVERLAY_IN_CAPTURE") == "1"   # chỉ để thử nghiệm
PREFS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "overlay.json")


def _dpi_aware():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass


class Overlay:
    def __init__(self, hub, scanner, root: tk.Tk):
        """root: cửa sổ chính của app – overlay dùng chung vòng lặp giao diện, chỉ thêm 2 cửa sổ con."""
        from desktop import Images
        self.hub, self.scanner, self.root = hub, scanner, root
        _dpi_aware()
        user32 = ctypes.windll.user32
        self.W, self.H = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        self.k = root.winfo_fpixels("1i") / 96.0
        self.img = Images(root, self.k)
        self.img.listeners.append(self._redraw)
        self.prefs = self._load_prefs()
        self.collapsed = bool(self.prefs.get("collapsed"))
        self.visible = True
        self._toggle_req = False
        self._sig = None
        self._last_top = 0.0
        self._fonts: dict = {}
        self._drag = None
        self._d = None
        # 2 cửa sổ nhỏ vừa khít nội dung: khung (panel) + dải nhãn trên thẻ lõi (badges)
        self.layers = []
        for alpha in (PANEL_ALPHA, BADGE_ALPHA):
            win = tk.Toplevel(root)
            win.title("ARAM Helper overlay")
            win.overrideredirect(True)
            win.configure(bg=KEY)
            cv = tk.Canvas(win, width=1, height=1, bg=KEY, highlightthickness=0, bd=0)
            cv.pack()
            win.geometry("1x1+0+0")
            win.update_idletasks()
            self._style_window(win, alpha)
            win.withdraw()
            self.layers.append((win, cv))
        (self.panel, self.pcv), (self.bwin, self.bcv) = self.layers

    # ---------- tiện ích ----------
    def S(self, px) -> int:
        return int(round(px * self.k))

    def _load_prefs(self) -> dict:
        try:
            with open(PREFS, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_prefs(self):
        try:
            os.makedirs(os.path.dirname(PREFS), exist_ok=True)
            with open(PREFS, "w", encoding="utf-8") as f:
                json.dump(self.prefs, f)
        except Exception:
            pass

    @staticmethod
    def _style_window(win, alpha):
        """Luôn nằm trên, không hiện trên taskbar, bấm vào không cướp focus của game, không lọt vào ảnh chụp."""
        user32 = ctypes.windll.user32
        hwnd = user32.GetParent(win.winfo_id()) or win.winfo_id()
        GWL_EXSTYLE = -20
        WS_EX_LAYERED, WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE, WS_EX_TOPMOST = 0x80000, 0x80, 0x08000000, 0x8
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_TOPMOST)
        win.attributes("-transparentcolor", KEY)
        win.attributes("-alpha", alpha)
        win.attributes("-topmost", True)
        if not SHOW_IN_CAPTURE:
            try:
                user32.SetWindowDisplayAffinity(hwnd, 0x11)   # WDA_EXCLUDEFROMCAPTURE (Win10 2004+)
            except Exception:
                pass

    def _font(self, size, bold=False):
        key = (size, bold)
        if key not in self._fonts:
            self._fonts[key] = tkfont.Font(family=FONT, size=size, weight="bold" if bold else "normal")
        return self._fonts[key]

    def _fit(self, text, width, size, bold=False):
        f = self._font(size, bold)
        if f.measure(text) <= width:
            return text
        while text and f.measure(text + "…") > width:
            text = text[:-1]
        return text.rstrip() + "…"

    def _round_rect(self, cv, x0, y0, x1, y1, r, **kw):
        pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1, x1 - r, y1,
               x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
        return cv.create_polygon(pts, smooth=True, **kw)

    def _text(self, cv, x, y, s, size=10, color=TEXT, bold=False, anchor="nw", **kw):
        return cv.create_text(x, y, text=s, fill=color, anchor=anchor, font=self._font(size, bold), **kw)

    def _image(self, cv, x, y, src, size, anchor="nw", **kw):
        ph = self.img.photo(src, size)
        if ph is None:                     # chưa tải xong: ô trống, tải xong sẽ vẽ lại
            p = self.S(size)
            return cv.create_rectangle(x, y, x + p, y + p, fill="#000000", outline="", **kw) if anchor == "nw" else None
        return cv.create_image(x, y, image=ph, anchor=anchor, **kw)

    def _hover(self, cv, tag, rect, normal, hover):
        cv.tag_bind(tag, "<Enter>", lambda e: (cv.itemconfigure(rect, fill=hover), cv.configure(cursor="hand2")))
        cv.tag_bind(tag, "<Leave>", lambda e: (cv.itemconfigure(rect, fill=normal), cv.configure(cursor="")))

    # ---------- điều khiển ----------
    def toggle(self):            # gọi từ luồng phím tắt
        self._toggle_req = True

    def set_visible(self, on: bool):
        if on != self.visible:
            self._toggle_req = True

    def start(self):
        self.root.after(200, self._tick)

    def _redraw(self):
        self._sig = None

    def _pick(self, aug_id):
        slug = self.hub.slug()
        if slug and aug_id:
            self.hub.update_owned(slug, add=aug_id)
            if self.scanner:
                self.scanner.mark_hidden()
            self._sig = None

    def _set_collapsed(self, v):
        self.collapsed = v
        self.prefs["collapsed"] = v
        self._save_prefs()
        self._sig = None

    def _hide(self):
        self.visible = False
        for win, _ in self.layers:
            win.withdraw()
        self._sig = None

    # kéo thanh tiêu đề để di chuyển khung
    def _drag_start(self, e):
        self._drag = (e.x_root - self.panel.winfo_x(), e.y_root - self.panel.winfo_y())

    def _drag_move(self, e):
        if self._drag:
            x, y = e.x_root - self._drag[0], e.y_root - self._drag[1]
            self.panel.geometry(f"+{x}+{y}")

    def _drag_end(self, e):
        if self._drag:
            self._drag = None
            self.prefs["x"], self.prefs["y"] = self.panel.winfo_x(), self.panel.winfo_y()
            self._save_prefs()

    # ---------- vòng cập nhật ----------
    def _gather(self) -> dict | None:
        st = self.hub.state()
        game, champ, scan = st["game"], st["champion"], st.get("scan") or {}
        if not (game.get("in_game") or os.environ.get("ARAM_FAKE_SCREEN")):
            return None
        return {"champ": champ, "scan": scan, "advice": st.get("advice"), "owned": st.get("owned", []),
                "calib": scan.get("calibration")}

    def _tick(self):
        try:
            if self._toggle_req:
                self._toggle_req = False
                if self.visible:
                    self._hide()
                else:
                    self.visible = True
                    self._sig = None
            if self.visible and not self._drag:
                d = self._gather()
                sig = repr(self._signature(d)) + repr(self.collapsed)
                if sig != self._sig:
                    self._sig = sig
                    self._d = d
                    self._draw(d)
                if time.time() - self._last_top > 3:      # game có thể đẩy cửa sổ khác xuống
                    for win, _ in self.layers:
                        if win.state() != "withdrawn":
                            win.attributes("-topmost", True)
                            win.lift()
                    self._last_top = time.time()
        except Exception as e:  # không để overlay chết vì một lỗi vẽ
            print("overlay:", repr(e))
        self.root.after(400, self._tick)

    @staticmethod
    def _signature(d):
        if not d:
            return None
        champ = d["champ"] or {}
        adv = [(a["slot"], a["rank"], [c["id"] for c in a["candidates"]]) for a in (d["advice"] or [])]
        sc = d["scan"]
        return (champ.get("slug"), champ.get("fetched_at"), sc.get("status"), sc.get("error"), sc.get("calibrated"),
                adv, tuple(d["owned"]), repr(d["calib"]))

    def _draw(self, d):
        for _, cv in self.layers:
            cv.delete("all")
        if not d:
            for win, _ in self.layers:
                win.withdraw()
            return
        self._draw_panel(d)
        if d["advice"] and d["calib"]:
            self._draw_badges(d)
            self._shrink_wrap(self.bwin, self.bcv)
        else:
            self.bwin.withdraw()

    # ---------- khung chính ----------
    def _draw_panel(self, d):
        cv, S = self.pcv, self.S
        champ, scan, adv = d["champ"] or {}, d["scan"], d["advice"] or []
        W, pad = S(272), S(10)
        x, right = pad, W - pad
        y = 0

        # Thanh tiêu đề (kéo để di chuyển)
        hh = S(34)
        head_bg = self._round_rect(cv, 0, 0, W, hh, S(10), fill=BG, outline="", tags=("head",))
        dot_col = GOOD if adv else (OK if scan.get("error") or not scan.get("calibrated") else MUTED)
        cv.create_oval(x, hh / 2 - S(4), x + S(8), hh / 2 + S(4), fill=dot_col, outline="", tags=("head",))
        name = champ.get("name") or "ARAM Helper"
        tier = champ.get("tier", "")
        t = self._text(cv, x + S(16), hh / 2, self._fit(name, S(130), 11, True), 11, TEXT, True, anchor="w", tags=("head",))
        tx = cv.bbox(t)[2] + S(6)
        if tier:
            self._text(cv, tx, hh / 2, tier, 10, TIER_COLOR.get(tier, OK), True, anchor="w", tags=("head",))
        if champ.get("winrate"):
            self._text(cv, right - S(46), hh / 2, f"{champ['winrate']:.1f}%", 9, MUTED, anchor="e", tags=("head",))
        for tag in ("head",):
            cv.tag_bind(tag, "<ButtonPress-1>", self._drag_start)
            cv.tag_bind(tag, "<B1-Motion>", self._drag_move)
            cv.tag_bind(tag, "<ButtonRelease-1>", self._drag_end)
            cv.tag_bind(tag, "<Enter>", lambda e: cv.configure(cursor="fleur"))
            cv.tag_bind(tag, "<Leave>", lambda e: cv.configure(cursor=""))
        # nút thu gọn / ẩn
        for i, (sym, fn, tip) in enumerate((("▸" if self.collapsed else "▾", lambda: self._set_collapsed(not self.collapsed), "col"),
                                            ("✕", self._hide, "hide"))):
            bx = right - S(36) + i * S(20)
            r = cv.create_rectangle(bx - S(2), hh / 2 - S(9), bx + S(16), hh / 2 + S(9), fill=BG, outline="", tags=(tip,))
            self._text(cv, bx + S(7), hh / 2, sym, 10, MUTED, anchor="center", tags=(tip,))
            self._hover(cv, tip, r, BG, BG_HOVER)
            cv.tag_bind(tip, "<Button-1>", lambda e, fn=fn: fn())
        y = hh

        body_items_start = y
        if self.collapsed:
            if adv:
                best = min(adv, key=lambda a: a["rank"])
                y = self._row(cv, y, W, best, compact=True)
        else:
            if adv:
                y = self._section(cv, y, "GỢI Ý – bấm để đánh dấu đã chọn")
                for a in sorted(adv, key=lambda a: a["rank"]):
                    y = self._row(cv, y, W, a)
                y += S(2)
            elif scan.get("error") or not scan.get("calibrated"):
                msg = scan.get("error") or f"Chưa hiệu chỉnh: khi bảng chọn lõi hiện ra, bấm {label('calibrate')}."
                t = self._text(cv, x, y + S(6), msg, 8, OK, width=W - 2 * pad)
                y = cv.bbox(t)[3] + S(6)

            if d["owned"]:
                y = self._section(cv, y, "ĐÃ CHỌN")
                ix = x
                for i in d["owned"][:9]:
                    self._image(cv, ix, y, i, 22)
                    ix += S(26)
                names = ", ".join(self._aug_name(i, champ) for i in d["owned"])
                t = self._text(cv, x, y + S(26), names, 8, MUTED, width=W - 2 * pad)
                y = cv.bbox(t)[3] + S(6)

            builds = champ.get("builds") or []
            if builds:
                b = builds[0]
                y = self._section(cv, y, f"BUILD · thắng {b.get('winrate', '?')}%")
                ix = x
                for it in b.get("items", [])[:6] + b.get("boots", [])[:1]:
                    size = 28 if it.get("core") else 24
                    if it.get("core"):
                        cv.create_rectangle(ix - S(1), y - S(1), ix + S(size) + S(1), y + S(size) + S(1), outline=GOOD, width=S(2))
                    self._image(cv, ix, y + (0 if it.get("core") else S(2)), it.get("icon"), size)
                    ix += S(size) + S(5)
                y += S(30)
                core = [i["name"] for i in b.get("items", []) if i.get("core")]
                if core:
                    t = self._text(cv, x, y, " → ".join(core), 8, GOOD, True, width=W - 2 * pad)
                    y = cv.bbox(t)[3] + S(6)
        # nền thân (nối liền dưới thanh tiêu đề), đặt dưới cùng để chữ nằm trên
        if y > body_items_start:
            y += S(4)
            body = self._round_rect(cv, 0, body_items_start - S(10), W, y, S(10), fill=BG, outline="")
            cv.create_line(S(8), body_items_start, W - S(8), body_items_start, fill=LINE)
            cv.tag_lower(head_bg)
            cv.tag_lower(body)
        else:
            y = hh
            cv.tag_lower(head_bg)

        cv.config(width=W, height=y)
        px = self.prefs.get("x", self.W - W - S(24))
        py = self.prefs.get("y", S(90))
        px = max(0, min(self.W - S(60), px))
        py = max(0, min(self.H - S(40), py))
        self.panel.geometry(f"{W}x{y}+{px}+{py}")
        if self.panel.state() == "withdrawn":
            self.panel.deiconify()

    def _section(self, cv, y, title):
        y += self.S(8)
        self._text(cv, self.S(10), y, title, 7, MUTED, True)
        return y + self.S(16)

    def _row(self, cv, y, W, a, compact=False):
        """1 dòng gợi ý: hạng, icon, tên, tỉ lệ thắng, +combo. Bấm = đánh dấu đã chọn."""
        S = self.S
        b, top = a["best"], a["rank"] == 1
        h = S(30)
        tag = f"row{a['slot']}"
        normal = GOOD_BG if top else BG
        r = cv.create_rectangle(S(4), y + S(1), W - S(4), y + h - S(1), fill=normal, outline="", tags=(tag,))
        self._text(cv, S(16), y + h / 2, "★" if top else str(a["rank"]), 10, GOOD if top else MUTED, True,
                   anchor="center", tags=(tag,))
        self._image(cv, S(28), y + h / 2, b["id"], 22, anchor="w", tags=(tag,))
        nm = b["name"] + (f" (1 trong {len(a['candidates'])})" if len(a["candidates"]) > 1 else "")
        self._text(cv, S(56), y + h / 2, self._fit(nm, S(130 if not compact else 120), 10, top), 10,
                   GOOD if top else TEXT, top, anchor="w", tags=(tag,))
        wr = "?" if b.get("winrate") is None else f"{b['winrate']:.1f}%" + ("*" if b.get("source") == "chung" else "")
        self._text(cv, W - S(12), y + h / 2 - (S(6) if b.get("fit") else 0), wr, 9, TEXT if not top else GOOD, True,
                   anchor="e", tags=(tag,))
        if b.get("fit"):
            self._text(cv, W - S(12), y + h / 2 + S(7), f"+{TIER_BONUS[b['fit']]} combo {b['fit']}", 7,
                       TIER_COLOR.get(b["fit"], MUTED), anchor="e", tags=(tag,))
        self._hover(cv, tag, r, normal, BG_HOVER)
        cv.tag_bind(tag, "<Button-1>", lambda e, i=b["id"]: self._pick(i))
        return y + h

    # ---------- nhãn trên thẻ lõi ----------
    def _draw_badges(self, d):
        cv, S = self.bcv, self.S
        calib = d["calib"]
        sx, sy = self.W / calib["width"], self.H / calib["height"]
        size = calib["size"] * sx
        for a in d["advice"]:
            i = a["slot"]
            if i >= len(calib["centers"]):
                continue
            cx, cy = calib["centers"][i][0] * sx, calib["centers"][i][1] * sy
            b, top = a["best"], a["rank"] == 1
            wr = "?" if b.get("winrate") is None else f"{b['winrate']:.1f}%"
            txt = f"★ {wr}" if top else f"#{a['rank']}  {wr}"
            sub = f"+{TIER_BONUS[b['fit']]} combo {b['fit']}" if b.get("fit") else ""
            if len(a["candidates"]) > 1:
                sub = (sub + " · " if sub else "") + f"1 trong {len(a['candidates'])}"
            w = max(S(96), self._font(11, True).measure(txt) + S(24), self._font(8).measure(sub) + S(20))
            h = S(40) if sub else S(26)
            bottom = cy - size * 0.68                 # ngay trên icon, ngoài vùng bộ quét đọc
            if bottom - h < S(4):
                bottom = cy + size * 0.68 + h
            y0 = bottom - h
            tag = f"badge{i}"
            fill = GOOD if top else BG
            rect = self._round_rect(cv, cx - w / 2, y0, cx + w / 2, bottom, S(9), fill=fill,
                                    outline=GOOD if top else LINE, width=1, tags=(tag,))
            fg = "#05261a" if top else TEXT
            self._text(cv, cx, y0 + S(4), txt, 11, fg, True, anchor="n", tags=(tag,))
            if sub:
                self._text(cv, cx, y0 + S(22), sub, 8, "#0b3d28" if top else MUTED, anchor="n", tags=(tag,))
            self._hover(cv, tag, rect, fill, "#5cf0b0" if top else BG_HOVER)
            cv.tag_bind(tag, "<Button-1>", lambda e, i=b["id"]: self._pick(i))

    @staticmethod
    def _shrink_wrap(win, cv):
        """Nội dung vẽ theo toạ độ màn hình; thu cửa sổ lại vừa khít nội dung rồi đặt đúng chỗ."""
        bb = cv.bbox("all")
        if not bb:
            win.withdraw()
            return
        x0, y0, x1, y1 = bb[0] - 2, bb[1] - 2, bb[2] + 2, bb[3] + 2
        cv.move("all", -x0, -y0)
        cv.config(width=x1 - x0, height=y1 - y0)
        win.geometry(f"{x1 - x0}x{y1 - y0}+{x0}+{y0}")
        if win.state() == "withdrawn":
            win.deiconify()

    def _aug_name(self, i, champ):
        for items in (champ.get("augments") or {}).values():
            for a in items:
                if a["id"] == i:
                    return a["name"]
        return self.hub.catalog().get(i, {}).get("name", f"#{i}")

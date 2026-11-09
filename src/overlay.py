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

import advice
import game_window
import paths
import settings
from advice import TIER_BONUS
from i18n import T

KEY = "#010203"                 # màu "trong suốt" (góc bo tròn)
BG = "#0d111c"
BG_HOVER = "#1b2236"
LINE = "#2a3147"
TEXT = "#eef0f6"
MUTED = "#8c93aa"
GOOD = "#3ddc97"
GOOD_BG = "#123a2a"
OK = "#f5a53a"
ACCENT = "#6aa8ff"
TIER_COLOR = {"S+": "#ff8a5c", "S": "#ff8a5c", "A": "#f5c451", "B": "#6aa8ff", "C": MUTED, "D": MUTED}
FONT = "Segoe UI"
SHOW_IN_CAPTURE = os.environ.get("ARAM_OVERLAY_IN_CAPTURE") == "1"   # chỉ để thử nghiệm
PREFS = str(paths.DATA / "overlay.json")


def _dpi_aware():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass


class Overlay:
    def __init__(self, hub, scanner, root: tk.Tk):
        """root: cửa sổ chính của app – overlay dùng chung vòng lặp giao diện, chỉ thêm 2 cửa sổ con."""
        from widgets import Images
        self.hub, self.scanner, self.root = hub, scanner, root
        _dpi_aware()
        self.dpi = root.winfo_fpixels("1i") / 96.0
        self.zoom = 1.0
        self.k = self.dpi
        self._fonts: dict = {}
        self.img = Images(root, self.k)
        self._apply_scale()
        self.img.listeners.append(self._redraw)
        self.prefs = self._load_prefs()
        self.collapsed = bool(self.prefs.get("collapsed"))
        self.visible = bool(settings.get("overlay"))
        self._toggle_req = False
        self._sig = None
        self._last_top = 0.0
        self._drag = None
        # 2 cửa sổ nhỏ vừa khít nội dung: khung (panel) + dải nhãn trên thẻ lõi (badges)
        self.layers = []
        for alpha in (settings.get("ov_opacity"), settings.get("ov_badge_opacity")):
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
        settings.on_change(lambda ch: root.after(0, self._on_settings, ch))

    # ---------- cài đặt ----------
    def _apply_scale(self):
        self.zoom = max(0.6, min(1.8, float(settings.get("ov_scale") or 1.0)))
        self.k = self.dpi * self.zoom
        self.img.scale = self.k
        self._fonts = {}

    def _on_settings(self, ch: dict):
        if "ov_opacity" in ch:
            self.panel.attributes("-alpha", max(0.2, min(1.0, float(ch["ov_opacity"]))))
        if "ov_badge_opacity" in ch:
            self.bwin.attributes("-alpha", max(0.2, min(1.0, float(ch["ov_badge_opacity"]))))
        if "ov_scale" in ch:
            self._apply_scale()
        if "overlay" in ch:
            self.set_visible(bool(ch["overlay"]))
        self._sig = None

    def reset_position(self):
        """Về góc phải trên, bỏ vị trí đã kéo."""
        self.prefs.pop("x", None)
        self.prefs.pop("y", None)
        self._save_prefs()
        settings.set("ov_corner", "top-right")
        self._sig = None

    def _position(self, W, H):
        """Góc chọn sẵn tính theo cửa sổ game; vị trí kéo thả giữ nguyên. Luôn nằm trong các màn hình."""
        corner = settings.get("ov_corner") or "custom"
        m = self.S(24)
        if corner == "custom" and "x" in self.prefs:
            px, py = self.prefs["x"], self.prefs["y"]
        else:
            gx, gy, gw, gh = game_window.rect()
            left = corner in ("top-left", "bottom-left")
            bottom = corner in ("bottom-right", "bottom-left")
            px = gx + (m if left else gw - W - m)
            py = gy + (gh - H - self.S(180) if bottom else self.S(90))
        vx, vy, vw, vh = game_window.virtual_screen()
        px = max(vx, min(vx + vw - self.S(60), px))
        py = max(vy, min(vy + vh - self.S(40), py))
        return int(px), int(py)

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
            self._fonts[key] = tkfont.Font(family=FONT, size=max(6, int(round(size * self.zoom))),
                                           weight="bold" if bold else "normal")
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
        if "width" in kw:
            kw["width"] = int(kw["width"])
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
            if settings.get("ov_corner") != "custom":
                settings.set("ov_corner", "custom")

    # ---------- vòng cập nhật ----------
    def _gather(self) -> dict | None:
        st = self.hub.state()
        game, champ, scan = st["game"], st["champion"], st.get("scan") or {}
        if not (game.get("in_game") or os.environ.get("ARAM_FAKE_SCREEN")):
            return None
        return {"champ": champ, "scan": scan, "advice": st.get("advice"), "owned": st.get("owned", []),
                "calib": scan.get("calibration"), "counter": st.get("counter") or []}

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
                sig = repr(self._signature(d)) + repr(self.collapsed) + repr(settings.all_values())
                if sig != self._sig:
                    self._sig = sig
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
                adv, tuple(d["owned"]), repr(d["calib"]), repr(d.get("counter")))

    def _draw(self, d):
        for _, cv in self.layers:
            cv.delete("all")
        if not d:
            for win, _ in self.layers:
                win.withdraw()
            return
        if settings.get("ov_only_offer") and not d["advice"]:
            self.panel.withdraw()
        else:
            self._draw_panel(d)
        if d["advice"] and d["calib"] and settings.get("ov_badges"):
            self._draw_badges(d)
            self._shrink_wrap(self.bwin, self.bcv)
        else:
            self.bwin.withdraw()

    # ---------- khung chính ----------
    def _draw_panel(self, d):
        cv, S = self.pcv, self.S
        champ, scan, adv = d["champ"] or {}, d["scan"], d["advice"] or []
        W, pad = S(int(settings.get("ov_width") or 272)), S(10)

        def show(k):
            return bool(settings.get("ov_show_" + k))
        x, right = pad, W - pad
        y = 0

        # Thanh tiêu đề (kéo để di chuyển)
        hh = S(34)
        head_bg = self._round_rect(cv, 0, 0, W, hh, S(10), fill=BG, outline="", tags=("head",))
        dot_col = GOOD if adv else (OK if scan.get("error") else MUTED)
        try:
            from theme import app_logo
            self._logo = app_logo(self.root, S(20))
            cv.create_image(x - S(2), hh / 2, image=self._logo, anchor="w", tags=("head",))
            x += S(22)
        except Exception:
            pass
        cv.create_oval(x, hh / 2 - S(4), x + S(8), hh / 2 + S(4), fill=dot_col, outline="", tags=("head",))
        name = champ.get("name") or "ARAM Helper"
        tier = champ.get("tier", "")
        t = self._text(cv, x + S(16), hh / 2, self._fit(name, W - x - S(132), 11, True), 11, TEXT, True, anchor="w", tags=("head",))
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
            if adv and show("offer"):
                best = min(adv, key=lambda a: a["rank"])
                y = self._row(cv, y, W, best, compact=True)
        else:
            if adv and show("offer"):
                y = self._section(cv, y, T("GỢI Ý – bấm để đánh dấu đã chọn"))
                for a in sorted(adv, key=lambda a: a["rank"]):
                    y = self._row(cv, y, W, a)
                y += S(2)
                # Cặp combo liên quan tới các lõi đang được đưa ra (ưu tiên combo hoàn thành với lõi đã có)
                offered = [c["id"] for a in adv for c in a["candidates"]]
                combos = advice.offer_combos(champ, offered, set(d["owned"]), limit=3) if show("combo") else []
                if combos:
                    y = self._section(cv, y, T("COMBO – viền xanh: đang được đưa ra · viền lam: đã có"))
                    for cb in combos:
                        y = self._combo_row(cv, y, W, cb)
            elif not adv and scan.get("error"):
                msg = scan.get("error")
                t = self._text(cv, x, y + S(6), msg, 8, OK, width=W - 2 * pad)
                y = cv.bbox(t)[3] + S(6)

            if d["owned"] and show("owned"):
                y = self._section(cv, y, T("ĐÃ CHỌN"))
                ix = x
                for i in d["owned"][:max(1, (W - 2 * pad) // S(26))]:
                    self._image(cv, ix, y, i, 22)
                    ix += S(26)
                names = ", ".join(self._aug_name(i, champ) for i in d["owned"])
                t = self._text(cv, x, y + S(26), names, 8, MUTED, width=W - 2 * pad)
                y = cv.bbox(t)[3] + S(6)

            builds = (champ.get("builds") or [])[:int(settings.get("ov_builds") or 3)] if show("build") else []
            if builds:
                y = self._section(cv, y, T("LỐI LÊN ĐỒ – viền xanh: món cốt lõi"))
                for b in builds:
                    y = self._build_row(cv, y, W, b)

            # 2 dòng cuối: đồ nên lên theo đội hình + trang bị của đội địch
            if d.get("counter") and show("counter"):
                y = self._section(cv, y, T("THEO ĐỘI ĐỊCH"))
                for line in d["counter"][:2]:
                    y = self._counter_row(cv, y, W, line)
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
        px, py = self._position(W, y)
        self.panel.geometry(f"{W}x{y}+{px}+{py}")
        if self.panel.state() == "withdrawn":
            self.panel.deiconify()

    def _combo_row(self, cv, y, W, cb):
        """1 combo: hạng, icon các lõi (viền xanh = đang được đưa ra, viền lam = đã có), tên rút gọn."""
        S = self.S
        x = S(10)
        self._text(cv, x, y + S(11), cb["tier"], 9, TIER_COLOR.get(cb["tier"], MUTED), True, anchor="w")
        ix = x + S(20)
        for k, a in enumerate(cb["augments"]):
            if k:
                self._text(cv, ix + S(1), y + S(11), "+", 8, MUTED, anchor="w")
                ix += S(10)
            edge = GOOD if a["offered"] else ACCENT if a["owned"] else None
            if edge:
                cv.create_rectangle(ix - S(1), y, ix + S(21), y + S(22), outline=edge, width=S(2))
            self._image(cv, ix, y + S(1), a["id"], 20)
            ix += S(24)
        if cb["owned_count"]:
            self._text(cv, W - S(10), y + S(11), T("có {n}/{m}", n=cb["owned_count"], m=len(cb["augments"])), 8, ACCENT, True, anchor="e")
        names = " + ".join(a["name"] for a in cb["augments"])
        self._text(cv, x + S(20), y + S(25), self._fit(names, W - S(40), 8), 8, MUTED)
        return y + S(42)

    def _build_row(self, cv, y, W, b):
        """1 lối lên đồ: tên ngắn, rồi icon 5–6 món + giày (món cốt lõi viền xanh)."""
        S = self.S
        x = S(10)
        self._text(cv, x, y, self._fit(b.get("name", ""), W - S(20), 8, True), 8, TEXT, True)
        y += S(16)
        ix = x
        for it in b.get("items", [])[:6] + b.get("boots", [])[:1]:
            size = 24 if it.get("core") else 22
            if it.get("core"):
                cv.create_rectangle(ix - S(1), y - S(1), ix + S(size) + S(1), y + S(size) + S(1), outline=GOOD, width=S(2))
            self._image(cv, ix, y + (0 if it.get("core") else S(1)), it.get("icon"), size)
            ix += S(size) + S(5)
        return y + S(30)

    def _counter_row(self, cv, y, W, line):
        """1 dòng: icon món + tên món (đậm) + lý do ngắn; dòng tóm tắt đội địch thì chỉ có chữ."""
        S = self.S
        x = S(10)
        if line.get("icon"):
            cv.create_rectangle(x - S(1), y - S(1), x + S(21), y + S(21), outline=OK, width=S(1))
            self._image(cv, x, y, line["icon"], 20)
            name = self._fit(line["name"], S(120), 9, True)
            t = self._text(cv, x + S(28), y + S(10), name, 9, OK, True, anchor="w")
            wx = cv.bbox(t)[2] + S(6)
            self._text(cv, wx, y + S(10), self._fit(line["why"], W - S(10) - wx, 8), 8, MUTED, anchor="w")
        else:
            self._text(cv, x, y + S(10), self._fit(line["why"], W - S(20), 8), 8, MUTED, anchor="w")
        return y + S(26)

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
        nm = b["name"] + (" (" + T("1 trong {n}", n=len(a["candidates"])) + ")" if len(a["candidates"]) > 1 else "")
        self._text(cv, S(56), y + h / 2, self._fit(nm, W - S(142 if not compact else 152), 10, top), 10,
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
        gx, gy, gw, gh = game_window.rect()          # nhãn bám theo cửa sổ game (kể cả ở màn hình phụ)
        sx, sy = gw / calib["width"], gh / calib["height"]
        size = calib["size"] * sx
        for a in d["advice"]:
            i = a["slot"]
            if i >= len(calib["centers"]):
                continue
            cx, cy = gx + calib["centers"][i][0] * sx, gy + calib["centers"][i][1] * sy
            b, top = a["best"], a["rank"] == 1
            wr = "?" if b.get("winrate") is None else f"{b['winrate']:.1f}%"
            txt = f"★ {wr}" if top else f"#{a['rank']}  {wr}"
            sub = f"+{TIER_BONUS[b['fit']]} combo {b['fit']}" if b.get("fit") else ""
            if len(a["candidates"]) > 1:
                sub = (sub + " · " if sub else "") + T("1 trong {n}", n=len(a["candidates"]))
            w = max(S(96), self._font(11, True).measure(txt) + S(24), self._font(8).measure(sub) + S(20))
            h = S(40) if sub else S(26)
            bottom = cy - size * 0.68                 # ngay trên icon, ngoài vùng bộ quét đọc
            if bottom - h < gy + S(4):
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

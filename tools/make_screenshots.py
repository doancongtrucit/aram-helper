# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
"""Tạo ảnh minh hoạ cho docs/USER_GUIDE.md (Windows).

Dùng dữ liệu mẫu (tests/fixture_*.html) và một màn chọn lõi giả lập – không chụp màn hình thật của máy.
Chạy:  python tests/fetch_fixtures.py   (nếu chưa có)
       python tools/make_screenshots.py
Ảnh lưu vào docs/images/.
"""
import ctypes
import ctypes.wintypes as wt
import os
import sys
import time
from pathlib import Path

os.environ["OPENBLAS_NUM_THREADS"] = "1"
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
ctypes.windll.shcore.SetProcessDpiAwareness(2)

import numpy as np  # noqa: E402
import tkinter as tk  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

import settings  # noqa: E402
import tempfile  # noqa: E402

# Ảnh hướng dẫn luôn dùng cài đặt mặc định (tiếng Việt, tự vừa cửa sổ), không đụng data/settings.json của máy
settings._reset_for_tests(Path(tempfile.mkdtemp()) / "settings.json")
import advice  # noqa: E402
import desktop  # noqa: E402
import theme  # noqa: E402
import overlay  # noqa: E402
import screen_scan as ss  # noqa: E402
from synthetic import make_screen  # noqa: E402
from test_desktop import CATALOG, CHAMP, FakeHub  # noqa: E402

OUT = ROOT / "docs" / "images"
OUT.mkdir(parents=True, exist_ok=True)
CHAMP["fetched_at"] = time.time() - 600
OFFER = [[1018], [3048], [1134]]          # Khổng Nhân Can Đảm, Bầy Ong Nảy Bật, Rút Kiếm Ra
OWNED = [1058]                            # Cú Đấm Thần Bí
FONT = "C:/Windows/Fonts/segoeuib.ttf"

# Đội địch mẫu (Soraka, Aatrox, Vladimir, Lux, Malphite – Malphite đã lên Giáp Gai) → 2 dòng gợi ý đồ
import counter_items  # noqa: E402
import ddragon  # noqa: E402
_DD = ddragon.get()
_ENEMIES = [{"slug": s, "champion_name": s, "items": it} for s, it in
            (("soraka", []), ("aatrox", []), ("vladimir", []), ("lux", []), ("malphite", [3075]))]
COUNTER = counter_items.two_lines(CHAMP, _ENEMIES, _DD) if _DD else []


# ---------- chụp nội dung 1 cửa sổ (không lấy gì phía sau) ----------
def print_window(win) -> Image.Image:
    u, g = ctypes.windll.user32, ctypes.windll.gdi32
    u.GetParent.restype = wt.HWND
    hwnd = u.GetParent(win.winfo_id()) or win.winfo_id()
    r = wt.RECT()
    u.GetWindowRect(hwnd, ctypes.byref(r))
    w, h = r.right - r.left, r.bottom - r.top
    u.GetWindowDC.restype, u.GetWindowDC.argtypes = wt.HDC, [wt.HWND]
    g.CreateCompatibleDC.restype, g.CreateCompatibleDC.argtypes = wt.HDC, [wt.HDC]
    g.CreateCompatibleBitmap.restype = wt.HBITMAP
    g.CreateCompatibleBitmap.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int]
    g.SelectObject.argtypes = [wt.HDC, wt.HGDIOBJ]
    u.PrintWindow.argtypes = [wt.HWND, wt.HDC, wt.UINT]
    g.DeleteObject.argtypes, g.DeleteDC.argtypes = [wt.HGDIOBJ], [wt.HDC]
    u.ReleaseDC.argtypes = [wt.HWND, wt.HDC]
    g.GetDIBits.argtypes = [wt.HDC, wt.HBITMAP, wt.UINT, wt.UINT, ctypes.c_void_p, ctypes.c_void_p, wt.UINT]
    wdc = u.GetWindowDC(hwnd)
    mdc = g.CreateCompatibleDC(wdc)
    bmp = g.CreateCompatibleBitmap(wdc, w, h)
    g.SelectObject(mdc, bmp)
    u.PrintWindow(hwnd, mdc, 2)

    class BIH(ctypes.Structure):
        _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG), ("biPlanes", wt.WORD),
                    ("biBitCount", wt.WORD), ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                    ("a", wt.LONG), ("b", wt.LONG), ("c", wt.DWORD), ("d", wt.DWORD)]
    bi = BIH(ctypes.sizeof(BIH), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = np.empty((h, w, 4), np.uint8)
    g.GetDIBits(mdc, bmp, 0, h, buf.ctypes.data, ctypes.byref(bi), 0)
    g.DeleteObject(bmp)
    g.DeleteDC(mdc)
    u.ReleaseDC(hwnd, wdc)
    img = Image.fromarray(buf[..., [2, 1, 0]])
    img.info["origin"] = (r.left, r.top)
    return img


def wait(root, ms):
    root.after(ms, root.quit)
    root.mainloop()


def rel(widget, img):
    """Toạ độ widget trong ảnh chụp cửa sổ."""
    ox, oy = img.info["origin"]
    return widget.winfo_rootx() - ox, widget.winfo_rooty() - oy, widget.winfo_width(), widget.winfo_height()


def annotate(img: Image.Image, marks, scale=1.0) -> Image.Image:
    """Đánh số chú thích: marks = [(số, x, y)] – vòng tròn đỏ có số."""
    img = img.convert("RGB")
    d = ImageDraw.Draw(img)
    r = int(17 * scale)
    font = ImageFont.truetype(FONT, int(20 * scale))
    for n, x, y in marks:
        d.ellipse((x - r, y - r, x + r, y + r), fill=(239, 68, 68), outline=(255, 255, 255), width=max(2, int(3 * scale)))
        d.text((x, y), str(n), fill="white", font=font, anchor="mm")
    return img


def save(img: Image.Image, name: str, width: int = 1400):
    if img.width > width:
        img = img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)
    img.save(OUT / name, optimize=True)
    print("đã lưu", OUT / name, img.size)


# ---------- giả lập hub / scanner / overlay cho cửa sổ chính ----------
class Hub(FakeHub):
    offer = True
    calib = None

    def slug(self):
        return "yasuo"

    def state(self):
        s = super().state()
        s["advice"] = advice.rank_offer(OFFER, CHAMP, CATALOG, set(self.owned)) if self.offer else None
        hint = advice.reroll_hint(s["advice"], CHAMP, [True, True, True]) if s["advice"] else None
        for r in s["advice"] or []:
            r["reroll"] = r["slot"] == hint                      # minh hoạ gợi ý đổi lõi (↻)
        s["scan"] = {"status": "Đã thấy bảng chọn lõi.", "calibrated": True, "offer": {"visible": self.offer},
                     "calibration": self.calib}
        s["counter"] = COUNTER
        return s


class Dummy:
    visible = True

    def set_visible(self, v): pass
    def request_calibration(self, d=0): pass
    def mark_hidden(self): pass
    def reset_position(self): pass


def main_window_shots(root):
    hub = Hub()
    hub.owned = list(OWNED)
    hub.offer = False                         # mặc định cửa sổ chính không đổi khi đang chọn lõi
    win = tk.Toplevel(root)
    app = desktop.App(win, hub, Dummy(), Dummy())
    app._champs = [(s, n, theme.fold(n)) for s, n in (("yasuo", "Yasuo"), ("yone", "Yone"), ("yuumi", "Yuumi"),
                                                        ("masteryi", "Master Yi"), ("kayle", "Kayle"))]
    win.geometry("1500x900+20+20")
    for _ in range(4):
        app._poll()
        wait(root, 500)
    wait(root, 2500)                          # đợi tải icon
    app._full_sig = None
    app._poll()
    wait(root, 600)

    # 1) Tổng quan tab Lõi & trang bị: lõi bên trái, trang bị bên phải + chú thích
    img = print_window(win)
    first_card = app.cards[3048]["w"]
    section = first_card.master.master
    more_btn = [w for w in section.winfo_children()[0].winfo_children() if w.cget("text").startswith("Xem thêm")][0]
    items_head = app._right.inner.winfo_children()[1 if COUNTER else 0]
    settings_btn = app.settings_btn
    R = 20

    def after(w):          # ngay sau nội dung (theo bề rộng nội dung, không theo khung giãn)
        x, y, ww, hh = rel(w, img)
        return x + min(ww, w.winfo_reqwidth()) + R, y + hh // 2

    def before(w):
        x, y, ww, hh = rel(w, img)
        return x - R - 2, y + hh // 2

    def inside_right(w, frac=0.5):
        x, y, ww, hh = rel(w, img)
        return x + ww - R - 6, y + int(hh * frac)

    def below(w):          # ngay dưới phần tử (thanh trên chật, không đặt số đè lên nút)
        x, y, ww, hh = rel(w, img)
        return x + ww // 2, y + hh + R + 2

    pts = [(1, *below(app.chip)), (2, *inside_right(app.search_box)), (3, *below(settings_btn)),
           (4, *after(app.scan_lbl)), (5, *after(app.head.winfo_children()[1])), (6, *before(app.tabs)),
           (7, *before(more_btn)), (8, *rel(first_card, img)[:2]), (9, *after(items_head))]
    save(annotate(img, pts, 1.1), "main-window.png")

    # 2) Tab Combo lõi
    app._set_tab("combo")
    app._poll()
    wait(root, 1200)
    save(print_window(win), "combo.png")

    # 3) Tìm tướng nhanh: gõ vài chữ → danh sách chọn (↑ ↓ Enter)
    app._set_tab("aug")
    app._poll()
    wait(root, 600)
    app.search.focus_force()
    app.search_var.set("y")
    wait(root, 500)
    img = print_window(win)
    if app._popup is not None:
        pop = print_window(app._popup[0])
        ox, oy = img.info["origin"]
        px, py = pop.info["origin"]
        img.paste(pop, (px - ox, py - oy))
    save(img.crop((0, 0, img.width, int(img.height * 0.45))), "search-champion.png")

    # 4) Tìm lõi bằng tay
    app._hide_popup()
    app.search_var.set("bay ong, vu luc, nhanh")
    app._light_update()
    wait(root, 800)
    img = print_window(win)
    save(img.crop((0, 0, int(img.width * 0.62), int(img.height * 0.75))), "search.png")
    app.search_var.set("")
    win.focus_force()

    # 5) Cài đặt (2 thẻ Chung / Overlay) – hiện đường dẫn mẫu, không lộ thư mục thật của máy chụp
    import paths
    real_data, paths.DATA = paths.DATA, Path("%LOCALAPPDATA%") / "ARAM Helper"
    app.open_settings()
    dlg = app._settings_dlg
    for page, name in (("general", "settings.png"), ("overlay", "settings-overlay.png")):
        dlg._go(page)
        wait(root, 500)
        save(print_window(dlg.win), name, 900)
    dlg.close()
    paths.DATA = real_data
    win.destroy()


# ---------- overlay ghép lên màn chọn lõi giả lập ----------
def overlay_shots(root):
    W, H = ctypes.windll.user32.GetSystemMetrics(0), ctypes.windll.user32.GetSystemMetrics(1)
    cat = list(CATALOG.values())
    names = {a["id"]: a["name"] for a in cat}
    icons = ss.load_icons(cat)
    bg = make_screen(icons, [o[0] for o in OFFER], "prismatic", W, H, seed=3, names=names)
    bg = Image.fromarray(bg[..., ::-1])
    s = 128 * W / 1920
    gap, cy = int(W * 300 / 1920), int(H * 0.40)
    calib = {"width": W, "height": H, "size": int(s), "centers": [[W // 2 - gap, cy], [W // 2, cy], [W // 2 + gap, cy]]}

    # Màn chọn lõi giả lập chỉ phủ đúng vùng sẽ chụp (che màn hình thật ở vùng đó), overlay nằm trên
    from PIL import ImageGrab, ImageTk
    stage = tk.Toplevel(root)
    stage.overrideredirect(True)
    stage.withdraw()
    stage_label = tk.Label(stage, bd=0)
    stage_label.pack()
    stage.attributes("-topmost", True)
    photos = []

    def show_stage(box):
        x0, y0, x1, y1 = box
        ph = ImageTk.PhotoImage(bg.crop(box))
        photos.append(ph)
        stage_label.configure(image=ph)
        stage.geometry(f"{x1 - x0}x{y1 - y0}+{x0}+{y0}")
        stage.deiconify()
        stage.attributes("-topmost", True)

    def raise_overlay():
        """Ép 2 cửa sổ overlay lên trên màn nền (cả hai đều 'luôn trên cùng')."""
        u = ctypes.windll.user32
        u.GetParent.restype = wt.HWND
        u.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.UINT]
        for win, _ in ov.layers:
            hwnd = u.GetParent(win.winfo_id()) or win.winfo_id()
            u.SetWindowPos(hwnd, wt.HWND(-1), 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)   # TOPMOST, NOSIZE|NOMOVE|NOACTIVATE

    def screen_is_clean(img, box):
        """Chắc chắn ảnh chỉ có màn giả lập + overlay: dải mép trái của vùng chụp phải trùng ảnh nền."""
        x0, y0, x1, y1 = box
        a = np.asarray(img.crop((0, 0, 20, y1 - y0))).astype(int)
        b = np.asarray(bg.crop((x0, y0, x0 + 20, y1))).astype(int)
        return np.abs(a - b).mean() < 3

    hub = Hub()
    hub.owned = list(OWNED)
    hub.calib = calib
    overlay.PREFS = str(OUT / "_overlay_prefs.json")      # không đụng vị trí overlay thật
    overlay.SHOW_IN_CAPTURE = True                       # cho phép chụp overlay (chỉ trong script này)
    ov = overlay.Overlay(hub, Dummy(), root)
    ov.prefs = {"x": int(W * 0.70), "y": int(H * 0.12)}

    def draw(collapsed):
        """Vẽ overlay ngay (ép trạng thái thu gọn, không phụ thuộc chuột người dùng)."""
        ov.collapsed = collapsed
        ov._sig = None
        ov._draw(ov._gather())
        wait(root, 50)

    for collapsed, name in ((False, "overlay-ingame.png"), (True, "overlay-collapsed.png")):
        draw(collapsed)
        wait(root, 2000)                                 # đợi tải icon
        draw(collapsed)
        px, py, pw, ph = ov.panel.winfo_x(), ov.panel.winfo_y(), ov.panel.winfo_width(), ov.panel.winfo_height()
        if collapsed:
            box = (px - 30, py - 30, px + pw + 30, py + ph + 30)
        else:
            box = (calib["centers"][0][0] - int(2.2 * s), max(0, min(py, cy - int(1.6 * s)) - 40),
                   min(W, px + pw + 70), max(cy + int(2.8 * s), py + ph + 30))
        show_stage(box)
        wait(root, 200)
        draw(collapsed)                                  # vẽ lại ngay trước khi chụp
        raise_overlay()
        wait(root, 250)
        img = ImageGrab.grab(bbox=box)
        stage.withdraw()
        if not screen_is_clean(img, box):
            raise SystemExit("Ảnh chụp lẫn màn hình thật – dừng, không lưu.")
        if collapsed:
            save(img, name, 800)
        else:
            ox, oy = box[:2]
            # số chú thích nằm ngoài mép khung / nhãn để không che chữ
            marks = [(1, px - 26 - ox, py + int(17 * ov.k) - oy), (2, px - 26 - ox, py + int(80 * ov.k) - oy),
                     (3, calib["centers"][1][0] - int(0.95 * s) - ox, cy - int(1.0 * s) - oy),
                     (4, px + pw + 26 - ox, py + int(17 * ov.k) - oy)]
            save(annotate(img, marks, 1.4), name, 1500)
    for win, _ in ov.layers:
        win.destroy()
    stage.destroy()
    try:
        os.remove(overlay.PREFS)
    except OSError:
        pass


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    main_window_shots(root)
    overlay_shots(root)
    root.destroy()

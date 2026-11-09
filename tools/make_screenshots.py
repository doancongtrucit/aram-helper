"""Tạo ảnh minh hoạ cho HUONG_DAN.md (Windows).

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
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
ctypes.windll.shcore.SetProcessDpiAwareness(2)

import numpy as np  # noqa: E402
import tkinter as tk  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

import advice  # noqa: E402
import desktop  # noqa: E402
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
        s["scan"] = {"status": "Đã thấy bảng chọn lõi.", "calibrated": True, "offer": {"visible": self.offer},
                     "calibration": self.calib}
        return s


class Dummy:
    visible = True

    def set_visible(self, v): pass
    def request_calibration(self, d=0): pass
    def mark_hidden(self): pass


def main_window_shots(root):
    hub = Hub()
    hub.owned = list(OWNED)
    win = tk.Toplevel(root)
    app = desktop.App(win, hub, Dummy(), Dummy())
    win.geometry("1500x1100+20+20")
    for _ in range(4):
        app._poll()
        wait(root, 500)
    wait(root, 2500)                          # đợi tải icon
    app._poll()
    wait(root, 400)

    # 1) Tổng quan tab Lõi & trang bị (có ô Nên chọn) + chú thích
    img = print_window(win)
    first_card = app.cards[3048]["w"]
    section = first_card.master.master
    more_btn = [w for w in section.winfo_children()[0].winfo_children() if w.cget("text").startswith("Xem thêm")][0]
    # Số chú thích đặt vào chỗ trống cạnh từng phần, không đè lên chữ
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

    def top_mid(w):
        x, y, ww, hh = rel(w, img)
        return x + ww // 2, y

    pts = [(1, *after(app.status)), (2, *inside_right(app.search)), (3, *inside_right(app.pick, 0.5)),
           (4, *after(app.scan_lbl)), (5, *after(app.head)), (6, *after(app.tabs)),
           (7, *after(app.owned_bar)), (8, *top_mid(app.advice_box)), (9, *before(more_btn)),
           (10, *rel(first_card, img)[:2])]
    pts[2] = (3, pts[2][1] - 40, pts[2][2])          # tránh mũi tên của ô chọn tướng
    save(annotate(img, pts, 1.1), "main-window.png")

    # 2) Trang bị gợi ý
    target = [w for w in app.scroll.inner.winfo_children() if isinstance(w, tk.Label) and w.cget("text") == "Trang bị gợi ý"][0]
    total = app.scroll.inner.winfo_height()
    app.scroll.canvas.yview_moveto(max(0, (target.winfo_y() - 10) / total))
    wait(root, 400)
    img = print_window(win)
    save(img, "items.png")

    # 3) Tab Combo lõi
    app._set_tab("combo")
    app._poll()
    wait(root, 1200)
    save(print_window(win), "combo.png")

    # 4) Tìm lõi bằng tay
    hub.offer = False
    app._set_tab("aug")
    app._poll()
    app.search.event_generate("<FocusIn>")
    app.search_var.set("bay ong, vu luc, nhanh")
    app._light_update()
    wait(root, 800)
    img = print_window(win)
    save(img.crop((0, 0, img.width, int(img.height * 0.62))), "search.png")
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

    # Màn chọn lõi giả lập phủ toàn màn hình (che màn hình thật), overlay nằm trên, rồi chụp vùng cần
    from PIL import ImageGrab, ImageTk
    stage = tk.Toplevel(root)
    stage.overrideredirect(True)
    stage.geometry(f"{W}x{H}+0+0")
    photo = ImageTk.PhotoImage(bg)
    tk.Label(stage, image=photo, bd=0).pack()
    stage.attributes("-topmost", True)                   # che kín màn hình thật
    wait(root, 300)

    def raise_overlay():
        """Ép 2 cửa sổ overlay lên trên màn nền (cả hai đều 'luôn trên cùng')."""
        u = ctypes.windll.user32
        u.GetParent.restype = wt.HWND
        u.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.UINT]
        for win, _ in ov.layers:
            hwnd = u.GetParent(win.winfo_id()) or win.winfo_id()
            u.SetWindowPos(hwnd, wt.HWND(-1), 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)   # TOPMOST, NOSIZE|NOMOVE|NOACTIVATE

    def screen_is_clean(img):
        """Chắc chắn ảnh chỉ có màn giả lập + overlay: góc trái dưới phải trùng ảnh nền."""
        a = np.asarray(img.crop((0, H - 200, 300, H))).astype(int)
        b = np.asarray(bg.crop((0, H - 200, 300, H))).astype(int)
        return np.abs(a - b).mean() < 3

    hub = Hub()
    hub.owned = list(OWNED)
    hub.calib = calib
    overlay.PREFS = str(OUT / "_overlay_prefs.json")      # không đụng vị trí overlay thật
    overlay.SHOW_IN_CAPTURE = True                       # cho phép chụp overlay (chỉ trong script này)
    ov = overlay.Overlay(hub, Dummy(), root)
    ov.prefs = {"x": int(W * 0.70), "y": int(H * 0.12)}

    for collapsed, name in ((False, "overlay-ingame.png"), (True, "overlay-collapsed.png")):
        ov.collapsed = collapsed
        ov._sig = None
        for _ in range(3):
            ov._tick()
            ov._last_top = 0
            wait(root, 900)
        raise_overlay()
        wait(root, 400)
        img = ImageGrab.grab(bbox=(0, 0, W, H))
        if not screen_is_clean(img):
            raise SystemExit("Ảnh chụp lẫn màn hình thật – dừng, không lưu.")
        if collapsed:
            x, y = ov.panel.winfo_x(), ov.panel.winfo_y()
            img = img.crop((x - 30, y - 30, x + ov.panel.winfo_width() + 30, y + ov.panel.winfo_height() + 30))
            save(img, name, 800)
        else:
            x0 = calib["centers"][0][0] - int(2.2 * s)
            x1 = min(W, ov.panel.winfo_x() + ov.panel.winfo_width() + 70)
            y0 = max(0, min(ov.panel.winfo_y(), cy - int(1.6 * s)) - 40)
            y1 = cy + int(2.8 * s)
            pb = (ov.panel.winfo_x(), ov.panel.winfo_y(), ov.panel.winfo_width())
            # số chú thích nằm ngoài mép khung / nhãn để không che chữ
            marks = [(1, pb[0] - 26, pb[1] + int(17 * ov.k)), (2, pb[0] - 26, pb[1] + int(80 * ov.k)),
                     (3, calib["centers"][1][0] - int(0.95 * s), cy - int(1.0 * s)),
                     (4, pb[0] + pb[2] + 26, pb[1] + int(17 * ov.k))]
            img = annotate(img, marks, 1.4).crop((x0, y0, x1, y1))
            save(img, name, 1500)
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

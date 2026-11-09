"""ARAM Helper – ứng dụng máy tính gợi ý lõi ARAM Hỗn Loạn (Windows; macOS chỉ có cửa sổ chính).

Chạy: python app.py            (hoặc shortcut do install-windows.bat / install-macos.sh tạo)
      python app.py --no-overlay --champion yasuo

Phím tắt (cả khi đang trong game; nếu bị app khác chiếm thì tự dùng phím dự phòng, hiện trong app):
  Ctrl+Alt+A      hiệu chỉnh vị trí 3 ô lõi (dự phòng: Ctrl+Alt+K, Ctrl+Alt+Shift+A)
  Ctrl+Alt+1/2/3  đánh dấu đã chọn lõi ở ô 1/2/3 (dự phòng: Ctrl+Alt+Shift+1/2/3)
  Ctrl+Alt+O      ẩn / hiện overlay (dự phòng: Ctrl+Alt+Shift+O)
"""
from __future__ import annotations

import os

# Phải đặt trước khi bất kỳ module nào import numpy: tránh OpenBLAS giữ ~500 MB bộ nhớ cho các luồng thừa
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import sys  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402

import advice  # noqa: E402
import hotkeys  # noqa: E402
import live_client  # noqa: E402
import playaram  # noqa: E402

IS_WINDOWS = sys.platform == "win32"
if IS_WINDOWS:
    try:  # quét màn hình – cần opencv; thiếu thì app vẫn chạy (chỉ không tự đọc lõi)
        from scanner import Scanner
        SCANNER = Scanner()
        SCANNER_ERROR = None
    except Exception as _e:  # noqa: N816
        SCANNER = None
        SCANNER_ERROR = f"Không bật được quét màn hình ({_e}). Cài: pip install -r requirements.txt"
else:
    SCANNER = None
    SCANNER_ERROR = "Tự đọc lõi trên màn hình, overlay và phím tắt hiện chỉ có trên Windows."


class Hub:
    """Trạng thái dùng chung cho cửa sổ chính + overlay: trận hiện tại, tướng đang xem, lõi đã chọn."""

    def __init__(self, scanner=None):
        self.scanner = scanner
        self.lock = threading.Lock()
        self.game = {"in_game": False}
        self.champion = None
        self.focus_slug = None          # tướng chọn tay (ưu tiên hơn tướng trong trận cho tới khi bấm "Tự động")
        self.error = None
        self.owned: dict[str, list[int]] = {}
        self._catalog: dict[int, dict] | None = None
        self._wake = threading.Event()

    # ----- dữ liệu -----
    def catalog(self) -> dict[int, dict]:
        if self._catalog is None:
            try:
                self._catalog = {a["id"]: a for a in playaram.get_augment_catalog()}
            except Exception:
                return {}
        return self._catalog

    def refresh(self):
        game = live_client.current_game()
        game_slug = playaram.slugify(game["champion_raw"]) if game.get("champion_raw") else None
        slug = self.focus_slug or game_slug
        champ, err = None, None
        if slug:
            try:
                champ = playaram.get_champion(slug)
            except Exception as e:
                err = f"Không lấy được dữ liệu cho {slug}: {e}"
        with self.lock:
            if game.get("in_game") and not self.game.get("in_game") and game_slug:
                self.owned[game_slug] = []     # vừa vào trận mới: xoá lõi đã chọn của trận trước
            self.game, self.champion, self.error = game, champ, err

    def loop(self):
        while True:
            try:
                self.refresh()
            except Exception as e:
                self.error = str(e)
            self._wake.wait(1.5)
            self._wake.clear()

    def set_focus(self, slug: str | None):
        self.focus_slug = playaram.slugify(slug) if slug else None
        with self.lock:
            if not self.focus_slug or (self.champion or {}).get("slug") != self.focus_slug:
                self.champion = None if self.focus_slug else self.champion
        self._wake.set()                       # tải ngay, không đợi vòng 1,5 giây

    # ----- lõi đã chọn -----
    def slug(self) -> str | None:
        return (self.champion or {}).get("slug") or self.focus_slug

    def owned_ids(self, slug: str | None = None) -> list[int]:
        return list(self.owned.get(slug or self.slug() or "", []))

    def update_owned(self, slug: str, add=None, remove=None, toggle=None, clear=False) -> list[int]:
        with self.lock:
            cur = self.owned.setdefault(slug, [])
            if clear:
                cur.clear()
            if add is not None and add not in cur:
                cur.append(add)
            if remove is not None and remove in cur:
                cur.remove(remove)
            if toggle is not None:
                cur.remove(toggle) if toggle in cur else cur.append(toggle)
            return list(cur)

    def pick_slot(self, i: int):
        """Phím Ctrl+Alt+1/2/3: đánh dấu lõi ở ô i của bảng chọn đang hiện là đã chọn."""
        if not self.scanner:
            return
        offer = self.scanner.snapshot()["offer"] or {}
        slug = self.slug()
        if not offer.get("visible") or not offer.get("slots") or not slug or i >= len(offer["slots"]):
            return
        ranked = {r["slot"]: r for r in self.offer_advice(offer) or []}
        if i in ranked:
            self.update_owned(slug, add=ranked[i]["best"]["id"])
            self.scanner.mark_hidden()

    # ----- gợi ý -----
    def offer_advice(self, offer: dict | None):
        if not offer or not offer.get("slots") or not self.champion:
            return None
        slots = [s["candidates"] for s in offer["slots"]]
        return advice.rank_offer(slots, self.champion, self.catalog(), set(self.owned_ids()))

    def state(self) -> dict:
        scan = self.scanner.snapshot() if self.scanner else {"error": SCANNER_ERROR}
        with self.lock:
            out = {"game": self.game, "champion": self.champion, "error": self.error,
                   "owned": self.owned_ids(), "focus": self.focus_slug, "scan": scan}
        offer = scan.get("offer") or {}
        out["advice"] = self.offer_advice(offer) if offer.get("visible") else None
        return out


HUB = Hub(SCANNER)


def _setup_output():
    """Chạy bằng pythonw (không có cửa sổ dòng lệnh) thì ghi log ra data/app.log."""
    if sys.stdout is None or sys.stderr is None:
        playaram.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        log = open(playaram.CACHE_DIR / "app.log", "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stdout or log
        sys.stderr = sys.stderr or log
    else:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    print(f"--- ARAM Helper khởi động {time.strftime('%Y-%m-%d %H:%M:%S')}")


def main():
    _setup_output()
    import tkinter as tk
    if IS_WINDOWS:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)   # chữ/ảnh sắc nét trên màn hình DPI cao
        except Exception:
            pass
    import desktop

    if "--champion" in sys.argv[:-1]:                         # mở thẳng 1 tướng: --champion yasuo
        HUB.set_focus(sys.argv[sys.argv.index("--champion") + 1])
    threading.Thread(target=HUB.loop, daemon=True, name="hub").start()
    root = tk.Tk()

    overlay = None
    if IS_WINDOWS and "--no-overlay" not in sys.argv:
        try:
            import overlay as overlay_mod
            overlay = overlay_mod.Overlay(HUB, SCANNER, root)
        except Exception as e:
            print(f"Không bật được overlay: {e}")

    # Mỗi việc có phím dự phòng nếu app khác đã chiếm tổ hợp đầu
    keys = {f"pick{i + 1}": ([f"ctrl+alt+{i + 1}", f"ctrl+alt+shift+{i + 1}"], (lambda i=i: HUB.pick_slot(i)))
            for i in range(3)}
    if SCANNER:
        SCANNER.in_game_fn = lambda: HUB.game.get("in_game", False)   # dùng chung, không gọi Live API 2 lần
        SCANNER.start()
        keys["calibrate"] = (["ctrl+alt+a", "ctrl+alt+k", "ctrl+alt+shift+a"], lambda: SCANNER.request_calibration(0))
    else:
        print(SCANNER_ERROR)
    if overlay:
        keys["overlay"] = (["ctrl+alt+o", "ctrl+alt+shift+o"], overlay.toggle)
    if IS_WINDOWS:
        hotkeys.start(keys)
        print(f"Phím tắt: {hotkeys.label('calibrate')} hiệu chỉnh · {hotkeys.label('pick1')}/2/3 đánh dấu lõi đã chọn · "
              f"{hotkeys.label('overlay')} ẩn/hiện overlay")

    desktop.App(root, HUB, SCANNER, overlay)
    if overlay:
        overlay.start()
    root.mainloop()                     # đóng cửa sổ chính = thoát app (overlay, quét màn hình dừng theo)


if __name__ == "__main__":
    main()

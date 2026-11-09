"""ARAM Helper – ứng dụng máy tính gợi ý lõi ARAM Hỗn Loạn (Windows; macOS chỉ có cửa sổ chính).

Chạy từ mã nguồn: python app.py   (người dùng cài bản exe / .app từ GitHub Releases)
      python app.py --no-overlay --champion yasuo

Phím tắt (cả khi đang trong game; nếu bị app khác chiếm thì tự dùng phím dự phòng, hiện trong app):
  Ctrl+Alt+A      định vị lõi: tìm lại vị trí 3 thẻ lõi (dự phòng: Ctrl+Alt+K, Ctrl+Alt+Shift+A)
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
import counter_items  # noqa: E402
import ddragon  # noqa: E402
import hotkeys  # noqa: E402
import i18n  # noqa: E402
import localize  # noqa: E402
import settings  # noqa: E402
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
        self._dds: dict[str, dict] = {}     # Data Dragon theo ngôn ngữ (tải ở luồng nền)
        self._aug_names: dict[str, dict[int, str]] = {}   # tên lõi theo ngôn ngữ ("en")
        self._counter_key = None
        self._counter: list[dict] = []
        self._loc_key = None
        self._loc_champ = None
        settings.on_change(lambda ch: self._wake.set() if "lang" in ch else None)   # đổi ngôn ngữ: tải ngay

    # ----- dữ liệu -----
    def catalog(self) -> dict[int, dict]:
        """Danh mục lõi theo ngôn ngữ đang chọn (id → lõi)."""
        if self._catalog is None:
            try:
                self._catalog = {a["id"]: a for a in playaram.get_augment_catalog()}
            except Exception:
                return {}
        return localize.catalog(self._catalog, i18n.lang(), self._aug_names.get(i18n.lang(), {}))

    def dd(self) -> dict | None:
        return self._dds.get(i18n.ddragon_locale())

    def _load_lang_data(self, in_game: bool):
        """Ở luồng nền: Data Dragon (cần khi trong trận hoặc khi giao diện tiếng Anh) + tên lõi tiếng Anh."""
        loc, lang = i18n.ddragon_locale(), i18n.lang()
        if loc not in self._dds and (in_game or lang != "vi"):
            d = ddragon.get(loc)               # lần đầu ~0,5 s, sau đó đọc từ cache
            if d:
                self._dds[loc] = d
        if lang != "vi" and lang not in self._aug_names:
            try:
                self._aug_names[lang] = {a["id"]: a["name"] for a in playaram.get_augment_catalog(lang=lang)}
            except Exception:
                pass

    def champion_view(self) -> dict | None:
        """Dữ liệu tướng đã đổi sang ngôn ngữ đang chọn (lưu lại theo tướng + thời điểm tải + ngôn ngữ)."""
        champ, lang = self.champion, i18n.lang()
        key = (id(champ), (champ or {}).get("fetched_at"), lang, lang in self._aug_names, bool(self.dd()))
        if key != self._loc_key:
            self._loc_key = key
            self._loc_champ = localize.champion(champ, lang, self._aug_names.get(lang, {}), self.dd())
        return self._loc_champ

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
        self._load_lang_data(bool(game.get("in_game")))
        if game.get("in_game") and not self.game.get("in_game"):
            enemies = game.get("enemies") or []
            print(f"[{time.strftime('%H:%M:%S')}] vào trận: {game.get('champion_name')} · đội địch: "
                  + (", ".join(f"{e['slug']}({len(e['items'])} món)" for e in enemies)
                     if enemies else "KHÔNG đọc được (kiểm tra trường 'team' của Live API)"), flush=True)
        with self.lock:
            if game.get("in_game") and not self.game.get("in_game") and game_slug:
                self.owned[game_slug] = []     # vừa vào trận mới: xoá lõi đã chọn của trận trước
            self.game, self.champion, self.error = game, champ, err

    def counter(self) -> list[dict]:
        """2 dòng gợi ý đồ theo đội hình + trang bị địch (rỗng nếu không trong trận)."""
        g, champ, dd = self.game, self.champion_view(), self.dd()
        enemies = g.get("enemies") or []
        if not (g.get("in_game") and enemies and champ and dd):
            return []
        key = (champ.get("slug"), tuple((e["slug"], tuple(e["items"])) for e in enemies),
               tuple(g.get("my_items") or ()), i18n.lang())
        if key != self._counter_key:
            self._counter_key = key
            self._counter = counter_items.two_lines(champ, enemies, dd, g.get("my_items") or [])
        return self._counter

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
        return advice.rank_offer(slots, self.champion_view(), self.catalog(), set(self.owned_ids()))

    def state(self) -> dict:
        scan = self.scanner.snapshot() if self.scanner else {"error": SCANNER_ERROR}
        with self.lock:
            out = {"game": self.game, "champion": self.champion_view(), "error": self.error,
                   "owned": self.owned_ids(), "focus": self.focus_slug, "scan": scan}
        offer = scan.get("offer") or {}
        out["advice"] = self.offer_advice(offer) if offer.get("visible") else None
        out["counter"] = self.counter()
        return out


HUB = Hub(SCANNER)


def _setup_output():
    """Chạy bằng pythonw hoặc bản exe (không có cửa sổ dòng lệnh) thì ghi log ra app.log trong thư mục dữ liệu."""
    import paths
    if sys.stdout is None or sys.stderr is None or paths.FROZEN:
        playaram.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = playaram.CACHE_DIR / "app.log"
        try:                                   # dùng lâu dài: log quá 1 MB thì xoay vòng (giữ 1 bản cũ)
            if path.stat().st_size > 1_000_000:
                path.replace(path.with_suffix(".log.1"))
        except OSError:
            pass
        log = open(path, "a", encoding="utf-8", buffering=1)
        sys.stdout = log if paths.FROZEN else (sys.stdout or log)
        sys.stderr = log if paths.FROZEN else (sys.stderr or log)
    else:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    from version import __version__
    print(f"--- ARAM Helper {__version__} khởi động {time.strftime('%Y-%m-%d %H:%M:%S')}")


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
    def combos(name):
        return hotkeys.combos_for(name, settings.get("hk_" + name))

    keys = {f"pick{i + 1}": (combos(f"pick{i + 1}"), (lambda i=i: HUB.pick_slot(i))) for i in range(3)}
    if SCANNER:
        SCANNER.in_game_fn = lambda: HUB.game.get("in_game", False)   # dùng chung, không gọi Live API 2 lần
        SCANNER.start()
        keys["calibrate"] = (combos("calibrate"), lambda: SCANNER.request_calibration(0))
        keys["diagnose"] = (combos("diagnose"), SCANNER.request_diagnostic)
    else:
        print(SCANNER_ERROR)
    if overlay:
        keys["overlay"] = (combos("overlay"), overlay.toggle)
    if IS_WINDOWS:
        hotkeys.start(keys)

        def on_hotkey_change(changed):         # đổi phím trong Cài đặt → đăng ký lại ngay (luồng nền, không chặn UI)
            for k in changed:
                if k.startswith("hk_"):
                    name = k[3:]
                    threading.Thread(target=hotkeys.update, args=(name, combos(name)), daemon=True).start()
        settings.on_change(on_hotkey_change)
        print(f"Phím tắt: {hotkeys.label('calibrate')} định vị lõi · {hotkeys.label('pick1')}/2/3 đánh dấu lõi đã chọn · "
              f"{hotkeys.label('overlay')} ẩn/hiện overlay")

    import esp32_link
    if esp32_link.Esp32Link.enabled():          # data/esp32.json có thì đẩy màn ARAM lên ESP32 (bật/tắt trong Cài đặt)
        esp32_link.Esp32Link(HUB.state, log=print).start()
        print("ESP32: bật màn ARAM qua Wi-Fi.")

    desktop.App(root, HUB, SCANNER, overlay)
    if overlay:
        overlay.start()
    root.mainloop()                     # đóng cửa sổ chính = thoát app (overlay, quét màn hình dừng theo)


if __name__ == "__main__":
    main()

"""Luồng nền: khi đang trong trận và đã hiệu chỉnh, chụp màn hình mỗi giây để đọc 3 lõi đang được đưa ra.

Hiệu chỉnh: phím tắt toàn cục (mặc định Ctrl+Alt+A, xem app.py) khi đang hiện bảng chọn lõi trong game.
"""
from __future__ import annotations

import threading
import time
import traceback

import hotkeys
import live_client
import playaram
import screen_scan as ss

SCAN_INTERVAL = 1.0
MISS_TO_HIDE = 2          # số lần quét liên tiếp không thấy bảng lõi thì coi như bảng đã đóng


class Scanner:
    def __init__(self):
        self.lock = threading.Lock()
        self.status = "Đang khởi động bộ quét…"
        self.error = None
        self.ready = False
        self.calib = ss.Calibration.load()
        self.offer = None            # {"slots": [...], "at": ts, "visible": bool}
        self.calibrating_at = None   # thời điểm sẽ hiệu chỉnh (đếm ngược)
        self.catalog: list[dict] = []
        self.icons = None
        self.bank = None
        self._misses = 0
        self._in_game = False
        self._last_live = 0.0
        self.in_game_fn = None       # app gán hàm đọc trạng thái trận có sẵn → không gọi Live API lần 2
        self._ocr_cache: dict = {}   # kết quả OCR của bảng chọn đang hiện

    # ---------- public ----------
    def snapshot(self) -> dict:
        with self.lock:
            return {
                "ready": self.ready,
                "calibrated": self.calib is not None,
                "calibration": self.calib.__dict__ if self.calib else None,
                "status": self.status,
                "error": self.error,
                "ocr": _ocr_available(),
                "calibrating_in": max(0, round(self.calibrating_at - time.time(), 1)) if self.calibrating_at else None,
                "offer": self.offer,
            }

    def request_calibration(self, delay: float = 0.0):
        with self.lock:
            self.calibrating_at = time.time() + delay
            self.status = f"Sẽ hiệu chỉnh sau {delay:.0f} giây – mở bảng chọn lõi trong game." if delay else "Đang hiệu chỉnh…"

    def reset_calibration(self):
        with self.lock:
            self.calib = None
            if ss.CALIB_FILE.exists():
                ss.CALIB_FILE.unlink()
            self.status = "Đã xoá hiệu chỉnh."

    def start(self):
        threading.Thread(target=self._run, daemon=True, name="scanner").start()

    def mark_hidden(self):
        """Người dùng đã chọn lõi: ẩn offer hiện tại cho tới khi bảng chọn mới xuất hiện."""
        with self.lock:
            if self.offer:
                self.offer["visible"] = False
                self.offer["done"] = True
            self.status = "Đã ghi nhận lõi đã chọn – chờ lượt chọn tiếp theo."

    # ---------- internal ----------
    def _set(self, **kw):
        with self.lock:
            for k, v in kw.items():
                setattr(self, k, v)

    def _load(self):
        self._set(status="Đang tải danh sách lõi và icon (lần đầu mất khoảng 1 phút)…")
        self.catalog = playaram.get_augment_catalog()
        ss.ensure_icons(self.catalog, log=lambda *_: None)
        self.icons = ss.load_icons(self.catalog)
        self.bank = ss.bank_for(self.icons)
        self._set(ready=True, status="Sẵn sàng." if self.calib else
                  f"Chưa hiệu chỉnh: khi bảng chọn lõi hiện trong game, bấm {hotkeys.label('calibrate')} (hoặc nút Hiệu chỉnh).")

    def _check_game(self):
        if ss.FAKE_SCREEN:
            return True
        if self.in_game_fn:
            return bool(self.in_game_fn())
        if time.time() - self._last_live > 3:
            self._in_game = live_client.current_game().get("in_game", False)
            self._last_live = time.time()
        return self._in_game

    def _calibrate_now(self):
        self._set(calibrating_at=None, status="Đang hiệu chỉnh… (khoảng 10 giây)")
        img = ss.grab_screen()
        if img.max() < 10:
            self._set(status="Ảnh chụp màn hình bị đen: chuyển game sang chế độ Không viền (Borderless) rồi thử lại.")
            return
        calib = ss.calibrate(img, self.icons, log=lambda *_: None)
        if calib:
            res = ss.read_offer(img, calib, self.bank, self.catalog)
            if not ss.confident(res):
                calib = None
        if not calib:
            self._set(status="Không tìm thấy 3 lõi trên màn hình. Thử lại khi bảng chọn lõi đang hiện rõ.")
            return
        calib.save()
        self._set(calib=calib, status="Hiệu chỉnh xong – app sẽ tự đọc lõi mỗi khi bảng chọn hiện ra.")
        self._publish(res)
        del img

    def _publish(self, res):
        slots = [{"candidates": r["candidates"], "score": round(r["score"], 3)} for r in res]
        with self.lock:
            same = self.offer and [s["candidates"] for s in self.offer["slots"]] == [s["candidates"] for s in slots]
            if same:
                if not self.offer.get("done"):     # đã bấm chọn lõi thì không hiện lại offer cũ
                    self.offer["visible"] = True
            else:
                self.offer = {"slots": slots, "at": time.time(), "visible": True}

    def _scan_once(self):
        # Chỉ chụp vùng quanh 3 thẻ lõi (~1/5 màn hình) thay vì cả màn hình
        full = ss.screen_size()
        x0, y0, x1, y1 = ss.scan_region(self.calib, full)
        img = ss.grab_screen((x0, y0, x1, y1))
        res = ss.read_offer(img, self.calib, self.bank, self.catalog, origin=(x0, y0), full=full,
                            ocr_cache=self._ocr_cache)
        del img
        if ss.confident(res):
            self._misses = 0
            self._publish(res)
            self._set(status="Đã thấy bảng chọn lõi.")
        else:
            self._misses += 1
            if self._misses >= MISS_TO_HIDE:
                self._ocr_cache.clear()
                with self.lock:
                    if self.offer:
                        self.offer["visible"] = False
                self._set(status="Đang quét… (chưa thấy bảng chọn lõi)")

    def _run(self):
        try:
            self._load()
        except Exception as e:
            self._set(error=f"Không khởi động được bộ quét: {e}", status="Lỗi")
            return
        while True:
            try:
                if self.calibrating_at and time.time() >= self.calibrating_at:
                    self._calibrate_now()
                elif self.calib and self._check_game():
                    self._scan_once()
                elif self.calib:
                    self._set(status="Chờ vào trận để quét.")
                self._set(error=None)
            except Exception as e:
                traceback.print_exc()
                self._set(error=str(e))
            time.sleep(0.25 if self.calibrating_at else SCAN_INTERVAL)


def _ocr_available() -> bool:
    try:
        import ocr
        return ocr.installed()       # chỉ kiểm tra có cài, không nạp WinRT (nạp khi thật sự cần OCR)
    except Exception:
        return False



"""Luồng nền: khi đang trong trận và đã hiệu chỉnh, chụp màn hình mỗi giây để đọc 3 lõi đang được đưa ra.

Hiệu chỉnh: phím tắt toàn cục (mặc định Ctrl+Alt+A, xem app.py) khi đang hiện bảng chọn lõi trong game.
"""
from __future__ import annotations

import threading
import time
import traceback

import diag
import hotkeys
import live_client
import playaram
import screen_scan as ss

SCAN_INTERVAL = 1.0
MISS_TO_HIDE = 2          # số lần quét liên tiếp không thấy bảng lõi thì coi như bảng đã đóng
WIDE_EVERY = 3.0          # chưa thấy bảng lõi: cứ ~3 giây dò thô vùng rộng một lần (~70 ms) phòng thẻ xê dịch


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
        self.alt_names: dict[int, list[str]] = {}
        self.icons = None
        self.bank = None
        self._misses = 0
        self._in_game = False
        self._last_live = 0.0
        self.in_game_fn = None       # app gán hàm đọc trạng thái trận có sẵn → không gọi Live API lần 2
        self._ocr_cache: dict = {}   # kết quả OCR của bảng chọn đang hiện
        self._diag_last_log = self._diag_last_save = 0.0
        self._diag_last_offer = None
        self._diag_req = False
        self._was_in_game = False
        self._last_wide = 0.0

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
        try:   # tên tiếng Anh: OCR nhận được cả khi game để tiếng Anh
            self.alt_names = {a["id"]: [a["name"]] for a in playaram.get_augment_catalog(lang="en")}
        except Exception:
            self.alt_names = {}
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
            res = ss.read_offer(img, calib, self.bank, self.catalog, alt_names=self.alt_names)
            if not ss.confident(res):
                calib = None
        if not calib:
            diag.save(img, {"note": "hiệu chỉnh thất bại"}, "calibration-failed")
            diag.log("hiệu chỉnh thất bại – đã lưu ảnh màn hình vào data/debug/")
            self._set(status="Không tìm thấy 3 lõi trên màn hình. Thử lại khi bảng chọn lõi đang hiện rõ.")
            return
        diag.log(f"hiệu chỉnh xong {calib.__dict__}")
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
        kw = dict(origin=(x0, y0), full=full, ocr_cache=self._ocr_cache, alt_names=self.alt_names)
        res = ss.read_offer(img, self.calib, self.bank, self.catalog, **kw)
        near = max(r["score"] for r in res) >= ss.NEAR_MIN
        since = time.time() - self._last_wide
        if not ss.confident(res) and ((near and since > 2) or since > WIDE_EVERY):
            # Thẻ lõi có thể đã xê dịch so với lúc hiệu chỉnh (khi đó điểm ở vị trí cũ rơi về ~0, không chỉ
            # "gần khớp") → định kỳ dò thô vùng rộng ±25%, thấy thì dời tâm rồi xác nhận lại bằng dò thường.
            self._last_wide = time.time()
            coarse = ss.detect(img, self.calib, self.bank, (x0, y0), full, ss.WIDE_SHIFT, step=2)
            if max(r["score"] for r in coarse) >= ss.NEAR_MIN:
                moved = ss.recenter(self.calib, coarse, full)
                again = ss.read_offer(img, moved, self.bank, self.catalog, **kw)
                if ss.confident(again):
                    self.calib = ss.recenter(moved, again, full)
                    self.calib.save()
                    diag.log(f"thẻ lõi xê dịch → cập nhật vị trí hiệu chỉnh {self.calib.centers}")
                    res = again
        self._diagnose(res, img, (x0, y0))
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
                best = max(r["score"] for r in res)
                self._set(status=f"Đang quét… (chưa thấy bảng chọn lõi · khớp tốt nhất {best:.2f})")

    # ---------- chẩn đoán ----------
    def _diagnose(self, res, img, origin):
        """Ghi điểm khớp vào log (thưa) và lưu ảnh vùng quét khi gần khớp mà chưa chắc – để tìm lỗi trong game thật."""
        conf = ss.confident(res)
        scores = [round(r["score"], 2) for r in res]
        margins = [round(r["score"] - r["second"], 3) for r in res]
        now = time.time()
        names = {a["id"]: a["name"] for a in self.catalog}
        if conf and [r["candidates"] for r in res] != self._diag_last_offer:
            self._diag_last_offer = [r["candidates"] for r in res]
            diag.log(f"đọc được lõi: {[[names.get(c, c) for c in r['candidates']] for r in res]} điểm {scores}")
        elif not conf and now - self._diag_last_log > 20:
            self._diag_last_log = now
            diag.log(f"quét: chưa chắc · điểm {scores} · cách biệt {margins} · ngưỡng {ss.MATCH_MIN}/{ss.MARGIN_MIN}")
        if not conf and max(scores) >= ss.NEAR_MIN and now - self._diag_last_save > 10:
            self._diag_last_save = now
            diag.save(img, {"origin": origin, "calibration": self.calib.__dict__, "scores": scores, "margins": margins,
                            "best": [[names.get(c, c) for c in r["candidates"]] for r in res]}, "near-match")

    def request_diagnostic(self):
        """Gọi từ phím tắt: luồng quét sẽ lưu ảnh chẩn đoán ở vòng kế tiếp."""
        self._diag_req = True

    def save_diagnostic(self):
        """Phím tắt: lưu ảnh cả màn hình + kết quả quét hiện tại vào data/debug/ để gửi khi báo lỗi."""
        img = ss.grab_screen()
        info = {"calibration": self.calib.__dict__ if self.calib else None}
        if self.calib and self.bank is not None:
            res = ss.read_offer(img, self.calib, self.bank, self.catalog, use_ocr=True, alt_names=self.alt_names)
            wide = ss.read_offer(img, self.calib, self.bank, self.catalog, use_ocr=False, shift=ss.WIDE_SHIFT)
            names = {a["id"]: a["name"] for a in self.catalog}
            info.update({
                "confident": ss.confident(res),
                "scores": [round(r["score"], 3) for r in res], "seconds": [round(r["second"], 3) for r in res],
                "best": [[names.get(c, c) for c in r["candidates"]] for r in res],
                "wide_scores": [round(r["score"], 3) for r in wide], "wide_shift": [(r["dx"], r["dy"]) for r in wide],
                "ocr": [r.get("ocr") for r in res],
            })
        path = diag.save(img, info, "manual")
        self._set(status=f"Đã lưu ảnh chẩn đoán: {path.name}")

    def _run(self):
        try:
            self._load()
        except Exception as e:
            self._set(error=f"Không khởi động được bộ quét: {e}", status="Lỗi")
            return
        while True:
            try:
                in_game = self._check_game()
                if in_game != self._was_in_game:
                    self._was_in_game = in_game
                    diag.log(("vào trận – " + (f"bắt đầu quét, hiệu chỉnh {self.calib.__dict__}" if self.calib
                                               else "CHƯA hiệu chỉnh nên chưa quét")) if in_game else "ra khỏi trận")
                if self._diag_req:
                    self._diag_req = False
                    self.save_diagnostic()
                if self.calibrating_at and time.time() >= self.calibrating_at:
                    self._calibrate_now()
                elif self.calib and in_game:
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



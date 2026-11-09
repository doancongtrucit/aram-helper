# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
"""Luồng nền: khi đang trong trận, chụp vùng 3 thẻ lõi để đọc các lõi đang được đưa ra.

Vị trí bảng lõi: chưa có thì ước tính theo độ phân giải của cửa sổ game và tự lưu lại ở lượt chọn lõi đầu tiên
đọc được. Định vị thủ công (phím tắt, mặc định Ctrl+Alt+A) chỉ cần khi ước tính sai.
Tần suất quét thích ứng: nhanh khi bảng chọn lõi đang hiện / gần khớp, thưa khi lâu không thấy.
"""
from __future__ import annotations

import threading
import time
import traceback

import diag
import game_window
import pick_watch
import live_client
import playaram
import screen_scan as ss

SCAN_INTERVAL = 1.0      # giây giữa 2 lần quét bình thường
SCAN_FAST = 0.6          # đang thấy / gần thấy bảng chọn lõi
SCAN_IDLE = 1.5          # lâu không thấy bảng chọn lõi (giữa các lượt chọn) → nhẹ CPU hơn
IDLE_AFTER = 120.0
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
        self._last_seen = 0.0        # lần cuối thấy / gần thấy bảng chọn lõi
        self._est = None             # vị trí ước tính theo độ phân giải (khi chưa định vị)
        self.clicks = pick_watch.ClickWatcher()
        self._session_at = 0.0       # lúc bảng chọn lõi hiện ra (đổi lõi trong cùng lượt vẫn giữ)
        self.picked = None           # {"id", "slot", "slots"} – lõi tự ghi nhận theo cú bấm chuột
        self._pick_id = 0

    # ---------- public ----------
    def snapshot(self) -> dict:
        with self.lock:
            return {
                "ready": self.ready,
                "calibrated": self.calib is not None,
                "estimated": self.calib is None,
                "calibration": (self.calib or self._est).__dict__ if (self.calib or self._est) else None,
                "status": self.status,
                "error": self.error,
                "ocr": _ocr_available(),
                "calibrating_in": max(0, round(self.calibrating_at - time.time(), 1)) if self.calibrating_at else None,
                "offer": self.offer,
                "picked": self.picked,
            }

    def request_calibration(self, delay: float = 0.0):
        with self.lock:
            self.calibrating_at = time.time() + delay
            self.status = (f"Sẽ định vị bảng lõi sau {delay:.0f} giây – mở bảng chọn lõi trong game." if delay
                           else "Đang định vị bảng lõi…")

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
                  "Sẵn sàng – vị trí bảng lõi sẽ tự xác định ở lượt chọn lõi đầu tiên.")

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
        self._set(calibrating_at=None, status="Đang định vị bảng lõi… (khoảng 10 giây)")
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
            diag.log("định vị bảng lõi thất bại – đã lưu ảnh màn hình vào thư mục debug")
            self._set(status="Không tìm thấy bảng lõi trên màn hình. Thử lại khi bảng chọn lõi đang hiện rõ.")
            return
        diag.log(f"đã định vị bảng lõi {calib.__dict__}")
        calib.save()
        self._set(calib=calib, status="Đã định vị bảng lõi – app sẽ tự đọc lõi mỗi khi bảng chọn hiện ra.")
        self._publish(res)
        del img

    def _publish(self, res, rerolls=None):
        slots = [{"candidates": r["candidates"], "score": round(r["score"], 3)} for r in res]
        with self.lock:
            if not (self.offer and self.offer.get("visible")):
                self._session_at = time.time()
            elif len(self.offer["slots"]) == len(slots):
                # Giữ kết quả đã thu hẹp (đọc được tên bằng OCR): lần quét sau OCR trượt chỉ còn "1 trong N lõi"
                # thì không lùi lại – tránh gợi ý trên overlay nhảy qua lại mỗi giây.
                for new, old in zip(slots, self.offer["slots"]):
                    if len(old["candidates"]) < len(new["candidates"]) and set(old["candidates"]) <= set(new["candidates"]):
                        new["candidates"] = old["candidates"]
            same = self.offer and [s["candidates"] for s in self.offer["slots"]] == [s["candidates"] for s in slots]
            if same:
                if not self.offer.get("done"):     # đã bấm chọn lõi thì không hiện lại offer cũ
                    self.offer["visible"] = True
            else:
                self.offer = {"slots": slots, "at": time.time(), "visible": True}
            if rerolls is not None:
                self.offer["rerolls"] = rerolls

    def _offer_closed(self):
        """Bảng chọn vừa đóng: nếu người chơi đã bấm vào 1 thẻ (và chưa tự đánh dấu) → ghi nhận lõi ở thẻ đó."""
        self.clicks.stop()
        slot = self.clicks.take(self._session_at)
        with self.lock:
            offer = self.offer
            if offer is None or offer.get("done") or slot is None or slot >= len(offer["slots"]):
                return
            offer["done"] = True
            self._pick_id += 1
            self.picked = {"id": self._pick_id, "slot": slot, "slots": [s["candidates"] for s in offer["slots"]]}
        diag.log(f"tự ghi nhận lõi đã chọn: thẻ {slot + 1}")

    def _active_calib(self, full) -> ss.Calibration:
        """Vị trí đã định vị (nếu cùng tỉ lệ khung hình với vùng game), không thì ước tính theo độ phân giải."""
        if self.calib and self.calib.fits(*full):
            return self.calib
        if not self._est or (self._est.width, self._est.height) != tuple(full):
            self._est = ss.Calibration.estimate(*full)
        return self._est

    def _scan_once(self):
        # Chỉ chụp vùng quanh 3 thẻ lõi (~1/5 vùng game) thay vì cả màn hình
        full = ss.screen_size()
        calib = self._active_calib(full)
        x0, y0, x1, y1 = ss.scan_region(calib, full)
        img = ss.grab_screen((x0, y0, x1, y1))
        kw = dict(origin=(x0, y0), full=full, ocr_cache=self._ocr_cache, alt_names=self.alt_names)
        res = ss.read_offer(img, calib, self.bank, self.catalog, **kw)
        near = max(r["score"] for r in res) >= ss.NEAR_MIN
        since = time.time() - self._last_wide
        if not ss.confident(res) and ((near and since > 2) or since > WIDE_EVERY):
            # Thẻ lõi có thể đã xê dịch so với lúc hiệu chỉnh (khi đó điểm ở vị trí cũ rơi về ~0, không chỉ
            # "gần khớp") → định kỳ dò thô vùng rộng ±25%, thấy thì dời tâm rồi xác nhận lại bằng dò thường.
            self._last_wide = time.time()
            coarse = ss.detect(img, calib, self.bank, (x0, y0), full, ss.WIDE_SHIFT, step=2)
            if max(r["score"] for r in coarse) >= ss.NEAR_MIN:
                moved = ss.recenter(calib, coarse, full)
                again = ss.read_offer(img, moved, self.bank, self.catalog, **kw)
                if ss.confident(again):
                    calib = ss.recenter(moved, again, full)
                    diag.log(f"thẻ lõi lệch so với vị trí cũ → cập nhật {calib.centers}")
                    res = again
        if ss.confident(res) and (calib.estimated or calib is not self.calib):
            calib.estimated = False                   # lượt chọn đầu tiên đọc được → lưu làm vị trí chuẩn
            calib.save()
            diag.log(f"tự định vị bảng lõi {calib.__dict__}")
            self._set(calib=calib)
        self._diagnose(res, img, (x0, y0), calib)
        rerolls = ss.rerolls_left(img, res, (x0, y0)) if ss.confident(res) else None
        del img
        if ss.confident(res) or max(r["score"] for r in res) >= ss.NEAR_MIN:
            self._last_seen = time.time()
        if ss.confident(res):
            self._misses = 0
            self._publish(res, rerolls)
            gx, gy = game_window.rect()[:2] if not ss.FAKE_SCREEN else (0, 0)
            self.clicks.watch(ss.card_rects(calib, full, (gx, gy)))
            self._set(status="Đã thấy bảng chọn lõi.")
        else:
            self._misses += 1
            if self._misses >= MISS_TO_HIDE:
                self._ocr_cache.clear()
                with self.lock:
                    was_visible = bool(self.offer and self.offer.get("visible"))
                    if self.offer:
                        self.offer["visible"] = False
                if was_visible:
                    self._offer_closed()
                best = max(r["score"] for r in res)
                self._set(status=f"Đang quét… (chưa thấy bảng chọn lõi · khớp tốt nhất {best:.2f})")

    # ---------- chẩn đoán ----------
    def _diagnose(self, res, img, origin, calib):
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
            diag.save(img, {"origin": origin, "calibration": calib.__dict__, "scores": scores, "margins": margins,
                            "best": [[names.get(c, c) for c in r["candidates"]] for r in res]}, "near-match")

    def request_diagnostic(self):
        """Gọi từ phím tắt: luồng quét sẽ lưu ảnh chẩn đoán ở vòng kế tiếp."""
        self._diag_req = True

    def save_diagnostic(self):
        """Phím tắt: lưu ảnh cả màn hình + kết quả quét hiện tại vào data/debug/ để gửi khi báo lỗi."""
        img = ss.grab_screen()
        calib = self._active_calib((img.shape[1], img.shape[0]))
        info = {"calibration": calib.__dict__, "game_area": ss.screen_size()}
        if self.bank is not None:
            res = ss.read_offer(img, calib, self.bank, self.catalog, use_ocr=True, alt_names=self.alt_names)
            wide = ss.read_offer(img, calib, self.bank, self.catalog, use_ocr=False, shift=ss.WIDE_SHIFT)
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
                    diag.log(("vào trận – vùng game " + str(ss.screen_size()) + ", " +
                              (f"vị trí bảng lõi {self.calib.__dict__}" if self.calib else "dùng vị trí ước tính"))
                             if in_game else "ra khỏi trận")
                if self._diag_req:
                    self._diag_req = False
                    self.save_diagnostic()
                if self.calibrating_at and time.time() >= self.calibrating_at:
                    self._calibrate_now()
                elif in_game:
                    self._scan_once()
                else:
                    self._set(status="Chờ vào trận để quét.")
                self._set(error=None)
            except Exception as e:
                traceback.print_exc()
                self._set(error=str(e))
            time.sleep(self._interval())

    def _interval(self) -> float:
        if self.calibrating_at:
            return 0.25
        since = time.time() - self._last_seen
        return SCAN_FAST if since < 5 else SCAN_IDLE if since > IDLE_AFTER else SCAN_INTERVAL


def _ocr_available() -> bool:
    try:
        import ocr
        return ocr.installed()       # chỉ kiểm tra có cài, không nạp WinRT (nạp khi thật sự cần OCR)
    except Exception:
        return False



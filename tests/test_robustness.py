# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
"""Độ bền khi app chạy lâu dưới khay: ghi file an toàn, cache hỏng, mạng lỗi, hết trận giữa lượt chọn lõi,
tướng chọn tay, chỉ 1 bản chạy, log xoay vòng, gói báo lỗi chỉ giữ vùng thẻ lõi."""
import json
import os
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import paths  # noqa: E402
import playaram  # noqa: E402

WIN = sys.platform == "win32"


class AtomicWrite(unittest.TestCase):
    def test_replaces_whole_file_and_leaves_no_temp(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "sub" / "x.json"
            paths.write_atomic(p, '{"a": 1}')
            paths.write_atomic(p, b'{"a": 2}')
            self.assertEqual(json.loads(p.read_text(encoding="utf-8")), {"a": 2})
            self.assertEqual([f.name for f in p.parent.iterdir()], ["x.json"])

    def test_failed_write_keeps_old_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.json"
            paths.write_atomic(p, "cũ")
            with mock.patch("os.replace", side_effect=OSError("đĩa đầy")), self.assertRaises(OSError):
                paths.write_atomic(p, "mới")
            self.assertEqual(p.read_text(encoding="utf-8"), "cũ")
            self.assertEqual(len(list(Path(d).iterdir())), 1)       # file tạm đã dọn


class DataCache(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.p = [mock.patch.object(playaram, "CACHE_DIR", Path(self.tmp.name)),
                  mock.patch.dict(playaram._mem, clear=True)]
        for p in self.p:
            p.start()
        playaram.reset_backoff()

    def tearDown(self):
        for p in self.p:
            p.stop()
        playaram.reset_backoff()
        self.tmp.cleanup()

    def test_corrupt_cache_is_dropped_not_fatal(self):
        f = Path(self.tmp.name) / "champ_yasuo.json"
        f.write_text('{"slug": "yasuo", "augm', encoding="utf-8")         # ghi dở (tắt máy giữa chừng)
        self.assertIsNone(playaram._read_cache("champ_yasuo", 3600))
        self.assertFalse(f.exists())

    def test_network_error_uses_stale_cache_then_backs_off(self):
        playaram._write_cache("champ_lux", {"slug": "lux", "schema": playaram.SCHEMA, "augments": {}})
        playaram._mem.clear()
        old = json.loads((Path(self.tmp.name) / "champ_lux.json").read_text(encoding="utf-8"))
        old["fetched_at"] = 0
        (Path(self.tmp.name) / "champ_lux.json").write_text(json.dumps(old), encoding="utf-8")
        calls = []

        def offline(*a, **k):
            calls.append(1)
            raise urllib.error.URLError("offline")
        with mock.patch("urllib.request.urlopen", side_effect=offline), mock.patch.object(playaram, "MIN_INTERVAL", 0):
            c = playaram.get_champion("lux")
            self.assertTrue(c["stale"])
            for _ in range(5):                                   # luồng nền hỏi lại mỗi 1,5 giây
                playaram.get_champion("lux")
        self.assertEqual(len(calls), 1)                          # chỉ 1 request thật, sau đó chờ thử lại
        with self.assertRaises(playaram.Unavailable):
            playaram._get("/tuong/lux")
        self.assertEqual(playaram.describe_error(playaram.Unavailable("x")), "không tải được dữ liệu (kiểm tra mạng)")
        playaram.reset_backoff()
        with mock.patch("urllib.request.urlopen", side_effect=offline), mock.patch.object(playaram, "MIN_INTERVAL", 0):
            playaram.get_champion("lux")
        self.assertEqual(len(calls), 2)                          # bấm "Tải lại" → thử ngay

    def test_transformed_champion_maps_to_base(self):
        """Lỗi thấy trong trận thật: Gnar biến thành Gnar Khổng Lồ → Live API báo "GnarBig" → tải /tuong/gnarbig lỗi 404."""
        self.assertEqual(playaram.game_slug("GnarBig"), "gnar")
        self.assertEqual(playaram.game_slug("game_character_displayname_Gnar"), "gnar")
        playaram._write_cache("_champions", {"slugs": ["gnar", "lux", "monkeyking"]})
        self.assertEqual(playaram.game_slug("LuxSomethingForm"), "lux")       # tướng biến hình chưa có trong danh sách
        self.assertEqual(playaram.game_slug("MonkeyKing"), "monkeyking")
        self.assertEqual(playaram.game_slug("Zaahen"), "zaahen")               # tướng mới chưa có trong cache: giữ nguyên

    def test_odd_percent_cells(self):
        self.assertEqual(playaram._pct("52,3 %"), 52.3)
        self.assertIsNone(playaram._pct("—"))
        self.assertIsNone(playaram._pct("N/A"))
        self.assertEqual(playaram._pct(None, 0.0), 0.0)


class HubGame(unittest.TestCase):
    def setUp(self):
        import app
        self.app = app
        self.hub = app.Hub(None)
        self.games = []
        self.p = [mock.patch.object(app.live_client, "current_game", side_effect=lambda: self.games.pop(0)),
                  mock.patch.object(app.playaram, "get_champion",
                                    side_effect=lambda s, force=False: {"slug": s, "name": s, "fetched_at": 1}),
                  mock.patch.object(app.playaram, "get_augment_catalog", return_value=[{"id": 1, "name": "x"}]),
                  mock.patch.object(app.ddragon, "get", return_value=None)]
        for p in self.p:
            p.start()

    def tearDown(self):
        for p in self.p:
            p.stop()

    def test_new_game_drops_manually_viewed_champion(self):
        self.hub.set_focus("yasuo")
        self.games = [{"in_game": False}, {"in_game": True, "champion_raw": "Lux"}]
        self.hub.refresh()
        self.assertEqual(self.hub.champion["slug"], "yasuo")
        self.hub.refresh()                                       # vào trận chơi Lux
        self.assertIsNone(self.hub.focus_slug)
        self.assertEqual(self.hub.champion["slug"], "lux")

    def test_viewing_another_champion_during_game_is_kept(self):
        self.games = [{"in_game": True, "champion_raw": "Lux"}, {"in_game": True, "champion_raw": "Lux"}]
        self.hub.refresh()
        self.hub.set_focus("yasuo")
        self.hub.refresh()
        self.assertEqual(self.hub.champion["slug"], "yasuo")

    def test_catalog_is_never_fetched_on_caller_thread(self):
        self.app.playaram.get_augment_catalog.side_effect = AssertionError("không được tải mạng ở luồng giao diện")
        self.assertEqual(self.hub.catalog(), {})
        self.app.playaram.get_augment_catalog.side_effect = None
        self.games = [{"in_game": False}]
        self.hub.refresh()                                       # luồng nền nạp
        self.assertIn(1, self.hub.catalog())

    def test_reload_forces_fresh_download(self):
        self.hub.set_focus("lux")
        self.games = [{"in_game": False}, {"in_game": False}]
        self.hub.refresh()
        self.hub.reload()
        self.hub.refresh()
        self.assertEqual(self.app.playaram.get_champion.call_args_list[-1].kwargs, {"force": True})


class ScannerLife(unittest.TestCase):
    def setUp(self):
        try:
            import scanner
        except Exception as e:                       # pragma: no cover
            self.skipTest(f"không nạp được bộ quét: {e}")
        self.sc = scanner.Scanner()
        self.scanner = scanner

    def test_game_end_during_offer_clears_everything(self):
        sc = self.sc
        sc._publish([{"candidates": [1], "score": 0.9}, {"candidates": [2], "score": 0.9}, {"candidates": [3], "score": 0.9}])
        sc.clicks.watch([(0, 0, 10, 10)])
        sc.clicks.last = (0, time.time())
        sc._end_game()
        self.assertIsNone(sc.snapshot()["offer"])
        self.assertIsNone(sc.clicks.rects)
        self.assertIsNone(sc.clicks.take(0))                     # cú bấm cũ không sang trận sau

    def test_start_up_retries_after_network_error(self):
        sc = self.sc
        attempts = []

        def load(quiet=False):
            attempts.append(1)
            if len(attempts) < 3:
                raise urllib.error.URLError("offline")
        with mock.patch.object(sc, "_load", side_effect=load), mock.patch.object(self.scanner.time, "sleep") as sleep:
            sc._start_up()
        self.assertEqual(len(attempts), 3)
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [30.0, 60.0])
        self.assertIsNone(sc.error)

    def test_manual_choice_sticks_until_card_changes(self):
        sc = self.sc
        sc._publish([{"candidates": [1, 2, 3], "score": 0.9}, {"candidates": [5], "score": 0.9}])
        self.assertTrue(sc.choose(0, 2))
        self.assertFalse(sc.choose(0, 99))                       # không phải lõi có thể ở thẻ này
        sc._publish([{"candidates": [1, 2, 3], "score": 0.9}, {"candidates": [5], "score": 0.9}])
        self.assertEqual(sc.offer["slots"][0]["candidates"], [2])
        sc._publish([{"candidates": [7, 8], "score": 0.9}, {"candidates": [5], "score": 0.9}])     # đổi thẻ
        self.assertEqual(sc.offer["slots"][0]["candidates"], [7, 8])


class RotatingLogTest(unittest.TestCase):
    def test_rotates_while_running(self):
        import app
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "app.log"
            log = app.RotatingLog(p, limit=2000)
            for i in range(400):
                log.write(f"dòng {i:04d} " + "x" * 20 + "\n")
            log.flush()
            self.assertTrue(p.with_suffix(".log.1").exists())
            self.assertLess(p.stat().st_size, 4000)
            log._f.close()


@unittest.skipUnless(WIN, "chỉ Windows")
class SingleInstance(unittest.TestCase):
    def test_second_acquire_fails(self):
        import single_instance as si
        name = f"Local\\ARAMHelperTest.{os.getpid()}"
        saved = si._handle
        try:
            self.assertTrue(si.acquire(name))
            result = []
            t = threading.Thread(target=lambda: result.append(si.acquire(name)))
            t.start()
            t.join()
            self.assertEqual(result, [False])
        finally:
            si.release()
            si._handle = saved


class ReportPrivacy(unittest.TestCase):
    def test_full_screenshot_is_cropped_to_cards(self):
        import report
        info = {"calibration": {"width": 2560, "height": 1440, "size": 215,
                                "centers": [[792, 416], [1280, 416], [1768, 416]]}}
        x0, y0, x1, y1 = report.crop_box(2560, 1440, info)
        self.assertGreater(x0, 300)
        self.assertLess(x1, 2300)
        self.assertGreater(y0, 50)
        self.assertLess(y1, 1440 * 0.8)                           # gồm nút đổi lõi, không tới khung chat phía dưới
        self.assertEqual(report.crop_box(800, 300, {"origin": [10, 10]}), (0, 0, 800, 300))
        x0, y0, x1, y1 = report.crop_box(1920, 1080, {})
        self.assertLess(y1, 1080 * 0.7)

    def test_bundle_contains_only_cropped_images(self):
        import report
        from PIL import Image
        with tempfile.TemporaryDirectory() as d, mock.patch.object(report.paths, "DATA", Path(d)):
            dbg = Path(d) / "debug"
            dbg.mkdir()
            Image.new("RGB", (1920, 1080), "red").save(dbg / "20260101-000000-manual.png")
            (dbg / "20260101-000000-manual.json").write_text("{}", encoding="utf-8")
            out = report.make_bundle(Path(d) / "out")
            import io
            import zipfile
            with zipfile.ZipFile(out) as z:
                im = Image.open(io.BytesIO(z.read("debug/20260101-000000-manual.png")))
                self.assertLess(im.height, 1080 * 0.6)


class PatchLag(unittest.TestCase):
    def test_compares_year_and_ddragon_numbers(self):
        try:
            import desktop
        except Exception as e:                       # pragma: no cover – không có tkinter
            self.skipTest(str(e))
        self.assertEqual(desktop.patch_lag("26.21", "16.22.1"), ("26.21", "26.22"))
        self.assertIsNone(desktop.patch_lag("26.22", "16.22.1"))
        self.assertIsNone(desktop.patch_lag(None, "16.22.1"))
        self.assertIsNone(desktop.patch_lag("26.22", None))


class CalibrationFile(unittest.TestCase):
    def test_corrupt_calibration_means_not_calibrated(self):
        try:
            import screen_scan as ss
        except Exception as e:                       # pragma: no cover
            self.skipTest(str(e))
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "calibration.json"
            f.write_text('{"width": 2560, "hei', encoding="utf-8")
            with mock.patch.object(ss, "CALIB_FILE", f):
                self.assertIsNone(ss.Calibration.load())
                ss.Calibration(1920, 1080, 150, [(1, 2), (3, 4), (5, 6)]).save()
                self.assertEqual(ss.Calibration.load().centers, [(1, 2), (3, 4), (5, 6)])


if __name__ == "__main__":
    unittest.main()

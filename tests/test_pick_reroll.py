# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
"""Tự ghi nhận lõi đã chọn (cú bấm chuột lên thẻ) và gợi ý đổi lõi (↻)."""
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import advice  # noqa: E402
import pick_watch  # noqa: E402

try:
    import numpy as np
    import screen_scan as ss
    HAS_SS = True
except Exception:
    HAS_SS = False


def ranked(*scores):
    out = [{"slot": i, "best": {"id": i, "score": s}} for i, s in enumerate(scores)]
    for r, o in enumerate(sorted(out, key=lambda o: -o["best"]["score"]), start=1):
        o["rank"] = r
    return out


class RerollHint(unittest.TestCase):
    CHAMP = {"winrate": 55.0}

    def test_weakest_card_with_reroll_left(self):
        self.assertEqual(advice.reroll_hint(ranked(60, 51, 53), self.CHAMP, [True, True, True]), 1)

    def test_skip_used_reroll_and_best_card(self):
        self.assertEqual(advice.reroll_hint(ranked(60, 51, 53), self.CHAMP, [True, False, True]), 2)
        self.assertIsNone(advice.reroll_hint(ranked(50, 60, 61), self.CHAMP, [False, True, True]))   # thẻ yếu hết lượt đổi

    def test_no_hint_when_offer_is_good(self):
        self.assertIsNone(advice.reroll_hint(ranked(60, 58, 54.5), self.CHAMP, [True, True, True]))
        self.assertIsNone(advice.reroll_hint(ranked(60, 51, 53), self.CHAMP, None))


class ClickWatcher(unittest.TestCase):
    def test_slot_at_and_take(self):
        rects = [(0, 0, 100, 200), (150, 0, 250, 200), (300, 0, 400, 200)]
        self.assertEqual(pick_watch.ClickWatcher.slot_at(rects, 200, 50), 1)
        self.assertIsNone(pick_watch.ClickWatcher.slot_at(rects, 120, 50))      # giữa 2 thẻ
        self.assertIsNone(pick_watch.ClickWatcher.slot_at(rects, 200, 260))     # nút đổi lõi bên dưới
        w = pick_watch.ClickWatcher()
        t0 = time.time()
        w.last = (2, t0 + 1)
        self.assertIsNone(w.take(t0 + 5))         # bấm trước khi bảng chọn này hiện ra
        w.last = (2, t0 + 1)
        self.assertEqual(w.take(t0), 2)
        self.assertIsNone(w.take(t0))             # đã lấy rồi


@unittest.skipUnless(HAS_SS, "cần opencv")
class ScreenGeometry(unittest.TestCase):
    def test_rerolls_left_by_colour(self):
        img = np.full((900, 1600, 3), 30, np.uint8)
        res = []
        for i, cx in enumerate((400, 800, 1200)):
            r = {"center": (cx, 200), "size": 150}
            y = int(200 + ss.REROLL_Y * 150)
            colour = (90, 90, 90) if i == 1 else (40, 110, 200)            # thẻ giữa: nút xám (đã dùng)
            img[y - 20:y + 20, cx - 32:cx + 32] = colour
            res.append(r)
        self.assertEqual(ss.rerolls_left(img, res), [True, False, True])

    def test_card_rects_follow_game_window_offset(self):
        c = ss.Calibration(2560, 1440, 215, [(792, 416), (1280, 416), (1771, 416)])
        a = ss.card_rects(c, (2560, 1440))
        b = ss.card_rects(c, (2560, 1440), offset=(-2560, 0))                # game ở màn hình bên trái
        self.assertEqual(b[1][0], a[1][0] - 2560)
        x0, y0, x1, y1 = a[1]
        self.assertTrue(x0 < 1280 < x1 and y0 < 416 < y1)
        self.assertLess(y1, 416 + ss.REROLL_Y * 215 - 0.12 * 215)            # không trùm nút đổi lõi

    def test_scan_region_includes_reroll_buttons(self):
        c = ss.Calibration(2560, 1440, 215, [(792, 416), (1280, 416), (1771, 416)])
        y1 = ss.scan_region(c, (2560, 1440))[3]
        self.assertGreater(y1, 416 + ss.REROLL_Y * 215 + 0.12 * 215)


@unittest.skipUnless(HAS_SS, "cần opencv")
class ScannerAutoPick(unittest.TestCase):
    def test_offer_closed_records_clicked_card(self):
        import scanner
        sc = scanner.Scanner()
        sc._session_at = time.time() - 5
        sc.offer = {"slots": [{"candidates": [1]}, {"candidates": [2]}, {"candidates": [3, 4]}],
                    "at": sc._session_at, "visible": False}
        sc.clicks.last = (2, time.time())
        sc._offer_closed()
        self.assertEqual(sc.picked["slot"], 2)
        self.assertEqual(sc.picked["slots"][2], [3, 4])
        self.assertTrue(sc.offer["done"])
        first = sc.picked["id"]
        sc.clicks.last = (0, time.time())
        sc._offer_closed()                          # đã ghi nhận lượt này → không ghi lại
        self.assertEqual(sc.picked["id"], first)

    def test_no_click_no_pick(self):
        import scanner
        sc = scanner.Scanner()
        sc.offer = {"slots": [{"candidates": [1]}], "at": time.time(), "visible": False}
        sc._offer_closed()
        self.assertIsNone(sc.picked)


if __name__ == "__main__":
    unittest.main()

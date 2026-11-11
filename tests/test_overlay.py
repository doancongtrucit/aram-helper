# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
"""Overlay: vẽ được, bấm chọn lõi, thu gọn, kéo khung và nhớ vị trí (dữ liệu mẫu, không cần game)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

import advice  # noqa: E402
from test_desktop import CATALOG, CHAMP, HAS_TK, FakeHub  # noqa: E402

CALIB = {"width": 1920, "height": 1080, "size": 128, "centers": [[660, 432], [960, 432], [1260, 432]]}


class Hub(FakeHub):
    offer = True
    my_items = ()           # đồ đang có trong trận (giả lập)
    reroll = None           # thẻ được gợi ý đổi lõi (giả lập)

    def slug(self):
        return "yasuo"

    def state(self):
        s = super().state()
        s["advice"] = advice.rank_offer([[1018], [3048], [1134]], CHAMP, CATALOG, set(self.owned)) if self.offer else None
        for r in s["advice"] or []:
            r["reroll"] = r["slot"] == self.reroll
        s["scan"] = {"status": "ok", "calibrated": True, "calibration": CALIB}
        s["game"] = {**s["game"], "my_items": list(self.my_items)}
        return s


class Scan:
    def __init__(self, hub):
        self.hub = hub

    def mark_hidden(self):
        self.hub.offer = False


@unittest.skipUnless(HAS_TK and sys.platform == "win32", "cần Windows + tkinter")
class OverlayUI(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        import overlay
        self.tmp = tempfile.TemporaryDirectory()
        overlay.PREFS = os.path.join(self.tmp.name, "overlay.json")
        self.root = tk.Tk()
        self.root.withdraw()
        self.hub = Hub()
        self.hub.owned = [1058]
        self.ov = overlay.Overlay(self.hub, Scan(self.hub), self.root)
        self.tick()

    def tearDown(self):
        self.root.destroy()
        self.tmp.cleanup()

    def tick(self):
        self.ov._sig = None
        self.ov._tick()
        self.root.update()

    def test_draws_panel_and_badges(self):
        self.assertTrue(self.ov.is_shown(self.ov.panel))
        self.assertTrue(self.ov.is_shown(self.ov.bwin))
        tags = {t for i in self.ov.bcv.find_all() for t in self.ov.bcv.gettags(i)}
        self.assertEqual({t for t in tags if t.startswith("badge")}, {"badge0", "badge1", "badge2"})

    def test_never_uses_activating_tk_calls(self):
        """Overlay không được gọi deiconify / lift / -topmost của tkinter (các lệnh này lấy focus của game;
        khi overlay ẩn đi, Windows chuyển focus sang cửa sổ chính → người chơi 1 màn hình bị văng khỏi game)."""
        import tkinter as tk
        from unittest import mock
        with mock.patch.object(tk.Toplevel, "deiconify") as dei, mock.patch.object(tk.Toplevel, "lift") as lift,                 mock.patch.object(tk.Toplevel, "withdraw") as wd:
            self.hub.offer = True
            self.tick()
            self.ov._last_top = 0
            self.tick()
            self.hub.offer = False
            self.tick()
            self.ov._hide()
        self.assertFalse(dei.called or lift.called or wd.called)

    def test_no_activate_style_survives_tk_alpha(self):
        """Tk ghi đè extended style khi đổi -alpha; cờ WS_EX_NOACTIVATE phải còn sau khi tạo và sau khi đổi độ đậm,
        nếu không bấm vào overlay sẽ làm game mất focus."""
        import ctypes
        import overlay

        def ok(win):
            st = ctypes.windll.user32.GetWindowLongW(overlay._hwnd(win), overlay.GWL_EXSTYLE)
            return st & overlay.NO_ACTIVATE_EX == overlay.NO_ACTIVATE_EX
        self.assertTrue(ok(self.ov.panel) and ok(self.ov.bwin))
        self.ov._on_settings({"ov_opacity": 0.5, "ov_badge_opacity": 0.9})
        self.assertTrue(ok(self.ov.panel) and ok(self.ov.bwin))

    def test_reroll_hint_drawn_on_row_and_badge(self):
        import i18n
        self.hub.reroll = 0
        self.tick()
        texts = [self.ov.pcv.itemcget(i, "text") for i in self.ov.pcv.find_all() if self.ov.pcv.type(i) == "text"]
        badge = [self.ov.bcv.itemcget(i, "text") for i in self.ov.bcv.find_all() if self.ov.bcv.type(i) == "text"]
        self.assertIn(i18n.T("↻ nên đổi"), texts)
        self.assertTrue(any(i18n.T("↻ nên đổi thẻ này") in t for t in badge))

    def test_pick_marks_owned_and_hides_offer(self):
        self.ov._pick(3048)
        self.tick()
        self.assertIn(3048, self.hub.owned)
        self.assertFalse(self.ov.is_shown(self.ov.bwin))

    def test_check_mark_on_owned_items(self):
        builds = CHAMP["builds"]
        first = [it["id"] for it in builds[0]["items"] if it.get("id")][:2]
        self.assertEqual(len(first), 2)                 # dữ liệu mẫu có mã trang bị
        self.assertEqual(len(self.ov.pcv.find_withtag("have")), 0)
        self.hub.my_items = (*first, 999999)            # 2 món của lối 1 + 1 món ngoài lối
        self.tick()
        shown = sum(it.get("id") in first for b in builds[:3] for it in b["items"][:6] + b.get("boots", [])[:1])
        self.assertEqual(len(self.ov.pcv.find_withtag("have")), shown)
        self.hub.my_items = ()                           # bán đồ → bỏ dấu
        self.tick()
        self.assertEqual(len(self.ov.pcv.find_withtag("have")), 0)

    def test_collapse_shrinks_panel(self):
        full = self.ov.panel.winfo_height()
        self.ov._set_collapsed(True)
        self.tick()
        self.assertLess(self.ov.panel.winfo_height(), full)

    def test_drag_saves_position(self):
        import overlay
        x0, y0 = self.ov.panel.winfo_x(), self.ov.panel.winfo_y()
        self.ov._drag_start(SimpleNamespace(x_root=x0 + 20, y_root=y0 + 10))
        self.ov._drag_move(SimpleNamespace(x_root=x0 - 180, y_root=y0 + 110))
        self.root.update()
        self.ov._drag_end(None)
        self.assertEqual((self.ov.prefs["x"], self.ov.prefs["y"]), (x0 - 200, y0 + 100))
        self.assertTrue(os.path.exists(overlay.PREFS))

    def test_hide(self):
        self.ov._hide()
        self.root.update()
        self.assertFalse(self.ov.visible)
        self.assertFalse(self.ov.is_shown(self.ov.panel))


if __name__ == "__main__":
    unittest.main()

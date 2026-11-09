"""Kiểm tra cửa sổ chính dựng được giao diện từ dữ liệu mẫu (không cần mạng, không cần game)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
import fixtures  # noqa: E402
import playaram  # noqa: E402
import settings  # noqa: E402

HERE = Path(__file__).parent
CHAMP = playaram.parse_champion_page(fixtures.load("yasuo"), "yasuo")
CHAMP["fetched_at"] = 0
CATALOG = {a["id"]: a for a in playaram.parse_augment_catalog(fixtures.load("augments"))}


class FakeHub:
    def __init__(self):
        self.owned = []
        self.focus = None
        self.adv = None

    def catalog(self):
        return CATALOG

    def state(self):
        return {"game": {"in_game": True, "champion_name": "Yasuo"}, "champion": CHAMP, "owned": list(self.owned),
                "focus": None, "error": None, "scan": {"status": "Sẵn sàng.", "calibrated": True}, "advice": self.adv}

    def update_owned(self, slug, add=None, remove=None, toggle=None, clear=False):
        if toggle is not None:
            self.owned.remove(toggle) if toggle in self.owned else self.owned.append(toggle)
        if add is not None and add not in self.owned:
            self.owned.append(add)

    def set_focus(self, slug):
        self.focus = slug


try:
    import tkinter as tk
    _root = tk.Tk()
    _root.destroy()
    HAS_TK = True
except Exception:
    HAS_TK = False


@unittest.skipUnless(HAS_TK, "cần màn hình / tkinter")
class DesktopUI(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        import desktop
        self.desktop = desktop
        self.tmp = tempfile.TemporaryDirectory()
        settings._reset_for_tests(Path(self.tmp.name) / "settings.json")
        settings.set_many({"top_n": 8}, save=False)
        self.no_net = mock.patch.object(desktop.App, "_load_champion_list", lambda self: None)
        self.no_net.start()
        self.root = tk.Tk()
        self.root.withdraw()
        self.hub = FakeHub()
        self.app = desktop.App(self.root, self.hub)
        self.app._champs = [("yasuo", "Yasuo", "yasuo"), ("yone", "Yone", "yone"), ("jinx", "Jinx", "jinx"),
                            ("masteryi", "Master Yi", "master yi")]
        self.tick()

    def tearDown(self):
        self.root.destroy()
        self.no_net.stop()
        settings._reset_for_tests(settings.PATH)
        self.tmp.cleanup()

    def tick(self):
        self.app._poll()
        self.root.update()

    def visible_cards(self, rarity):
        return [c for c in self.app.cards.values() if c["rarity"] == rarity and c["w"].winfo_manager() == "grid"]

    def fake_size(self, w, h):
        self.app.body.winfo_width = lambda: w
        self.app.body.winfo_height = lambda: h
        self.app._full_sig = None
        self.tick()

    def test_top_n_and_more(self):
        self.assertEqual(len(self.app.cards), 48)
        for r in ("prismatic", "gold", "silver"):
            self.assertEqual(len(self.visible_cards(r)), 8)
        self.app._toggle_more("gold")
        self.tick()
        self.assertEqual(len(self.visible_cards("gold")), 16)
        self.assertEqual(len(self.visible_cards("silver")), 8)

    def test_auto_fit_grows_with_height(self):
        settings.set("top_n", 0)
        cols, small = self.app._per_tier(800, 500)
        _, big = self.app._per_tier(800, 1100)
        self.assertGreaterEqual(small, cols)          # ít nhất 1 hàng mỗi bậc
        self.assertGreater(big, small)
        self.assertEqual(big % cols, 0)

    def test_wide_window_shows_augments_and_items_side_by_side(self):
        self.fake_size(1400, 800)
        self.assertIsNotNone(self.app._left)
        self.assertIsNotNone(self.app._right)
        self.assertTrue(self.app._left.inner.winfo_children())
        self.assertTrue(self.app._right.inner.winfo_children())
        self.fake_size(int(self.app.S(560)), 800)      # hẹp: 1 cột cuộn chung
        self.assertIsNone(self.app._left)
        self.assertIsNotNone(self.app._single)

    def test_click_marks_owned_and_combo_fit(self):
        self.app._own(toggle=1058)                # Cú Đấm Thần Bí
        self.tick()
        self.assertEqual(self.hub.owned, [1058])
        bay_ong = self.app.cards[3048]

        def texts(w):
            out = [w.cget("text")] if isinstance(w, tk.Label) else []
            for ch in w.winfo_children():
                out += texts(ch)
            return out
        self.assertTrue({"hợp combo A", "◆A"} & set(texts(bay_ong["w"])))   # thẻ hẹp: nhãn rút gọn

    def test_search_augment_shows_extra_card_and_advice(self):
        self.app.search.event_generate("<FocusIn>")
        self.app.search_var.set("get jinxed")       # hạng 15 bậc Vàng (ngoài top 8)
        self.app._light_update()
        self.root.update()
        jinx = next(c for c in self.app.cards.values() if c["fold"] == "get jinxed")
        self.assertEqual(jinx["w"].winfo_manager(), "grid")
        self.assertTrue(self.app.advice_box.winfo_children())

    def test_champion_quick_filter(self):
        self.assertEqual([s for s, _ in self.app.champion_matches("y")], ["yasuo", "yone", "masteryi"])
        self.assertEqual(self.app.champion_matches("master y"), [("masteryi", "Master Yi")])
        self.assertEqual(self.app.champion_matches("ya, yo"), [])    # dấu phẩy = tìm nhiều lõi
        self.app._show_popup(self.app.champion_matches("yo"))
        self.app._popup_pick()
        self.assertEqual(self.hub.focus, "yone")
        self.assertIsNone(self.app._popup)

    def test_main_window_keeps_view_during_offer_by_default(self):
        best = CATALOG[next(iter(CATALOG))]
        cand = {"id": best["id"], "name": best["name"], "winrate": 55.0, "source": "tướng", "fit": None}
        self.hub.adv = [{"slot": 0, "rank": 1, "best": cand, "candidates": [cand]}]
        self.tick()
        self.assertFalse(self.app.advice_box.winfo_children())
        settings.set("app_follow_offer", True)
        self.root.update()
        self.tick()
        self.assertTrue(self.app.advice_box.winfo_children())

    def test_language_and_zoom_rebuild(self):
        settings.set("lang", "en")
        self.root.update()
        self.tick()
        self.assertEqual(self.app.status.cget("text"), "In game: Yasuo")
        settings.set("ui_zoom", 1.3)
        self.root.update()
        self.assertAlmostEqual(self.app.zoom, 1.3)
        self.tick()
        self.assertEqual(len(self.app.cards), 48)

    def test_combo_tab(self):
        self.app._set_tab("combo")
        self.tick()
        self.assertTrue(self.app._single.inner.winfo_children())

    def test_settings_dialog_pages(self):
        self.app.open_settings()
        dlg = self.app._settings_dlg
        for page in ("overlay", "esp32", "general"):
            dlg._go(page)
            self.root.update()
        settings.set("lang", "en")                  # hộp thoại dựng lại theo ngôn ngữ mới
        self.root.update()
        self.assertIn("Settings", dlg.win.title())
        dlg.close()


if __name__ == "__main__":
    unittest.main()

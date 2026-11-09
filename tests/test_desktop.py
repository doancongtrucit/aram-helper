"""Kiểm tra cửa sổ chính dựng được giao diện từ dữ liệu mẫu (không cần mạng, không cần game)."""
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
import fixtures  # noqa: E402
import playaram  # noqa: E402

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
        self.root = tk.Tk()
        self.root.withdraw()
        self.hub = FakeHub()
        self.app = desktop.App(self.root, self.hub)
        self.app._width = 1200
        self.tick()

    def tearDown(self):
        self.root.destroy()

    def tick(self):
        self.app._poll()
        self.root.update()

    def visible_cards(self, rarity):
        return [c for c in self.app.cards.values() if c["rarity"] == rarity and c["w"].winfo_manager() == "grid"]

    def test_three_rows_top8_and_more(self):
        self.assertEqual(len(self.app.cards), 48)
        for r in ("prismatic", "gold", "silver"):
            self.assertEqual(len(self.visible_cards(r)), 8)
        self.app._toggle_more("gold")
        self.tick()
        self.assertEqual(len(self.visible_cards("gold")), 16)
        self.assertEqual(len(self.visible_cards("silver")), 8)

    def test_click_marks_owned_and_combo_fit(self):
        self.app._own(toggle=1058)                # Cú Đấm Thần Bí
        self.tick()
        self.assertEqual(self.hub.owned, [1058])
        bay_ong = self.app.cards[3048]
        texts = [w.cget("text") for w in bay_ong["w"].winfo_children()[0].winfo_children()[1].winfo_children()[1].winfo_children()]
        self.assertIn("hợp combo A", texts)

    def test_search_shows_extra_card_and_advice(self):
        self.app.search.event_generate("<FocusIn>")
        self.app.search_var.set("get jinxed")       # hạng 15 bậc Vàng (ngoài top 8)
        self.app._light_update()
        self.root.update()
        jinx = next(c for c in self.app.cards.values() if c["fold"] == "get jinxed")
        self.assertEqual(jinx["w"].winfo_manager(), "grid")
        self.assertTrue(self.app.advice_box.winfo_children())

    def test_combo_tab(self):
        self.app._set_tab("combo")
        self.tick()
        self.assertTrue(self.app.scroll.inner.winfo_children())


if __name__ == "__main__":
    unittest.main()

# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
"""Parser còn đọc được giao diện HIỆN TẠI của trang nguồn (chỉ chạy khi đã tải trang thật về máy)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))
import fixtures  # noqa: E402
import playaram  # noqa: E402


class RealPages(unittest.TestCase):
    def test_champion_page_structure(self):
        d = playaram.parse_champion_page(fixtures.load_real("yasuo"), "yasuo")
        self.assertTrue(d["name"] and d["tier"] and d["patch"])
        self.assertGreater(d["winrate"], 30)
        self.assertEqual(set(d["augments"]), {"prismatic", "gold", "silver"})
        for items in d["augments"].values():
            self.assertGreaterEqual(len(items), 8)
            self.assertTrue(all(a["winrate"] is not None and a["icon"] for a in items))
        self.assertTrue(d["builds"] and d["builds"][0]["items"])
        self.assertTrue(d["playstyles"] and d["playstyles"][0]["combos"])
        self.assertTrue(d["other_items"] and d["boots"] and d["spells"])

    def test_catalog_structure(self):
        cat = playaram.parse_augment_catalog(fixtures.load_real("augments"))
        self.assertGreater(len(cat), 100)
        self.assertEqual({a["rarity"] for a in cat}, {"prismatic", "gold", "silver"})
        self.assertTrue(all(a["asset"] for a in cat))


if __name__ == "__main__":
    unittest.main()

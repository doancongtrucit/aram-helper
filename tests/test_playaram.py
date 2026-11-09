# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))
import fixtures  # noqa: E402
import playaram  # noqa: E402

FIXTURE = fixtures.load("yasuo")


class ParseChampionPage(unittest.TestCase):
    def setUp(self):
        self.d = playaram.parse_champion_page(FIXTURE, "yasuo")

    def test_header(self):
        self.assertEqual(self.d["name"], "Yasuo")
        self.assertEqual(self.d["tier"], "S+")
        self.assertAlmostEqual(self.d["winrate"], 58.34)
        self.assertEqual(self.d["games"], 34670)
        self.assertEqual(self.d["patch"], "26.22")

    def test_augments_by_rarity(self):
        aug = self.d["augments"]
        self.assertEqual(set(aug), {"prismatic", "gold", "silver"})
        self.assertEqual(len(aug["prismatic"]), 16)
        first = aug["prismatic"][0]
        self.assertEqual(first["id"], 3048)
        self.assertEqual(first["name"], "Bầy Ong Nảy Bật")
        self.assertAlmostEqual(first["winrate"], 71.00)
        self.assertAlmostEqual(first["pickrate"], 1.9)
        self.assertTrue(first["icon"].startswith("https://playaram.gg/"))

    def test_html_entities_unescaped(self):
        names = [a["name"] for a in self.d["augments"]["gold"]]
        self.assertIn("Take'em Down Down Down", names)


class ParseBuildsAndCombos(unittest.TestCase):
    def setUp(self):
        self.d = playaram.parse_champion_page(FIXTURE, "yasuo")

    def test_item_builds(self):
        b = self.d["builds"]
        self.assertEqual(len(b), 3)
        self.assertEqual(b[0]["name"], "Chí mạng · Nghi Thức Suy Vong")
        self.assertAlmostEqual(b[0]["winrate"], 61.64)
        self.assertEqual(b[0]["games"], 171)
        self.assertEqual([i["name"] for i in b[0]["items"] if i["core"]], ["Nghi Thức Suy Vong", "Gươm Suy Vong"])
        self.assertEqual(len(b[0]["items"]), 5)
        self.assertEqual([x["name"] for x in b[0]["boots"]], ["Giày Cuồng Nộ"])
        self.assertEqual([x["name"] for x in b[0]["spells"]], ["Tốc Biến", "Đánh Dấu"])

    def test_playstyles_and_combos(self):
        s = self.d["playstyles"]
        self.assertEqual(len(s), 3)
        self.assertEqual(s[0]["tier"], "S")
        combo = s[0]["combos"][0]
        self.assertEqual(combo["tier"], "S")
        self.assertEqual([(a["id"], a["rarity"]) for a in combo["augments"]],
                         [(1058, "prismatic"), (1018, "prismatic"), (1136, "silver")])
        self.assertIn("Bão Kiếm (Q)", combo["why"])
        self.assertEqual(len(s[0]["tips"]), 4)
        self.assertTrue(s[0]["url"].endswith("/loi-choi/yasuo-loc-xoay-lien-hoan"))

    def test_single_rows(self):
        self.assertEqual(self.d["boots"][0]["name"], "Giày Phàm Ăn")
        self.assertEqual(len(self.d["spells"][0]["icons"]), 2)
        self.assertEqual(len(self.d["other_items"]), 7)


class Slugify(unittest.TestCase):
    def test_slugs(self):
        self.assertEqual(playaram.slugify("game_character_displayname_MonkeyKing"), "monkeyking")
        self.assertEqual(playaram.slugify("DrMundo"), "drmundo")
        self.assertEqual(playaram.slugify("Kai'Sa"), "kaisa")


if __name__ == "__main__":
    unittest.main()

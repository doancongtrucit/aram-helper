# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))
import fixtures  # noqa: E402
import sample_pages  # noqa: E402
import playaram  # noqa: E402

FIXTURE = fixtures.load("yasuo")
SAMPLE = sample_pages.CHAMPION          # dữ liệu mẫu dựng nên trang trên (số liệu tự đặt)


class ParseChampionPage(unittest.TestCase):
    def setUp(self):
        self.d = playaram.parse_champion_page(FIXTURE, "yasuo")

    def test_header(self):
        for key in ("name", "tier", "winrate", "games", "patch", "updated"):
            self.assertEqual(self.d[key], SAMPLE[key], key)
        self.assertTrue(self.d["icon"].startswith("https://playaram.gg/"))

    def test_augments_by_rarity(self):
        aug = self.d["augments"]
        self.assertEqual(set(aug), {"prismatic", "gold", "silver"})
        self.assertEqual(len(aug["prismatic"]), 16)
        first, want = aug["prismatic"][0], SAMPLE["augments"]["prismatic"][0]
        self.assertEqual((first["id"], first["name"]), (3048, "Bầy Ong Nảy Bật"))
        self.assertAlmostEqual(first["winrate"], want["winrate"])
        self.assertAlmostEqual(first["pickrate"], want["pickrate"])
        self.assertTrue(first["icon"].startswith("https://playaram.gg/"))

    def test_html_entities_unescaped(self):
        names = [a["name"] for a in self.d["augments"]["gold"]]
        self.assertIn("Take'em Down Down Down", names)


class ParseBuildsAndCombos(unittest.TestCase):
    def setUp(self):
        self.d = playaram.parse_champion_page(FIXTURE, "yasuo")

    def test_item_builds(self):
        b, want = self.d["builds"], SAMPLE["builds"]
        self.assertEqual(len(b), 3)
        self.assertEqual(b[0]["name"], want[0]["name"])
        self.assertEqual(b[0]["style"], want[0]["style"])
        self.assertAlmostEqual(b[0]["winrate"], want[0]["winrate"])
        self.assertEqual(b[0]["games"], want[0]["games"])
        self.assertEqual([i["name"] for i in b[0]["items"] if i["core"]],
                         [i["name"] for i in want[0]["items"] if i["core"]])
        self.assertEqual(len(b[0]["items"]), 5)
        self.assertEqual([x["name"] for x in b[0]["boots"]], [x["name"] for x in want[0]["boots"]])
        self.assertEqual([x["name"] for x in b[0]["spells"]], ["Tốc Biến", "Đánh Dấu"])
        self.assertEqual(b[0]["with"][0]["name"], want[0]["with"][0]["name"])

    def test_playstyles_and_combos(self):
        s, want = self.d["playstyles"], SAMPLE["playstyles"]
        self.assertEqual(len(s), 3)
        self.assertEqual([x["tier"] for x in s], [x["tier"] for x in want])
        combo = s[0]["combos"][0]
        self.assertEqual(combo["tier"], "S")
        self.assertEqual([(a["id"], a["rarity"]) for a in combo["augments"]],
                         [(a["id"], a["rarity"]) for a in want[0]["combos"][0]["augments"]])
        self.assertIn("(Q)", combo["why"])                   # phím kỹ năng <kbd>Q</kbd> → (Q)
        self.assertEqual(len(s[0]["tips"]), 4)
        self.assertTrue(s[0]["url"].endswith(want[0]["url"]))

    def test_single_rows(self):
        self.assertEqual(self.d["boots"][0]["name"], SAMPLE["boots"][0]["name"])
        self.assertEqual(len(self.d["spells"][0]["icons"]), 2)
        self.assertEqual(len(self.d["other_items"]), 7)


class Slugify(unittest.TestCase):
    def test_slugs(self):
        self.assertEqual(playaram.slugify("game_character_displayname_MonkeyKing"), "monkeyking")
        self.assertEqual(playaram.slugify("DrMundo"), "drmundo")
        self.assertEqual(playaram.slugify("Kai'Sa"), "kaisa")


if __name__ == "__main__":
    unittest.main()

# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
"""Phân tích đội hình địch → gợi ý trang bị (dữ liệu tự dựng, không cần mạng)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import counter_items as ci  # noqa: E402
import ddragon  # noqa: E402


def item(name, tags, gold=3000, armor=0, mr=0, antiheal=False, boots=False):
    return {"name": name, "tags": tags, "gold": gold, "armor": armor, "mr": mr, "antiheal": antiheal, "boots": boots}


DD = {
    "version": "16.22.1",
    "champions": {
        "soraka": {"name": "Soraka", "tags": ["Support", "Mage"], "attack": 2, "magic": 7, "defense": 5},
        "aatrox": {"name": "Aatrox", "tags": ["Fighter"], "attack": 8, "magic": 3, "defense": 4},
        "malphite": {"name": "Malphite", "tags": ["Tank", "Mage"], "attack": 5, "magic": 7, "defense": 9},
        "veigar": {"name": "Veigar", "tags": ["Mage"], "attack": 2, "magic": 10, "defense": 2},
        "lux": {"name": "Lux", "tags": ["Mage", "Support"], "attack": 2, "magic": 9, "defense": 4},
        "jinx": {"name": "Jinx", "tags": ["Marksman"], "attack": 9, "magic": 4, "defense": 2},
    },
    "items": {
        "3031": item("Vô Cực Kiếm", ["Damage", "CriticalStrike"]),
        "3046": item("Ma Vũ Song Kiếm", ["CriticalStrike", "AttackSpeed"]),
        "3033": item("Lời Nhắc Tử Vong", ["Damage", "CriticalStrike", "ArmorPenetration"], antiheal=True),
        "3036": item("Nỏ Thần Dominik", ["Damage", "CriticalStrike", "ArmorPenetration"]),
        "3156": item("Chùy Gai Malmortius", ["SpellBlock", "Damage", "LifeSteal"], mr=40),
        "3165": item("Quỷ Thư Morello", ["Health", "SpellDamage"], antiheal=True),
        "3135": item("Trượng Hư Vô", ["MagicPenetration", "SpellDamage"]),
        "3089": item("Mũ Phù Thủy", ["SpellDamage"]),
        "3075": item("Giáp Gai", ["Health", "Armor"], armor=75, antiheal=True),
        "3143": item("Khiên Randuin", ["Health", "Armor"], armor=75),
        "3111": item("Giày Thủy Ngân", ["Boots", "SpellBlock", "Tenacity"], gold=1250, mr=20, boots=True),
    },
}
CRIT = {"builds": [{"winrate": 60, "items": [{"id": 3031}, {"id": 3046}, {"id": 3036}]}], "other_items": []}
AP = {"builds": [{"winrate": 55, "items": [{"id": 3089}, {"id": 3135}, {"id": 3165}]}], "other_items": []}


def enemy(slug, items=()):
    return {"slug": slug, "champion_name": slug, "items": list(items)}


class CounterItems(unittest.TestCase):
    def test_my_class(self):
        self.assertEqual(ci.my_class(CRIT, DD["items"]), "crit")
        self.assertEqual(ci.my_class(AP, DD["items"]), "ap")
        # món lai Chí mạng + Sức mạnh phép (như Nghi Thức Suy Vong của Yasuo) không làm tướng AD thành AP
        items = dict(DD["items"], **{"123430": item("Nghi Thức", ["CriticalStrike", "SpellDamage"])})
        yasuo = {"builds": [{"items": [{"id": 123430}, {"id": 3031}, {"id": 3036}]},
                            {"items": [{"id": 123430}, {"id": 3031}, {"id": 3046}]}]}
        self.assertEqual(ci.my_class(yasuo, items), "crit")

    def test_healers_and_magic_damage(self):
        team = [enemy("soraka"), enemy("aatrox"), enemy("veigar"), enemy("lux"), enemy("malphite")]
        out = ci.suggest(CRIT, team, DD)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["name"], "Lời Nhắc Tử Vong")              # 2 hồi máu (Soraka, Aatrox)
        self.assertIn("hồi máu", out[0]["why"])
        # 3 khống chế cứng (Lux, Malphite, Veigar) + đa số phép → giày kháng hiệu ứng có kháng phép, gộp 2 lý do
        self.assertEqual(out[1]["name"], "Giày Thủy Ngân")
        self.assertIn("khống chế", out[1]["why"])
        self.assertIn("phép", out[1]["why"])
        self.assertTrue(out[0]["icon"].endswith("/img/item/3033.png"))

    def test_magic_damage_without_cc(self):
        team = [enemy("soraka"), enemy("aatrox"), enemy("lux"), enemy("lux"), enemy("soraka")]
        out = ci.suggest(CRIT, team, DD, my_items=[3111])               # đã có giày → món kháng phép
        self.assertEqual([o["name"] for o in out], ["Lời Nhắc Tử Vong", "Chùy Gai Malmortius"])

    def test_enemy_armor_items_trigger_armor_pen(self):
        team = [enemy("jinx", [3143]), enemy("aatrox", [3075]), enemy("jinx"), enemy("jinx"), enemy("lux")]
        out = ci.suggest(CRIT, team, DD)
        self.assertIn("Nỏ Thần Dominik", [o["name"] for o in out] + ["Lời Nhắc Tử Vong"])
        prof = ci.team_profile(team, DD)
        self.assertEqual(len(prof["armor_stack"]), 2)

    def test_ap_gets_ap_items_and_skips_owned(self):
        team = [enemy("soraka"), enemy("aatrox"), enemy("malphite"), enemy("jinx"), enemy("jinx")]
        out = ci.suggest(AP, team, DD, my_items=[3165])
        names = [o["name"] for o in out]
        self.assertNotIn("Quỷ Thư Morello", names)                        # đã có thì không gợi ý lại
        for o in out:
            self.assertIn("SpellDamage", DD["items"][str(o["item_id"])]["tags"])

    def test_no_enemies(self):
        self.assertEqual(ci.suggest(CRIT, [], DD), [])
        self.assertEqual(ci.summary([], DD), "")

    def test_summary(self):
        s = ci.summary([enemy("soraka"), enemy("aatrox"), enemy("malphite")], DD)
        self.assertIn("2 hồi máu", s)
        self.assertIn("1 đỡ đòn", s)

    def test_trim_ddragon(self):
        raw_items = {
            "3033": {"name": "Lời Nhắc", "tags": ["Damage"], "maps": {"12": True}, "gold": {"purchasable": True, "total": 3000},
                     "description": "<b>Vết Thương Sâu</b> 40%", "stats": {}},
            "1001": {"name": "Giày", "tags": ["Boots"], "maps": {"12": True}, "gold": {"purchasable": True, "total": 300},
                     "into": ["3111"], "description": "", "stats": {}},
            "9999": {"name": "Chỉ ở bản đồ khác", "tags": [], "maps": {"12": False},
                     "gold": {"purchasable": True, "total": 3000}, "description": "", "stats": {}},
        }
        raw_champs = {"Aatrox": {"id": "Aatrox", "name": "Aatrox", "tags": ["Fighter"],
                                 "info": {"attack": 8, "magic": 3, "defense": 4}}}
        raw_items["773114"] = dict(raw_items["3033"], name="Món chế độ khác")     # nhóm 77xxxx bị loại
        raw_items["223011"] = dict(raw_items["3033"], name="Món ARAM")            # nhóm 22xxxx được giữ
        t = ddragon.trim("16.22.1", raw_champs, raw_items)
        self.assertEqual(set(t["items"]), {"3033", "223011"})
        self.assertTrue(t["items"]["3033"]["antiheal"])
        self.assertEqual(t["champions"]["aatrox"]["attack"], 8)


if __name__ == "__main__":
    unittest.main()

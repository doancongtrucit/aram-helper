import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))
import fixtures  # noqa: E402
import advice  # noqa: E402
import playaram  # noqa: E402

HERE = Path(__file__).parent
CHAMP = playaram.parse_champion_page(fixtures.load("yasuo"), "yasuo")
CATALOG = {a["id"]: a for a in playaram.parse_augment_catalog(fixtures.load("augments"))}
CU_DAM, BAY_ONG, KHONG_NHAN, RUT_KIEM = 1058, 3048, 1018, 1134


class Advice(unittest.TestCase):
    def test_combo_fit_with_owned(self):
        fit = advice.combo_fit(CHAMP, {CU_DAM})
        self.assertEqual(fit[KHONG_NHAN], "S")      # Cú Đấm + Khổng Nhân + Quăng Quật: combo S
        self.assertEqual(fit[BAY_ONG], "A")
        self.assertNotIn(CU_DAM, fit)
        self.assertEqual(advice.combo_fit(CHAMP, set()), {})

    def test_score_sources(self):
        s = advice.score(BAY_ONG, CHAMP, CATALOG, set())
        self.assertEqual((s["source"], s["winrate"], s["score"]), ("tướng", 71.0, 71.0))
        g = advice.score(RUT_KIEM, CHAMP, CATALOG, set())      # không có trong top 16 của Yasuo
        self.assertEqual(g["source"], "chung")
        self.assertAlmostEqual(g["score"], CHAMP["winrate"] + CATALOG[RUT_KIEM]["winrate"] - 50, places=2)

    def test_rank_offer(self):
        res = advice.rank_offer([[KHONG_NHAN], [BAY_ONG], [RUT_KIEM]], CHAMP, CATALOG, {CU_DAM})
        self.assertEqual([r["slot"] for r in res], [0, 1, 2])          # giữ thứ tự ô trên màn hình
        best = min(res, key=lambda r: r["rank"])
        self.assertEqual(best["best"]["id"], BAY_ONG)                  # 71% + 3 (combo A)
        self.assertEqual(best["best"]["fit"], "A")

    def test_offer_combos_prefers_owned_partner(self):
        # Đang được đưa ra Bầy Ong + Khổng Nhân, đã có Cú Đấm Thần Bí
        res = advice.offer_combos(CHAMP, [BAY_ONG, KHONG_NHAN, RUT_KIEM], {CU_DAM})
        self.assertLessEqual(len(res), 3)
        self.assertTrue(res)
        top = res[0]
        self.assertGreaterEqual(top["owned_count"], 1)                       # combo dùng được lõi đã có lên đầu
        self.assertEqual(top["tier"], "S")                                   # Cú Đấm + Khổng Nhân + Quăng Quật
        self.assertIn(KHONG_NHAN, top["offered"])
        flags = {a["id"]: (a["offered"], a["owned"]) for a in top["augments"]}
        self.assertEqual(flags[CU_DAM], (False, True))
        self.assertEqual(flags[KHONG_NHAN], (True, False))
        for c in res:                                                        # combo nào cũng chứa lõi đang được đưa ra
            self.assertTrue(c["offered"])

    def test_offer_combos_none_when_unrelated(self):
        self.assertEqual(advice.offer_combos(CHAMP, [RUT_KIEM], set()), [])

    def test_ambiguous_slot_picks_best_candidate(self):
        res = advice.rank_offer([[RUT_KIEM, BAY_ONG]], CHAMP, CATALOG, set())
        self.assertEqual(res[0]["best"]["id"], BAY_ONG)
        self.assertEqual(len(res[0]["candidates"]), 2)


if __name__ == "__main__":
    unittest.main()

import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
import fixtures  # noqa: E402
sys.path.insert(0, str(Path(__file__).parent))

import ocr  # noqa: E402
import playaram  # noqa: E402

FIXTURE = fixtures.load("augments")
CATALOG = playaram.parse_augment_catalog(FIXTURE)
BY_NAME = {a["name"]: a["id"] for a in CATALOG}
RARITY = {a["id"]: a["rarity"] for a in CATALOG}


class AugmentCatalog(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(len(CATALOG), 226)
        first = CATALOG[0]
        self.assertEqual(first["name"], "Phong Ngôn Chúc Phúc")
        self.assertEqual(first["tier"], "S+")
        self.assertEqual(first["rarity"], "prismatic")
        self.assertEqual(first["asset"], "assets/ux/cherry/augments/icons/windspeakersblessing_large.png")


class OcrMatching(unittest.TestCase):
    def test_fold(self):
        self.assertEqual(ocr.fold("Chiến Hoặc Chuồn!"), "chien hoac chuon")
        self.assertEqual(ocr.fold("Đánh Nhừ Tử"), "danh nhu tu")

    def test_best_name_from_garbled_ocr(self):
        cands = {1: "Chiến Hoặc Chuồn", 2: "Vỏ Bọc Bảo Hộ", 3: "Yêu Tinh"}
        self.assertEqual(ocr.best_name(["Chién Hoäc Chubn"], cands)[0], 1)
        self.assertEqual(ocr.best_name(["Lorem ipsum", "Vo Boc Båo Hô dolor"], cands)[0], 2)

    def test_best_name_unsure(self):
        self.assertIsNone(ocr.best_name(["xyz"], {1: "Hút", 2: "Tăng Cường"})[0])
        self.assertIsNone(ocr.best_name([], {1: "Hút"})[0])


try:
    import cv2  # noqa: F401
    import screen_scan as ss
    HAS_CV = (ss.ICON_DIR / f"{CATALOG[0]['id']}.png").exists()
except Exception:
    HAS_CV = False


class ResolveRarity(unittest.TestCase):
    @unittest.skipUnless(HAS_CV, "cần opencv")
    def test_filters_shared_icon_by_round_rarity(self):
        # Tìm 2 lõi dùng chung file icon nhưng khác độ hiếm
        by_asset = {}
        for a in CATALOG:
            by_asset.setdefault(a["asset"], []).append(a)
        pair = next([g[0], b] for g in by_asset.values() for b in g[1:] if b["rarity"] != g[0]["rarity"])
        want, other = pair
        uniq = [a for a in CATALOG if a["rarity"] == want["rarity"] and len(by_asset[a["asset"]]) == 1][:2]
        res = [{"id": other["id"], "candidates": [other["id"], want["id"]], "score": 0.9, "second": 0.5}] + \
              [{"id": a["id"], "candidates": [a["id"]], "score": 0.9, "second": 0.5} for a in uniq]
        out = ss.resolve_rarity(res, RARITY)
        self.assertEqual(out[0]["candidates"], [want["id"]])


@unittest.skipUnless(HAS_CV, "cần opencv và icon đã tải (python screen_scan.py icons)")
class DetectSynthetic(unittest.TestCase):
    """Ảnh giả lập bảng chọn lõi (không phải ảnh game thật)."""

    @classmethod
    def setUpClass(cls):
        from synthetic import make_screen
        cls.make = staticmethod(make_screen)
        cls.icons = ss.load_icons(CATALOG)
        cls.names = {a["id"]: a["name"] for a in CATALOG}
        first = make_screen(cls.icons, [BY_NAME["Rút Kiếm Ra"], BY_NAME["Cú Đấm Thần Bí"], BY_NAME["Bầy Ong Nảy Bật"]],
                            "prismatic", seed=1)
        cls.calib = ss.calibrate(first, cls.icons, log=lambda *_: None)

    def test_calibration_finds_three_icons(self):
        self.assertIsNotNone(self.calib)
        xs = [c[0] for c in self.calib.centers]
        for got, want in zip(xs, (660, 960, 1260)):
            self.assertLess(abs(got - want), 8)
        self.assertLess(abs(self.calib.size - 128), 10)

    def test_detects_offers_with_names(self):
        bank = ss.bank_for(self.icons)
        rng = random.Random(3)
        by_r = {}
        for a in CATALOG:
            by_r.setdefault(a["rarity"], []).append(a["id"])
        for i in range(10):
            r = rng.choice(sorted(by_r))
            offer = rng.sample(by_r[r], 3)
            img = self.make(self.icons, offer, r, seed=50 + i, names=self.names)
            res = ss.read_offer(img, self.calib, bank, CATALOG)
            self.assertTrue(ss.confident(res))
            for slot, want in zip(res, offer):
                self.assertIn(want, slot["candidates"])


if __name__ == "__main__":
    unittest.main()

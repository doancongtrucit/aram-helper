# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
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
    HAS_SS = True
    HAS_CV = (ss.ICON_DIR / f"{CATALOG[0]['id']}.png").exists()
except Exception:
    HAS_SS = HAS_CV = False


class EstimatedPosition(unittest.TestCase):
    """Vị trí bảng lõi ước tính theo độ phân giải (khi chưa định vị) – so với số đo trên game thật."""

    @unittest.skipUnless(HAS_SS, "cần opencv")
    def test_matches_measured_1440p(self):
        est = ss.Calibration.estimate(2560, 1440)
        self.assertTrue(est.estimated)
        self.assertLess(abs(est.size - 215), 3)
        for (x, y), (mx, my) in zip(est.centers, [(792, 416), (1280, 416), (1771, 416)]):
            self.assertLess(abs(x - mx), 6)
            self.assertLess(abs(y - my), 3)

    @unittest.skipUnless(HAS_SS, "cần opencv")
    def test_fits_same_aspect_only(self):
        c = ss.Calibration(2560, 1440, 215, [(792, 416), (1280, 416), (1771, 416)])
        self.assertTrue(c.fits(1920, 1080))          # cùng 16:9 → tự co giãn
        self.assertFalse(c.fits(2560, 1080))         # 21:9 → dùng vị trí ước tính




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


@unittest.skipUnless(HAS_CV, "cần opencv và icon đã tải (chạy app một lần)")
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

    def test_wide_search_recovers_shifted_cards(self):
        """Thẻ lõi xê dịch ~20% cỡ icon so với lúc hiệu chỉnh: dò thường trượt, dò rộng tìm lại và dời tâm."""
        bank = ss.bank_for(self.icons)
        offer = [BY_NAME["Rút Kiếm Ra"], BY_NAME["Cú Đấm Thần Bí"], BY_NAME["Bầy Ong Nảy Bật"]]
        img = self.make(self.icons, offer, "prismatic", seed=9, names=self.names)
        import numpy as np
        shift = 26                                            # px, ~20% của icon 128 px
        moved = np.roll(img, (shift, -shift), axis=(0, 1))    # xuống 26, sang trái 26
        normal = ss.read_offer(moved, self.calib, bank, CATALOG)
        wide = ss.read_offer(moved, self.calib, bank, CATALOG, shift=ss.WIDE_SHIFT)
        self.assertFalse(ss.confident(normal))
        self.assertTrue(ss.confident(wide))
        for slot, want in zip(wide, offer):
            self.assertIn(want, slot["candidates"])
        fixed = ss.recenter(self.calib, wide, (1920, 1080))
        for (x0, y0), (x1, y1) in zip(self.calib.centers, fixed.centers):
            self.assertLess(abs((x1 - x0) + shift), 8)
            self.assertLess(abs((y1 - y0) - shift), 8)
        self.assertTrue(ss.confident(ss.read_offer(moved, fixed, bank, CATALOG)))

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

    @unittest.skipUnless(ocr.installed(), "cần OCR của Windows")
    def test_champion_ability_augment_read_by_name(self):
        """Lõi kỹ năng tướng: icon trong game là kỹ năng của tướng (không có icon mẫu) → đọc bằng tên."""
        import numpy as np
        bank = ss.bank_for(self.icons)
        known = [BY_NAME["Rút Kiếm Ra"], BY_NAME["Cú Đấm Thần Bí"]]
        target = next(a["id"] for a in CATALOG if a["rarity"] == "prismatic" and a["id"] not in known
                      and len(a["name"]) > 8)
        icons = dict(self.icons)
        rng = np.random.default_rng(5)
        fake = np.zeros_like(icons[target])                      # icon lạ: không giống icon nào trong bộ mẫu
        fake[..., :3] = rng.integers(0, 255, fake[..., :3].shape)
        fake[..., 3] = 255
        icons[target] = fake
        offer = known + [target]
        img = self.make(icons, offer, "prismatic", seed=21, names=self.names)
        res = ss.read_offer(img, self.calib, bank, CATALOG)
        self.assertFalse(ss.slot_ok(res[2]))
        self.assertTrue(res[2].get("by_name"))
        self.assertEqual(res[2]["id"], target)
        self.assertTrue(ss.confident(res))

    def test_calibrates_with_one_unknown_icon(self):
        """Hiệu chỉnh khi 1 ô là lõi kỹ năng tướng: thấy 2 icon, suy ra ô thứ 3."""
        import numpy as np
        known = [BY_NAME["Rút Kiếm Ra"], BY_NAME["Cú Đấm Thần Bí"]]
        target = BY_NAME["Bầy Ong Nảy Bật"]
        icons = dict(self.icons)
        fake = np.zeros_like(icons[target])
        fake[..., 3] = 255
        icons[target] = fake
        img = self.make(icons, [known[0], target, known[1]], "prismatic", seed=4)
        calib = ss.calibrate(img, self.icons, log=lambda *_: None)
        self.assertIsNotNone(calib)
        for got, want in zip([c[0] for c in calib.centers], (660, 960, 1260)):
            self.assertLess(abs(got - want), 12)


if __name__ == "__main__":
    unittest.main()

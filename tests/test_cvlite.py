# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
"""cvlite (thay OpenCV trong bản cài) phải cho kết quả như OpenCV thật ở mọi chỗ bộ quét dùng.
OpenCV chỉ cài khi phát triển (requirements-dev.txt); thiếu thì bỏ qua phần so sánh."""
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import cvlite  # noqa: E402

try:
    import cv2
except ImportError:          # pragma: no cover
    cv2 = None

RNG = np.random.default_rng(7)


def _img(h, w, c=3):
    return RNG.integers(0, 256, (h, w, c) if c else (h, w), dtype=np.uint8)


class Basics(unittest.TestCase):
    def test_png_roundtrip_keeps_bgr_and_alpha(self):
        im = _img(9, 13, 4)
        ok, buf = cvlite.imencode(".png", im)
        self.assertTrue(ok)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "ảnh thử.png"                    # đường dẫn có dấu
            buf.tofile(str(p))
            np.testing.assert_array_equal(cvlite.imread(str(p), cvlite.IMREAD_UNCHANGED), im)
            np.testing.assert_array_equal(cvlite.imdecode(np.fromfile(str(p), np.uint8), cvlite.IMREAD_COLOR),
                                          im[..., :3])
        self.assertIsNone(cvlite.imread("khong-co.png"))

    def test_resize_shapes(self):
        self.assertEqual(cvlite.resize(_img(100, 80, 4), (40, 50), interpolation=cvlite.INTER_AREA).shape, (50, 40, 4))
        self.assertEqual(cvlite.resize(_img(30, 20, 0), None, fx=2, fy=2, interpolation=cvlite.INTER_CUBIC).shape, (60, 40))
        f = cvlite.resize(RNG.random((64, 64, 3)).astype(np.float32), (40, 40), interpolation=cvlite.INTER_AREA)
        self.assertEqual((f.shape, f.dtype), ((40, 40, 3), np.float32))

    def test_match_template_finds_patch(self):
        img = RNG.random((120, 160))
        t = img[40:60, 70:95].copy()
        r = cvlite.matchTemplate(img.astype(np.float32), t.astype(np.float32), cvlite.TM_CCOEFF_NORMED)
        self.assertEqual(np.unravel_index(np.nanargmax(r), r.shape), (40, 70))
        self.assertAlmostEqual(float(np.nanmax(r)), 1.0, places=4)


@unittest.skipIf(cv2 is None, "cần opencv-python-headless (requirements-dev.txt) để so sánh")
class SameAsOpenCV(unittest.TestCase):
    def test_gray_is_exact(self):
        im = _img(37, 53)
        np.testing.assert_array_equal(cvlite.cvtColor(im, cvlite.COLOR_BGR2GRAY), cv2.cvtColor(im, cv2.COLOR_BGR2GRAY))

    def test_hsv_saturation(self):
        im = _img(40, 40)
        a = cvlite.cvtColor(im, cvlite.COLOR_BGR2HSV).astype(int)
        b = cv2.cvtColor(im, cv2.COLOR_BGR2HSV).astype(int)
        self.assertLessEqual(np.abs(a[..., 1] - b[..., 1]).max(), 1)      # bộ quét chỉ dùng độ bão hoà
        self.assertLessEqual(np.abs(a[..., 2] - b[..., 2]).max(), 0)

    def test_area_downscale_close(self):
        for src, dst in (((256, 256, 4), (64, 64)), ((215, 215, 3), (46, 46)), ((1440, 2560, 3), (400, 225)),
                         ((64, 64, 4), (32, 32))):
            im = RNG.integers(0, 256, src, dtype=np.uint8)
            a = cvlite.resize(im, dst, interpolation=cvlite.INTER_AREA).astype(int)
            b = cv2.resize(im, dst, interpolation=cv2.INTER_AREA).astype(int)
            self.assertLessEqual(np.abs(a - b).max(), 1, (src, dst))
            self.assertLess(np.abs(a - b).mean(), 0.05, (src, dst))
        f = RNG.random((60, 60, 3)).astype(np.float32)
        a = cvlite.resize(f, (46, 46), interpolation=cvlite.INTER_AREA)
        b = cv2.resize(f, (46, 46), interpolation=cv2.INTER_AREA)
        self.assertLess(np.abs(a - b).max(), 1e-4)

    def test_masked_match_template(self):
        img = RNG.random((150, 200)).astype(np.float32) * 255
        t = img[30:56, 100:126].copy()
        m = (RNG.random(t.shape) > 0.3).astype(np.float32)
        a = cvlite.matchTemplate(img, t, cvlite.TM_CCOEFF_NORMED, mask=m)
        b = cv2.matchTemplate(img, t, cv2.TM_CCOEFF_NORMED, mask=m)
        self.assertEqual(a.shape, b.shape)
        ok = np.isfinite(a) & np.isfinite(b)
        self.assertGreater(ok.mean(), 0.99)
        self.assertLess(np.abs(a[ok] - b[ok]).max(), 2e-3)


if __name__ == "__main__":
    unittest.main()

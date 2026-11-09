"""Tuỳ chọn (settings.json) và chuỗi Anh / Việt."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import i18n  # noqa: E402
import localize  # noqa: E402
import settings  # noqa: E402


class SettingsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "settings.json"
        settings._reset_for_tests(self.path)

    def tearDown(self):
        settings._reset_for_tests(settings.PATH)
        self.tmp.cleanup()

    def test_defaults_persist_and_notify(self):
        self.assertEqual(settings.get("lang"), "vi")
        seen = []
        settings.on_change(seen.append)
        settings.set("ov_opacity", 0.5)
        settings.set("ov_opacity", 0.5)             # không đổi → không báo lần 2
        self.assertEqual(seen, [{"ov_opacity": 0.5}])
        settings._reset_for_tests(self.path)        # đọc lại từ file
        self.assertEqual(settings.get("ov_opacity"), 0.5)
        settings.set("unknown_key", 1)
        self.assertIsNone(settings.get("unknown_key"))

    def test_reset(self):
        settings.set_many({"top_n": 5, "lang": "en"})
        settings.reset(["top_n"])
        self.assertEqual(settings.get("top_n"), 0)
        self.assertEqual(settings.get("lang"), "en")

    def test_translate(self):
        self.assertEqual(i18n.T("Thắng {wr}%", wr=55), "Thắng 55%")
        settings.set("lang", "en")
        self.assertEqual(i18n.T("Thắng {wr}%", wr=55), "Win 55%")
        self.assertEqual(i18n.T("chuỗi chưa dịch"), "chuỗi chưa dịch")
        self.assertEqual(i18n.ddragon_locale(), "en_US")

    def test_scanner_status(self):
        s = "Đang quét… (chưa thấy bảng chọn lõi · khớp tốt nhất 0.31)"
        self.assertEqual(i18n.status(s), s)
        settings.set("lang", "en")
        self.assertEqual(i18n.status(s), "Scanning… (no augment choice yet · best match 0.31)")
        self.assertEqual(i18n.status("Sẵn sàng."), "Ready.")

    def test_localize_catalog(self):
        cat = {1: {"id": 1, "name": "Cú Đấm Thần Bí", "rarity": "gold"}, 2: {"id": 2, "name": "Lõi lạ"}}
        out = localize.catalog(cat, "en", {1: "Mystic Punch"})
        self.assertEqual(out[1]["name"], "Mystic Punch")
        self.assertEqual(out[2]["name"], "Lõi lạ")             # chưa có tên tiếng Anh: giữ tên gốc
        self.assertEqual(cat[1]["name"], "Cú Đấm Thần Bí")     # không sửa dữ liệu gốc
        self.assertIs(localize.catalog(cat, "vi", {}), cat)


if __name__ == "__main__":
    unittest.main()

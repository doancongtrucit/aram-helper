# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
"""Gói báo lỗi: đủ file cần thiết, che thông tin cá nhân, không mang theo file cấu hình lạ."""
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import paths  # noqa: E402
import report  # noqa: E402


class BugReport(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.data, self.out = root / "data", root / "out"
        (self.data / "debug").mkdir(parents=True)
        home = str(Path.home())
        (self.data / "app.log").write_text(f"mở {home}\\cache\\x\nkết nối 10.20.30.40:4210\nok 127.0.0.1\n",
                                           encoding="utf-8")
        (self.data / "calibration.json").write_text('{"width": 2560}', encoding="utf-8")
        (self.data / "secret.json").write_text('{"token": "secret"}', encoding="utf-8")
        for i in range(15):
            (self.data / "debug" / f"shot{i:02}.png").write_bytes(b"\x89PNG fake")
            (self.data / "debug" / f"shot{i:02}.json").write_text('{"note": "x"}', encoding="utf-8")
        self.patch = mock.patch.object(paths, "DATA", self.data)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_bundle_contents_and_privacy(self):
        path = report.make_bundle(self.out, extra={"scan_status": "Sẵn sàng."})
        self.assertTrue(path.name.startswith("ARAM-Helper-bug-report-") and path.suffix == ".zip")
        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())
            self.assertIn("system.json", names)
            self.assertIn("app.log", names)
            self.assertIn("calibration.json", names)
            self.assertNotIn("secret.json", names)                      # chỉ gom file trong danh sách cho phép
            self.assertEqual(len([n for n in names if n.endswith(".png")]), report.MAX_DEBUG)
            log = z.read("app.log").decode("utf-8")
            self.assertNotIn(str(Path.home()), log)
            self.assertNotIn("10.20.30.40", log)
            self.assertIn("x.x.x.x", log)
            self.assertIn("127.0.0.1", log)                             # địa chỉ máy mình giữ nguyên
            info = json.loads(z.read("system.json").decode("utf-8"))
            self.assertEqual(info["scan_status"], "Sẵn sàng.")
            self.assertIn("app_version", info)

    def test_sanitize_username(self):
        with mock.patch.object(report, "_secrets", return_value=["C:\\Users\\alice", "alice"]):
            self.assertEqual(report.sanitize("C:\\Users\\alice\\x alice 10.0.0.2"), "~\\x <user> x.x.x.x")


if __name__ == "__main__":
    unittest.main()

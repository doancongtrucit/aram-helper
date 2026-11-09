# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
"""Kiểm tra bản mới: so số phiên bản, đọc GitHub (giả lập), nhớ kết quả 1 ngày."""
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import paths  # noqa: E402
import updater  # noqa: E402


class UpdaterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = mock.patch.object(updater, "STATE", Path(self.tmp.name) / "update.json")
        self.state.start()

    def tearDown(self):
        self.state.stop()
        self.tmp.cleanup()

    def test_compare(self):
        self.assertTrue(updater.newer("v1.2.0", "1.1.9"))
        self.assertTrue(updater.newer("v1.10", "1.9.3"))
        self.assertFalse(updater.newer("v1.1.0", "1.1.0"))
        self.assertFalse(updater.newer("", "1.0"))

    def fake(self, tag):
        body = json.dumps({"tag_name": tag, "html_url": "https://example.invalid/r"}).encode()
        return mock.patch("urllib.request.urlopen", return_value=io.BytesIO(body))

    def test_check_and_cache(self):
        with self.fake("v99.0.0") as op:
            self.assertEqual(updater.check()["version"], "v99.0.0")
            self.assertEqual(updater.check()["version"], "v99.0.0")   # lần 2 dùng kết quả đã nhớ
            self.assertEqual(op.call_count, 1)
        with self.fake("v0.0.1"):
            self.assertIsNone(updater.check(force=True))

    def test_network_error_is_quiet(self):
        with mock.patch("urllib.request.urlopen", side_effect=OSError("offline")):
            self.assertIsNone(updater.check(force=True))

    def test_data_dir(self):
        self.assertTrue(str(paths.DATA))
        with mock.patch.dict("os.environ", {"ARAM_HELPER_DATA": self.tmp.name}):
            self.assertEqual(paths._data_dir(), Path(self.tmp.name))
        with mock.patch.object(paths, "FROZEN", True), mock.patch.dict("os.environ", {"LOCALAPPDATA": self.tmp.name}):
            import os
            os.environ.pop("ARAM_HELPER_DATA", None)          # khôi phục khi thoát patch.dict
            if sys.platform == "win32":
                self.assertEqual(paths._data_dir(), Path(self.tmp.name) / "ARAM Helper")


if __name__ == "__main__":
    unittest.main()

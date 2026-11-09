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

    def test_status_states(self):
        with self.fake("v99.0.0"):
            self.assertEqual(updater.status(force=True)[0], "new")
        with self.fake("v0.0.1"):
            self.assertEqual(updater.status(force=True), ("latest", None))
        with mock.patch("urllib.request.urlopen", side_effect=OSError("offline")):
            self.assertEqual(updater.status(force=True), ("error", None))

    def test_parse_sums(self):
        h = "ab" * 32
        sums = updater.parse_sums(f"{h}  ARAM-Helper-Setup.exe\n{h.upper()} *other.zip\nrác\n")
        self.assertEqual(sums, {"ARAM-Helper-Setup.exe": h, "other.zip": h})

    def test_can_self_update(self):
        exe = Path(self.tmp.name) / "ARAM Helper.exe"
        exe.write_bytes(b"")
        with mock.patch.object(updater.sys, "platform", "win32"):
            self.assertFalse(updater.can_self_update(str(exe)))          # bản portable: không có trình gỡ cài
            (Path(self.tmp.name) / "unins000.exe").write_bytes(b"")
            self.assertTrue(updater.can_self_update(str(exe)))
        with mock.patch.object(updater.sys, "platform", "darwin"):
            self.assertFalse(updater.can_self_update(str(exe)))

    def _prepare(self, payload: bytes, sums_for: bytes):
        import hashlib
        sums = f"{hashlib.sha256(sums_for).hexdigest()}  {updater.SETUP}\n"

        def download(url, dest, progress=None, timeout=30):
            self.assertTrue(url.endswith("/v9.9.9/" + updater.SETUP))
            dest.write_bytes(payload)
            if progress:
                progress(len(payload), len(payload))
        seen = []
        with mock.patch.object(updater, "update_dir", return_value=Path(self.tmp.name) / "upd"), \
                mock.patch.object(updater, "_read_url", return_value=sums), \
                mock.patch.object(updater, "_download", side_effect=download):
            return updater.prepare("v9.9.9", lambda d, t: seen.append(d)), seen

    def test_prepare_verifies_hash(self):
        path, seen = self._prepare(b"installer", b"installer")
        self.assertEqual(path.read_bytes(), b"installer")
        self.assertEqual(seen, [9])
        cmd = updater.install_command(path)
        self.assertIn("/VERYSILENT", cmd)
        self.assertIn("/RELAUNCH=1", cmd)

    def test_prepare_rejects_bad_hash(self):
        with self.assertRaises(updater.UpdateError):
            self._prepare(b"tampered", b"installer")
        self.assertFalse(any((Path(self.tmp.name) / "upd").glob("*.exe")))   # file sai đã bị xoá

    def test_prepare_needs_checksum(self):
        with mock.patch.object(updater, "_read_url", return_value="nothing here"), \
                self.assertRaises(updater.UpdateError):
            updater.prepare("v9.9.9")

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

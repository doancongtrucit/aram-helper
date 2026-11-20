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

    TEST_SK = bytes(range(32))                       # khoá thử, chỉ dùng trong test

    def _signed(self, sums: str, sk: bytes | None = None):
        """Giả lập máy chủ: SHA256SUMS.txt (bytes) + chữ ký; khoá công khai của app đổi thành khoá thử."""
        import ed25519
        sig = ed25519.sign(sk or self.TEST_SK, sums.encode()).hex()
        return (mock.patch.object(updater, "SIGNING_KEY", ed25519.public_key(self.TEST_SK).hex()),
                mock.patch.object(updater, "_read_bytes", return_value=sums.encode()),
                mock.patch.object(updater, "_read_url", return_value=sig))

    def _prepare(self, payload: bytes, sums_for: bytes, sk: bytes | None = None):
        import hashlib
        sums = f"{hashlib.sha256(sums_for).hexdigest()}  {updater.SETUP}\n"

        def download(url, dest, progress=None, timeout=30):
            self.assertTrue(url.endswith("/v9.9.9/" + updater.SETUP))
            dest.write_bytes(payload)
            if progress:
                progress(len(payload), len(payload))
        seen = []
        key, sums_p, sig_p = self._signed(sums, sk)
        with mock.patch.object(updater, "update_dir", return_value=Path(self.tmp.name) / "upd"), \
                key, sums_p, sig_p, mock.patch.object(updater, "_download", side_effect=download):
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
        key, sums_p, sig_p = self._signed("nothing here")
        with key, sums_p, sig_p, self.assertRaises(updater.UpdateError) as cm:
            updater.prepare("v9.9.9")
        self.assertEqual(cm.exception.kind, "no_entry")

    def test_prepare_rejects_wrong_signature(self):
        with self.assertRaises(updater.UpdateError) as cm:
            self._prepare(b"installer", b"installer", sk=bytes(32))     # ký bằng khoá khác
        self.assertEqual(cm.exception.kind, "signature")
        self.assertFalse(any((Path(self.tmp.name) / "upd").glob("*.exe")))

    def test_prepare_rejects_missing_signature(self):
        key, sums_p, _ = self._signed("x")
        with key, sums_p, mock.patch.object(updater, "_read_url", side_effect=OSError("404")), \
                self.assertRaises(updater.UpdateError) as cm:
            updater.prepare("v9.9.9")
        self.assertEqual(cm.exception.kind, "signature")

    def test_real_public_key_is_valid(self):
        import ed25519
        self.assertEqual(len(bytes.fromhex(updater.SIGNING_KEY)), 32)
        self.assertIsNotNone(ed25519._decompress(bytes.fromhex(updater.SIGNING_KEY)))
        self.assertFalse(updater.signature_ok(b"x", "00" * 64))

    def test_ed25519_rfc8032_vector(self):
        import ed25519
        sk = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
        pk = ed25519.public_key(sk)
        self.assertEqual(pk.hex(), "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
        sig = ed25519.sign(sk, b"")
        self.assertEqual(sig.hex()[:32], "e5564300c360ac729086e2cc806e828a")
        self.assertTrue(ed25519.verify(pk, b"", sig))
        self.assertFalse(ed25519.verify(pk, b"x", sig))
        self.assertFalse(ed25519.verify(pk, b"", sig[:-1] + bytes([sig[-1] ^ 1])))

    def test_failed_check_keeps_cached_release(self):
        with self.fake("v99.0.0"):
            updater.check(force=True)
        with mock.patch("urllib.request.urlopen", side_effect=OSError("offline")):
            self.assertEqual(updater.status(force=True)[0], "new")     # vẫn nhớ bản mới đã thấy
        st = json.loads(updater.STATE.read_text(encoding="utf-8"))
        self.assertLess(st["checked"], __import__("time").time() - updater.EVERY + 700)   # thử lại sau ~10 phút

    class Resp(io.BytesIO):
        def __init__(self, body, url="https://objects.example.invalid/x", length=True):
            super().__init__(body)
            self.headers = {"Content-Length": str(len(body))} if length else {}
            self._url = url

        def geturl(self):
            return self._url

    def test_download_progress_and_part_file(self):
        dest = Path(self.tmp.name) / "setup.exe"
        seen = []
        with mock.patch("urllib.request.urlopen", return_value=self.Resp(b"x" * 200_000)):
            updater._download("https://example.invalid/s", dest, lambda d, t: seen.append((d, t)))
        self.assertEqual(dest.stat().st_size, 200_000)
        self.assertEqual(seen[-1], (200_000, 200_000))
        self.assertFalse(dest.with_suffix(".exe.part").exists())

    def test_download_rejects_http_and_cleans_up(self):
        dest = Path(self.tmp.name) / "setup.exe"
        with mock.patch("urllib.request.urlopen", return_value=self.Resp(b"abc", url="http://evil.invalid/x")), \
                self.assertRaises(updater.UpdateError) as cm:
            updater._download("https://example.invalid/s", dest)
        self.assertEqual(cm.exception.kind, "insecure")
        self.assertFalse(dest.exists() or dest.with_suffix(".exe.part").exists())

    def test_bad_version_and_messages(self):
        for bad in ("", "latest", "v1.0/../../x", "v1.2.3-rc"):
            with self.assertRaises(updater.UpdateError):
                updater.prepare(bad)
        self.assertEqual(updater.describe(updater.UpdateError("mismatch")), "mã băm bộ cài không khớp – đã huỷ")
        self.assertEqual(updater.describe(ValueError("x")), "x")

    def test_prepare_removes_old_installers(self):
        old = Path(self.tmp.name) / "upd"
        old.mkdir()
        (old / "ARAM-Helper-1.0.0-Setup.exe").write_bytes(b"old")
        (old / "ARAM-Helper-9.9.9-Setup.exe.part").write_bytes(b"half")
        path, _ = self._prepare(b"installer", b"installer")
        self.assertEqual(sorted(p.name for p in old.iterdir()), [path.name])

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

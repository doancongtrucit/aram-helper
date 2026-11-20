# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
"""Khay hệ thống + mở cùng Windows + giới hạn bộ nhớ đệm tướng."""
import os
import queue
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))
import autostart  # noqa: E402
import playaram  # noqa: E402
import settings  # noqa: E402
from test_desktop import HAS_TK, FakeHub  # noqa: E402

WIN = sys.platform == "win32"


@unittest.skipUnless(WIN, "chỉ Windows")
class Autostart(unittest.TestCase):
    """Ghi vào khoá thử riêng (không đụng khoá Run thật) + thư mục Startup giả."""

    def setUp(self):
        import winreg
        self.winreg = winreg
        self.tmp = tempfile.TemporaryDirectory()
        self.patches = [mock.patch.object(autostart, "RUN_KEY", r"Software\ARAMHelperTest\Run"),
                        mock.patch.dict(os.environ, {"APPDATA": self.tmp.name})]
        for p in self.patches:
            p.start()
        self.lnk = autostart._legacy_shortcut()

    def tearDown(self):
        autostart.set_enabled(False)
        for p in self.patches:
            p.stop()
        for k in (r"Software\ARAMHelperTest\Run", r"Software\ARAMHelperTest"):
            try:
                self.winreg.DeleteKey(self.winreg.HKEY_CURRENT_USER, k)
            except OSError:
                pass
        self.tmp.cleanup()

    def test_enable_disable(self):
        self.assertFalse(autostart.is_enabled())
        self.assertTrue(autostart.set_enabled(True))
        self.assertIn("--minimized", autostart._read())
        self.assertFalse(autostart.set_enabled(False))
        self.assertIsNone(autostart._read())

    def test_legacy_shortcut_is_removed_and_stays_off(self):
        self.lnk.parent.mkdir(parents=True)
        self.lnk.write_bytes(b"x")
        autostart.migrate()
        self.assertFalse(self.lnk.exists())
        self.assertIsNone(autostart._read())               # mặc định tắt: không tự bật khoá Run
        self.assertFalse(autostart.is_enabled())

    def test_disable_removes_legacy_shortcut(self):
        self.lnk.parent.mkdir(parents=True)
        self.lnk.write_bytes(b"x")
        self.assertFalse(autostart.set_enabled(False))
        self.assertFalse(self.lnk.exists())


@unittest.skipUnless(WIN, "chỉ Windows")
class TrayIcon(unittest.TestCase):
    def test_clicks_become_events_and_stop_removes_icon(self):
        import ctypes
        import tray
        t = tray.Tray("ARAM Helper test", None)
        self.assertTrue(t.start())
        try:
            send = ctypes.windll.user32.SendMessageW
            send.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
            send(t.hwnd, tray.WM_TRAY, 1, tray.WM_LBUTTONUP)
            self.assertEqual(t.events.get(timeout=2), "open")
        finally:
            t.stop()
        self.assertIsNone(t._nid)


class FakeTray:
    hwnd = 1

    def __init__(self):
        self.events = queue.Queue()
        self.notes, self.stopped = [], False

    def notify(self, title, text):
        self.notes.append(text)

    def set_labels(self, labels):
        self.labels = labels

    def stop(self):
        self.stopped = True


@unittest.skipUnless(HAS_TK, "cần màn hình / tkinter")
class DesktopTray(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        import desktop
        self.tmp = tempfile.TemporaryDirectory()
        settings._reset_for_tests(Path(self.tmp.name) / "settings.json")
        settings.set_many({"check_updates": False}, save=False)
        self.no_net = mock.patch.object(desktop.App, "_load_champion_list", lambda self: None)
        self.no_net.start()
        self.root = tk.Tk()
        self.root.withdraw()
        self.tray = FakeTray()
        self.app = desktop.App(self.root, FakeHub(), tray=self.tray)
        self.app._poll()
        self.root.update()

    def tearDown(self):
        try:
            self.root.destroy()
        except Exception:
            pass
        self.no_net.stop()
        settings._reset_for_tests(settings.PATH)
        self.tmp.cleanup()

    def test_close_hides_to_tray_with_one_time_hint(self):
        self.app._on_close()
        self.assertTrue(self.app.in_tray)
        self.assertEqual(self.root.state(), "withdrawn")
        self.assertEqual(len(self.tray.notes), 1)
        self.app.show_window()
        self.app._on_close()
        self.assertEqual(len(self.tray.notes), 1)          # chỉ nhắc lần đầu

    def test_hidden_window_skips_redraw(self):
        self.app.hide_to_tray(hint=False)
        with mock.patch.object(self.app, "_render") as render:
            self.app._full_sig = None
            self.app._poll()
        render.assert_not_called()

    def test_tray_open_and_quit_events(self):
        self.app.hide_to_tray(hint=False)
        self.tray.events.put("open")
        self.app._pump_tray()
        self.assertFalse(self.app.in_tray)
        self.assertEqual(self.root.state(), "normal")
        self.tray.events.put("quit")
        self.app._pump_tray()
        self.assertTrue(self.tray.stopped)
        with self.assertRaises(Exception):
            self.root.winfo_exists()

    def test_close_quits_when_tray_disabled(self):
        settings.set_many({"tray": False}, save=False)
        self.app._on_close()
        self.assertTrue(self.tray.stopped)


class ChampionCache(unittest.TestCase):
    def test_keeps_only_recent_champions_in_ram(self):
        with mock.patch.dict(playaram._mem, clear=True):
            playaram._remember("_augments", {"a": 1})
            for i in range(playaram.MEM_CHAMPS + 5):
                playaram._remember(f"champ_{i}", {"i": i})
            champs = [k for k in playaram._mem if k.startswith("champ_")]
            self.assertEqual(len(champs), playaram.MEM_CHAMPS)
            self.assertIn("_augments", playaram._mem)        # danh mục lõi không bị đẩy ra
            self.assertIn(f"champ_{playaram.MEM_CHAMPS + 4}", champs)
            self.assertNotIn("champ_0", champs)


if __name__ == "__main__":
    unittest.main()

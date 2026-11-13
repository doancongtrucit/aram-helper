# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
"""Nhận biết League đang ở chế độ Toàn màn hình (đọc game.cfg) – overlay chỉ hiện khi Không viền."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import game_window  # noqa: E402

CFG = """[General]
Height=1080
Width=1920
WindowMode={mode}
[HUD]
WindowMode=9
"""


class WindowMode(unittest.TestCase):
    def test_reads_general_section(self):
        for mode in (0, 1, 2):
            self.assertEqual(game_window.window_mode(CFG.format(mode=mode)), mode)

    def test_missing_or_bad_value(self):
        self.assertIsNone(game_window.window_mode("[General]\nWidth=1920\n"))
        self.assertIsNone(game_window.window_mode("[General]\nWindowMode=abc\n"))
        self.assertIsNone(game_window.window_mode("[HUD]\nWindowMode=0\n"))     # chỉ tính mục [General]

    def test_cfg_path_next_to_game_folder(self):
        exe = os.path.join("C:", os.sep, "Riot Games", "League of Legends", "Game", "League of Legends.exe")
        self.assertEqual(game_window._game_cfg_paths(exe)[0],
                         os.path.join("C:", os.sep, "Riot Games", "League of Legends", "Config", "game.cfg"))

    @unittest.skipUnless(sys.platform == "win32", "Windows")
    def test_fullscreen_from_running_game_cfg(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "Config"))
            exe = os.path.join(d, "Game", "League of Legends.exe")
            for mode, expect in ((0, True), (2, False)):
                with open(os.path.join(d, "Config", "game.cfg"), "w", encoding="utf-8") as f:
                    f.write(CFG.format(mode=mode))
                with mock.patch.object(game_window, "_game_exe", return_value=exe), \
                        mock.patch.object(game_window, "_d3d_fullscreen", return_value=False):
                    self.assertIs(game_window.exclusive_fullscreen(force=True), expect)

    @unittest.skipUnless(sys.platform == "win32", "Windows")
    def test_no_game_or_error_means_not_fullscreen(self):
        with mock.patch.object(game_window, "_game_exe", return_value=None), \
                mock.patch.object(game_window, "_d3d_fullscreen", return_value=False):
            self.assertFalse(game_window.exclusive_fullscreen(force=True))
        with mock.patch.object(game_window, "_d3d_fullscreen", side_effect=OSError):
            self.assertFalse(game_window.exclusive_fullscreen(force=True))
        with mock.patch.object(game_window, "_d3d_fullscreen", return_value=True):
            self.assertTrue(game_window.exclusive_fullscreen(force=True))


if __name__ == "__main__":
    unittest.main()

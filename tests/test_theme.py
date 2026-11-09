# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
"""Font giao diện: Inter đi kèm app được nạp riêng cho tiến trình; nạp lỗi thì về font hệ thống."""
import sys
import tkinter as tk
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import theme  # noqa: E402


class FontTest(unittest.TestCase):
    def setUp(self):
        self.saved = dict(theme._ui)
        theme._ui.update(regular=None, semi=None)
        self.root = tk.Tk()
        self.root.withdraw()

    def tearDown(self):
        self.root.destroy()
        theme._ui.update(self.saved)

    def test_font_files_bundled(self):
        for name in theme.FONT_FILES + ("OFL.txt",):
            self.assertTrue((theme.paths.RES / "assets" / "fonts" / name).is_file(), name)

    @unittest.skipUnless(sys.platform in ("win32", "darwin"), "nạp font riêng chỉ có trên Windows / macOS")
    def test_load_inter(self):
        self.assertTrue(theme.load_fonts(self.root))
        self.assertEqual(theme.family(), ("Inter", "normal"))
        self.assertEqual(theme.family(True)[0][:5], "Inter")
        self.assertEqual(theme.font(10, mono=True)[0], theme.MONO)

    def test_fallback_when_font_missing(self):
        with mock.patch.object(theme, "_register_font_file", return_value=False), \
                mock.patch("tkinter.font.families", return_value=("Segoe UI",)):
            self.assertFalse(theme.load_fonts(self.root))
        self.assertEqual(theme.family(True), (theme.FONT, "bold"))


if __name__ == "__main__":
    unittest.main()

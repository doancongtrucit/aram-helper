"""Phím tắt: đọc tổ hợp, kiểm tra hợp lệ, thứ tự phím người dùng chọn + phím dự phòng."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import hotkeys  # noqa: E402


class Hotkeys(unittest.TestCase):
    def test_parse(self):
        m, vk = hotkeys.parse("ctrl+alt+a")
        self.assertEqual(vk, ord("A"))
        self.assertEqual(m & 0x3, 0x3)
        self.assertEqual(hotkeys.parse("ctrl+shift+f5")[1], 0x74)
        self.assertEqual(hotkeys.parse("alt+7")[1], ord("7"))
        with self.assertRaises(ValueError):
            hotkeys.parse("ctrl+meta+a")

    def test_valid_needs_ctrl_or_alt(self):
        self.assertTrue(hotkeys.valid("ctrl+shift+l"))
        self.assertTrue(hotkeys.valid("alt+f2"))
        self.assertFalse(hotkeys.valid("shift+a"))
        self.assertFalse(hotkeys.valid("a"))
        self.assertFalse(hotkeys.valid("ctrl+alt+enter"))

    def test_custom_first_then_fallbacks(self):
        self.assertEqual(hotkeys.combos_for("calibrate", "ctrl+shift+l")[:2], ["ctrl+shift+l", "ctrl+alt+a"])
        self.assertEqual(hotkeys.combos_for("calibrate", "ctrl+alt+a"), hotkeys.DEFAULTS["calibrate"])
        self.assertEqual(hotkeys.combos_for("overlay", "shift+o"), hotkeys.DEFAULTS["overlay"])   # không hợp lệ → bỏ

    def test_pretty(self):
        self.assertEqual(hotkeys.pretty("ctrl+shift+l"), "Ctrl+Shift+L")


if __name__ == "__main__":
    unittest.main()

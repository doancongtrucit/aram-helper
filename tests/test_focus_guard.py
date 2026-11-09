# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
"""Giữ focus cho game: chỉ trả focus khi app VÔ TÌNH lấy (không có phím / chuột ngay trước đó)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import focus_guard as fg  # noqa: E402


class Decide(unittest.TestCase):
    def test_accidental_activation_is_returned(self):
        self.assertEqual(fg.decide(prev_is_game=True, now_is_ours=True, idle_ms=1500), "return")

    def test_user_switch_is_respected(self):
        self.assertEqual(fg.decide(True, True, idle_ms=50), "user")          # Alt+Tab / bấm vào app

    def test_unrelated_changes_ignored(self):
        self.assertIsNone(fg.decide(True, False, 2000))                      # game → app khác (Discord…)
        self.assertIsNone(fg.decide(False, True, 2000))                      # app → app (không phải từ game)


if __name__ == "__main__":
    unittest.main()

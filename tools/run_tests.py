# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
"""Chạy toàn bộ test; báo lỗi nếu có test hỏng HOẶC quá nhiều test bị bỏ qua (thiếu dữ liệu / môi trường),
để bước test khi phát hành không "xanh" mà thực ra không kiểm tra gì.

    python tools/run_tests.py            # MAX_SKIPS mặc định 2 (2 test so với trang thật đã tải về máy)
"""
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_SKIPS = int(os.environ.get("MAX_SKIPS", "2"))

if __name__ == "__main__":
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT / "tests"))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    skipped = result.skipped
    print(f"\n{result.testsRun} test · {len(result.failures) + len(result.errors)} lỗi · {len(skipped)} bỏ qua "
          f"(tối đa {MAX_SKIPS})")
    for test, reason in skipped:
        print(f"  bỏ qua: {test.id()} – {reason}")
    if not result.wasSuccessful():
        sys.exit(1)
    if len(skipped) > MAX_SKIPS:
        print("Quá nhiều test bị bỏ qua – kiểm tra dữ liệu mẫu / icon / môi trường.")
        sys.exit(1)

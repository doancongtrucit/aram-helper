# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
"""Trang HTML cho test.

- load(name): trang MẪU dựng từ tests/sample_data.json (số liệu tự đặt) – luôn có, chạy được ở mọi nơi.
- load_real(name): trang THẬT đã tải về máy (tests/fixture_*.html, không commit – tải bằng
  python tests/fetch_fixtures.py) để kiểm tra parser còn đọc được giao diện hiện tại của trang nguồn.
"""
import unittest
from pathlib import Path

import sample_pages

HERE = Path(__file__).parent
FILES = {"yasuo": HERE / "fixture_yasuo.html", "augments": HERE / "fixture_augments.html"}
_SAMPLES = {"yasuo": sample_pages.champion_page, "augments": sample_pages.catalog_page}


def load(name: str) -> str:
    return _SAMPLES[name]()


def load_real(name: str) -> str:
    path = FILES[name]
    if not path.exists():
        raise unittest.SkipTest(f"thiếu {path.name} – chạy: python tests/fetch_fixtures.py")
    return path.read_text(encoding="utf-8")

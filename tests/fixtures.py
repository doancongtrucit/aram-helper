"""Trang HTML mẫu của trang nguồn dữ liệu, dùng cho test.

Các file tests/fixture_*.html không nằm trong repo. Tải về máy để chạy test:  python tests/fetch_fixtures.py

Test kiểm tra giá trị cụ thể (tỉ lệ thắng, id lõi trong combo của Yasuo...) được viết theo bản chụp ngày
2026-11-09; tải bản mới thì một số test giá trị có thể lệch vì dữ liệu trên trang đã đổi – phần kiểm tra
cấu trúc (đọc đủ 3 bậc lõi, build, combo...) vẫn có ý nghĩa.
"""
import unittest
from pathlib import Path

HERE = Path(__file__).parent
FILES = {"yasuo": HERE / "fixture_yasuo.html", "augments": HERE / "fixture_augments.html"}


def load(name: str) -> str:
    path = FILES[name]
    if not path.exists():
        raise unittest.SkipTest(f"thiếu {path.name} – chạy: python tests/fetch_fixtures.py")
    return path.read_text(encoding="utf-8")

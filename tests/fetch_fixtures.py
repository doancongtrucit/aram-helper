"""Tải trang mẫu của trang nguồn dữ liệu về tests/ để chạy test (chỉ dùng trên máy, không commit)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import playaram  # noqa: E402
from fixtures import FILES  # noqa: E402

PAGES = {"yasuo": "/tuong/yasuo", "augments": "/loi-aram-hon-loan"}

if __name__ == "__main__":
    for name, path in PAGES.items():
        html = playaram._get(path)            # có giãn cách giữa các request
        FILES[name].write_text(html, encoding="utf-8")
        print(f"đã lưu {FILES[name].name} ({len(html) // 1024} KB)")

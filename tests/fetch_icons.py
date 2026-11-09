# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
"""Tải icon lõi (CommunityDragon) cho các test nhận diện màn hình vào thư mục dữ liệu
(ARAM_HELPER_DATA nếu có đặt – GitHub Actions dùng thư mục tạm)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))
import playaram  # noqa: E402
import sample_pages  # noqa: E402
import screen_scan as ss  # noqa: E402

if __name__ == "__main__":
    catalog = playaram.parse_augment_catalog(sample_pages.catalog_page())
    n = ss.ensure_icons(catalog)
    have = sum((ss.ICON_DIR / f"{a['id']}.png").exists() for a in catalog)
    print(f"icon: tải thêm {n}, có {have}/{len(catalog)} trong {ss.ICON_DIR}")
    sys.exit(0 if have >= len(catalog) * 0.9 else 1)

# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
"""Thông tin bản quyền, developer và nguồn dữ liệu – một chỗ duy nhất, dùng cho app, file exe và bộ cài."""
from __future__ import annotations

APP_NAME = "ARAM Helper"
DEVELOPER = "doancongtrucit"
YEAR = "2026"
COPYRIGHT = f"© {YEAR} {DEVELOPER}. All rights reserved."
REPO_URL = "https://github.com/doancongtrucit/aram-helper"
RELEASES_URL = REPO_URL + "/releases"
ISSUES_URL = REPO_URL + "/issues"
DEVELOPER_URL = "https://github.com/doancongtrucit"
EMAIL = "doancongtrucit@gmail.com"          # liên hệ công khai của developer (xin phép sử dụng, góp ý)

# Nguồn dữ liệu (ghi công)
DATA_SOURCES = [
    ("playaram.gg", "https://playaram.gg", "thống kê lõi, combo, lối lên đồ"),
    ("Riot Data Dragon", "https://developer.riotgames.com/docs/lol#data-dragon", "tên, icon tướng / trang bị / phép"),
    ("CommunityDragon", "https://www.communitydragon.org", "icon lõi"),
]

# Câu miễn trừ Riot yêu cầu cho sản phẩm dùng tài sản / dữ liệu của League of Legends
RIOT_DISCLAIMER = (
    "ARAM Helper isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot Games or anyone "
    "officially involved in producing or managing Riot Games properties. Riot Games, and all associated properties "
    "are trademarks or registered trademarks of Riot Games, Inc."
)

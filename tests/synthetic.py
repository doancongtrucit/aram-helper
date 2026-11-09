"""Tạo ảnh màn hình giả lập bảng chọn 3 lõi để thử bộ nhận diện (khi chưa có ảnh game thật).

Ảnh giả lập: nền tối có nhiễu, 3 thẻ lõi màu theo độ hiếm, icon dán bằng alpha, chữ mô tả bên dưới,
vài icon nhỏ làm nhiễu ở góc (giống HUD), làm mờ nhẹ và nén JPEG.
"""
from __future__ import annotations

import random

import cv2
import numpy as np


CARD_COLORS = {"prismatic": (160, 70, 140), "gold": (40, 120, 170), "silver": (120, 110, 100)}


def _paste(dst, rgba, cx, cy, size):
    im = cv2.resize(rgba, (size, size), interpolation=cv2.INTER_AREA).astype(np.float32)
    a = im[..., 3:4] / 255.0
    x0, y0 = cx - size // 2, cy - size // 2
    roi = dst[y0:y0 + size, x0:x0 + size].astype(np.float32)
    dst[y0:y0 + size, x0:x0 + size] = (roi * (1 - a) + im[..., :3] * a).astype(np.uint8)


def _draw_names(img: np.ndarray, items) -> np.ndarray:
    """Vẽ tên lõi tiếng Việt (cv2 không vẽ được dấu nên dùng PIL)."""
    from PIL import Image, ImageDraw, ImageFont
    pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    d = ImageDraw.Draw(pil)
    for text, cx, y, px in items:
        font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", px)
        w = d.textlength(text, font=font)
        d.text((cx - w / 2, y), text, font=font, fill=(245, 235, 210))
    return cv2.cvtColor(np.asarray(pil), cv2.COLOR_RGB2BGR)


def make_screen(icons: dict[int, np.ndarray], offer: list[int], rarity: str = "gold",
                width=1920, height=1080, icon_frac=128 / 1920, seed=0,
                names: dict[int, str] | None = None) -> np.ndarray:
    rng = random.Random(seed)
    nprng = np.random.default_rng(seed)
    img = np.zeros((height, width, 3), np.uint8)
    grad = np.linspace(20, 45, height, dtype=np.float32)[:, None, None]
    img[:] = np.clip(grad + nprng.normal(0, 6, (height, width, 3)), 0, 255).astype(np.uint8)
    size = int(round(width * icon_frac))
    gap = int(width * 300 / 1920)
    cy = int(height * 0.40)
    centers = [(width // 2 - gap, cy), (width // 2, cy), (width // 2 + gap, cy)]
    for (cx, cy_), aug_id in zip(centers, offer):
        cw, ch = int(size * 2.0), int(size * 3.4)
        x0, y0 = cx - cw // 2, cy_ - int(size * 0.9)
        col = np.array(CARD_COLORS[rarity], np.float32)
        card = np.linspace(0.5, 1.0, ch, dtype=np.float32)[:, None, None] * col
        img[y0:y0 + ch, x0:x0 + cw] = card.astype(np.uint8)
        cv2.rectangle(img, (x0, y0), (x0 + cw, y0 + ch), (200, 200, 200), 2)
        _paste(img, icons[aug_id], cx, cy_, size)
        for i in range(4):
            cv2.putText(img, "Lorem ipsum dolor " * 2, (x0 + 10, cy_ + size + 60 + i * 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45 * width / 1920, (230, 230, 230), 1)
    if names:
        px = int(22 * width / 1920)
        img = _draw_names(img, [(names[a], cx, cy_ + size // 2 + 12, px) for (cx, cy_), a in zip(centers, offer)])
    # icon nhiễu nhỏ ở HUD
    others = [k for k in icons if k not in offer]
    for i in range(6):
        _paste(img, icons[rng.choice(others)], int(width * 0.3) + i * int(width * 0.03), int(height * 0.93), int(width * 0.022))
    img = cv2.GaussianBlur(img, (3, 3), 0.7)
    ok, enc = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return cv2.imdecode(enc, cv2.IMREAD_COLOR)

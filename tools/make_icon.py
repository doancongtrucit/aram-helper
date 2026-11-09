"""Vẽ icon app (assets/icon.png 512px + assets/icon.ico nhiều cỡ) bằng Pillow. Chạy: python tools/make_icon.py"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"


def draw(size: int = 1024) -> Image.Image:
    s = size
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    # nền: ô vuông bo góc, chuyển màu tím đậm → xanh đêm
    bg = Image.new("RGBA", (s, s))
    px = bg.load()
    for y in range(s):
        for x in range(s):
            t = (x + y) / (2 * s)
            px[x, y] = (int(58 + (14 - 58) * t), int(28 + (20 - 28) * t), int(110 + (44 - 110) * t), 255)
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, s - 1, s - 1), radius=int(s * 0.22), fill=255)
    img.paste(bg, (0, 0), mask)

    d = ImageDraw.Draw(img)
    cx, cy = s / 2, s / 2
    # lõi (augment): viên kim cương lăng trụ với viền sáng, quầng sáng phía sau
    glow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((cx - s * 0.33, cy - s * 0.33, cx + s * 0.33, cy + s * 0.33), fill=(197, 140, 255, 120))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(s * 0.06)))
    r = s * 0.30
    top, right, bottom, left = (cx, cy - r), (cx + r * 0.82, cy), (cx, cy + r), (cx - r * 0.82, cy)
    d.polygon([top, right, (cx, cy)], fill=(236, 214, 255))
    d.polygon([right, bottom, (cx, cy)], fill=(160, 96, 240))
    d.polygon([bottom, left, (cx, cy)], fill=(112, 62, 200))
    d.polygon([left, top, (cx, cy)], fill=(206, 166, 255))
    d.polygon([top, right, bottom, left], outline=(255, 255, 255), width=max(2, int(s * 0.018)))
    # dấu tick xanh: "nên chọn"
    g = (61, 220, 151)
    w = int(s * 0.07)
    pts = [(cx + s * 0.12, cy + s * 0.25), (cx + s * 0.21, cy + s * 0.34), (cx + s * 0.38, cy + s * 0.15)]
    d.ellipse((cx + s * 0.06, cy + s * 0.07, cx + s * 0.46, cy + s * 0.47), fill=(10, 30, 24))
    d.line(pts, fill=g, width=w, joint="curve")
    for p in (pts[0], pts[-1]):
        d.ellipse((p[0] - w / 2, p[1] - w / 2, p[0] + w / 2, p[1] + w / 2), fill=g)
    return img


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    big = draw(1024)
    big.resize((512, 512), Image.LANCZOS).save(OUT / "icon.png", optimize=True)
    big.save(OUT / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("đã lưu", OUT / "icon.png", OUT / "icon.ico")

"""Xuất icon app từ assets/icon.svg: assets/icon.png (512 px) + assets/icon.ico (16–256 px).

SVG có hiệu ứng (đổ bóng, phát sáng) nên vẽ bằng Edge / Chrome chạy ẩn để giữ đúng hình, rồi thu nhỏ bằng Pillow.
Chạy (Windows):  python tools/make_icon.py
"""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
SVG = ASSETS / "icon.svg"
RENDER = 1024
ICO_SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256]


def find_browser() -> str:
    for p in (os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
              os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
              os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
              shutil.which("msedge"), shutil.which("chrome"), shutil.which("google-chrome")):
        if p and Path(p).exists():
            return p
    raise SystemExit("Cần Microsoft Edge hoặc Google Chrome để vẽ SVG.")


def render(svg: Path, size: int) -> Image.Image:
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "icon.html"
        page.write_text(f"""<!doctype html><html><body style="margin:0;background:transparent">
<img src="{svg.as_uri()}" width="{size}" height="{size}" style="display:block"></body></html>""", encoding="utf-8")
        out = Path(tmp) / "icon.png"
        subprocess.run([find_browser(), "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        "--default-background-color=00000000", "--force-device-scale-factor=1",
                        f"--window-size={size},{size}", f"--screenshot={out}", page.as_uri()],
                       check=True, capture_output=True, timeout=60)
        return Image.open(out).convert("RGBA").crop((0, 0, size, size))


if __name__ == "__main__":
    big = render(SVG, RENDER)
    big.resize((512, 512), Image.LANCZOS).save(ASSETS / "icon.png", optimize=True)
    big.save(ASSETS / "icon.ico", sizes=[(s, s) for s in ICO_SIZES])
    print("saved", ASSETS / "icon.png", ASSETS / "icon.ico")

# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
# PyInstaller: đóng gói ARAM Helper thành thư mục app (onedir – mở nhanh, ít bị diệt virus báo nhầm hơn onefile).
# Không chạy trực tiếp: dùng  python tools/build.py  (tạo file thông tin phiên bản rồi gọi PyInstaller với spec này).
import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent          # noqa: F821 – SPECPATH do PyInstaller cung cấp
WIN = sys.platform == "win32"

# Các module nạp muộn (import trong hàm) – liệt kê để chắc chắn được đóng gói
hidden = ["about", "report", "desktop", "theme", "widgets", "views.search", "views.augments", "views.items", "views.combos", "settings_ui", "overlay", "scanner", "screen_scan", "ocr", "hotkeys",
          "ddragon", "counter_items", "localize", "updater", "diag", "game_window", "pick_watch", "focus_guard", "controls", "cvlite", "ed25519", "single_instance", "tray", "autostart"]
if WIN:
    hidden += ["winrt.windows.media.ocr", "winrt.windows.graphics.imaging", "winrt.windows.storage.streams",
               "winrt.windows.foundation", "winrt.windows.foundation.collections", "winrt.windows.globalization"]

a = Analysis(
    [str(ROOT / "src" / "app.py")],
    pathex=[str(ROOT / "src")],
    datas=[(str(ROOT / "assets" / "icon.png"), "assets"), (str(ROOT / "assets" / "icon.ico"), "assets"),
           (str(ROOT / "assets" / "fonts"), "assets/fonts"),
           (str(ROOT / "LICENSE"), "."), (str(ROOT / "THIRD_PARTY_NOTICES.md"), ".")],
    hiddenimports=hidden,
    # cv2: app dùng cvlite.py (numpy + Pillow) thay OpenCV – OpenCV chỉ còn trong môi trường test.
    # Ảnh AVIF / WebP của Pillow, yaml: app không dùng (icon là PNG / JPEG).
    excludes=["matplotlib", "pandas", "scipy", "IPython", "pytest", "PyQt5", "PySide6", "tests",
              "cv2", "yaml", "PIL._avif", "PIL.AvifImagePlugin", "PIL._webp", "PIL.WebPImagePlugin"],
    noarchive=False,
)
# Dữ liệu múi giờ + bản dịch hộp thoại của Tcl/Tk: app không dùng lệnh clock của Tcl, hộp thoại tự dịch qua i18n.py
_DROP = ("_tcl_data/tzdata/", "_tcl_data/msgs/", "_tk_data/msgs/")
a.datas = [d for d in a.datas if not d[0].replace(chr(92), "/").startswith(_DROP)]
a.binaries = [b for b in a.binaries if "opencv_videoio_ffmpeg" not in b[0] and "_avif" not in b[0]]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ARAM Helper",
    console=False,                    # app cửa sổ, log ghi vào thư mục dữ liệu (app.log)
    icon=str(ROOT / "assets" / ("icon.ico" if WIN else "icon.png")),
    version=str(ROOT / "build" / "version_info.txt") if WIN else None,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="ARAM Helper", upx=False)

if sys.platform == "darwin":
    app = BUNDLE(coll, name="ARAM Helper.app", icon=str(ROOT / "assets" / "icon.png"), bundle_identifier="io.github.doancongtrucit.aramhelper",
                 info_plist={"NSHighResolutionCapable": True, "LSApplicationCategoryType": "public.app-category.games",
                             "NSHumanReadableCopyright": "© 2026 doancongtrucit. All rights reserved."})

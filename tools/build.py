"""Build bản app để chia sẻ.

    python tools/build.py            # Windows: dist/ARAM-Helper-<ver>-win64-portable.zip (+ Setup.exe nếu có Inno Setup)
                                     # macOS:   dist/ARAM-Helper-<ver>-macos.zip (ARAM Helper.app)

Cần: pip install -r requirements.txt pyinstaller  (nên dùng môi trường riêng, vd. build/venv).
Bộ cài Windows cần Inno Setup 6 (ISCC.exe) – GitHub Actions có sẵn; trên máy thì tuỳ chọn.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from version import __version__  # noqa: E402

BUILD, DIST = ROOT / "build", ROOT / "dist"
APP = DIST / "ARAM Helper"


def version_info():
    """Thông tin phiên bản hiện trong Properties của file exe."""
    nums = [int(x) for x in __version__.split(".")[:3]] + [0]
    while len(nums) < 4:
        nums.append(0)
    t = tuple(nums[:4])
    BUILD.mkdir(exist_ok=True)
    (BUILD / "version_info.txt").write_text(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={t}, prodvers={t}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0,
                    date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'doancongtrucit'),
      StringStruct('FileDescription', 'ARAM Helper – gợi ý lõi và trang bị ARAM Hỗn Loạn'),
      StringStruct('FileVersion', '{__version__}'),
      StringStruct('InternalName', 'ARAM Helper'),
      StringStruct('OriginalFilename', 'ARAM Helper.exe'),
      StringStruct('ProductName', 'ARAM Helper'),
      StringStruct('ProductVersion', '{__version__}'),
      StringStruct('LegalCopyright', 'github.com/doancongtrucit/aram-helper')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""", encoding="utf-8")


def pyinstaller():
    for p in (APP, DIST / "ARAM Helper.app"):
        shutil.rmtree(p, ignore_errors=True)
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                    "--distpath", str(DIST), "--workpath", str(BUILD / "pyinstaller"),
                    str(ROOT / "packaging" / "aram_helper.spec")], check=True, cwd=ROOT)


def zip_dir(src: Path, out: Path, extra: dict[str, str] | None = None):
    out.unlink(missing_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for f in sorted(src.rglob("*")):
            if f.is_file():
                z.write(f, Path(src.name) / f.relative_to(src))
        for name, text in (extra or {}).items():
            z.writestr(str(Path(src.name) / name), text)
    print(f"đã tạo {out.name} ({out.stat().st_size / 1e6:.0f} MB)")


def find_iscc() -> str | None:
    for p in (shutil.which("ISCC"), r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
              r"C:\Program Files\Inno Setup 6\ISCC.exe",
              os.path.expandvars(r"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe")):
        if p and Path(p).exists():
            return p
    return None


def main():
    DIST.mkdir(exist_ok=True)
    if sys.platform == "win32":
        version_info()
    pyinstaller()
    if sys.platform == "win32":
        # Bản portable: có portable.txt → dữ liệu lưu trong thư mục app (chép đi máy khác được)
        zip_dir(APP, DIST / f"ARAM-Helper-{__version__}-win64-portable.zip",
                {"portable.txt": "Có file này: ARAM Helper lưu dữ liệu vào thư mục data\\ cạnh exe.\r\n"
                                 "Xoá file này: lưu vào %LOCALAPPDATA%\\ARAM Helper.\r\n"})
        iscc = find_iscc()
        if iscc:
            subprocess.run([iscc, f"/DAppVersion={__version__}", f"/DSourceDir={APP}", f"/DOutDir={DIST}",
                            str(ROOT / "packaging" / "installer.iss")], check=True)
            print(f"đã tạo ARAM-Helper-{__version__}-Setup.exe")
        else:
            print("Không thấy Inno Setup 6 (ISCC.exe) – bỏ qua bộ cài, chỉ có bản portable.")
    elif sys.platform == "darwin":
        out = DIST / f"ARAM-Helper-{__version__}-macos.zip"
        out.unlink(missing_ok=True)
        # ditto giữ nguyên symlink + quyền chạy trong .app (zipfile của Python thì không)
        subprocess.run(["ditto", "-c", "-k", "--keepParent", str(DIST / "ARAM Helper.app"), str(out)], check=True)
        print(f"đã tạo {out.name}")


if __name__ == "__main__":
    main()

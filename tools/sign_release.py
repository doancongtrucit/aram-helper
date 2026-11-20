# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
"""Ký file mã băm của bản phát hành (SHA256SUMS.txt → SHA256SUMS.txt.sig) bằng Ed25519.

    python tools/sign_release.py keygen <file khoá riêng>   # 1 lần: tạo khoá, in khoá công khai cho updater.py
    python tools/sign_release.py sign SHA256SUMS.txt        # GitHub Actions: khoá riêng lấy từ biến môi trường
                                                            # RELEASE_SIGNING_KEY (GitHub secret, dạng hex)
    python tools/sign_release.py verify SHA256SUMS.txt      # kiểm tra lại bằng khoá công khai trong updater.py

Khoá riêng TUYỆT ĐỐI không commit vào repo. App (updater.py) từ chối tự cập nhật nếu chữ ký thiếu / sai.
"""
from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import ed25519  # noqa: E402


def _secret() -> bytes:
    key = os.environ.get("RELEASE_SIGNING_KEY", "").strip()
    if not key:
        sys.exit("Thiếu RELEASE_SIGNING_KEY (GitHub → Settings → Secrets and variables → Actions). "
                 "Không đăng bản phát hành chưa ký: app ≥ 2.0 sẽ từ chối tự cập nhật.")
    try:
        sk = bytes.fromhex(key)
    except ValueError:
        sys.exit("RELEASE_SIGNING_KEY phải là chuỗi hex 64 ký tự")
    if len(sk) != 32:
        sys.exit("RELEASE_SIGNING_KEY phải là chuỗi hex 64 ký tự")
    return sk


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd, path = argv[0], Path(argv[1])
    if cmd == "keygen":
        if path.exists():
            sys.exit(f"{path} đã có – không ghi đè khoá cũ")
        sk = secrets.token_bytes(32)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(sk.hex() + "\n", encoding="ascii")
        print("Khoá riêng đã lưu (giữ kín, KHÔNG commit):", path)
        print("Khoá công khai (dán vào SIGNING_KEY trong src/updater.py):", ed25519.public_key(sk).hex())
        return 0
    if cmd == "sign":
        sk = _secret()
        import updater
        if ed25519.public_key(sk).hex() != updater.SIGNING_KEY:
            sys.exit("RELEASE_SIGNING_KEY không khớp khoá công khai SIGNING_KEY trong src/updater.py")
        sig = ed25519.sign(sk, path.read_bytes())
        out = path.with_name(path.name + ".sig")
        out.write_text(sig.hex() + "\n", encoding="ascii")
        print(f"đã ký {path.name} → {out.name}")
        return 0
    if cmd == "verify":
        import updater
        sig = path.with_name(path.name + ".sig").read_text(encoding="ascii")
        ok = updater.signature_ok(path.read_bytes(), sig)
        print("chữ ký hợp lệ" if ok else "CHỮ KÝ SAI")
        return 0 if ok else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

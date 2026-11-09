"""Chẩn đoán bộ quét lõi: ghi log có thời gian và lưu ảnh vùng quét vào data/debug/ (chỉ trên máy, không gửi đi).

Ảnh chẩn đoán giúp chỉnh bộ nhận diện theo giao diện game thật. Giữ tối đa MAX_FILES ảnh mới nhất.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import paths

DEBUG_DIR = paths.DATA / "debug"
MAX_FILES = 30


def log(msg: str):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def save(img_bgr, info: dict, tag: str) -> Path:
    import cv2
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"{time.strftime('%Y%m%d-%H%M%S')}-{tag}"
    path = DEBUG_DIR / f"{stem}.png"
    cv2.imencode(".png", img_bgr)[1].tofile(str(path))
    (DEBUG_DIR / f"{stem}.json").write_text(json.dumps(info, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    files = sorted(DEBUG_DIR.glob("*.png"))
    for old in files[:-MAX_FILES]:                  # dọn ảnh cũ
        old.unlink(missing_ok=True)
        old.with_suffix(".json").unlink(missing_ok=True)
    log(f"đã lưu ảnh chẩn đoán {path.name}")
    return path

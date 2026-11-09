"""OCR có sẵn của Windows (Windows.Media.Ocr) để đọc tên lõi, phân xử khi nhiều lõi dùng chung icon.

Máy chỉ có OCR tiếng Anh vẫn dùng được: chữ tiếng Việt bị đọc sai dấu, nên so khớp sau khi bỏ dấu
và chỉ so với vài ứng viên đã lọc bằng icon.
"""
from __future__ import annotations

import asyncio
import difflib
import re
import unicodedata

import numpy as np

_engine = None
_ready: bool | None = None      # None = chưa nạp WinRT (chỉ nạp khi thật sự cần OCR, tiết kiệm ~10 MB)


def installed() -> bool:
    """Đã cài gói winrt OCR chưa – không nạp gì."""
    import importlib.util
    try:
        return importlib.util.find_spec("winrt.windows.media.ocr") is not None
    except Exception:
        return False


def _init() -> bool:
    global _engine, _ready, BitmapAlphaMode, BitmapPixelFormat, SoftwareBitmap, DataWriter
    if _ready is None:
        try:
            from winrt.windows.graphics.imaging import BitmapAlphaMode, BitmapPixelFormat, SoftwareBitmap
            from winrt.windows.media.ocr import OcrEngine
            from winrt.windows.storage.streams import DataWriter
            _engine = OcrEngine.try_create_from_user_profile_languages()
            _ready = _engine is not None
        except Exception:  # không phải Windows / chưa cài winrt
            _ready = False
    return _ready


def __getattr__(name):          # ocr.AVAILABLE → nạp OCR lần đầu được hỏi tới
    if name == "AVAILABLE":
        return installed()
    raise AttributeError(name)


def fold(s: str) -> str:
    s = unicodedata.normalize("NFD", s.replace("đ", "d").replace("Đ", "D"))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


async def _recognize(bgr: np.ndarray) -> list[str]:
    h, w = bgr.shape[:2]
    bgra = np.dstack([bgr, np.full((h, w), 255, np.uint8)])
    writer = DataWriter()
    writer.write_bytes(bgra.tobytes())
    bmp = SoftwareBitmap.create_copy_from_buffer(writer.detach_buffer(), BitmapPixelFormat.BGRA8, w, h,
                                                 BitmapAlphaMode.PREMULTIPLIED)
    result = await _engine.recognize_async(bmp)
    return [line.text for line in result.lines]


def read_lines(bgr: np.ndarray) -> list[str]:
    """Các dòng chữ trong ảnh (BGR uint8). Trả [] nếu OCR không có."""
    if bgr is None or bgr.size == 0 or not _init():
        return []
    import cv2
    h = bgr.shape[0]
    if h < 120:                         # chữ nhỏ: phóng to giúp OCR đọc tốt hơn
        k = 120 / h
        bgr = cv2.resize(bgr, None, fx=k, fy=k, interpolation=cv2.INTER_CUBIC)
    bgr = np.ascontiguousarray(bgr[: 4000, : 4000])
    try:
        return asyncio.run(_recognize(bgr))
    except Exception:
        return []


def best_name(lines: list[str], candidates: dict[int, str], min_ratio: float = 0.6) -> tuple[int | None, float]:
    """Chọn ứng viên có tên giống một dòng OCR nhất. Trả (id, độ giống) hoặc (None, điểm)."""
    folded = [fold(l) for l in lines if l.strip()]
    if not folded:
        return None, 0.0
    scores = {}
    for aug_id, name in candidates.items():
        n = fold(name)
        best = 0.0
        for line in folded:
            # so cả dòng và đoạn con cùng độ dài (tên có thể nằm chung dòng với chữ khác)
            best = max(best, difflib.SequenceMatcher(None, n, line).ratio())
            if len(line) > len(n):
                for i in range(0, len(line) - len(n) + 1):
                    best = max(best, difflib.SequenceMatcher(None, n, line[i:i + len(n)]).ratio())
        scores[aug_id] = best
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    top_id, top = ranked[0]
    second = ranked[1][1] if len(ranked) > 1 else 0.0
    if top >= min_ratio and top - second >= 0.08:
        return top_id, top
    return None, top

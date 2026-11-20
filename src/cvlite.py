# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
"""Phần nhỏ của OpenCV mà bộ quét dùng, viết lại bằng numpy + Pillow (đã có sẵn trong app).

OpenCV (opencv-python-headless) chiếm ~84 MB trong bản cài – hơn nửa dung lượng app – trong khi bộ quét chỉ cần:
đổi cỡ ảnh, đổi hệ màu, đọc / ghi PNG và so khớp mẫu có mặt nạ (TM_CCOEFF_NORMED, dùng khi định vị bảng lõi).
Cùng tên hàm / hằng số như cv2 nên code gọi giữ nguyên: `import cvlite as cv2`. Ảnh vẫn theo quy ước của OpenCV:
mảng numpy, thứ tự kênh BGR / BGRA. tests/test_cvlite.py so từng hàm với OpenCV thật (cài ở requirements-dev.txt).
"""
from __future__ import annotations

import io

import numpy as np
from PIL import Image

INTER_NEAREST, INTER_LINEAR, INTER_CUBIC, INTER_AREA = 0, 1, 2, 3
COLOR_BGR2GRAY, COLOR_GRAY2BGRA, COLOR_BGR2HSV, COLOR_RGB2BGR, COLOR_BGR2RGB = 6, 9, 40, 4, 4
IMREAD_COLOR, IMREAD_UNCHANGED = 1, -1
TM_CCOEFF_NORMED = 5


# ---------- đổi cỡ ----------
def _area_axis(a: np.ndarray, n_out: int, axis: int) -> np.ndarray:
    """Thu nhỏ 1 trục theo diện tích phủ (đúng như INTER_AREA của OpenCV, kể cả tỉ lệ lẻ như 215 → 46):
    điểm ảnh ra = trung bình các điểm ảnh vào trong khoảng của nó, điểm ở mép tính theo phần bị phủ."""
    a = np.moveaxis(a, axis, 0).astype(np.float64)
    n_in = a.shape[0]
    scale = n_in / n_out
    cum = np.concatenate([np.zeros((1,) + a.shape[1:]), np.cumsum(a, axis=0)], axis=0)
    edges = np.arange(n_out + 1) * scale
    idx = np.minimum(np.floor(edges).astype(np.int64), n_in)
    frac = (edges - idx).reshape((-1,) + (1,) * (a.ndim - 1))
    integral = cum[idx] + frac * a[np.minimum(idx, n_in - 1)]
    return np.moveaxis((integral[1:] - integral[:-1]) / scale, 0, axis)


def _resize_plane(plane: np.ndarray, size: tuple[int, int], interpolation: int) -> np.ndarray:
    w, h = size
    src_h, src_w = plane.shape
    if interpolation == INTER_AREA and w <= src_w and h <= src_h:
        out = _area_axis(_area_axis(plane, h, 0), w, 1)
        if plane.dtype == np.uint8:
            return np.clip(np.floor(out + 0.5), 0, 255).astype(np.uint8)      # làm tròn nửa lên như OpenCV
        return out.astype(plane.dtype)
    if interpolation == INTER_AREA:            # phóng to: OpenCV dùng gần như song tuyến
        method = Image.Resampling.BILINEAR
    else:
        method = {INTER_NEAREST: Image.Resampling.NEAREST, INTER_LINEAR: Image.Resampling.BILINEAR,
                  INTER_CUBIC: Image.Resampling.BICUBIC}.get(interpolation, Image.Resampling.BILINEAR)
    if plane.dtype == np.uint8:
        return np.asarray(Image.fromarray(plane, "L").resize((w, h), method))
    out = np.asarray(Image.fromarray(plane.astype(np.float32), "F").resize((w, h), method))
    return out.astype(plane.dtype, copy=False)


def resize(img: np.ndarray, dsize, fx: float | None = None, fy: float | None = None,
           interpolation: int = INTER_LINEAR) -> np.ndarray:
    """Như cv2.resize: dsize = (rộng, cao), hoặc None kèm fx / fy. Từng kênh đổi cỡ riêng (không nhân alpha)."""
    if dsize is None:
        dsize = (int(round(img.shape[1] * fx)), int(round(img.shape[0] * (fy or fx))))
    w, h = int(dsize[0]), int(dsize[1])
    if img.ndim == 2:
        return _resize_plane(img, (w, h), interpolation)
    planes = [_resize_plane(np.ascontiguousarray(img[..., c]), (w, h), interpolation) for c in range(img.shape[2])]
    return np.ascontiguousarray(np.stack(planes, axis=-1))


# ---------- hệ màu ----------
def _gray(bgr: np.ndarray) -> np.ndarray:
    if bgr.dtype == np.uint8:                # cùng công thức số nguyên của OpenCV (khớp từng điểm ảnh)
        b, g, r = (bgr[..., i].astype(np.uint32) for i in range(3))
        return ((r * 9798 + g * 19235 + b * 3735 + 16384) >> 15).astype(np.uint8)
    b, g, r = (bgr[..., i] for i in range(3))
    return (0.299 * r + 0.587 * g + 0.114 * b).astype(bgr.dtype)


def _hsv(bgr: np.ndarray) -> np.ndarray:
    """uint8 theo quy ước OpenCV: H 0–179, S và V 0–255."""
    f = bgr[..., :3].astype(np.float32)
    b, g, r = f[..., 0], f[..., 1], f[..., 2]
    v = f.max(axis=-1)
    diff = v - f.min(axis=-1)
    s = np.where(v > 0, diff * 255.0 / np.maximum(v, 1e-6), 0)
    safe = np.maximum(diff, 1e-6)
    h = np.where(v == r, 60 * (g - b) / safe, np.where(v == g, 120 + 60 * (b - r) / safe, 240 + 60 * (r - g) / safe))
    h = np.where(diff == 0, 0, h) % 360
    return np.stack([np.round(h / 2) % 180, np.round(s), v], axis=-1).astype(np.uint8)


def cvtColor(img: np.ndarray, code: int) -> np.ndarray:  # noqa: N802 – cùng tên với OpenCV
    if code == COLOR_BGR2GRAY:
        return _gray(img)
    if code == COLOR_GRAY2BGRA:
        alpha = np.full(img.shape[:2], 255 if img.dtype == np.uint8 else 1, img.dtype)
        return np.dstack([img, img, img, alpha])
    if code == COLOR_BGR2HSV:
        return _hsv(img)
    if code == COLOR_RGB2BGR:                   # = COLOR_BGR2RGB: đảo thứ tự 3 kênh
        return np.ascontiguousarray(img[..., 2::-1] if img.shape[-1] == 3 else img[..., [2, 1, 0, 3]])
    raise ValueError(f"cvlite.cvtColor: chưa hỗ trợ mã {code}")


# ---------- đọc / ghi ảnh ----------
def _to_cv(im: Image.Image, unchanged: bool) -> np.ndarray:
    if not unchanged:
        return cvtColor(np.asarray(im.convert("RGB")), COLOR_RGB2BGR)
    if im.mode in ("P", "LA", "PA") or (im.mode == "L" and "transparency" in im.info):
        im = im.convert("RGBA")
    elif im.mode not in ("L", "RGB", "RGBA"):
        im = im.convert("RGBA" if "A" in im.mode else "RGB")
    a = np.asarray(im)
    return a if a.ndim == 2 else cvtColor(a, COLOR_RGB2BGR)


def imread(path: str, flags: int = IMREAD_COLOR) -> np.ndarray | None:
    try:
        with Image.open(path) as im:
            return _to_cv(im, flags == IMREAD_UNCHANGED)
    except Exception:
        return None


def imdecode(buf: np.ndarray, flags: int = IMREAD_COLOR) -> np.ndarray | None:
    try:
        with Image.open(io.BytesIO(np.asarray(buf, np.uint8).tobytes())) as im:
            return _to_cv(im, flags == IMREAD_UNCHANGED)
    except Exception:
        return None


def imencode(ext: str, img: np.ndarray, params=None) -> tuple[bool, np.ndarray]:
    """Chỉ cần PNG / JPEG (ảnh chẩn đoán)."""
    a = np.asarray(img)
    if a.ndim == 3:
        a = cvtColor(a, COLOR_BGR2RGB)
    pil = Image.fromarray(a)
    out = io.BytesIO()
    fmt = "JPEG" if ext.lower() in (".jpg", ".jpeg") else "PNG"
    pil.save(out, fmt, **({"compress_level": 3} if fmt == "PNG" else {"quality": 90}))
    return True, np.frombuffer(out.getvalue(), np.uint8)


# ---------- so khớp mẫu ----------
def _fft_size(n: int) -> int:
    """Kích thước FFT nhanh (chỉ có thừa số 2, 3, 5) ≥ n."""
    while True:
        m = n
        for p in (2, 3, 5):
            while m % p == 0:
                m //= p
        if m == 1:
            return n
        n += 1


class _Correlator:
    """Tương quan chéo 'valid' của 1 ảnh với nhiều nhân cùng cỡ, qua FFT (FFT của ảnh tính 1 lần)."""

    _last: tuple | None = None          # (ảnh gốc, shape FFT, F, F2): định vị so ~100 mẫu với cùng 1 ảnh

    def __init__(self, src: np.ndarray, img: np.ndarray, kh: int, kw: int):
        self.H, self.W = img.shape
        self.kh, self.kw = kh, kw
        self.shape = (_fft_size(self.H), _fft_size(self.W))
        last = _Correlator._last
        if last is not None and last[0] is src and last[1] == self.shape:
            self.F, self.F2 = last[2], last[3]
        else:
            self.F = np.fft.rfft2(img, self.shape)
            self.F2 = np.fft.rfft2(img * img, self.shape)
            _Correlator._last = (src, self.shape, self.F, self.F2)

    def corr(self, kernel: np.ndarray, squared: bool = False, both: bool = False):
        """Tương quan với ảnh (hoặc ảnh bình phương); both=True trả cả 2 (dùng chung FFT của nhân)."""
        K = np.fft.rfft2(kernel[::-1, ::-1], self.shape)       # tương quan = tích chập với nhân lật ngược

        def out(F):
            return np.fft.irfft2(F * K, self.shape)[self.kh - 1:self.H, self.kw - 1:self.W]
        if both:
            return out(self.F), out(self.F2)
        return out(self.F2 if squared else self.F)


def matchTemplate(image: np.ndarray, templ: np.ndarray, method: int = TM_CCOEFF_NORMED,  # noqa: N802
                  mask: np.ndarray | None = None) -> np.ndarray:
    """TM_CCOEFF_NORMED (có hoặc không mặt nạ nhị phân), cùng công thức OpenCV:
    R = Σ T'·I' / sqrt(Σ T'² · Σ I'²), T' = M·(T − TB), I' = M·(I − IB) – TB, IB: trung bình trong mặt nạ.
    Ô có phương sai 0 → NaN (như OpenCV)."""
    if method != TM_CCOEFF_NORMED:
        raise ValueError("cvlite.matchTemplate: chỉ hỗ trợ TM_CCOEFF_NORMED")
    img = np.asarray(image, np.float64)
    t = np.asarray(templ, np.float64)
    m = np.ones_like(t) if mask is None else (np.asarray(mask, np.float64) > 0).astype(np.float64)
    n = m.sum()
    if n == 0:
        return np.full((img.shape[0] - t.shape[0] + 1, img.shape[1] - t.shape[1] + 1), np.nan, np.float32)
    tp = m * (t - (m * t).sum() / n)
    c = _Correlator(image, img, *t.shape)
    num = c.corr(tp)
    s1, s2 = c.corr(m, both=True)         # Σ M·I và Σ M·I² trong mỗi cửa sổ
    var_i = s2 - s1 * s1 / n
    den = np.sqrt(np.maximum((tp * tp).sum() * var_i, 0))
    with np.errstate(divide="ignore", invalid="ignore"):
        r = np.where(den > 1e-6 * max(1.0, float((tp * tp).sum())), num / den, np.nan)
    return np.clip(r, -1, 1).astype(np.float32)

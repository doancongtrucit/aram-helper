"""Nhận diện 3 lõi đang được đưa ra trên màn hình bằng so khớp icon.

Hai bước:
1. Hiệu chỉnh (calibrate): tìm vị trí + kích thước 3 ô icon lõi trên màn hình (chậm ~1-3 s, làm 1 lần
   cho mỗi độ phân giải). Kết quả lưu ở data/calibration.json.
2. Nhận diện (detect): cắt đúng 3 ô đó, so với toàn bộ icon lõi bằng tương quan chuẩn hoá có mask
   (ZNCC) – vài chục ms, chạy mỗi giây được.

Chỉ chụp màn hình, không đọc bộ nhớ hay can thiệp game. Game cần chạy chế độ
Không viền (Borderless) hoặc Cửa sổ – chế độ Toàn màn hình độc quyền thường cho ảnh đen.

CLI để thử với ảnh chụp sẵn:
    python screen_scan.py icons                 # tải icon
    python screen_scan.py calibrate anh.png     # hiệu chỉnh từ ảnh
    python screen_scan.py detect anh.png        # nhận diện từ ảnh (cần đã hiệu chỉnh)
"""
from __future__ import annotations

import json
import os

# numpy/OpenBLAS mặc định giữ sẵn bộ nhớ cho mỗi nhân CPU (~500 MB cam kết); ma trận ở đây nhỏ → 1 luồng là đủ.
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import time  # noqa: E402
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

import playaram

DATA = Path(__file__).parent / "data"
ICON_DIR = DATA / "icons"
CALIB_FILE = DATA / "calibration.json"
CDRAGON = "https://raw.communitydragon.org/latest/game/"

ID_SIZE = 40          # cỡ icon (px) khi nhận diện
ID_SHIFT = 3          # dò lệch ±px quanh vị trí đã hiệu chỉnh (ở cỡ ID_SIZE)
MATCH_MIN = 0.55      # điểm tối thiểu để coi là khớp
MARGIN_MIN = 0.02     # cách biệt tối thiểu với icon khác (ngoài nhóm dễ nhầm)
CLOSE_DELTA = 0.045   # icon có điểm cách icon tốt nhất ≤ mức này được coi là dễ nhầm → ứng viên (OCR phân xử)
CLOSE_MAX = 6


# ---------------- icon ----------------

def ensure_icons(catalog: list[dict], log=print) -> int:
    """Tải icon gốc (256px, có alpha) của mọi lõi vào data/icons/<id>.png. Trả về số icon mới tải."""
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    n = 0
    for a in catalog:
        dest = ICON_DIR / f"{a['id']}.png"
        if dest.exists() or not a.get("asset"):
            continue
        for url in (CDRAGON + a["asset"], playaram.BASE + "/media/game-asset/" + a["asset"]):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": playaram.USER_AGENT})
                with urllib.request.urlopen(req, timeout=15) as r:
                    dest.write_bytes(r.read())
                n += 1
                break
            except Exception:
                continue
        else:
            log(f"  không tải được icon {a['id']} {a['name']}")
        time.sleep(0.05)
    return n


def _load_rgba(path: Path) -> np.ndarray | None:
    im = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if im is None:
        return None
    if im.ndim == 2:
        im = cv2.cvtColor(im, cv2.COLOR_GRAY2BGRA)
    if im.shape[2] == 3:
        im = np.dstack([im, np.full(im.shape[:2], 255, np.uint8)])
    return im


def _tight_square(im: np.ndarray) -> np.ndarray:
    """Giữ nguyên khung vuông gốc của icon (icon game luôn vẽ đủ khung), chỉ đảm bảo là hình vuông."""
    h, w = im.shape[:2]
    s = max(h, w)
    out = np.zeros((s, s, 4), np.uint8)
    out[(s - h) // 2:(s - h) // 2 + h, (s - w) // 2:(s - w) // 2 + w] = im
    return out


# ---------------- ngân hàng mẫu ----------------

def unique_icons(icons: dict[int, np.ndarray]) -> dict[int, list[int]]:
    """Nhiều lõi dùng chung 1 icon (vd. DOOM/HEAVY/THRASH/POWER). Trả về {id đại diện: [mọi id cùng icon]}."""
    groups: dict[bytes, list[int]] = {}
    for aug_id, rgba in icons.items():
        key = cv2.resize(rgba, (32, 32), interpolation=cv2.INTER_AREA).tobytes()
        groups.setdefault(key, []).append(aug_id)
    return {ids[0]: ids for ids in groups.values()}


class Bank:
    """Mẫu icon ở cỡ cố định (ID_SIZE), mỗi mẫu ứng với một nhóm lõi dùng chung icon (self.groups[k]).

    Mô hình cả ô: pixel ≈ g·(α·icon) + (1-α)·nền_c  (g: độ sáng, nền_c: màu nền mỗi kênh).
    Chỉ giữ 2 ma trận: FG = α·icon (K x P·3) và BG = 1-α (K x P) → ~4 MB thay vì ~20 MB."""

    def __init__(self, icons: dict[int, np.ndarray], size: int):
        self.size = size
        self.ids: list[int] = []
        self.groups: list[list[int]] = []
        FG, BG = [], []
        for aug_id, members in unique_icons(icons).items():
            im = cv2.resize(_tight_square(icons[aug_id]), (size, size), interpolation=cv2.INTER_AREA).astype(np.float32)
            a = im[..., 3] / 255.0
            if (a > 0.5).sum() < size * size * 0.05:            # icon gần như trống
                continue
            self.ids.append(aug_id)
            self.groups.append(members)
            FG.append((a[..., None] * im[..., :3]).ravel())
            BG.append((1 - a).ravel())
        self.FG = np.stack(FG).astype(np.float32)          # K x D   (D = P·3)
        self.BG = np.stack(BG).astype(np.float32)          # K x P
        K = len(self.ids)
        fg3 = self.FG.reshape(K, -1, 3)
        G = np.zeros((K, 4, 4), np.float64)
        G[:, 0, 0] = (self.FG.astype(np.float64) ** 2).sum(1)
        bb = (self.BG.astype(np.float64) ** 2).sum(1)
        for c in range(3):
            v = (fg3[..., c] * self.BG).sum(1)
            G[:, 0, c + 1] = G[:, c + 1, 0] = v
            G[:, c + 1, c + 1] = bb
        self.Ginv = np.linalg.inv(G + np.eye(4) * 1e-3)    # tính sẵn: mỗi lần quét chỉ còn phép nhân

    def score(self, windows: np.ndarray) -> np.ndarray:
        """Điểm R² của mô hình 'icon dán trên nền 1 màu' trên toàn ô. N x K, 1 = khớp hoàn hảo.
        Phạt cả icon sai lẫn icon chỉ khớp một phần (vì vùng nền cũng phải khớp)."""
        N, K = windows.shape[0], len(self.ids)
        r1 = windows @ self.FG.T                                    # N x K
        ch = windows.reshape(N, -1, 3)
        planes = np.ascontiguousarray(ch.transpose(2, 0, 1))                # 3 x N x P, liền bộ nhớ → BLAS nhanh
        r2 = np.stack([planes[c] @ self.BG.T for c in range(3)], axis=2)    # N x K x 3
        rhs = np.concatenate([r1[..., None], r2], axis=2).astype(np.float64)  # N x K x 4
        coef = np.einsum("kij,nkj->nki", self.Ginv, rhs)
        sse = (windows.astype(np.float64) ** 2).sum(1)[:, None] - (coef * rhs).sum(2)
        ch = ch.astype(np.float64)
        sst = ((ch - ch.mean(1, keepdims=True)) ** 2).sum((1, 2))[:, None]
        r2score = 1 - sse / np.maximum(sst, 1e-6)
        return np.where(coef[..., 0] > 0, r2score, -1.0)


ICON_KEEP = 64   # chỉ giữ icon 64px trong RAM (hiệu chỉnh dùng ≤ 54px, nhận diện 40px): 4 MB thay vì 59 MB


def load_icons(catalog: list[dict]) -> dict[int, np.ndarray]:
    icons = {}
    for a in catalog:
        im = _load_rgba(ICON_DIR / f"{a['id']}.png")
        if im is not None:
            im = _tight_square(im)
            if im.shape[0] > ICON_KEEP:
                im = cv2.resize(im, (ICON_KEEP, ICON_KEEP), interpolation=cv2.INTER_AREA)
            icons[a["id"]] = im
    return icons


# ---------------- hiệu chỉnh ----------------

@dataclass
class Calibration:
    width: int
    height: int
    size: int                       # cạnh icon trên màn hình (px)
    centers: list[tuple[int, int]]  # tâm 3 icon (px)

    def save(self):
        DATA.mkdir(exist_ok=True)
        CALIB_FILE.write_text(json.dumps(self.__dict__), encoding="utf-8")

    @staticmethod
    def load() -> "Calibration | None":
        if not CALIB_FILE.exists():
            return None
        d = json.loads(CALIB_FILE.read_text(encoding="utf-8"))
        return Calibration(d["width"], d["height"], d["size"], [tuple(c) for c in d["centers"]])


def _nms_peaks(score: np.ndarray, radius: int, k: int = 12, floor: float = 0.3):
    s = score.copy()
    peaks = []
    for _ in range(k):
        y, x = np.unravel_index(np.argmax(s), s.shape)
        v = float(s[y, x])
        if v < floor:
            break
        peaks.append((v, int(x), int(y)))
        s[max(0, y - radius):y + radius + 1, max(0, x - radius):x + radius + 1] = -1
    return peaks


def _best_triple(peaks, size):
    """3 đỉnh cùng hàng ngang, cách đều nhau, xa nhau hơn 1 icon."""
    best = None
    for i in range(len(peaks)):
        for j in range(len(peaks)):
            for k in range(len(peaks)):
                a, b, c = peaks[i], peaks[j], peaks[k]
                if not (a[1] < b[1] < c[1]):
                    continue
                if max(abs(a[2] - b[2]), abs(b[2] - c[2]), abs(a[2] - c[2])) > size * 0.25:
                    continue
                d1, d2 = b[1] - a[1], c[1] - b[1]
                if min(d1, d2) < size * 1.2 or max(d1, d2) / min(d1, d2) > 1.2:
                    continue
                s = (a[0] + b[0] + c[0]) / 3
                if best is None or s > best[0]:
                    best = (s, [a, b, c])
    return best


def calibrate(screen_bgr: np.ndarray, icons: dict[int, np.ndarray], log=print) -> Calibration | None:
    """Tìm 3 icon lõi trên ảnh màn hình. Cần ảnh chụp lúc đang hiện bảng chọn lõi."""
    H, W = screen_bgr.shape[:2]
    f = 400.0 / W                                     # làm việc ở độ rộng 400 px
    y_lo, y_hi = int(H * 0.08), int(H * 0.85)         # bảng chọn lõi nằm giữa màn hình
    small = cv2.resize(screen_bgr[y_lo:y_hi], (int(W * f), int((y_hi - y_lo) * f)), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(np.float32)
    uniq = [icons[k] for k in unique_icons(icons)]
    best = None
    t0 = time.time()
    # Kích thước icon trên màn hình: 4%–13% chiều rộng
    for frac in np.arange(0.04, 0.135, 0.01):
        s = int(round(W * frac * f))
        if s < 12:
            continue
        acc = None
        for rgba in uniq:
            im = cv2.resize(_tight_square(rgba), (s, s), interpolation=cv2.INTER_AREA)
            tg = cv2.cvtColor(im[..., :3], cv2.COLOR_BGR2GRAY).astype(np.float32)
            m = (im[..., 3] > 127).astype(np.float32)
            if m.sum() < s * s * 0.05:
                continue
            r = cv2.matchTemplate(gray, tg, cv2.TM_CCOEFF_NORMED, mask=m)
            r = np.nan_to_num(r, nan=-1, posinf=-1, neginf=-1)
            acc = r if acc is None else np.maximum(acc, r)
        if acc is None:
            continue
        triple = _best_triple(_nms_peaks(acc, s), s)
        if triple and (best is None or triple[0] > best[0]):
            best = (triple[0], s, triple[1])
    log(f"  hiệu chỉnh thô: {time.time() - t0:.1f}s, điểm {best[0]:.2f}" if best else "  không tìm thấy 3 icon thẳng hàng")
    if not best or best[0] < 0.45:
        return None
    _, s, pts = best
    size = int(round(s / f))
    centers = [(int(round((x + s / 2) / f)), int(round((y + s / 2) / f)) + y_lo) for _, x, y in pts]
    calib = _refine(screen_bgr, Calibration(W, H, size, centers), icons)
    return calib


def _refine(screen_bgr, calib: Calibration, icons) -> Calibration:
    """Tinh chỉnh cỡ icon ±15% bằng điểm nhận diện trung bình của 3 ô."""
    best = (-1.0, calib)
    for k in np.linspace(0.85, 1.15, 13):
        c = Calibration(calib.width, calib.height, int(round(calib.size * k)), calib.centers)
        res = detect(screen_bgr, c, bank_for(icons))
        sc = float(np.mean([r["score"] for r in res])) if res else -1
        if sc > best[0]:
            best = (sc, c)
    # Tinh chỉnh tâm theo độ lệch tốt nhất tìm được
    c = best[1]
    res = detect(screen_bgr, c, bank_for(icons))
    k = c.size / ID_SIZE
    centers = [(int(round(cx + r["dx"] * k)), int(round(cy + r["dy"] * k))) for (cx, cy), r in zip(c.centers, res)]
    return Calibration(c.width, c.height, c.size, centers)


_bank_cache: dict[int, Bank] = {}


def bank_for(icons: dict[int, np.ndarray]) -> Bank:
    key = id(icons)
    if key not in _bank_cache:
        _bank_cache.clear()
        _bank_cache[key] = Bank(icons, ID_SIZE)
    return _bank_cache[key]


# ---------------- nhận diện ----------------

def scan_region(calib: Calibration, full: tuple[int, int]) -> tuple[int, int, int, int]:
    """Vùng màn hình đủ chứa 3 icon + chữ trên thẻ (để OCR). Chỉ chụp vùng này thay vì cả màn hình."""
    W, H = full
    sx, sy = W / calib.width, H / calib.height
    s = calib.size * sx
    xs = [cx * sx for cx, _ in calib.centers]
    ys = [cy * sy for _, cy in calib.centers]
    x0, x1 = max(0, int(min(xs) - 1.5 * s)), min(W, int(max(xs) + 1.5 * s))
    y0, y1 = max(0, int(min(ys) - 1.4 * s)), min(H, int(max(ys) + 2.5 * s))
    return x0, y0, x1, y1


def detect(screen_bgr: np.ndarray, calib: Calibration, bank: Bank,
           origin: tuple[int, int] = (0, 0), full: tuple[int, int] | None = None) -> list[dict]:
    """Nhận diện lõi ở 3 vị trí đã hiệu chỉnh. Luôn trả 3 kết quả (kể cả điểm thấp).
    screen_bgr có thể chỉ là một vùng của màn hình: origin = góc trái trên của vùng, full = (W, H) cả màn."""
    W, H = full or (screen_bgr.shape[1], screen_bgr.shape[0])
    ox, oy = origin
    sx, sy = W / calib.width, H / calib.height
    out = []
    S, R = ID_SIZE, ID_SHIFT
    for cx, cy in calib.centers:
        size = calib.size * sx
        half = size / 2 * (S + 2 * R) / S
        x0, y0 = int(round(cx * sx - half)) - ox, int(round(cy * sy - half)) - oy
        x1, y1 = int(round(cx * sx + half)) - ox, int(round(cy * sy + half)) - oy
        crop = screen_bgr[max(0, y0):y1, max(0, x0):x1]
        if crop.size == 0 or crop.shape[0] < 8 or crop.shape[1] < 8:
            out.append({"id": None, "score": -1.0, "second": -1.0, "dx": 0, "dy": 0})
            continue
        crop = cv2.resize(crop, (S + 2 * R, S + 2 * R), interpolation=cv2.INTER_AREA).astype(np.float32)
        wins, shifts = [], []
        for dy in range(2 * R + 1):
            for dx in range(2 * R + 1):
                wins.append(crop[dy:dy + S, dx:dx + S].ravel())
                shifts.append((dx - R, dy - R))
        sc = bank.score(np.stack(wins))           # N x K
        per_t = sc.max(axis=0)                     # K
        order = np.argsort(per_t)[::-1]
        b = int(order[0])
        n = int(np.argmax(sc[:, b]))
        # Các icon gần giống nhau (cùng hình chính, khác viền mờ) đều là ứng viên
        close = [int(k) for k in order[:CLOSE_MAX] if per_t[k] >= per_t[b] - CLOSE_DELTA]
        cands = [i for k in close for i in bank.groups[k]]
        far = [per_t[k] for k in order if int(k) not in close]
        out.append({
            "id": bank.ids[b],
            "candidates": cands,
            "score": float(per_t[b]),
            "second": float(far[0]) if far else -1.0,
            "dx": shifts[n][0], "dy": shifts[n][1],
            "center": (int(round(cx * sx)), int(round(cy * sy))), "size": int(round(size)),
        })
    return out


def read_offer(screen_bgr: np.ndarray, calib: Calibration, bank: Bank, catalog: list[dict],
               use_ocr: bool = True, origin: tuple[int, int] = (0, 0), full: tuple[int, int] | None = None,
               ocr_cache: dict | None = None) -> list[dict]:
    """Nhận diện đầy đủ: icon → ứng viên → lọc độ hiếm → OCR tên nếu còn nhiều ứng viên.
    ocr_cache: {(ô, ứng viên)} → kết quả OCR; bảng chọn còn nguyên thì không OCR lại mỗi giây."""
    import ocr
    rarity_of = {a["id"]: a["rarity"] for a in catalog}
    names = {a["id"]: a["name"] for a in catalog}
    res = resolve_rarity(detect(screen_bgr, calib, bank, origin, full), rarity_of)
    # Chỉ OCR khi icon đã khớp chắc chắn (bảng chọn lõi thật sự đang hiện) – lúc đánh nhau thì bỏ qua
    if not use_ocr or not ocr.AVAILABLE or not confident(res):
        return res
    h, w = screen_bgr.shape[:2]
    ox, oy = origin
    out = []
    for i, r in enumerate(res):
        r = {**r, "ocr": None}
        if len(r["candidates"]) > 1:
            key = (i, tuple(r["candidates"]))
            if ocr_cache is not None and key in ocr_cache:
                pick, info = ocr_cache[key]
            else:
                cx, cy = r["center"]
                s = r["size"]
                # Tên lõi thường ở dưới icon trong thẻ; đọc rộng cả thẻ cho chắc
                x0, x1 = max(0, int(cx - 1.4 * s) - ox), min(w, int(cx + 1.4 * s) - ox)
                y0, y1 = max(0, int(cy - 1.3 * s) - oy), min(h, int(cy + 2.4 * s) - oy)
                lines = ocr.read_lines(screen_bgr[y0:y1, x0:x1])
                pick, ratio = ocr.best_name(lines, {c: names.get(c, "") for c in r["candidates"]})
                info = {"lines": lines, "ratio": round(ratio, 2)}
                if ocr_cache is not None:
                    ocr_cache[key] = (pick, info)
            r["ocr"] = info
            if pick is not None:
                r["candidates"] = [pick]
                r["id"] = pick
        out.append(r)
    return out


def confident(results: list[dict]) -> bool:
    return len(results) == 3 and all(
        r["id"] is not None and r["score"] >= MATCH_MIN and r["score"] - r["second"] >= MARGIN_MIN for r in results
    )


def resolve_rarity(results: list[dict], rarity_of: dict[int, str]) -> list[dict]:
    """3 lõi trong một lượt cùng độ hiếm: lấy độ hiếm từ ô đã chắc chắn để lọc ứng viên ô còn lại."""
    known = [rarity_of.get(r["candidates"][0]) for r in results
             if r.get("candidates") and len({rarity_of.get(c) for c in r["candidates"]}) == 1]
    if not known:
        return results
    rarity = max(set(known), key=known.count)
    out = []
    for r in results:
        cands = [c for c in r.get("candidates", []) if rarity_of.get(c) == rarity] or r.get("candidates", [])
        out.append({**r, "candidates": cands, "id": cands[0] if cands else r["id"], "rarity": rarity})
    return out


# ---------------- chụp màn hình ----------------

def _dpi_aware():
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass


FAKE_SCREEN = os.environ.get("ARAM_FAKE_SCREEN")   # thử nghiệm: đọc ảnh này thay vì chụp màn hình


def screen_size() -> tuple[int, int]:
    """(W, H) màn hình chính theo điểm ảnh thật."""
    if FAKE_SCREEN:
        from PIL import Image
        with Image.open(FAKE_SCREEN) as im:     # chỉ đọc kích thước, không giải mã cả ảnh
            return im.size
    import ctypes
    _dpi_aware()
    return ctypes.windll.user32.GetSystemMetrics(0), ctypes.windll.user32.GetSystemMetrics(1)


_gdi = None


def _gdi_setup():
    import ctypes
    from ctypes import wintypes as wt
    u, g = ctypes.windll.user32, ctypes.windll.gdi32
    u.GetDC.restype, u.GetDC.argtypes = wt.HDC, [wt.HWND]
    u.ReleaseDC.argtypes = [wt.HWND, wt.HDC]
    g.CreateCompatibleDC.restype, g.CreateCompatibleDC.argtypes = wt.HDC, [wt.HDC]
    g.CreateCompatibleBitmap.restype = wt.HBITMAP
    g.CreateCompatibleBitmap.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int]
    g.SelectObject.restype, g.SelectObject.argtypes = wt.HGDIOBJ, [wt.HDC, wt.HGDIOBJ]
    g.BitBlt.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                         wt.HDC, ctypes.c_int, ctypes.c_int, wt.DWORD]
    g.GetDIBits.argtypes = [wt.HDC, wt.HBITMAP, wt.UINT, wt.UINT, ctypes.c_void_p, ctypes.c_void_p, wt.UINT]
    g.DeleteObject.argtypes, g.DeleteDC.argtypes = [wt.HGDIOBJ], [wt.HDC]

    class BIH(ctypes.Structure):
        _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG), ("biPlanes", wt.WORD),
                    ("biBitCount", wt.WORD), ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                    ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
                    ("biClrImportant", wt.DWORD)]
    return ctypes, u, g, BIH


def _gdi_grab(x0: int, y0: int, x1: int, y1: int) -> np.ndarray:
    """Chụp vùng bằng GDI trực tiếp: ~12 ms cho vùng thẻ lõi (Pillow ImageGrab ~50 ms)."""
    global _gdi
    if _gdi is None:
        _gdi = _gdi_setup()
    ctypes, u, g, BIH = _gdi
    w, h = x1 - x0, y1 - y0
    sdc = u.GetDC(None)
    mdc = g.CreateCompatibleDC(sdc)
    bmp = g.CreateCompatibleBitmap(sdc, w, h)
    old = g.SelectObject(mdc, bmp)
    try:
        g.BitBlt(mdc, 0, 0, w, h, sdc, x0, y0, 0x00CC0020)          # SRCCOPY
        bi = BIH(ctypes.sizeof(BIH), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
        buf = np.empty((h, w, 4), np.uint8)
        if not g.GetDIBits(mdc, bmp, 0, h, buf.ctypes.data, ctypes.byref(bi), 0):
            raise OSError("GetDIBits thất bại")
        return np.ascontiguousarray(buf[..., :3])                     # BGRA → BGR
    finally:
        g.SelectObject(mdc, old)
        g.DeleteObject(bmp)
        g.DeleteDC(mdc)
        u.ReleaseDC(None, sdc)


def grab_screen(bbox: tuple[int, int, int, int] | None = None) -> np.ndarray:
    """Chụp màn hình chính, hoặc chỉ vùng bbox = (x0, y0, x1, y1) – nhẹ hơn nhiều so với cả màn."""
    if FAKE_SCREEN:
        im = read_image(FAKE_SCREEN)
        return im[bbox[1]:bbox[3], bbox[0]:bbox[2]].copy() if bbox else im
    _dpi_aware()
    try:
        return _gdi_grab(*(bbox or (0, 0, *screen_size())))
    except Exception:                       # dự phòng
        from PIL import ImageGrab
        return cv2.cvtColor(np.asarray(ImageGrab.grab(bbox=bbox)), cv2.COLOR_RGB2BGR)


def read_image(path: str) -> np.ndarray:
    data = np.fromfile(path, np.uint8)     # đọc được cả đường dẫn có dấu tiếng Việt
    im = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if im is None:
        raise ValueError(f"Không đọc được ảnh {path}")
    return im


def annotate(screen_bgr, calib: Calibration, results, names: dict[int, str]) -> np.ndarray:
    out = screen_bgr.copy()
    for (cx, cy), r in zip(calib.centers, results):
        h = calib.size // 2
        ok = r["score"] >= MATCH_MIN
        cv2.rectangle(out, (cx - h, cy - h), (cx + h, cy + h), (80, 220, 120) if ok else (60, 60, 230), 2)
        label = f"{r['id']} {r['score']:.2f}"
        cv2.putText(out, label, (cx - h, cy + h + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    return out


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "icons"
    catalog = playaram.get_augment_catalog()
    names = {a["id"]: a["name"] for a in catalog}
    print(f"Đã tải thêm {ensure_icons(catalog)} icon ({len(catalog)} lõi).")
    if cmd in ("calibrate", "detect"):
        icons = load_icons(catalog)
        img = read_image(sys.argv[2]) if len(sys.argv) > 2 else grab_screen()
        if cmd == "calibrate":
            c = calibrate(img, icons)
            if not c:
                sys.exit("Không hiệu chỉnh được – ảnh có đang hiện bảng chọn 3 lõi không?")
            c.save()
            print("Đã lưu hiệu chỉnh:", c)
        calib = Calibration.load()
        if not calib:
            sys.exit("Chưa hiệu chỉnh.")
        t0 = time.time()
        res = detect(img, calib, bank_for(icons))
        print(f"Nhận diện {1000 * (time.time() - t0):.0f} ms, chắc chắn: {confident(res)}")
        for r in res:
            print(f"  {names.get(r['id'], r['id'])}: {r['score']:.3f} (thứ 2: {r['second']:.3f})")
        out = DATA / "debug_detect.png"
        cv2.imencode(".png", annotate(img, calib, res, names))[1].tofile(str(out))
        print("Ảnh đánh dấu:", out)

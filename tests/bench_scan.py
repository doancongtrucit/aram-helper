"""Đo độ chính xác nhận diện trên ảnh giả lập. Chạy: python tests/bench_scan.py [số_lượt]"""
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8")

import playaram  # noqa: E402
import screen_scan as ss  # noqa: E402
from synthetic import make_screen  # noqa: E402

N = int(sys.argv[1]) if len(sys.argv) > 1 else 40
WITH_NAMES = '--no-names' not in sys.argv  # thẻ có vẽ tên lõi + dùng OCR
cat = playaram.get_augment_catalog()
names = {a["id"]: a["name"] for a in cat}
rarity_of = {a["id"]: a["rarity"] for a in cat}
icons = ss.load_icons(cat)
by_rarity = {}
for a in cat:
    if a["id"] in icons:
        by_rarity.setdefault(a["rarity"], []).append(a["id"])

rng = random.Random(7)
for width, height in ((1920, 1080), (2560, 1440)):
    r0 = rng.choice(list(by_rarity))
    first = make_screen(icons, rng.sample(by_rarity[r0], 3), r0, width, height, seed=1)
    t = time.time()
    calib = ss.calibrate(first, icons, log=lambda *_: None)
    print(f"[{width}x{height}] hiệu chỉnh {time.time() - t:.1f}s → {calib}")
    if not calib:
        continue
    bank = ss.bank_for(icons)
    exact = in_group = conf = 0
    t_det = 0.0
    for i in range(N):
        r = rng.choice(list(by_rarity))
        offer = rng.sample(by_rarity[r], 3)
        img = make_screen(icons, offer, r, width, height, seed=100 + i, names=names if WITH_NAMES else None)
        t = time.time()
        res = ss.read_offer(img, calib, bank, cat, use_ocr=WITH_NAMES)
        t_det += time.time() - t
        conf += ss.confident(res)
        exact += all(x["candidates"] == [o] for x, o in zip(res, offer))
        ok = all(o in x["candidates"] for x, o in zip(res, offer))
        in_group += ok
        if not ok:
            print("  SAI", [names[o] for o in offer], "→", [[names[c] for c in x["candidates"]] for x in res],
                  [round(x["score"], 2) for x in res])
    print(f"  đúng nhóm {in_group}/{N} · chỉ còn 1 lựa chọn {exact}/{N} · chắc chắn {conf}/{N} · "
          f"{1000 * t_det / N:.0f} ms/lượt")

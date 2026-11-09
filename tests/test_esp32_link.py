# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
"""Gói ARAM gửi lên ESP32: lọc ký tự, dựng nội dung, giới hạn kích thước, gửi UDP thật tới cổng cục bộ."""
import json
import socket
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))
import fixtures  # noqa: E402
import advice  # noqa: E402
import esp32_link as el  # noqa: E402
import playaram  # noqa: E402

CHAMP = playaram.parse_champion_page(fixtures.load("yasuo"), "yasuo")
CATALOG = {a["id"]: a for a in playaram.parse_augment_catalog(fixtures.load("augments"))}
CU_DAM, BAY_ONG, KHONG_NHAN, RUT_KIEM = 1058, 3048, 1018, 1134
COUNTER = [{"item_id": 3033, "name": "Lời Nhắc Tử Vong", "why": "3/5 địch hồi máu", "icon": "x"},
           {"item_id": None, "name": "Đội địch", "why": "65% phép · 2 khống chế", "icon": None}]


def state(offer=True, in_game=True):
    return {"game": {"in_game": in_game}, "champion": CHAMP, "owned": [CU_DAM],
            "advice": advice.rank_offer([[KHONG_NHAN], [BAY_ONG], [RUT_KIEM]], CHAMP, CATALOG, {CU_DAM}) if offer else None,
            "counter": COUNTER}


class Clean(unittest.TestCase):
    def test_keeps_vietnamese_drops_symbols(self):
        self.assertEqual(el.clean("Bầy Ong ★ Nảy Bật · 71% → A"), "Bầy Ong Nảy Bật - 71% > A")
        self.assertEqual(el.clean("Ngộ Không 🐒"), "Ngộ Không")
        self.assertTrue(len(el.clean("x" * 100, 10)) <= 10)


class Payload(unittest.TestCase):
    def test_offer_payload(self):
        p = el.build_payload(state())
        self.assertEqual(p["ig"], 1)
        self.assertEqual(p["ch"], "Yasuo")
        self.assertEqual(p["of"][0][0], "Bầy Ong Nảy Bật")       # xếp theo hạng, lõi nên chọn đầu tiên
        self.assertEqual(p["of"][0][3], 1)
        self.assertEqual(p["of"][0][2], "+3 A")
        self.assertEqual(p["cb"][0], "S")                         # combo S với Cú Đấm đã có
        self.assertEqual(p["ct"][0], ["Lời Nhắc Tử Vong", "3/5 địch hồi máu"])
        self.assertEqual(p["ct"][1][0], "Địch:")
        self.assertIn(">", p["bd"])
        self.assertEqual(p["ow"], "Cú Đấm Thần Bí")

    def test_between_picks_has_no_offer(self):
        p = el.build_payload(state(offer=False))
        self.assertNotIn("of", p)
        self.assertIn("bd", p)

    def test_out_of_game(self):
        self.assertEqual(el.build_payload(state(in_game=False)), {"type": "aram", "ig": 0})

    def test_encode_fits_device_limit(self):
        p = el.build_payload(state())
        p["ow"] = "Ồ" * 2000
        data = el.encode(p, "tok", 3)
        self.assertLessEqual(len(data), el.MAX_BYTES)
        d = json.loads(data.decode("utf-8"))
        self.assertEqual((d["token"], d["seq"], d["type"]), ("tok", 3, "aram"))
        self.assertNotIn("ow", d)                                  # trường phụ bị bỏ khi quá dài


class Link(unittest.TestCase):
    def test_sends_on_change_and_final_out_of_game(self):
        rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        rx.bind(("127.0.0.1", 0))
        rx.settimeout(2)
        port = rx.getsockname()[1]
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "esp32.json"
            cfg.write_text(json.dumps({"host": "127.0.0.1", "port": port, "token": "tok"}), encoding="utf-8")
            st = {"v": state()}
            link = el.Esp32Link(lambda: st["v"], cfg, log=lambda *_: None)
            link.tick()
            first = json.loads(rx.recv(2048).decode("utf-8"))
            self.assertEqual((first["ig"], first["seq"]), (1, 1))
            st["v"] = state(in_game=False)
            link.tick()
            last = json.loads(rx.recv(2048).decode("utf-8"))
            self.assertEqual((last["ig"], last["seq"]), (0, 2))
            link.tick()                                            # đã báo hết trận: không gửi nữa
            with self.assertRaises(socket.timeout):
                rx.settimeout(0.3)
                rx.recv(2048)
        rx.close()

    def test_resolve_from_bridge_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            bridge = Path(tmp)
            (bridge / "config.json").write_text(json.dumps({"notifications": {"token": "abc"}}), encoding="utf-8")
            (bridge / "device_state.json").write_text(json.dumps({"connected": True, "ip": "10.0.0.9", "port": 4210}),
                                                      encoding="utf-8")
            cfg = bridge / "esp32.json"
            cfg.write_text(json.dumps({"bridge_dir": str(bridge)}), encoding="utf-8")
            self.assertEqual(el.Esp32Link(dict, cfg).resolve(), ("10.0.0.9", 4210, "abc"))
            (bridge / "device_state.json").write_text(json.dumps({"connected": False}), encoding="utf-8")
            self.assertIsNone(el.Esp32Link(dict, cfg).resolve())


if __name__ == "__main__":
    unittest.main()

"""Đẩy tóm tắt trận ARAM lên màn ESP32 (PC Control Deck, màn hình "ARAM") qua Wi-Fi UDP.

Dùng chung kênh UDP + token với thông báo PC của PC Control Deck. Cấu hình ở data/esp32.json (không commit):
    {"bridge_dir": "<thư mục host của PC Control Deck>"}   – đọc token (config.json) + IP thiết bị (device_state.json)
hoặc khai báo thẳng:
    {"host": "<IP thiết bị>", "port": 4210, "token": "<token>"}
Không có file cấu hình thì tính năng tắt.
"""
from __future__ import annotations

import json
import socket
import threading
import time
import unicodedata
from pathlib import Path

import advice
import paths
import settings

CONFIG = paths.DATA / "esp32.json"
MAX_BYTES = 1024          # giới hạn gói UDP của thiết bị (net_notify.h UDP_NOTIFY_MAX)
HEARTBEAT = 5.0           # đang trong trận: gửi lại mỗi 5 giây (thiết bị coi 15 giây im lặng là hết trận)
RESOLVE_EVERY = 30.0

_REPLACE = {"·": "-", "→": ">", "–": "-", "—": "-", "★": "", "…": "...", "’": "'", "“": '"', "”": '"'}


def _allowed(ch: str) -> bool:
    """Giống firmware (text_vi.cpp isAllowed): ASCII in được + chữ Latin tiếng Việt."""
    cp = ord(ch)
    return (0x20 <= cp <= 0x7E or (0xC0 <= cp <= 0x17F and cp not in (0xD7, 0xF7))
            or cp in (0x1A0, 0x1A1, 0x1AF, 0x1B0) or 0x1EA0 <= cp <= 0x1EF9)


def clean(text, limit: int = 60) -> str:
    s = unicodedata.normalize("NFC", str(text or ""))
    for a, b in _REPLACE.items():
        s = s.replace(a, b)
    s = " ".join("".join(ch for ch in s if _allowed(ch)).split())
    return s if len(s) <= limit else s[: limit - 1].rstrip() + "."


def _wr(s: dict) -> str:
    if s.get("winrate") is None:
        return "?"
    return f"{s['winrate']:.1f}%" + ("*" if s.get("source") == "chung" else "")


def build_payload(state: dict) -> dict:
    """Gói ARAM (chưa có token / seq) từ trạng thái app. ig = 0 khi không trong trận."""
    champ = state.get("champion") or {}
    game = state.get("game") or {}
    if not champ or not game.get("in_game"):
        return {"type": "aram", "ig": 0}
    owned = list(state.get("owned") or [])
    names = {a["id"]: a["name"] for items in (champ.get("augments") or {}).values() for a in items}
    p = {"type": "aram", "ig": 1, "ch": clean(champ.get("name"), 24), "tr": clean(champ.get("tier"), 3),
         "wr": f"{champ['winrate']:.1f}%" if champ.get("winrate") else ""}

    adv = sorted(state.get("advice") or [], key=lambda a: a["rank"])
    if adv:
        rows = []
        for a in adv[:3]:
            b = a["best"]
            name = b["name"] + (f" (1/{len(a['candidates'])})" if len(a["candidates"]) > 1 else "")
            note = f"+{advice.TIER_BONUS[b['fit']]} {b['fit']}" if b.get("fit") else ""
            rows.append([clean(name, 28), _wr(b), note, 1 if a["rank"] == 1 else 0])
        p["of"] = rows
        offered = [c["id"] for a in adv for c in a["candidates"]]
        combos = advice.offer_combos(champ, offered, set(owned), limit=1)
    else:
        combos = advice.offer_combos(champ, owned, set(owned), limit=1) if owned else []
    if combos:
        c = combos[0]
        p["cb"] = [c["tier"], clean(" + ".join(a["name"] for a in c["augments"]), 80),
                   f"{c['owned_count']}/{len(c['augments'])}"]

    ct = []
    for line in (state.get("counter") or [])[:2]:
        title = line["name"] if line.get("icon") else "Địch:"
        ct.append([clean(title, 26), clean(line.get("why"), 40)])
    if ct:
        p["ct"] = ct

    builds = champ.get("builds") or []
    if builds:
        core = [i["name"] for i in builds[0].get("items", []) if i.get("core")] or \
               [i["name"] for i in builds[0].get("items", [])[:2]]
        p["bd"] = clean(" > ".join(core), 60)
    if owned:
        p["ow"] = clean(", ".join(names.get(i) or f"#{i}" for i in owned), 80)
    return p


def encode(payload: dict, token: str, seq: int) -> bytes:
    """JSON UTF-8 ≤ MAX_BYTES; cắt bớt trường phụ nếu quá dài."""
    p = dict(payload, token=token, seq=seq)
    for key in ("ow", "cb", "bd"):
        data = json.dumps(p, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(data) <= MAX_BYTES:
            return data
        p.pop(key, None)
    return json.dumps(p, ensure_ascii=False, separators=(",", ":")).encode("utf-8")[:MAX_BYTES]


class Esp32Link:
    def __init__(self, state_fn, config_path: Path = CONFIG, log=print):
        self.state_fn, self.config_path, self.log = state_fn, config_path, log
        self.target = None            # (host, port, token)
        self._resolved_at = 0.0
        self._last = None             # payload đã gửi lần cuối (không gồm seq)
        self._last_sent = 0.0
        self.seq = 0
        self.sock = None              # tạo khi gửi gói đầu tiên

    @staticmethod
    def enabled(config_path: Path = CONFIG) -> bool:
        return config_path.exists()

    def resolve(self):
        """(host, port, token) từ data/esp32.json – trực tiếp hoặc qua thư mục bridge PC Control Deck."""
        try:
            cfg = json.loads(self.config_path.read_text(encoding="utf-8"))
            if cfg.get("host") and cfg.get("token"):
                return str(cfg["host"]), int(cfg.get("port", 4210)), str(cfg["token"])
            bridge = Path(cfg.get("bridge_dir", ""))
            token = (json.loads((bridge / "config.json").read_text(encoding="utf-8")).get("notifications") or {}).get("token")
            dev = json.loads((bridge / "device_state.json").read_text(encoding="utf-8"))
            if token and dev.get("connected") and dev.get("ip"):
                return str(dev["ip"]), int(dev.get("port", 4210)), str(token)
        except Exception:
            pass
        return None

    def tick(self):
        now = time.time()
        if self.target is None or now - self._resolved_at > RESOLVE_EVERY:
            target = self.resolve()
            if target != self.target:
                self.log(f"ESP32: {'gửi tới ' + target[0] + ':' + str(target[1]) if target else 'chưa có địa chỉ thiết bị'}")
            self.target, self._resolved_at = target, now
        if not self.target:
            return
        # Tắt trong Cài đặt: báo hết trận một lần (màn ESP32 về Home) rồi im lặng
        payload = build_payload(self.state_fn()) if settings.get("esp32") else {"type": "aram", "ig": 0}
        in_game = payload.get("ig") == 1
        changed = payload != self._last
        if not in_game and not (self._last or {}).get("ig"):
            return                      # ngoài trận và đã báo hết trận rồi: im lặng
        if changed:
            self.seq += 1
        if changed or now - self._last_sent >= HEARTBEAT:
            host, port, token = self.target
            try:
                if self.sock is None:
                    self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.sock.sendto(encode(payload, token, self.seq), (host, port))
                self._last, self._last_sent = payload, now
            except OSError as e:
                self.log(f"ESP32: gửi lỗi {type(e).__name__}")
                self._resolved_at = 0

    def loop(self):
        while True:
            try:
                self.tick()
            except Exception as e:
                self.log(f"ESP32: {e!r}")
            time.sleep(1.0)

    def start(self):
        threading.Thread(target=self.loop, daemon=True, name="esp32").start()

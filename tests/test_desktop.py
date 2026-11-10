# Copyright (c) 2026 doancongtrucit. All rights reserved. See LICENSE.
"""Kiểm tra cửa sổ chính dựng được giao diện từ dữ liệu mẫu (không cần mạng, không cần game)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))
import fixtures  # noqa: E402
import playaram  # noqa: E402
import settings  # noqa: E402

HERE = Path(__file__).parent
CHAMP = playaram.parse_champion_page(fixtures.load("yasuo"), "yasuo")
CHAMP["fetched_at"] = 0
CATALOG = {a["id"]: a for a in playaram.parse_augment_catalog(fixtures.load("augments"))}


class FakeHub:
    def __init__(self):
        self.owned = []
        self.focus = None
        self.adv = None

    def catalog(self):
        return CATALOG

    def state(self):
        return {"game": {"in_game": True, "champion_name": "Yasuo"}, "champion": CHAMP, "owned": list(self.owned),
                "focus": None, "error": None, "scan": {"status": "Sẵn sàng.", "calibrated": True}, "advice": self.adv}

    def update_owned(self, slug, add=None, remove=None, toggle=None, clear=False):
        if toggle is not None:
            self.owned.remove(toggle) if toggle in self.owned else self.owned.append(toggle)
        if add is not None and add not in self.owned:
            self.owned.append(add)

    def set_focus(self, slug):
        self.focus = slug


try:
    import tkinter as tk
    _root = tk.Tk()
    _root.destroy()
    HAS_TK = True
except Exception:
    HAS_TK = False


@unittest.skipUnless(HAS_TK, "cần màn hình / tkinter")
class DesktopUI(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        import desktop
        self.desktop = desktop
        self.tmp = tempfile.TemporaryDirectory()
        settings._reset_for_tests(Path(self.tmp.name) / "settings.json")
        settings.set_many({"check_updates": False}, save=False)   # không gọi mạng trong test
        self.no_net = mock.patch.object(desktop.App, "_load_champion_list", lambda self: None)
        self.no_net.start()
        self.root = tk.Tk()
        self.root.withdraw()
        self.hub = FakeHub()
        self.app = desktop.App(self.root, self.hub)
        self.app._champs = [("yasuo", "Yasuo", "yasuo"), ("yone", "Yone", "yone"), ("jinx", "Jinx", "jinx"),
                            ("masteryi", "Master Yi", "master yi")]
        self.tick()

    def tearDown(self):
        self.root.destroy()
        self.no_net.stop()
        settings._reset_for_tests(settings.PATH)
        self.tmp.cleanup()

    def tick(self):
        self.app._poll()
        self.root.update()

    def visible_cards(self, rarity):
        return [c for c in self.app.cards.values() if c["rarity"] == rarity and c["w"].winfo_manager() == "grid"]

    def fake_size(self, w, h):
        self.app.body.winfo_width = lambda: w
        self.app.body.winfo_height = lambda: h
        self.app._full_sig = None
        self.tick()

    def test_default_six_per_tier_and_more(self):
        self.assertEqual(len(self.app.cards), 48)
        for r in ("prismatic", "gold", "silver"):
            self.assertEqual(len(self.visible_cards(r)), 6)
        self.app._toggle_more("gold")
        self.tick()
        self.assertEqual(len(self.visible_cards("gold")), 16)
        self.assertEqual(len(self.visible_cards("silver")), 6)

    def test_auto_fit_grows_with_height(self):
        settings.set("top_n", 0)
        cols, small = self.app._per_tier(800, 500)
        _, big = self.app._per_tier(800, 1100)
        self.assertGreaterEqual(small, cols)          # ít nhất 1 hàng mỗi bậc
        self.assertGreater(big, small)
        self.assertEqual(big % cols, 0)

    def test_wide_window_shows_augments_and_items_side_by_side(self):
        self.fake_size(1400, 800)
        self.assertIsNotNone(self.app._left)
        self.assertIsNotNone(self.app._right)
        self.assertTrue(self.app._left.inner.winfo_children())
        self.assertTrue(self.app._right.inner.winfo_children())
        self.fake_size(int(self.app.S(560)), 800)      # hẹp: 1 cột cuộn chung
        self.assertIsNone(self.app._left)
        self.assertIsNotNone(self.app._single)

    def test_view_only_ignores_taken_augments(self):
        """Cửa sổ chính chỉ để xem / tìm: không hiện, không đánh dấu lõi đã chọn trong trận."""
        before = len(self.app.cards)
        self.hub.owned = [1058]                         # overlay đã ghi nhận 1 lõi
        self.tick()
        self.assertEqual(len(self.app.cards), before)
        self.assertFalse(hasattr(self.app, "owned_bar"))
        bay_ong = self.app.cards[3048]

        def texts(w):
            out = [w.cget("text")] if isinstance(w, tk.Label) else []
            for ch in w.winfo_children():
                out += texts(ch)
            return out
        shown = set(texts(bay_ong["w"]))
        self.assertTrue({"combo A", "◆A"} & shown)       # nhãn combo chung của tướng vẫn có
        self.assertFalse({"hợp combo A"} & shown)        # không còn "hợp combo" theo lõi đã chọn
        bay_ong["w"].event_generate("<Button-1>")        # bấm vào thẻ không đổi gì
        self.root.update()
        self.assertEqual(self.hub.owned, [1058])

    def test_search_augment_shows_extra_card_and_advice(self):
        self.app.search.event_generate("<FocusIn>")
        self.app.search_var.set("get jinxed")       # hạng 15 bậc Vàng (ngoài top 8)
        self.app._light_update()
        self.root.update()
        jinx = next(c for c in self.app.cards.values() if c["fold"] == "get jinxed")
        self.assertEqual(jinx["w"].winfo_manager(), "grid")
        self.assertTrue(self.app.advice_box.winfo_children())

    def test_champion_quick_filter(self):
        self.assertEqual([s for s, _ in self.app.champion_matches("y")], ["yasuo", "yone", "masteryi"])
        self.assertEqual(self.app.champion_matches("master y"), [("masteryi", "Master Yi")])
        self.assertEqual(self.app.champion_matches("ya, yo"), [])    # dấu phẩy = tìm nhiều lõi
        self.app._show_popup(self.app.champion_matches("yo"))
        self.app._popup_pick()
        self.assertEqual(self.hub.focus, "yone")
        self.assertIsNone(self.app._popup)

    def test_main_window_keeps_view_during_offer_by_default(self):
        best = CATALOG[next(iter(CATALOG))]
        cand = {"id": best["id"], "name": best["name"], "winrate": 55.0, "source": "tướng", "fit": None}
        self.hub.adv = [{"slot": 0, "rank": 1, "best": cand, "candidates": [cand]}]
        self.tick()
        self.assertFalse(self.app.advice_box.winfo_children())
        settings.set("app_follow_offer", True)
        self.root.update()
        self.tick()
        self.assertTrue(self.app.advice_box.winfo_children())

    def test_language_and_zoom_rebuild(self):
        settings.set("lang", "en")
        self.root.update()
        self.tick()
        self.assertEqual(self.app.status.cget("text"), "In game: Yasuo")
        settings.set("ui_zoom", 1.3)
        self.root.update()
        self.assertAlmostEqual(self.app.zoom, 1.3)
        self.tick()
        self.assertEqual(len(self.app.cards), 48)

    def test_back_to_game_button_only_when_viewing_other_champion(self):
        self.assertEqual(self.app.back_btn.winfo_manager(), "")
        orig = self.hub.state
        self.hub.state = lambda: {**orig(), "focus": "yone"}
        self.tick()
        self.assertEqual(self.app.back_btn.winfo_manager(), "pack")
        self.hub.state = orig
        self.tick()
        self.assertEqual(self.app.back_btn.winfo_manager(), "")

    def test_enemy_item_change_does_not_redraw_whole_page(self):
        """Đồ của địch đổi trong trận: chỉ khối "đồ theo đội địch" vẽ lại, trang không giật / nhảy."""
        self.fake_size(1400, 800)
        renders = []
        orig_render, orig_state = self.app._render, self.hub.state
        self.app._render = lambda st: (renders.append(1), orig_render(st))
        line = {"item_id": 3033, "name": "Lời Nhắc Tử Vong", "why": "3/5 địch hồi máu", "icon": None}
        self.hub.state = lambda: {**orig_state(), "counter": [line]}
        self.tick()
        self.assertEqual(renders, [])
        texts = [w.cget("text") for w in self.app._counter_box.winfo_children()[0].winfo_children()
                 if isinstance(w, tk.Label)]
        self.assertTrue(texts)
        self.hub.owned = [1058]                                     # overlay ghi nhận lõi: cũng không vẽ lại
        self.tick()
        self.assertEqual(renders, [])
        self.hub.state = orig_state

    def test_combo_tab(self):
        self.app._set_tab("combo")
        self.tick()
        self.assertTrue(self.app._single.inner.winfo_children())

    def test_ui_error_shows_toast_and_keeps_running(self):
        import io
        from contextlib import redirect_stdout
        broken = tk.Button(self.root, command=lambda: 1 / 0)
        out = io.StringIO()
        with redirect_stdout(out):
            broken.invoke()                      # lỗi trong callback → report_callback_exception
        self.root.update()
        self.assertIn("ZeroDivisionError", out.getvalue())
        self.assertTrue(self.app._toast_w.winfo_exists())
        with redirect_stdout(io.StringIO()):
            broken.invoke()                      # lỗi lặp lại: chỉ ghi log, không hiện thêm thông báo
        self.tick()                              # app vẫn chạy bình thường
        self.assertEqual(len(self.app.cards), 48)

    @unittest.skipUnless(sys.platform == "win32", "phím tắt chỉ có trên Windows")
    def test_hotkey_capture_in_settings(self):
        from types import SimpleNamespace as E
        self.app.open_settings()
        dlg = self.app._settings_dlg
        dlg._go("hotkeys")
        self.root.update()
        dlg._start_capture("calibrate")
        dlg._on_capture_key(E(keysym="l", keycode=76, state=0x4 | 0x1))          # Ctrl+Shift+L
        self.assertEqual(settings.get("hk_calibrate"), "ctrl+shift+l")
        dlg._start_capture("overlay")
        dlg._on_capture_key(E(keysym="l", keycode=76, state=0x4 | 0x1))          # trùng với Định vị lõi
        self.assertEqual(settings.get("hk_overlay"), "ctrl+alt+o")
        dlg._on_capture_key(E(keysym="BackSpace", keycode=8, state=0))
        dlg._start_capture("calibrate")
        dlg._on_capture_key(E(keysym="BackSpace", keycode=8, state=0))           # về mặc định
        self.assertEqual(settings.get("hk_calibrate"), "ctrl+alt+a")
        dlg._start_capture("pick1")
        dlg._on_capture_key(E(keysym="q", keycode=81, state=0x1))                # thiếu Ctrl/Alt → bỏ qua
        self.assertEqual(settings.get("hk_pick1"), "ctrl+alt+1")
        dlg.close()

    def test_about_page_and_license_viewer(self):
        import about
        self.app.open_settings("about")
        dlg = self.app._settings_dlg
        self.root.update()
        self.assertEqual(dlg.page, "about")

        def texts(w):
            out = [w.cget("text")] if isinstance(w, tk.Label) else []
            for ch in w.winfo_children():
                out += texts(ch)
            return out
        shown = texts(dlg.win)
        self.assertIn(about.COPYRIGHT, shown)
        self.assertIn(about.DEVELOPER, shown)
        viewer = dlg._show_file("LICENSE", "License")
        body = [c for c in viewer.winfo_children() if isinstance(c, tk.Text)][0].get("1.0", "end")
        self.assertIn("All rights reserved", body)
        viewer.destroy()
        import report
        with mock.patch.object(report, "default_dir", return_value=Path(self.tmp.name)),                 mock.patch.object(report.paths, "DATA", Path(self.tmp.name) / "data"):
            zipped = dlg._bug_report(confirm=False)
        self.assertTrue(zipped.exists())
        dlg.close()

    def test_one_click_update(self):
        import time
        import updater
        from tkinter import messagebox
        info = {"version": "v99.0.0", "url": "https://example.invalid/r"}
        self.app._show_update(info)
        self.root.update()
        # bản portable / macOS: chỉ mở trang tải
        with mock.patch.object(updater, "can_self_update", return_value=False), mock.patch("webbrowser.open") as op:
            self.app.start_update(info)
            op.assert_called_once_with(info["url"])
        with mock.patch.object(updater, "can_self_update", return_value=True), \
                mock.patch.object(updater, "prepare") as prep:
            self.app._st = {"game": {"in_game": True}}            # đang trong trận: không cập nhật
            self.app.start_update(info)
            prep.assert_not_called()
        # Cài đặt → Kiểm tra cập nhật
        self.app.open_settings("general")
        dlg = self.app._settings_dlg
        self.root.update()
        dlg._update_result("latest", None)
        self.assertEqual(dlg._upd_desc.cget("text"), "Bạn đang dùng bản mới nhất.")
        dlg._update_result("new", info)
        self.assertIn("v99.0.0", dlg._upd_desc.cget("text"))
        # bản cài: tải + kiểm tra (giả lập) → chạy bộ cài → đóng app
        setup = Path(self.tmp.name) / "ARAM-Helper-99.0.0-Setup.exe"
        self.app._st = {"game": {"in_game": False}}
        with mock.patch.object(updater, "can_self_update", return_value=True), \
                mock.patch.object(updater, "prepare", return_value=setup), \
                mock.patch.object(updater, "launch_installer") as launch, \
                mock.patch.object(messagebox, "askyesno", return_value=True), \
                mock.patch.object(self.root, "destroy") as quit_:
            self.app.start_update(info)
            end = time.time() + 5
            while not quit_.called and time.time() < end:
                self.root.update()
                time.sleep(0.05)
            launch.assert_called_once_with(setup)
            quit_.assert_called_once()
        dlg.close()

    def test_update_guards_and_failure(self):
        import time
        import updater
        from tkinter import messagebox
        info = {"version": "v99.0.0", "url": "https://example.invalid/r"}
        self.app._show_update(info)
        self.root.update()
        start_text = self.app._update_btn.cget("text")
        with mock.patch.object(updater, "can_self_update", return_value=True), \
                mock.patch.object(updater, "prepare") as prep, \
                mock.patch.object(updater, "launch_installer") as launch, \
                mock.patch.object(self.root, "destroy") as quit_:
            # đang cập nhật: bấm lần 2 (vd. từ Cài đặt) không mở hộp xác nhận thứ hai
            self.app._updating = True
            with mock.patch.object(messagebox, "askyesno") as ask:
                self.app.start_update(info)
                ask.assert_not_called()
            self.app._updating = False
            # trận bắt đầu trong lúc hộp xác nhận đang mở → không tải
            self.app._st = {"game": {"in_game": False}}

            def game_starts(*a, **k):
                self.app._st = {"game": {"in_game": True}}
                return True
            with mock.patch.object(messagebox, "askyesno", side_effect=game_starts):
                self.app.start_update(info)
            prep.assert_not_called()
            self.assertFalse(self.app.updating)
            # tải lỗi → nút về như cũ, bấm lại được
            self.app._st = {"game": {"in_game": False}}
            prep.side_effect = updater.UpdateError("download", "offline")
            with mock.patch.object(messagebox, "askyesno", return_value=True):
                self.app.start_update(info)
                end = time.time() + 5
                while self.app.updating and time.time() < end:
                    self.root.update()
                    time.sleep(0.05)
            self.assertFalse(self.app.updating)
            self.assertEqual(self.app._update_btn.cget("text"), start_text)
            # tải xong khi đang trong trận → chờ, hết trận mới cài
            setup = Path(self.tmp.name) / "s.exe"
            self.app._st = {"game": {"in_game": True}}
            self.app._update_install(setup)
            launch.assert_not_called()
            self.app._st = {"game": {"in_game": False}}
            self.app._update_install(setup)
            launch.assert_called_once_with(setup)

    def test_settings_dialog_pages(self):
        self.app.open_settings()
        dlg = self.app._settings_dlg
        for page in ("overlay", "hotkeys", "about", "general"):
            dlg._go(page)
            self.root.update()
        settings.set("lang", "en")                  # hộp thoại dựng lại theo ngôn ngữ mới
        self.root.update()
        self.assertIn("Settings", dlg.win.title())
        dlg.close()


if __name__ == "__main__":
    unittest.main()

"""Hộp thoại Cài đặt: 3 thẻ Chung / Overlay / ESP32. Mọi thay đổi áp dụng ngay (settings.set → các phần đăng ký tự cập nhật)."""
from __future__ import annotations

import tkinter as tk

import paths
import settings
from i18n import T

CORNERS = [("custom", "Kéo thả"), ("top-right", "Trên phải"), ("top-left", "Trên trái"),
           ("bottom-right", "Dưới phải"), ("bottom-left", "Dưới trái")]
SECTIONS = [("offer", "Gợi ý lõi"), ("combo", "Combo"), ("owned", "Lõi đã chọn"),
            ("build", "Lối lên đồ"), ("counter", "Theo đội địch")]


class SettingsDialog:
    def __init__(self, app):
        import theme as d
        self.app, self.d = app, d
        self.page = "general"
        self.win = tk.Toplevel(app.root)
        self.win.configure(bg=d.BG)
        self.win.resizable(False, False)
        self.win.transient(app.root)
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        self._listener = lambda ch: self.win.after(0, self._on_change, ch)
        settings.on_change(self._listener)
        self._build()
        x = app.root.winfo_rootx() + app.root.winfo_width() - self.win.winfo_reqwidth() - app.S(30)
        self.win.geometry(f"+{max(0, x)}+{app.root.winfo_rooty() + app.S(60)}")

    def close(self):
        try:
            settings._listeners.remove(self._listener)
        except ValueError:
            pass
        self.win.destroy()

    def _on_change(self, ch):
        if not self.win.winfo_exists():
            return
        if "lang" in ch or "ui_zoom" in ch:     # chữ / cỡ chữ đổi → dựng lại hộp thoại
            self._build()
        else:
            self._sync()

    # ----- khung -----
    def _build(self):
        d, a = self.d, self.app
        for w in self.win.winfo_children():
            w.destroy()
        self.vars: dict[str, tk.Variable] = {}
        self.win.title("ARAM Helper – " + T("Cài đặt"))
        tabs = tk.Frame(self.win, bg=d.BG, padx=a.S(12), pady=a.S(8))
        tabs.pack(fill="x")
        for key, text in (("general", T("Chung")), ("overlay", T("Overlay")), ("esp32", T("ESP32"))):
            on = key == self.page
            t = tk.Label(tabs, text=text, fg=d.TEXT if on else d.MUTED, bg=d.BG, font=a.f(10, True),
                         padx=a.S(10), pady=a.S(4), cursor="hand2")
            t.pack(side="left")
            if on:
                tk.Frame(t, bg=d.ACCENT, height=a.S(2)).place(relx=0, rely=1, relwidth=1, anchor="sw")
            t.bind("<Button-1>", lambda e, k=key: self._go(k))
        tk.Frame(self.win, bg=d.LINE, height=1).pack(fill="x", padx=a.S(12))
        self.body = tk.Frame(self.win, bg=d.PANEL, padx=a.S(14), pady=a.S(10))
        self.body.pack(fill="both", expand=True, padx=a.S(12), pady=a.S(8))
        getattr(self, "_page_" + self.page)()
        foot = tk.Frame(self.win, bg=d.BG, padx=a.S(12), pady=a.S(8))
        foot.pack(fill="x")
        from version import __version__
        a.button(foot, T("Đóng"), self.close, 9, primary=True).pack(side="right")
        try:
            tk.Label(foot, image=d.app_logo(a.root, a.S(20)), bg=d.BG).pack(side="left", padx=(0, a.S(6)))
        except Exception:
            pass
        a.label(foot, f"ARAM Helper {__version__}", 8, d.MUTED).pack(side="left")
        a.button(foot, T("Mặc định"), self._defaults, 9).pack(side="right", padx=a.S(6))

    def _go(self, key):
        self.page = key
        self._build()

    def _defaults(self):
        keys = {"general": ["lang", "ui_zoom", "top_n", "app_follow_offer", "always_on_top", "check_updates"],
                "overlay": [k for k in settings.DEFAULTS if k.startswith("ov_") or k == "overlay"],
                "esp32": ["esp32"]}[self.page]
        settings.reset(keys)

    def _sync(self):
        """Đồng bộ ô điều khiển với giá trị hiện tại (vd. bật overlay bằng phím tắt)."""
        for key, var in self.vars.items():
            v = settings.get(key)
            try:
                if var.get() != v:
                    var.set(v)
            except tk.TclError:
                pass

    # ----- ô điều khiển -----
    def _row(self, label):
        d, a = self.d, self.app
        row = tk.Frame(self.body, bg=d.PANEL, pady=a.S(4))
        row.pack(fill="x")
        a.label(row, label, 9, d.TEXT, width=24, anchor="w").pack(side="left")
        return row

    def _note(self, text):
        self.app.label(self.body, text, 8, self.d.MUTED, wraplength=self.app.S(400), justify="left").pack(
            anchor="w", pady=(0, self.app.S(4)))

    def _check(self, key, label, parent=None):
        d, a = self.d, self.app
        var = tk.BooleanVar(value=bool(settings.get(key)))
        self.vars[key] = var
        tk.Checkbutton(parent or self.body, text=label, variable=var, command=lambda: settings.set(key, var.get()),
                       bg=d.PANEL, fg=d.TEXT, selectcolor=d.BG, activebackground=d.PANEL, activeforeground=d.TEXT,
                       font=a.f(9), anchor="w").pack(anchor="w", side="left" if parent else "top")
        return var

    def _choice(self, key, label, options):
        d, a = self.d, self.app
        row = self._row(label)
        var = tk.StringVar(value=str(settings.get(key)))
        self.vars[key] = var
        for value, text in options:
            tk.Radiobutton(row, text=text, value=value, variable=var, command=lambda: settings.set(key, var.get()),
                           bg=d.PANEL, fg=d.TEXT, selectcolor=d.BG, activebackground=d.PANEL,
                           activeforeground=d.TEXT, font=a.f(9)).pack(side="left", padx=(0, a.S(6)))
        return row

    def _slider(self, key, label, lo, hi, step, fmt="{:.0%}", live=True, cast=float):
        """Thanh trượt. live=False: chỉ áp dụng khi nhả chuột (đổi cỡ giao diện dựng lại cả cửa sổ)."""
        d, a = self.d, self.app
        row = self._row(label)
        var = tk.DoubleVar(value=float(settings.get(key)))
        self.vars[key] = var
        val = a.label(row, fmt.format(cast(var.get())), 9, d.MUTED, width=6, anchor="e")

        def moved(_=None):
            v = cast(round(var.get() / step) * step) if cast is int else round(round(var.get() / step) * step, 2)
            val.configure(text=fmt.format(v))
            if live:
                settings.set(key, v)
            return v
        sc = tk.Scale(row, from_=lo, to=hi, resolution=step, orient="horizontal", variable=var, showvalue=False,
                      length=a.S(200), width=a.S(10), sliderlength=a.S(16), bg=d.ACCENT, fg=d.TEXT,
                      troughcolor=d.BG, highlightthickness=0, bd=0, sliderrelief="flat",
                      activebackground="#9cc6ff", command=moved)
        sc.pack(side="left")
        val.pack(side="left", padx=a.S(6))
        if not live:
            sc.bind("<ButtonRelease-1>", lambda e: settings.set(key, moved()))
        return row

    # ----- các trang -----
    def _page_general(self):
        a = self.app
        self._choice("lang", T("Ngôn ngữ"), [("vi", "Tiếng Việt"), ("en", "English")])
        self._slider("ui_zoom", T("Cỡ giao diện"), 0.7, 1.6, 0.1, live=False)
        self._note(T("Phím tắt: Ctrl + / Ctrl - / Ctrl 0 đổi cỡ giao diện."))
        row = self._row(T("Số lõi mỗi bậc"))
        auto = tk.BooleanVar(value=int(settings.get("top_n") or 0) == 0)
        n = tk.IntVar(value=int(settings.get("top_n") or 6) or 6)
        self.vars["top_n"] = tk.IntVar(value=int(settings.get("top_n") or 0))   # chỉ để _sync không lỗi
        spin = tk.Spinbox(row, from_=1, to=16, width=4, textvariable=n, font=a.f(9), bg=self.d.BG, fg=self.d.TEXT,
                          buttonbackground=self.d.PANEL2, relief="flat",
                          command=lambda: settings.set("top_n", int(n.get())))
        spin.bind("<Return>", lambda e: settings.set("top_n", max(1, min(16, int(n.get() or 6)))))

        def toggle_auto():
            spin.configure(state="disabled" if auto.get() else "normal")
            settings.set("top_n", 0 if auto.get() else max(1, int(n.get() or 6)))
        tk.Checkbutton(row, text=T("Tự vừa cửa sổ"), variable=auto, command=toggle_auto, bg=self.d.PANEL,
                       fg=self.d.TEXT, selectcolor=self.d.BG, activebackground=self.d.PANEL,
                       activeforeground=self.d.TEXT, font=a.f(9)).pack(side="left")
        spin.pack(side="left", padx=a.S(8))
        spin.configure(state="disabled" if auto.get() else "normal")
        tk.Frame(self.body, bg=self.d.PANEL, height=a.S(6)).pack()
        self._check("app_follow_offer", T("Cửa sổ chính phản ứng khi đang chọn lõi (tô sáng, ô Nên chọn)"))
        self._note(T("Tắt: cửa sổ chính giữ nguyên để xem tổng quát, gợi ý chọn lõi chỉ hiện trên overlay / ESP32."))
        self._check("always_on_top", T("Cửa sổ chính luôn nằm trên"))
        self._check("check_updates", T("Báo khi có bản mới (tự kiểm tra trên GitHub)"))
        row = self._row(T("Thư mục dữ liệu"))
        a.label(row, a._fit(str(paths.DATA), a.S(260), 8), 8, self.d.MUTED).pack(side="left")
        a.button(row, T("Mở"), paths.open_data_folder, 8).pack(side="left", padx=a.S(6))

    def _page_overlay(self):
        d, a = self.d, self.app
        self._check("overlay", T("Bật overlay"))
        self._slider("ov_opacity", T("Độ đậm khung"), 0.3, 1.0, 0.02)
        self._slider("ov_badge_opacity", T("Độ đậm nhãn trên thẻ lõi"), 0.3, 1.0, 0.02)
        self._slider("ov_scale", T("Cỡ overlay"), 0.7, 1.6, 0.1)
        self._slider("ov_width", T("Bề rộng khung"), 220, 420, 10, fmt="{} px", cast=int)
        row = self._choice("ov_corner", T("Vị trí khung"), [(k, T(t)) for k, t in CORNERS[:3]])
        row2 = tk.Frame(self.body, bg=d.PANEL)
        row2.pack(fill="x")
        a.label(row2, "", 9, width=24).pack(side="left")
        for value, text in CORNERS[3:]:
            tk.Radiobutton(row2, text=T(text), value=value, variable=self.vars["ov_corner"],
                           command=lambda: settings.set("ov_corner", self.vars["ov_corner"].get()),
                           bg=d.PANEL, fg=d.TEXT, selectcolor=d.BG, activebackground=d.PANEL,
                           activeforeground=d.TEXT, font=a.f(9)).pack(side="left", padx=(0, a.S(6)))
        if a.overlay:
            a.button(row2, T("Đặt lại vị trí"), a.overlay.reset_position, 8).pack(side="left", padx=a.S(6))
        del row
        tk.Frame(self.body, bg=d.PANEL, height=a.S(6)).pack()
        self._check("ov_badges", T("Nhãn ★ / #2 / #3 trên thẻ lõi"))
        self._check("ov_only_offer", T("Chỉ hiện khung khi đang chọn lõi"))
        row = self._row(T("Mục hiển thị"))
        for key, text in SECTIONS:
            self._check("ov_show_" + key, T(text), parent=row)
        self._choice("ov_builds", T("Số lối lên đồ"), [("1", "1"), ("2", "2"), ("3", "3")])
        var = self.vars["ov_builds"]
        for w in self.body.winfo_children()[-1].winfo_children():
            if isinstance(w, tk.Radiobutton):
                w.configure(command=lambda: settings.set("ov_builds", int(var.get())))
        if not a.overlay:
            self._note(T("Overlay chỉ có trên Windows."))

    def _page_esp32(self):
        import esp32_link
        self._check("esp32", T("Gửi màn ARAM lên ESP32 (PC Control Deck)"))
        if not esp32_link.Esp32Link.enabled():
            self._note(T("Cần file esp32.json trong thư mục dữ liệu – xem docs/USER_GUIDE.md, mục ESP32."))

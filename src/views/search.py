"""Ô tìm kiếm: lọc nhanh tướng (danh sách chọn ↑ ↓ Enter)."""
from __future__ import annotations

import tkinter as tk

import i18n
import playaram
from theme import PANEL, LINE, TEXT, ACCENT, fold


class SearchMixin:
    """Ô tìm kiếm: lọc nhanh tướng (danh sách chọn ↑ ↓ Enter)."""

    def _load_champion_list(self):
        try:
            slugs = playaram.get_champion_list()
        except Exception:
            slugs = []
        names = {}
        try:
            import ddragon
            dd = ddragon.get(i18n.ddragon_locale())
            names = {k: v["name"] for k, v in (dd or {}).get("champions", {}).items()}
        except Exception:
            pass
        champs = [(s, names.get(s, s.capitalize()), fold(names.get(s, s))) for s in slugs]
        self._champs = sorted(champs, key=lambda c: c[2])

    def champion_matches(self, text: str, limit: int = 8) -> list[tuple[str, str]]:
        t = fold(text).strip()
        if not t or "," in t:
            return []
        flat = t.replace(" ", "")
        starts = [c for c in self._champs if c[2].startswith(t) or c[0].startswith(flat)]
        inside = [c for c in self._champs if c not in starts and (t in c[2] or flat in c[0])]
        return [(slug, name) for slug, name, _ in (starts + inside)[:limit]]

    def _on_search(self):
        text = self.search_text()
        matches = self.champion_matches(text)
        try:
            focused = self.root.focus_get() is self.search
        except (KeyError, tk.TclError):     # Tk lỗi 'popdown' khi focus nằm ở menu/combobox
            focused = False
        if matches and focused:
            self._show_popup(matches)
        else:
            self._hide_popup()
        self._light_update()

    def _show_popup(self, matches):
        if self._popup is None:
            win = tk.Toplevel(self.root)
            win.overrideredirect(True)
            win.attributes("-topmost", True)
            lb = tk.Listbox(win, bg=PANEL, fg=TEXT, selectbackground=ACCENT, selectforeground="#06121f",
                            font=self.f(10), relief="flat", highlightthickness=1, highlightbackground=LINE,
                            activestyle="none")
            lb.pack(fill="both", expand=True)
            lb.bind("<ButtonRelease-1>", lambda e: self._popup_pick())
            self._popup = (win, lb)
        win, lb = self._popup
        lb.delete(0, "end")
        self._popup_slugs = [s for s, _ in matches]
        for slug, name in matches:
            lb.insert("end", f"  {name}")
        lb.selection_clear(0, "end")
        lb.selection_set(0)
        x, y = self.search.winfo_rootx(), self.search.winfo_rooty() + self.search.winfo_height()
        h = len(matches) * self.S(22) + 4
        win.geometry(f"{self.search.winfo_width()}x{h}+{x}+{y}")
        lb.configure(height=len(matches))

    def _hide_popup(self):
        if self._popup is not None:
            try:
                self._popup[0].destroy()
            except tk.TclError:
                pass
            self._popup = None

    def _popup_move(self, step):
        if self._popup is None:
            return
        lb = self._popup[1]
        cur = lb.curselection()
        i = (cur[0] if cur else -1) + step
        i = max(0, min(lb.size() - 1, i))
        lb.selection_clear(0, "end")
        lb.selection_set(i)
        lb.see(i)
        return "break"

    def _popup_pick(self):
        if self._popup is None:
            return
        cur = self._popup[1].curselection()
        slug = self._popup_slugs[cur[0] if cur else 0]
        self._hide_popup()
        self.search_var.set("")
        self.root.focus()
        self.hub.set_focus(slug)
        self._scroll_top = True
        return "break"

    def _auto(self):
        self.hub.set_focus(None)
        self._scroll_top = True

"""자동완성 콤보박스 - 타이핑하면 매칭되는 항목만 드롭다운에 표시"""

import customtkinter as ctk

HIGHLIGHT_BG = ("#EEF2FF", "#334155")
NORMAL_BG = "transparent"


class AutocompleteCombo(ctk.CTkFrame):
    """
    타이핑 시 자동 필터링되는 콤보박스.
    - 위/아래 화살표로 항목 이동, Enter로 선택
    - 클릭으로 즉시 선택
    - Tab으로 첫 번째 항목 자동완성
    """

    def __init__(self, parent, values: list, height=38, font=("", 18),
                 placeholder="입력 또는 선택...", **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._all_values = values
        self._filtered = values[:]
        self._selecting = False
        self._highlight_index = -1
        self._buttons = []

        self._entry = ctk.CTkEntry(
            self, height=height, font=font,
            placeholder_text=placeholder
        )
        self._entry.pack(fill="x")

        self._listbox_frame = None

        self._entry.bind("<KeyRelease>", self._on_key)
        self._entry.bind("<Tab>", self._on_tab)
        self._entry.bind("<Down>", self._on_arrow_down)
        self._entry.bind("<Up>", self._on_arrow_up)
        self._entry.bind("<Return>", self._on_enter)
        self._entry.bind("<FocusIn>", self._on_focus_in)
        self._entry.bind("<FocusOut>", self._on_focus_out)
        self._entry.bind("<Escape>", lambda e: self._hide_listbox())

    def _on_key(self, event):
        if event.keysym in ("Tab", "Return", "Escape", "Up", "Down"):
            return

        text = self._entry.get().strip()
        if text:
            self._filtered = [v for v in self._all_values
                              if text.lower() in v.lower()]
        else:
            self._filtered = self._all_values[:]

        self._highlight_index = -1

        if self._filtered:
            self._show_listbox()
        else:
            self._hide_listbox()

    def _on_arrow_down(self, event):
        if not self._listbox_frame or not self._buttons:
            if self._filtered:
                self._show_listbox()
            return "break"

        self._highlight_index = min(self._highlight_index + 1, len(self._buttons) - 1)
        self._update_highlight()
        return "break"

    def _on_arrow_up(self, event):
        if not self._listbox_frame or not self._buttons:
            return "break"

        self._highlight_index = max(self._highlight_index - 1, 0)
        self._update_highlight()
        return "break"

    def _on_enter(self, event):
        if self._highlight_index >= 0 and self._highlight_index < len(self._filtered):
            value = self._filtered[self._highlight_index]
            self._set_value(value)
            self._hide_listbox()
            return "break"

    def _update_highlight(self):
        for i, btn in enumerate(self._buttons):
            if i == self._highlight_index:
                btn.configure(fg_color=HIGHLIGHT_BG)
            else:
                btn.configure(fg_color=NORMAL_BG)

    def _on_tab(self, event):
        text = self._entry.get().strip()
        self._hide_listbox()

        if not text:
            return

        if text in self._all_values:
            return

        matches = [v for v in self._all_values if text.lower() in v.lower()]
        if matches:
            self._set_value(matches[0])
            return "break"

        return

    def _on_focus_in(self, event):
        text = self._entry.get().strip()
        if not text:
            self._filtered = self._all_values[:]
            self._show_listbox()

    def _on_focus_out(self, event):
        if self._selecting:
            return
        self.after(150, self._hide_listbox)

    def _show_listbox(self):
        self._hide_listbox()
        self._buttons = []

        if not self._filtered:
            return

        self._listbox_frame = ctk.CTkFrame(
            self, corner_radius=8, border_width=1,
            border_color=("gray75", "gray30"),
            fg_color=("#FFFFFF", "#1E293B")
        )
        self._listbox_frame.pack(fill="x", pady=(2, 0))

        for i, value in enumerate(self._filtered[:6]):
            btn = ctk.CTkButton(
                self._listbox_frame, text=value,
                font=("", 18), height=34,
                fg_color=HIGHLIGHT_BG if i == self._highlight_index else NORMAL_BG,
                text_color=("gray10", "gray90"),
                hover_color=HIGHLIGHT_BG,
                anchor="w",
                command=lambda v=value: self._on_item_click(v)
            )
            btn.pack(fill="x", padx=4, pady=1)
            self._buttons.append(btn)

        if len(self._filtered) > 6:
            ctk.CTkLabel(
                self._listbox_frame,
                text=f"  +{len(self._filtered) - 6}개 더...",
                font=("", 18), text_color=("gray50", "gray55"), height=26
            ).pack(anchor="w", padx=8)

    def _hide_listbox(self):
        if self._listbox_frame:
            self._listbox_frame.destroy()
            self._listbox_frame = None
        self._buttons = []
        self._highlight_index = -1

    def _on_item_click(self, value: str):
        self._selecting = True
        self._set_value(value)
        self._hide_listbox()
        self._entry.focus_set()
        self.after(50, self._clear_selecting)

    def _clear_selecting(self):
        self._selecting = False

    def _set_value(self, value: str):
        self._entry.delete(0, "end")
        self._entry.insert(0, value)

    def get(self) -> str:
        return self._entry.get().strip()

    def set(self, value: str):
        self._set_value(value)

    def focus_set(self):
        self._entry.focus_set()

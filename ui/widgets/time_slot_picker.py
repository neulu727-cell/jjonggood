"""30분 단위 시간 선택 위젯"""

import customtkinter as ctk
from utils.date_utils import generate_time_slots
import config

SELECTED_BG = "#4F46E5"
SELECTED_HOVER = "#4338CA"


class TimeSlotPicker(ctk.CTkFrame):
    """30분 간격 시간 슬롯을 버튼 그리드로 표시"""

    def __init__(self, parent, command=None, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._command = command
        self._selected = None
        self._buttons = {}

        slots = generate_time_slots(
            config.BUSINESS_HOURS_START,
            config.BUSINESS_HOURS_END,
            config.TIME_SLOT_INTERVAL,
        )

        for i, slot in enumerate(slots):
            row = i // 5
            col = i % 5
            btn = ctk.CTkButton(
                self, text=slot, width=75, height=34,
                font=("", 18), corner_radius=8,
                fg_color=("#F1F5F9", "#334155"),
                hover_color=("#E2E8F0", "#475569"),
                text_color=("gray20", "gray80"),
                border_width=0,
                command=lambda s=slot: self._on_select(s),
            )
            btn.grid(row=row, column=col, padx=3, pady=3)
            self._buttons[slot] = btn

    def _on_select(self, slot: str):
        if self._selected and self._selected in self._buttons:
            self._buttons[self._selected].configure(
                fg_color=("#F1F5F9", "#334155"),
                text_color=("gray20", "gray80"),
            )
        self._selected = slot
        self._buttons[slot].configure(
            fg_color=SELECTED_BG,
            hover_color=SELECTED_HOVER,
            text_color="white",
        )
        if self._command:
            self._command(slot)

    def get(self) -> str:
        return self._selected or ""

    def set(self, slot: str):
        if slot in self._buttons:
            self._on_select(slot)

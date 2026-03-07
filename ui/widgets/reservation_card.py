"""예약 카드 위젯 - 메인 화면의 예약 목록에 사용"""

import customtkinter as ctk
from database.models import Reservation
from utils.phone_formatter import format_phone_display

# 상태별 스타일
STATUS_STYLES = {
    "confirmed": {"bg": "#EEF2FF", "fg": "#4F46E5", "text": "예약"},
    "completed": {"bg": "#DCFCE7", "fg": "#16A34A", "text": "완료"},
    "cancelled": {"bg": "#FEE2E2", "fg": "#DC2626", "text": "취소"},
    "no_show":   {"bg": "#FEF3C7", "fg": "#D97706", "text": "노쇼"},
}


class ReservationCard(ctk.CTkFrame):
    """하나의 예약 정보를 카드 형태로 표시"""

    def __init__(self, parent, reservation: Reservation, on_click=None, **kwargs):
        super().__init__(
            parent, corner_radius=12, border_width=1,
            border_color=("gray85", "gray25"),
            fg_color=("#FFFFFF", "#1E293B"),
            cursor="hand2",
            **kwargs
        )
        self.reservation = reservation
        self._on_click = on_click

        self.bind("<Button-1>", self._handle_click)
        self._build_ui()

    def _build_ui(self):
        r = self.reservation
        style = STATUS_STYLES.get(r.status, STATUS_STYLES["confirmed"])

        # 전체를 가로로 배치
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="x", padx=15, pady=12)
        inner.bind("<Button-1>", self._handle_click)

        # 시간 블록 (강조)
        time_frame = ctk.CTkFrame(inner, fg_color=("#F1F5F9", "#334155"),
                                   corner_radius=8, width=70, height=44)
        time_frame.pack(side="left", padx=(0, 12))
        time_frame.pack_propagate(False)
        time_label = ctk.CTkLabel(
            time_frame, text=r.time, font=("", 18, "bold"),
            text_color=("#1E293B", "#F1F5F9")
        )
        time_label.pack(expand=True)
        time_label.bind("<Button-1>", self._handle_click)

        # 중앙: 고객 정보
        info_frame = ctk.CTkFrame(inner, fg_color="transparent")
        info_frame.pack(side="left", fill="x", expand=True)
        info_frame.bind("<Button-1>", self._handle_click)

        name_label = ctk.CTkLabel(
            info_frame, text=f"{r.customer_name}  ({r.pet_name})",
            font=("", 18, "bold"), anchor="w"
        )
        name_label.pack(anchor="w")
        name_label.bind("<Button-1>", self._handle_click)

        detail_text = f"{r.service_type}"
        if r.amount:
            detail_text += f"  ·  {r.amount:,}원"
        detail_label = ctk.CTkLabel(
            info_frame, text=detail_text,
            font=("", 18), text_color=("gray50", "gray55"), anchor="w"
        )
        detail_label.pack(anchor="w")
        detail_label.bind("<Button-1>", self._handle_click)

        # 우측: 상태 배지
        badge = ctk.CTkLabel(
            inner, text=style["text"], font=("", 18, "bold"),
            fg_color=style["bg"], text_color=style["fg"],
            corner_radius=6, width=52, height=26
        )
        badge.pack(side="right", padx=(10, 0))
        badge.bind("<Button-1>", self._handle_click)

    def _handle_click(self, event=None):
        if self._on_click:
            self._on_click(self.reservation)

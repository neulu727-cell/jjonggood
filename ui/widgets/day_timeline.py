"""일간 타임라인 위젯 - 2열 grid, 연속 예약 셀 병합, 고정 높이"""

import customtkinter as ctk
from database.models import Reservation
from utils.date_utils import generate_time_slots
from typing import List
import config

STATUS_COLORS = {
    "confirmed": {"bg": "#DBEAFE", "border": "#93C5FD", "text": "#1E40AF"},
    "completed": {"bg": "#DCFCE7", "border": "#86EFAC", "text": "#166534"},
    "cancelled": {"bg": "#FEE2E2", "border": "#FCA5A5", "text": "#991B1B"},
    "no_show":   {"bg": "#FEF3C7", "border": "#FDE68A", "text": "#92400E"},
}
SLOT_EMPTY_BG = ("#F0FDF4", "#0D2818")
SLOT_EMPTY_BORDER = ("#BBF7D0", "#1A4D2E")
SLOT_EMPTY_TIME_COLOR = ("#16A34A", "#4ADE80")
SLOT_EMPTY_HINT_COLOR = ("#86EFAC", "#2D6A4F")

ROW_HEIGHT = 48  # 한 슬롯 고정 높이 (font 18 기준)


class DayTimeline(ctk.CTkFrame):
    """타임라인. 연속 예약은 셀을 병합(rowspan)하여 표시."""

    def __init__(self, parent, reservations: List[Reservation] = None,
                 on_slot_click=None, on_reservation_click=None,
                 columns: int = 1, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)

        self._reservations = reservations or []
        self._on_slot_click = on_slot_click
        self._on_reservation_click = on_reservation_click
        self._columns = columns
        self._build_ui()

    def _build_ui(self):
        slots = generate_time_slots(
            config.BUSINESS_HOURS_START,
            config.BUSINESS_HOURS_END,
            config.TIME_SLOT_INTERVAL,
        )
        interval = config.TIME_SLOT_INTERVAL

        slot_set = set(slots)
        booked = {}
        booked_is_start = {}
        for r in self._reservations:
            rh, rm = map(int, r.time.split(":"))
            r_start = rh * 60 + rm
            n_slots = max(1, (r.duration + interval - 1) // interval)
            for s in range(n_slots):
                t = r_start + s * interval
                ts_str = f"{t // 60:02d}:{t % 60:02d}"
                if ts_str in slot_set:
                    booked[ts_str] = r
                    booked_is_start[ts_str] = (s == 0)

        if self._columns == 2:
            self._build_two_columns(slots, booked, booked_is_start, interval)
        else:
            self._build_single_column(slots, booked, booked_is_start, interval)

    def _build_single_column(self, slots, booked, booked_is_start, interval):
        i = 0
        while i < len(slots):
            ts = slots[i]
            r = booked.get(ts)
            if r:
                is_start = booked_is_start.get(ts, False)
                span = 1
                while i + span < len(slots) and booked.get(slots[i + span]) is r:
                    span += 1
                end_str = self._calc_end(ts, span, interval)
                w = self._make_booked_merged(ts, end_str, r, is_start, span)
                w.pack(fill="x", pady=1)
                i += span
            else:
                self._make_empty(ts).pack(fill="x", pady=1)
                i += 1

    def _build_two_columns(self, slots, booked, booked_is_start, interval):
        mid = (len(slots) + 1) // 2

        self.columnconfigure(0, weight=1, uniform="col")
        self.columnconfigure(1, weight=1, uniform="col")
        # 균등 배분: weight로 세로 공간 꽉 채움
        for i in range(mid):
            self.rowconfigure(i, weight=1, minsize=ROW_HEIGHT)

        skip = set()

        for i, ts in enumerate(slots):
            if i in skip:
                continue

            col = 0 if i < mid else 1
            row = i if i < mid else i - mid

            r = booked.get(ts)
            if r:
                is_start = booked_is_start.get(ts, False)
                span = 1
                j = i + 1
                while j < len(slots):
                    j_col = 0 if j < mid else 1
                    if j_col != col:
                        break
                    if booked.get(slots[j]) is r:
                        span += 1
                        skip.add(j)
                        j += 1
                    else:
                        break

                end_str = self._calc_end(ts, span, interval)
                w = self._make_booked_merged(ts, end_str, r, is_start, span)
                px = (0, 2) if col == 0 else (2, 0)
                w.grid(row=row, column=col, rowspan=span, sticky="nsew", padx=px, pady=1)
            else:
                w = self._make_empty(ts)
                px = (0, 2) if col == 0 else (2, 0)
                w.grid(row=row, column=col, sticky="nsew", padx=px, pady=1)

    @staticmethod
    def _calc_end(start_time: str, span: int, interval: int) -> str:
        sh, sm = map(int, start_time.split(":"))
        end = sh * 60 + sm + span * interval
        return f"{end // 60:02d}:{end % 60:02d}"

    def _make_empty(self, ts: str) -> ctk.CTkFrame:
        slot = ctk.CTkFrame(
            self, corner_radius=4, height=ROW_HEIGHT,
            fg_color=SLOT_EMPTY_BG,
            border_width=1, border_color=SLOT_EMPTY_BORDER,
            cursor="hand2"
        )
        inner = ctk.CTkFrame(slot, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=6)

        t = ctk.CTkLabel(inner, text=ts, font=("", 18, "bold"),
                         text_color=SLOT_EMPTY_TIME_COLOR, width=56, anchor="w")
        t.pack(side="left")

        h = ctk.CTkLabel(inner, text="+ 예약", font=("", 18),
                         text_color=SLOT_EMPTY_HINT_COLOR)
        h.pack(side="left", padx=(2, 0))

        for w in [slot, inner, t, h]:
            w.bind("<Button-1>", lambda *_, x=ts: self._click_empty(x))
        return slot

    def _make_booked_merged(self, start_time: str, end_time: str,
                            r: Reservation, is_start: bool, span: int) -> ctk.CTkFrame:
        s = STATUS_COLORS.get(r.status, STATUS_COLORS["confirmed"])
        pet_info = f"{r.pet_name}({r.breed})" if r.breed else r.pet_name

        slot = ctk.CTkFrame(
            self, corner_radius=4,
            fg_color=s["bg"], border_width=2, border_color=s["border"],
            cursor="hand2"
        )

        if span == 1:
            # 단일 슬롯 - 가로 레이아웃
            inner = ctk.CTkFrame(slot, fg_color="transparent")
            inner.pack(fill="both", expand=True, padx=6)

            ctk.CTkLabel(inner, text=start_time, font=("", 18, "bold"),
                         text_color=s["text"], width=56, anchor="w").pack(side="left")

            if is_start:
                fur = f"/{r.fur_length}" if r.fur_length else ""
                ctk.CTkLabel(inner, text=f"{pet_info} {r.service_type}{fur}",
                             font=("", 18, "bold"), text_color=s["text"],
                             anchor="w").pack(side="left", padx=(2, 0))
                if r.amount:
                    ctk.CTkLabel(inner, text=f"{r.amount:,}", font=("", 18),
                                 text_color=s["text"]).pack(side="right")
            else:
                ctk.CTkLabel(inner, text=f"~ {pet_info}",
                             font=("", 18), text_color=s["text"],
                             anchor="w").pack(side="left", padx=(2, 0))
        else:
            # 다중 슬롯 - 세로 레이아웃, 셀 병합
            inner = ctk.CTkFrame(slot, fg_color="transparent")
            inner.pack(fill="both", expand=True, padx=8, pady=2)

            if is_start:
                fur = f" / {r.fur_length}" if r.fur_length else ""
                # 1줄: 시간 + 이름
                top_row = ctk.CTkFrame(inner, fg_color="transparent")
                top_row.pack(fill="x")
                ctk.CTkLabel(top_row, text=f"{start_time}~{end_time}",
                             font=("", 18, "bold"), text_color=s["text"],
                             anchor="w").pack(side="left")
                ctk.CTkLabel(top_row, text=pet_info,
                             font=("", 18, "bold"), text_color=s["text"],
                             anchor="w").pack(side="left", padx=(6, 0))

                # 2줄: 서비스 + 금액
                mid_row = ctk.CTkFrame(inner, fg_color="transparent")
                mid_row.pack(fill="x")
                amt_text = f"  {r.amount:,}원" if r.amount else ""
                ctk.CTkLabel(mid_row, text=f"{r.service_type}{fur}{amt_text}",
                             font=("", 18), text_color=s["text"],
                             anchor="w").pack(side="left")

                # 3줄: 메모 (있으면)
                memo_parts = []
                if r.request:
                    memo_parts.append(r.request)
                if r.groomer_memo and r.groomer_memo != r.request:
                    memo_parts.append(r.groomer_memo)
                if memo_parts:
                    ctk.CTkLabel(inner, text=f"메모: {' / '.join(memo_parts)}", font=("", 18),
                                 text_color=s["text"], anchor="w",
                                 wraplength=300).pack(anchor="w")

                # 4줄: 완료 시간 (있으면)
                if r.status == "completed" and getattr(r, "completed_at", None):
                    ctk.CTkLabel(inner, text=f"완료: {r.completed_at}",
                                 font=("", 18), text_color=s["text"],
                                 anchor="w").pack(anchor="w")
            else:
                ctk.CTkLabel(inner, text=f"~ {pet_info}",
                             font=("", 18), text_color=s["text"],
                             anchor="w").pack(anchor="w")

        self._bind_recursive(slot, "<Button-1>", lambda *_, x=r: self._click_booked(x))
        return slot

    def _bind_recursive(self, widget, event, callback):
        """위젯과 모든 자식에 이벤트 바인딩"""
        widget.bind(event, callback)
        for child in widget.winfo_children():
            self._bind_recursive(child, event, callback)

    def _click_empty(self, ts):
        if self._on_slot_click:
            self._on_slot_click(ts)

    def _click_booked(self, r):
        if self._on_reservation_click:
            self._on_reservation_click(r)

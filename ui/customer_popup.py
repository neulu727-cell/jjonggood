"""전화 수신 팝업 - 고객 정보 + 캘린더 + 타임라인으로 바로 예약"""

import customtkinter as ctk
from datetime import date
from database.models import Customer, Reservation
from database.db_manager import DatabaseManager
from database import queries
from utils.phone_formatter import format_phone_display
from utils.date_utils import days_since, format_date_korean
from ui.widgets.month_calendar import MonthCalendar
from ui.widgets.day_timeline import DayTimeline
from typing import Optional
import config

ACCENT = "#4F46E5"
LABEL_COLOR = ("#64748B", "#94A3B8")


class CustomerPopup(ctk.CTkToplevel):
    """전화 수신 시 캘린더+타임라인 팝업.
    재방문: 슬롯 클릭 → 바로 예약
    신규: 슬롯 클릭 → 고객등록 → 예약
    """

    def __init__(self, parent, phone: str, db: DatabaseManager,
                 customer: Optional[Customer] = None,
                 last_visit: Optional[str] = None,
                 on_register_new=None,
                 on_reservation_saved=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.resizable(True, True)
        self.attributes("-topmost", True)
        self.configure(fg_color=("#FFFFFF", "#1E293B"))

        self._phone = phone
        self._db = db
        self._customer = customer
        self._last_visit = last_visit
        self._on_register_new = on_register_new
        self._on_reservation_saved = on_reservation_saved
        self._selected_date = date.today()
        self._pending_time = None

        self._is_returning = customer is not None

        if self._is_returning:
            self.title(f"전화수신 - {customer.pet_name} ({customer.breed})")
            self.geometry("950x640")
        else:
            self.title(f"전화수신 - 신규 {format_phone_display(phone)}")
            self.geometry("950x640")

        self.grab_set()
        self._build_ui()
        self._on_date_selected(date.today())

        self.update_idletasks()
        self._center_window()

        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception:
            pass

    def _center_window(self):
        w = self.winfo_width()
        h = self.winfo_height()
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"+{x}+{y}")

    def _build_ui(self):
        if self._is_returning:
            self._build_returning_header()
        else:
            self._build_new_header()

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=12, pady=(8, 12))

        left = ctk.CTkFrame(content, fg_color="transparent", width=400)
        left.pack(side="left", fill="y", padx=(0, 8))
        left.pack_propagate(False)

        self._calendar = MonthCalendar(
            left,
            on_date_select=self._on_date_selected,
            get_counts_fn=self._get_month_counts,
        )
        self._calendar.pack(fill="x")

        self._date_summary = ctk.CTkLabel(
            left, text="", font=("", 18), text_color=LABEL_COLOR
        )
        self._date_summary.pack(anchor="w", padx=10, pady=(10, 0))

        bottom = ctk.CTkFrame(left, fg_color="transparent")
        bottom.pack(side="bottom", fill="x", padx=10, pady=(10, 0))

        if self._is_returning:
            hint = "날짜 선택 → 빈 시간 클릭으로 바로 예약"
        else:
            hint = "날짜 선택 → 빈 시간 클릭 → 고객등록 → 예약"

        ctk.CTkLabel(
            bottom, text=hint, font=("", 18),
            text_color=LABEL_COLOR
        ).pack(anchor="w")

        ctk.CTkButton(
            bottom, text="닫기", width=130, height=40,
            font=("", 18), corner_radius=8,
            fg_color=("gray70", "gray35"), hover_color=("gray60", "gray45"),
            command=self.destroy
        ).pack(anchor="w", pady=(8, 0))

        right = ctk.CTkFrame(content, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True)

        self._date_title = ctk.CTkLabel(
            right, text="", font=("", 18, "bold")
        )
        self._date_title.pack(anchor="w", pady=(0, 6))

        self._timeline_scroll = ctk.CTkScrollableFrame(
            right, fg_color="transparent", corner_radius=10,
            border_width=1, border_color=("gray85", "gray25")
        )
        self._timeline_scroll.pack(fill="both", expand=True)

    def _build_returning_header(self):
        c = self._customer
        header = ctk.CTkFrame(self, height=70, corner_radius=0, fg_color=ACCENT)
        header.pack(fill="x")
        header.pack_propagate(False)

        left = ctk.CTkFrame(header, fg_color="transparent")
        left.pack(side="left", padx=20)

        ctk.CTkLabel(
            left, text="재방문", font=("", 18, "bold"),
            fg_color="#C7D2FE", text_color=ACCENT,
            corner_radius=6, width=70, height=24
        ).pack(side="left", padx=(0, 12))

        ctk.CTkLabel(
            left, text=f"{c.pet_name} ({c.breed})",
            font=("", 20, "bold"), text_color="white"
        ).pack(side="left")

        if c.weight:
            ctk.CTkLabel(
                left, text=f"{c.weight}kg",
                font=("", 18), text_color="#C7D2FE"
            ).pack(side="left", padx=(10, 0))

        right = ctk.CTkFrame(header, fg_color="transparent")
        right.pack(side="right", padx=20)

        ctk.CTkLabel(
            right, text=format_phone_display(self._phone),
            font=("", 18), text_color="#E0E7FF"
        ).pack(anchor="e")

        if self._last_visit:
            days = days_since(self._last_visit)
            ctk.CTkLabel(
                right, text=f"마지막 방문 {days}일 전",
                font=("", 18), text_color="#A5B4FC"
            ).pack(anchor="e")

    def _build_new_header(self):
        header = ctk.CTkFrame(self, height=70, corner_radius=0, fg_color="#DC2626")
        header.pack(fill="x")
        header.pack_propagate(False)

        left = ctk.CTkFrame(header, fg_color="transparent")
        left.pack(side="left", padx=20)

        ctk.CTkLabel(
            left, text="신규", font=("", 18, "bold"),
            fg_color="#FCA5A5", text_color="#991B1B",
            corner_radius=6, width=60, height=24
        ).pack(side="left", padx=(0, 12))

        ctk.CTkLabel(
            left, text=format_phone_display(self._phone),
            font=("", 20, "bold"), text_color="white"
        ).pack(side="left")

        ctk.CTkLabel(
            left, text="등록되지 않은 번호",
            font=("", 18), text_color="#FECACA"
        ).pack(side="left", padx=(15, 0))

    def _get_month_counts(self, year: int, month: int) -> dict:
        return queries.get_reservation_counts_by_month(self._db, year, month)

    def _on_date_selected(self, d: date):
        self._selected_date = d

        weekdays = ["월", "화", "수", "목", "금", "토", "일"]
        wd = weekdays[d.weekday()]
        today = date.today()

        if d == today:
            self._date_title.configure(text=f"오늘  {d.month}월 {d.day}일 ({wd})")
        else:
            self._date_title.configure(text=f"{d.month}월 {d.day}일 ({wd})")

        reservations = queries.get_reservations_by_date(
            self._db, d.strftime("%Y-%m-%d")
        )

        confirmed = sum(1 for r in reservations if r.status == "confirmed")
        self._date_summary.configure(
            text=f"{d.month}/{d.day}  |  예약 {confirmed}건 / 전체 {len(reservations)}건"
        )

        self._refresh_timeline(reservations)

    def _refresh_timeline(self, reservations=None):
        if reservations is None:
            reservations = queries.get_reservations_by_date(
                self._db, self._selected_date.strftime("%Y-%m-%d")
            )

        for w in self._timeline_scroll.winfo_children():
            w.destroy()

        timeline = DayTimeline(
            self._timeline_scroll,
            reservations=reservations,
            on_slot_click=self._on_slot_click,
            on_reservation_click=self._on_reservation_click,
        )
        timeline.pack(fill="x")

    def _on_slot_click(self, time_str: str):
        if self._is_returning:
            self._show_quick_booking(time_str)
        else:
            self._pending_time = time_str
            if self._on_register_new:
                self._on_register_new(self._phone, self._on_new_customer_saved)

    def _on_new_customer_saved(self, customer: Customer):
        self._customer = customer
        self._is_returning = True
        if self._pending_time:
            self._show_quick_booking(self._pending_time)
            self._pending_time = None

    def _show_quick_booking(self, time_str: str):
        form = ctk.CTkToplevel(self)
        d = self._selected_date
        c = self._customer
        form.title(f"예약 - {d.month}/{d.day} {time_str}")
        form.geometry("440x420")
        form.resizable(False, False)
        form.grab_set()
        form.attributes("-topmost", True)

        hdr = ctk.CTkFrame(form, fg_color=ACCENT, corner_radius=0, height=48)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(
            hdr, text=f"{d.month}/{d.day}  {time_str}  {c.pet_name}",
            font=("", 18, "bold"), text_color="white"
        ).pack(side="left", padx=15)

        body = ctk.CTkFrame(form, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=15)

        ctk.CTkLabel(body, text="미용 종류 *", font=("", 18, "bold"),
                     text_color=("gray20", "gray80")).pack(anchor="w")
        service_names = [s[0] for s in config.DEFAULT_SERVICES]
        service_combo = ctk.CTkComboBox(
            body, values=service_names, height=38, font=("", 18),
            dropdown_font=("", 18),
            command=lambda val: self._on_service_change(val, dur_entry, amt_entry)
        )
        service_combo.pack(fill="x", pady=(4, 10))
        service_combo.set(service_names[0])

        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x", pady=(0, 10))

        col_l = ctk.CTkFrame(row, fg_color="transparent")
        col_l.pack(side="left", fill="x", expand=True, padx=(0, 5))
        ctk.CTkLabel(col_l, text="소요시간 (분)", font=("", 18),
                     text_color=LABEL_COLOR).pack(anchor="w")
        dur_entry = ctk.CTkEntry(col_l, height=38, font=("", 18))
        dur_entry.pack(fill="x", pady=(2, 0))
        dur_entry.insert(0, str(config.DEFAULT_SERVICES[0][1]))

        col_r = ctk.CTkFrame(row, fg_color="transparent")
        col_r.pack(side="left", fill="x", expand=True, padx=(5, 0))
        ctk.CTkLabel(col_r, text="금액 (원)", font=("", 18),
                     text_color=LABEL_COLOR).pack(anchor="w")
        amt_entry = ctk.CTkEntry(col_r, height=38, font=("", 18))
        amt_entry.pack(fill="x", pady=(2, 0))
        amt_entry.insert(0, str(config.DEFAULT_SERVICES[0][2]))

        ctk.CTkLabel(body, text="메모", font=("", 18),
                     text_color=LABEL_COLOR).pack(anchor="w", pady=(0, 2))
        req_text = ctk.CTkTextbox(body, height=60, font=("", 18),
                                   border_width=1, border_color=("gray75", "gray30"),
                                   corner_radius=8)
        req_text.pack(fill="x", pady=(0, 15))

        ctk.CTkButton(
            body, text="예약 저장", height=44, font=("", 18, "bold"),
            corner_radius=10, fg_color="#22C55E", hover_color="#16A34A",
            command=lambda: self._save_booking(
                form, time_str, service_combo.get(),
                dur_entry.get(), amt_entry.get(),
                req_text.get("1.0", "end-1c")
            )
        ).pack(fill="x")

    def _on_service_change(self, val, dur_entry, amt_entry):
        for name, duration, price in config.DEFAULT_SERVICES:
            if name == val:
                dur_entry.delete(0, "end")
                dur_entry.insert(0, str(duration))
                amt_entry.delete(0, "end")
                amt_entry.insert(0, str(price))
                break

    def _save_booking(self, form, time_str, service, duration_str, amount_str, request):
        service = service.strip()
        if not service:
            return

        data = {
            "customer_id": self._customer.id,
            "date": self._selected_date.strftime("%Y-%m-%d"),
            "time": time_str,
            "service_type": service,
            "duration": int(duration_str) if duration_str.strip() else 60,
            "request": request.strip(),
            "amount": int(amount_str) if amount_str.strip() else 0,
        }

        if self._on_reservation_saved:
            self._on_reservation_saved(data)

        form.destroy()

        self._on_date_selected(self._selected_date)
        self._calendar.refresh()

    def _on_reservation_click(self, reservation: Reservation):
        menu = ctk.CTkToplevel(self)
        menu.title("예약 관리")
        menu.geometry("320x280")
        menu.resizable(False, False)
        menu.grab_set()
        menu.attributes("-topmost", True)

        ctk.CTkLabel(
            menu, text=f"{reservation.time}  {reservation.customer_name}",
            font=("", 18, "bold")
        ).pack(pady=(20, 3))
        ctk.CTkLabel(
            menu, text=f"{reservation.pet_name} | {reservation.service_type}",
            font=("", 18), text_color=LABEL_COLOR
        ).pack(pady=(0, 15))

        for status, text, color in [
            ("completed", "미용 완료", "#22C55E"),
            ("cancelled", "예약 취소", "#EF4444"),
            ("no_show", "노쇼 처리", "#F59E0B"),
        ]:
            ctk.CTkButton(
                menu, text=text, width=210, height=40, font=("", 18),
                corner_radius=10, fg_color=color,
                command=lambda s=status, m=menu, rid=reservation.id:
                    self._change_status(rid, s, m)
            ).pack(pady=2)

        ctk.CTkButton(
            menu, text="닫기", width=210, height=38, font=("", 18),
            corner_radius=8, fg_color=("gray70", "gray35"),
            command=menu.destroy
        ).pack(pady=(8, 5))

    def _change_status(self, reservation_id, action, menu):
        if action == "cancelled":
            queries.delete_reservation(self._db, reservation_id)
        else:
            queries.update_reservation_status(self._db, reservation_id, action)
        menu.destroy()
        self._on_date_selected(self._selected_date)
        self._calendar.refresh()

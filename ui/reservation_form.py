"""예약 등록 - 캘린더 + 타임라인 기반"""

import customtkinter as ctk
from datetime import date
from database.models import Customer, Reservation
from database.db_manager import DatabaseManager
from database import queries
from ui.widgets.month_calendar import MonthCalendar
from ui.widgets.day_timeline import DayTimeline
import config

ACCENT = "#4F46E5"
LABEL_COLOR = ("#64748B", "#94A3B8")


class ReservationForm(ctk.CTkToplevel):
    """캘린더에서 날짜 선택 → 타임라인에서 시간 클릭 → 예약 생성"""

    def __init__(self, parent, customer: Customer, on_save=None,
                 db: DatabaseManager = None, **kwargs):
        super().__init__(parent, **kwargs)
        self.title(f"예약 등록 - {customer.pet_name} ({customer.breed})")
        self.geometry("950x700")
        self.resizable(False, False)
        self.grab_set()

        self._customer = customer
        self._on_save = on_save
        self._db = db
        self._selected_date = date.today()
        self._selected_time = ""

        self._build_ui()
        self._on_date_selected(date.today())

    def _build_ui(self):
        c = self._customer

        header = ctk.CTkFrame(self, fg_color=ACCENT, corner_radius=0, height=52)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text=f"  예약 등록   {c.pet_name} ({c.breed})",
            font=("", 18, "bold"), text_color="white"
        ).pack(side="left", padx=20)

        if c.weight:
            ctk.CTkLabel(
                header, text=f"{c.weight}kg", font=("", 18),
                text_color="#C7D2FE"
            ).pack(side="left", padx=(5, 0))

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=15, pady=10)

        left = ctk.CTkFrame(content, fg_color="transparent", width=400)
        left.pack(side="left", fill="y", padx=(0, 10))
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

        right = ctk.CTkFrame(content, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True)

        self._date_title = ctk.CTkLabel(
            right, text="", font=("", 18, "bold")
        )
        self._date_title.pack(anchor="w", pady=(0, 8))

        self._timeline_scroll = ctk.CTkScrollableFrame(
            right, fg_color="transparent", corner_radius=10,
            border_width=1, border_color=("gray85", "gray25")
        )
        self._timeline_scroll.pack(fill="both", expand=True)

        self._timeline = None

    def _get_month_counts(self, year: int, month: int) -> dict:
        if not self._db:
            return {}
        return queries.get_reservation_counts_by_month(self._db, year, month)

    def _on_date_selected(self, d: date):
        self._selected_date = d

        weekdays = ["월", "화", "수", "목", "금", "토", "일"]
        wd = weekdays[d.weekday()]
        self._date_title.configure(text=f"{d.month}월 {d.day}일 ({wd}) 예약 현황")

        reservations = []
        if self._db:
            reservations = queries.get_reservations_by_date(
                self._db, d.strftime("%Y-%m-%d")
            )

        confirmed = sum(1 for r in reservations if r.status == "confirmed")
        completed = sum(1 for r in reservations if r.status == "completed")
        self._date_summary.configure(
            text=f"선택: {d.month}/{d.day}  |  예약 {confirmed}건  완료 {completed}건"
        )

        self._refresh_timeline(reservations)

    def _refresh_timeline(self, reservations=None):
        if reservations is None and self._db:
            reservations = queries.get_reservations_by_date(
                self._db, self._selected_date.strftime("%Y-%m-%d")
            )
        reservations = reservations or []

        for w in self._timeline_scroll.winfo_children():
            w.destroy()

        self._timeline = DayTimeline(
            self._timeline_scroll,
            reservations=reservations,
            on_slot_click=self._on_slot_click,
            on_reservation_click=self._on_reservation_click,
        )
        self._timeline.pack(fill="x")

    def _on_slot_click(self, time_str: str):
        self._selected_time = time_str
        self._show_booking_form(time_str)

    def _on_reservation_click(self, reservation: Reservation):
        menu = ctk.CTkToplevel(self)
        menu.title("예약 관리")
        menu.geometry("380x310")
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
        if self._db:
            if action == "cancelled":
                queries.delete_reservation(self._db, reservation_id)
            else:
                queries.update_reservation_status(self._db, reservation_id, action)
        menu.destroy()
        self._on_date_selected(self._selected_date)
        self._calendar.refresh()

    def _show_booking_form(self, time_str: str):
        form = ctk.CTkToplevel(self)
        form.title(f"예약 - {self._selected_date.month}/{self._selected_date.day} {time_str}")
        form.geometry("520x460")
        form.resizable(False, False)
        form.grab_set()
        form.attributes("-topmost", True)

        c = self._customer

        hdr = ctk.CTkFrame(form, fg_color=ACCENT, corner_radius=0, height=48)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(
            hdr, text=f"{self._selected_date.month}/{self._selected_date.day}  {time_str}  {c.pet_name}",
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
            command=lambda val: self._on_mini_service_change(val, dur_entry, amt_entry)
        )
        service_combo.pack(fill="x", pady=(4, 10))
        service_combo.set(service_names[0])

        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x", pady=(0, 10))

        left = ctk.CTkFrame(row, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True, padx=(0, 5))
        ctk.CTkLabel(left, text="소요시간 (분)", font=("", 18),
                     text_color=LABEL_COLOR).pack(anchor="w")
        dur_entry = ctk.CTkEntry(left, height=38, font=("", 18))
        dur_entry.pack(fill="x", pady=(2, 0))
        dur_entry.insert(0, str(config.DEFAULT_SERVICES[0][1]))

        right = ctk.CTkFrame(row, fg_color="transparent")
        right.pack(side="left", fill="x", expand=True, padx=(5, 0))
        ctk.CTkLabel(right, text="금액 (원)", font=("", 18),
                     text_color=LABEL_COLOR).pack(anchor="w")
        amt_entry = ctk.CTkEntry(right, height=38, font=("", 18))
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

    def _on_mini_service_change(self, val, dur_entry, amt_entry):
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

        if self._on_save:
            self._on_save(data)

        form.destroy()

        self._on_date_selected(self._selected_date)
        self._calendar.refresh()

"""메인 애플리케이션 윈도우 - 단일 창 컨트롤러"""

import time
import customtkinter as ctk
from database.db_manager import DatabaseManager
from database import queries
from database.models import Customer
from ui.main_screen import MainScreen
from ui.customer_form import CustomerForm
from ui.customer_detail import CustomerDetail
from ui.reservation_form import ReservationForm
from ui.customer_search import CustomerSearch
from utils.phone_formatter import normalize_phone
import config


class AppWindow(ctk.CTk):
    """메인 윈도우 - 모든 화면 전환과 콜백을 관리"""

    def __init__(self, db: DatabaseManager):
        super().__init__()
        self.title(config.WINDOW_TITLE)
        ctk.set_appearance_mode(config.APPEARANCE_MODE)
        ctk.set_default_color_theme(config.COLOR_THEME)

        # 화면 크기 자동 감지 → 중앙 배치
        self.update_idletasks()
        sx = self.winfo_screenwidth()
        sy = self.winfo_screenheight()
        w = min(sx - 40, 1300)
        h = min(sy - 80, 660)
        x = (sx - w) // 2
        y = max(5, (sy - h - 50) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

        self._db = db
        self._last_detected_phone = ""
        self._last_detected_time = 0

        self.main_screen = MainScreen(self, db=self._db)
        self.main_screen.pack(fill="both", expand=True)

    # ===== 전화 수신 =====

    def on_call_detected(self, phone_number: str):
        normalized = normalize_phone(phone_number)
        if not normalized:
            return

        now = time.time()
        if (self._last_detected_phone == normalized
                and now - self._last_detected_time < 30):
            return

        self._last_detected_phone = normalized
        self._last_detected_time = now

        self.after(0, lambda: self._show_call_popup(normalized))

    def _show_call_popup(self, phone: str):
        """전화수신 팝업 표시 + 수신 기록 저장"""
        try:
            customer = queries.find_customer_by_phone(self._db, phone)
            last_visit = None
            if customer:
                last_visit = queries.get_last_visit_date(self._db, customer.id)

            # 전화수신 기록 저장
            queries.add_call_history(
                self._db, phone,
                customer_id=customer.id if customer else None,
                pet_name=customer.pet_name if customer else "",
            )

            self.main_screen.show_call_popup(phone, customer, last_visit)
            self.main_screen.refresh_call_history()
        except Exception as e:
            print(f"  전화수신 처리 오류: {e}")

    # ===== 고객 등록 (팝업) =====

    def _open_customer_form_with_callback(self, phone: str, on_saved_callback=None):
        CustomerForm(
            self,
            phone=phone,
            on_save=lambda data: self._save_new_customer_and_callback(data, on_saved_callback),
        )

    def _save_new_customer_and_callback(self, data: dict, on_saved_callback=None):
        queries.create_customer(
            self._db,
            name=data["name"],
            phone=data["phone"],
            pet_name=data["pet_name"],
            breed=data["breed"],
            weight=data.get("weight"),
            age=data.get("age"),
            notes=data.get("notes", ""),
            memo=data.get("memo", ""),
        )
        customer = queries.find_customer_by_phone(self._db, data["phone"])
        if customer and on_saved_callback:
            on_saved_callback(customer)

    def _on_popup_reservation_saved(self, data: dict):
        rid = queries.create_reservation(
            self._db,
            customer_id=data["customer_id"],
            date=data["date"],
            time=data["time"],
            service_type=data["service_type"],
            duration=data.get("duration", 60),
            request=data.get("request", ""),
            amount=data.get("amount", 0),
            fur_length=data.get("fur_length", ""),
        )
        # 메모를 groomer_memo에도 저장
        memo = data.get("request", "").strip()
        if memo and rid:
            queries.update_reservation_memo(self._db, rid, memo)
        self.main_screen.refresh_reservations()

    # ===== 화면 전환 =====

    def _open_customer_form(self, phone: str):
        CustomerForm(
            self, phone=phone,
            on_save=self._save_new_customer,
        )

    def _save_new_customer(self, data: dict):
        queries.create_customer(
            self._db,
            name=data["name"],
            phone=data["phone"],
            pet_name=data["pet_name"],
            breed=data["breed"],
            weight=data.get("weight"),
            age=data.get("age"),
            notes=data.get("notes", ""),
            memo=data.get("memo", ""),
        )
        customer = queries.find_customer_by_phone(self._db, data["phone"])
        if customer:
            self._open_reservation_form(customer)

    def _open_customer_detail(self, customer: Customer):
        reservations = queries.get_customer_reservations(self._db, customer.id)
        last_visit = queries.get_last_visit_date(self._db, customer.id)

        CustomerDetail(
            self,
            customer=customer,
            reservations=reservations,
            last_visit=last_visit,
            on_new_reservation=self._open_reservation_form,
            on_update_memo=self._update_customer_memo,
            on_delete_customer=self._delete_customer,
            db=self._db,
        )

    def _open_reservation_form(self, customer: Customer):
        ReservationForm(
            self,
            customer=customer,
            on_save=self._save_reservation,
            db=self._db,
        )

    def _save_reservation(self, data: dict):
        queries.create_reservation(
            self._db,
            customer_id=data["customer_id"],
            date=data["date"],
            time=data["time"],
            service_type=data["service_type"],
            duration=data.get("duration", 60),
            request=data.get("request", ""),
            amount=data.get("amount", 0),
        )
        self.main_screen.refresh_reservations()

    def _delete_customer(self, customer_id: int):
        queries.delete_customer(self._db, customer_id)
        self.main_screen.refresh_reservations()

    def _update_customer_memo(self, customer_id: int, memo: str):
        queries.update_customer(self._db, customer_id, memo=memo)

    # ===== 빠른 메뉴 =====

    def show_customer_search(self):
        CustomerSearch(self, db=self._db, on_select=self._open_customer_detail)

    def show_customer_search_for_reservation(self):
        CustomerSearch(self, db=self._db, on_select=self._open_reservation_form)

    def _show_customer_search_for_slot(self, on_select_callback):
        """타임라인 슬롯에서 고객 검색 → 선택 시 콜백"""
        CustomerSearch(self, db=self._db, on_select=on_select_callback)

    def show_new_customer_form(self):
        CustomerForm(self, phone="", on_save=self._save_new_customer_manual)

    def _save_new_customer_manual(self, data: dict):
        normalized_phone = normalize_phone(data["phone"])
        if not normalized_phone:
            return
        queries.create_customer(
            self._db,
            name=data["name"],
            phone=normalized_phone,
            pet_name=data["pet_name"],
            breed=data["breed"],
            weight=data.get("weight"),
            age=data.get("age"),
            notes=data.get("notes", ""),
            memo=data.get("memo", ""),
        )

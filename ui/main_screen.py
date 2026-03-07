"""메인 화면 - 팝업 전화수신 + 캘린더 + 색상 타임라인"""

import customtkinter as ctk
from datetime import date, datetime
from database.db_manager import DatabaseManager
from database.models import Customer
from database import queries
from ui.widgets.status_indicator import StatusIndicator
from ui.widgets.month_calendar import MonthCalendar
from ui.widgets.day_timeline import DayTimeline
from utils.phone_formatter import format_phone_display
from utils.date_utils import days_since
from typing import Optional
import config

ACCENT = "#4F46E5"
SIDEBAR_BG = ("#F1F5F9", "#0F172A")
HEADER_BG = ("#4F46E5", "#312E81")
LABEL_COLOR = ("#64748B", "#94A3B8")
BOOKING_BG = "#059669"


class MainScreen(ctk.CTkFrame):

    def __init__(self, parent, db: DatabaseManager, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._db = db
        self._parent = parent
        self._selected_date = date.today()
        self._active_customer: Optional[Customer] = None
        self._active_phone: str = ""
        self._booking_mode = False
        self._move_mode = False
        self._move_reservation = None
        self._build_ui()
        self._on_date_selected(date.today())

    def _build_ui(self):
        # ===== 헤더 =====
        top = ctk.CTkFrame(self, height=44, corner_radius=0, fg_color=HEADER_BG)
        top.pack(fill="x")
        top.pack_propagate(False)
        ctk.CTkLabel(top, text=" 애견미용샵 예약관리",
                     font=("", 15, "bold"), text_color="white").pack(side="left", padx=8)
        rf = ctk.CTkFrame(top, fg_color="transparent")
        rf.pack(side="right", padx=8)
        self.status_indicator = StatusIndicator(rf, fg_color="transparent")
        self.status_indicator.pack(side="right")
        self._time_label = ctk.CTkLabel(rf, text="", font=("", 15),
                                         text_color=("#C7D2FE", "#A5B4FC"))
        self._time_label.pack(side="right", padx=(0, 8))
        self._update_clock()

        # ===== 콘텐츠 (3열: 캘린더 | 버튼+수신기록 | 타임라인) =====
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True)
        content.columnconfigure(0, weight=0, minsize=560)  # 캘린더 고정
        content.columnconfigure(1, weight=0, minsize=200)  # 버튼+수신기록 고정
        content.columnconfigure(2, weight=1)               # 타임라인 나머지 전부
        content.rowconfigure(0, weight=1)

        # ===== 1열: 캘린더 =====
        cal_col = ctk.CTkFrame(content, corner_radius=0, fg_color=SIDEBAR_BG, width=560)
        cal_col.grid(row=0, column=0, sticky="nsew")
        cal_col.pack_propagate(False)

        self._calendar = MonthCalendar(
            cal_col, on_date_select=self._on_date_selected,
            get_counts_fn=self._get_month_counts,
            get_names_fn=self._get_month_names)
        self._calendar.pack(fill="both", expand=True, padx=6, pady=(4, 4))

        sr = ctk.CTkFrame(cal_col, fg_color="transparent")
        sr.pack(fill="x", padx=10, pady=(0, 4))
        self._stat_label = ctk.CTkLabel(sr, text="", font=("", 15, "bold"), text_color=ACCENT)
        self._stat_label.pack(side="left")
        self._stat_detail = ctk.CTkLabel(sr, text="", font=("", 15), text_color=LABEL_COLOR)
        self._stat_detail.pack(side="right")

        # ===== 2열: 버튼 + 수신기록 =====
        mid_col = ctk.CTkFrame(content, corner_radius=0, fg_color=SIDEBAR_BG, width=200)
        mid_col.grid(row=0, column=1, sticky="nsew")
        mid_col.pack_propagate(False)

        for txt, clr, hclr, cmd in [
            ("고객 검색", "#3B82F6", "#2563EB", self._on_search_customer),
            ("예약 등록", "#22C55E", "#16A34A", self._on_manual_reservation),
            ("고객 등록", "#8B5CF6", "#7C3AED", self._on_new_customer),
            ("새로고침", ("gray70", "gray35"), ("gray60", "gray45"), self._refresh_all),
        ]:
            ctk.CTkButton(mid_col, text=txt, height=38, font=("", 15), corner_radius=5,
                           fg_color=clr, hover_color=hclr,
                           command=cmd).pack(fill="x", padx=6, pady=1)

        # 전화수신 히스토리
        ctk.CTkFrame(mid_col, height=1, fg_color=("gray80", "gray30")).pack(fill="x", padx=6, pady=(6, 2))

        call_hdr = ctk.CTkFrame(mid_col, fg_color="transparent")
        call_hdr.pack(fill="x", padx=6, pady=(0, 1))

        ctk.CTkButton(call_hdr, text="<", width=30, height=32, font=("", 15, "bold"),
                       fg_color="transparent", text_color=("gray30", "gray70"),
                       hover_color=("gray90", "gray20"), corner_radius=3,
                       command=self._call_hist_prev_day).pack(side="left")
        self._call_hist_date_label = ctk.CTkLabel(call_hdr, text="", font=("", 15, "bold"))
        self._call_hist_date_label.pack(side="left", expand=True)
        ctk.CTkButton(call_hdr, text=">", width=30, height=32, font=("", 15, "bold"),
                       fg_color="transparent", text_color=("gray30", "gray70"),
                       hover_color=("gray90", "gray20"), corner_radius=3,
                       command=self._call_hist_next_day).pack(side="right")

        self._call_hist_scroll = ctk.CTkScrollableFrame(
            mid_col, fg_color="transparent", corner_radius=4,
            scrollbar_button_color=("gray75", "gray35"))
        self._call_hist_scroll.pack(fill="both", expand=True, padx=6, pady=(0, 4))

        self._call_hist_date = date.today()
        self._render_call_history()

        # ===== 3열: 타임라인 =====
        main_area = ctk.CTkFrame(content, fg_color="transparent")
        main_area.grid(row=0, column=2, sticky="nsew")

        hdr = ctk.CTkFrame(main_area, fg_color="transparent", height=38)
        hdr.pack(fill="x", padx=8, pady=(3, 1))
        hdr.pack_propagate(False)
        self._date_title = ctk.CTkLabel(hdr, text="", font=("", 15, "bold"))
        self._date_title.pack(side="left")

        # 예약모드 표시 (숨김 상태)
        self._booking_label = ctk.CTkLabel(
            hdr, text="", font=("", 15, "bold"), text_color="white",
            fg_color=BOOKING_BG, corner_radius=4, height=32)
        self._booking_cancel = ctk.CTkButton(
            hdr, text="취소", height=32, width=56, font=("", 15),
            corner_radius=3, fg_color="#DC2626", hover_color="#B91C1C",
            command=self._exit_booking_mode)

        self._count_label = ctk.CTkLabel(hdr, text="0건", font=("", 15),
                                          fg_color=("#EEF2FF", "#312E81"), text_color=ACCENT,
                                          corner_radius=4, width=50, height=30)
        self._count_label.pack(side="right")

        # 타임라인 영역 (세로 꽉 채움)
        self._timeline_frame = ctk.CTkFrame(
            main_area, fg_color="transparent", corner_radius=0)
        self._timeline_frame.pack(fill="both", expand=True, padx=6, pady=(0, 3))

    # ===== 시계 =====
    def _update_clock(self):
        self._time_label.configure(text=datetime.now().strftime("%H:%M"))
        self.after(30000, self._update_clock)

    # ===== 전화수신 팝업 =====
    def show_call_popup(self, phone: str, customer: Optional[Customer] = None,
                        last_visit: Optional[str] = None):
        self._active_phone = phone
        self._active_customer = customer

        popup = ctk.CTkToplevel(self)
        popup.resizable(False, False)
        popup.attributes("-topmost", True)
        popup.grab_set()

        if customer:
            popup.title("전화 수신 - 재방문")
            popup.configure(fg_color=("#FFFFFF", "#1E293B"))

            bar = ctk.CTkFrame(popup, height=6, corner_radius=0, fg_color=ACCENT)
            bar.pack(fill="x")

            top = ctk.CTkFrame(popup, fg_color="transparent")
            top.pack(fill="x", padx=16, pady=(10, 4))

            ctk.CTkLabel(top, text="재방문 고객", font=("", 15, "bold"),
                         fg_color="#EEF2FF", text_color=ACCENT,
                         corner_radius=6, width=100, height=24).pack(side="left")
            if last_visit:
                ctk.CTkLabel(top, text=f"  마지막 방문 {days_since(last_visit)}일 전",
                             font=("", 15), text_color="#D97706").pack(side="left")
            else:
                ctk.CTkLabel(top, text="  첫 예약", font=("", 15),
                             text_color="#D97706").pack(side="left")

            info = f"{customer.pet_name} ({customer.breed})"
            if customer.weight:
                info += f"  {customer.weight}kg"
            ctk.CTkLabel(popup, text=info, font=("", 15, "bold")).pack(padx=16, anchor="w")
            ctk.CTkLabel(popup, text=format_phone_display(phone), font=("", 15),
                         text_color=LABEL_COLOR).pack(padx=16, anchor="w", pady=(0, 6))

            # 최근 예약 히스토리
            reservations = queries.get_customer_reservations(self._db, customer.id)
            memos = queries.get_customer_groomer_memos(self._db, customer.id)

            if reservations or memos:
                ctk.CTkFrame(popup, height=1, fg_color=("gray85", "gray30")).pack(fill="x", padx=12)
                hist_scroll = ctk.CTkScrollableFrame(popup, fg_color="transparent",
                                                      height=180, corner_radius=0)
                hist_scroll.pack(fill="both", expand=True, padx=12, pady=(4, 4))

                for rv in reservations[:5]:
                    rf = ctk.CTkFrame(hist_scroll, fg_color=("#F8FAFC", "#1A1A2E"), corner_radius=4)
                    rf.pack(fill="x", pady=1)

                    fur = f" / {rv.fur_length}" if rv.fur_length else ""
                    amt = f" {rv.amount:,}원" if rv.amount else ""
                    header = f"{rv.date} {rv.time}  {rv.service_type}{fur}{amt}"
                    ctk.CTkLabel(rf, text=header, font=("", 15, "bold"),
                                 text_color=("#334155", "#CBD5E1"),
                                 anchor="w").pack(fill="x", padx=6, pady=(3, 0))

                    memo_parts = []
                    if rv.request:
                        memo_parts.append(rv.request)
                    if rv.groomer_memo and rv.groomer_memo != rv.request:
                        memo_parts.append(rv.groomer_memo)
                    if memo_parts:
                        ctk.CTkLabel(rf, text=f"메모: {' / '.join(memo_parts)}", font=("", 15),
                                     text_color=("#4F46E5", "#A5B4FC"), anchor="w",
                                     wraplength=440).pack(fill="x", padx=6)

                    rv_memos = [m for m in memos if m.get("reservation_id") == rv.id]
                    for m in rv_memos:
                        if m["content"] != rv.groomer_memo:
                            ctk.CTkLabel(rf, text=f"  +메모: {m['content']}", font=("", 15),
                                         text_color=("#6B7280", "#9CA3AF"), anchor="w",
                                         wraplength=440).pack(fill="x", padx=6)

                    ctk.CTkFrame(rf, height=3, fg_color="transparent").pack()

            bf = ctk.CTkFrame(popup, fg_color="transparent")
            bf.pack(pady=(4, 10))
            ctk.CTkButton(bf, text="예약하기", width=140, height=40,
                           font=("", 15, "bold"), corner_radius=8,
                           fg_color="#22C55E", hover_color="#16A34A",
                           command=lambda: self._popup_reserve(popup, customer)
                           ).pack(side="left", padx=4)
            ctk.CTkButton(bf, text="닫기", width=90, height=40,
                           font=("", 15), corner_radius=8,
                           fg_color=("gray70", "gray35"),
                           command=popup.destroy).pack(side="left", padx=4)

            h = 520 if (reservations or memos) else 260
            popup.geometry(f"520x{h}")
        else:
            popup.title("전화 수신 - 신규")
            popup.geometry("480x260")
            popup.configure(fg_color=("#FFFFFF", "#1E293B"))

            bar = ctk.CTkFrame(popup, height=6, corner_radius=0, fg_color="#EF4444")
            bar.pack(fill="x")

            ctk.CTkLabel(popup, text="신규 고객", font=("", 15, "bold"),
                         fg_color="#FEE2E2", text_color="#DC2626",
                         corner_radius=6, width=100, height=26).pack(pady=(14, 6))

            ctk.CTkLabel(popup, text=format_phone_display(phone),
                         font=("", 19, "bold")).pack()
            ctk.CTkLabel(popup, text="등록되지 않은 번호", font=("", 15),
                         text_color=LABEL_COLOR).pack(pady=(2, 14))

            bf = ctk.CTkFrame(popup, fg_color="transparent")
            bf.pack()
            ctk.CTkButton(bf, text="고객등록", width=140, height=40,
                           font=("", 15, "bold"), corner_radius=8,
                           fg_color="#F59E0B", hover_color="#D97706",
                           command=lambda: self._popup_register(popup, phone)
                           ).pack(side="left", padx=4)
            ctk.CTkButton(bf, text="닫기", width=90, height=40,
                           font=("", 15), corner_radius=8,
                           fg_color=("gray70", "gray35"),
                           command=popup.destroy).pack(side="left", padx=4)

        popup.update_idletasks()
        pw, ph = popup.winfo_width(), popup.winfo_height()
        sx, sy = popup.winfo_screenwidth(), popup.winfo_screenheight()
        popup.geometry(f"+{(sx-pw)//2}+{(sy-ph)//2 - 50}")

        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception:
            pass

    def _popup_reserve(self, popup, customer):
        popup.destroy()
        self._active_customer = customer
        self._enter_booking_mode()

    def _popup_register(self, popup, phone):
        popup.destroy()
        if hasattr(self._parent, "_open_customer_form_with_callback"):
            self._parent._open_customer_form_with_callback(
                phone, self._on_new_customer_registered)

    def _on_new_customer_registered(self, customer: Customer):
        self._active_customer = customer
        self._active_phone = customer.phone if hasattr(customer, 'phone') else ""
        self._enter_booking_mode()

    # ===== 예약 모드 =====
    def _enter_booking_mode(self):
        self._booking_mode = True
        c = self._active_customer
        self._booking_label.configure(text=f"  {c.pet_name} 예약 중 - 시간 선택  ")
        self._booking_label.pack(side="left", padx=(10, 4))
        self._booking_cancel.pack(side="left")
        self._show_booking_guide(c)

    def _show_booking_guide(self, customer):
        guide = ctk.CTkToplevel(self)
        guide.overrideredirect(True)
        guide.attributes("-topmost", True)
        guide.configure(fg_color="#059669")

        inner = ctk.CTkFrame(guide, fg_color="#059669", corner_radius=0)
        inner.pack(fill="both", expand=True, padx=3, pady=3)

        breed = customer.breed if hasattr(customer, 'breed') else ""
        text = f"{customer.pet_name}({breed}) 예약 날짜를 정해주세요"
        ctk.CTkLabel(inner, text=text, font=("", 15, "bold"),
                     text_color="white").pack(padx=30, pady=(16, 4))
        ctk.CTkLabel(inner, text="캘린더에서 날짜 선택 → 타임라인에서 시간 클릭",
                     font=("", 15), text_color="#A7F3D0").pack(padx=30, pady=(0, 14))

        guide.update_idletasks()
        gw, gh = guide.winfo_reqwidth(), guide.winfo_reqheight()
        sx, sy = guide.winfo_screenwidth(), guide.winfo_screenheight()
        guide.geometry(f"+{(sx - gw) // 2}+{(sy - gh) // 2 - 40}")

        self.after(2500, lambda: guide.destroy() if guide.winfo_exists() else None)

    def _exit_booking_mode(self):
        self._booking_mode = False
        self._active_customer = None
        self._booking_label.pack_forget()
        self._booking_cancel.pack_forget()

    # ===== 예약 이동 모드 =====
    def _start_move_mode(self, reservation, popup):
        popup.destroy()
        self._move_mode = True
        self._move_reservation = reservation
        pet_info = f"{reservation.pet_name}({reservation.breed})" if reservation.breed else reservation.pet_name
        self._booking_label.configure(
            text=f"  {pet_info} 예약 이동 중 - 날짜/시간 선택  ")
        self._booking_label.pack(side="left", padx=(10, 4))
        self._booking_cancel.configure(command=self._exit_move_mode)
        self._booking_cancel.pack(side="left")
        self._show_move_guide(reservation)

    def _show_move_guide(self, reservation):
        guide = ctk.CTkToplevel(self)
        guide.overrideredirect(True)
        guide.attributes("-topmost", True)
        guide.configure(fg_color="#F59E0B")

        inner = ctk.CTkFrame(guide, fg_color="#F59E0B", corner_radius=0)
        inner.pack(fill="both", expand=True, padx=3, pady=3)

        breed = reservation.breed if hasattr(reservation, 'breed') else ""
        pet_info = f"{reservation.pet_name}({breed})" if breed else reservation.pet_name
        ctk.CTkLabel(inner, text=f"{pet_info} 예약을 옮길 날짜를 정해주세요",
                     font=("", 15, "bold"), text_color="white").pack(padx=30, pady=(16, 4))
        ctk.CTkLabel(inner, text="캘린더에서 날짜 선택 → 타임라인에서 시간 클릭",
                     font=("", 15), text_color="#FEF3C7").pack(padx=30, pady=(0, 14))

        guide.update_idletasks()
        gw, gh = guide.winfo_reqwidth(), guide.winfo_reqheight()
        sx, sy = guide.winfo_screenwidth(), guide.winfo_screenheight()
        guide.geometry(f"+{(sx - gw) // 2}+{(sy - gh) // 2 - 40}")
        self.after(2500, lambda: guide.destroy() if guide.winfo_exists() else None)

    def _complete_move(self, new_time):
        r = self._move_reservation
        new_date = self._selected_date.strftime("%Y-%m-%d")
        queries.update_reservation_with_history(
            self._db, r.id, date=new_date, time=new_time)
        self._exit_move_mode()
        self._on_date_selected(self._selected_date)
        self._calendar.refresh()

    def _exit_move_mode(self):
        self._move_mode = False
        self._move_reservation = None
        self._booking_label.pack_forget()
        self._booking_cancel.pack_forget()

    # ===== 캘린더/타임라인 =====
    def _get_month_counts(self, year, month):
        return queries.get_reservation_counts_by_month(self._db, year, month)

    def _get_month_names(self, year, month):
        return queries.get_reservation_names_by_month(self._db, year, month)

    def _on_date_selected(self, d):
        self._selected_date = d
        wd = ["월", "화", "수", "목", "금", "토", "일"][d.weekday()]
        if d == date.today():
            self._date_title.configure(text=f"오늘 {d.month}/{d.day}({wd})")
        else:
            self._date_title.configure(text=f"{d.month}/{d.day}({wd})")

        res = queries.get_reservations_by_date(self._db, d.strftime("%Y-%m-%d"))
        conf = sum(1 for r in res if r.status == "confirmed")
        comp = sum(1 for r in res if r.status == "completed")
        self._count_label.configure(text=f"{len(res)}건")
        self._stat_label.configure(text=f"{d.month}/{d.day}({wd})")
        self._stat_detail.configure(text=f"예약{conf} 완료{comp}")
        self._refresh_timeline(res)

    def _refresh_timeline(self, res=None):
        if res is None:
            res = queries.get_reservations_by_date(self._db, self._selected_date.strftime("%Y-%m-%d"))
        for w in self._timeline_frame.winfo_children():
            w.destroy()
        DayTimeline(
            self._timeline_frame, reservations=res,
            on_slot_click=self._on_slot_click,
            on_reservation_click=self._on_reservation_click,
            columns=2,
        ).pack(fill="both", expand=True)

    def _on_slot_click(self, time_str):
        if self._move_mode and self._move_reservation:
            self._complete_move(time_str)
        elif self._booking_mode and self._active_customer:
            self._show_quick_booking(time_str, self._active_customer)
        else:
            self._pending_slot_time = time_str
            if hasattr(self._parent, "_show_customer_search_for_slot"):
                self._parent._show_customer_search_for_slot(
                    lambda cust: self._show_quick_booking(self._pending_slot_time, cust)
                )

    def _show_quick_booking(self, time_str, customer):
        sel = {"svc": "", "fur": "", "dur": 0, "amt": 0}
        btn_refs = {"svc": [], "fur": [], "dur": [], "amt": []}

        OFF = ("gray85", "gray30")
        OFF_TEXT = ("gray30", "gray70")
        DEFAULTS = {"svc": "", "fur": "", "dur": 0, "amt": 0}

        def pick(group, value, color, toggle=True):
            if toggle and sel[group] == value:
                sel[group] = DEFAULTS[group]
                for b, v in btn_refs[group]:
                    b.configure(fg_color=OFF, text_color=OFF_TEXT)
                return
            sel[group] = value
            for b, v in btn_refs[group]:
                if v == value:
                    b.configure(fg_color=color, text_color="white")
                else:
                    b.configure(fg_color=OFF, text_color=OFF_TEXT)
            if group == "svc":
                for n, d, p in config.DEFAULT_SERVICES:
                    if n == value:
                        pick("dur", d, "#3B82F6", toggle=False)
                        pick("amt", p, "#F59E0B", toggle=False)
                        break

        def make_btns(parent, group, items, color, cols, h=34, font_size=15, display_fn=None):
            frame = ctk.CTkFrame(parent, fg_color="transparent")
            frame.pack(fill="x", pady=(2, 0))
            for i, val in enumerate(items):
                txt = display_fn(val) if display_fn else str(val)
                b = ctk.CTkButton(frame, text=txt, height=h, font=("", font_size),
                                   corner_radius=5, fg_color=OFF, text_color=OFF_TEXT,
                                   hover_color=color, border_width=0,
                                   command=lambda v=val, c=color: pick(group, v, c))
                row, col = divmod(i, cols)
                b.grid(row=row, column=col, sticky="ew", padx=1, pady=1)
                btn_refs[group].append((b, val))
            for c in range(cols):
                frame.columnconfigure(c, weight=1)
            return frame

        form = ctk.CTkToplevel(self)
        d = self._selected_date
        form.title(f"예약 {d.month}/{d.day} {time_str}")
        form.geometry("620x640")
        form.resizable(False, False)
        form.grab_set()
        form.attributes("-topmost", True)

        hdr = ctk.CTkFrame(form, fg_color=BOOKING_BG, corner_radius=0, height=46)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text=f" {d.month}/{d.day} {time_str}  {customer.pet_name}({customer.breed})",
                     font=("", 15, "bold"), text_color="white").pack(side="left", padx=10)

        body = ctk.CTkFrame(form, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=12, pady=8)

        # ── 이전 미용 내역 (토글 아코디언) ──
        prev_reservations = [
            r for r in queries.get_customer_reservations(self._db, customer.id)
            if r.status == "completed" and r.service_type
        ]
        seen = set()
        unique_prev = []
        for r in prev_reservations:
            key = (r.service_type, r.fur_length or "", r.amount)
            if key not in seen:
                seen.add(key)
                unique_prev.append(r)
            if len(unique_prev) >= 5:
                break

        if unique_prev:
            prev_list_frame = ctk.CTkFrame(body, fg_color="transparent")
            prev_expanded = [False]

            def toggle_prev():
                prev_expanded[0] = not prev_expanded[0]
                if prev_expanded[0]:
                    toggle_btn.configure(text="이전 미용  ▲")
                    prev_list_frame.pack(fill="x", pady=(2, 6), after=toggle_btn)
                else:
                    toggle_btn.configure(text="이전 미용  ▼")
                    prev_list_frame.pack_forget()

            toggle_btn = ctk.CTkButton(body, text="이전 미용  ▼", height=30,
                                        font=("", 14, "bold"), corner_radius=5,
                                        fg_color=("#E0E7FF", "#312E81"),
                                        text_color=("#4338CA", "#A5B4FC"),
                                        hover_color=("#C7D2FE", "#3730A3"),
                                        border_width=1, border_color=("#818CF8", "#4338CA"),
                                        command=toggle_prev)
            toggle_btn.pack(fill="x", pady=(0, 4))

            for i, pr in enumerate(unique_prev):
                fur_txt = f" / {pr.fur_length}" if pr.fur_length else ""
                amt_txt = f"{pr.amount // 10000}만원" if pr.amount >= 10000 and pr.amount % 10000 == 0 else f"{pr.amount // 1000}천원" if pr.amount >= 1000 else f"{pr.amount}원"
                label = f"{pr.service_type}{fur_txt} / {pr.duration}분 / {amt_txt}"
                def on_prev_click(r=pr):
                    pick("svc", r.service_type, "#4F46E5", toggle=False)
                    if r.fur_length:
                        pick("fur", r.fur_length, "#8B5CF6", toggle=False)
                    pick("dur", r.duration, "#3B82F6", toggle=False)
                    pick("amt", r.amount, "#F59E0B", toggle=False)
                    prev_expanded[0] = False
                    toggle_btn.configure(text="이전 미용  ▼")
                    prev_list_frame.pack_forget()
                b = ctk.CTkButton(prev_list_frame, text=label, height=30, font=("", 13),
                                   corner_radius=4, fg_color=("gray95", "#1E1B4B"),
                                   text_color=("#4338CA", "#C7D2FE"),
                                   hover_color=("#C7D2FE", "#3730A3"),
                                   anchor="w", command=on_prev_click)
                b.pack(fill="x", pady=1)

        ctk.CTkLabel(body, text="미용 종류", font=("", 15, "bold")).pack(anchor="w")
        svc_names = [s[0] for s in config.DEFAULT_SERVICES]
        make_btns(body, "svc", svc_names, "#4F46E5", cols=len(svc_names), h=36, font_size=15)

        ctk.CTkLabel(body, text="털 길이", font=("", 15, "bold")).pack(anchor="w", pady=(8, 0))
        make_btns(body, "fur", config.FUR_LENGTHS, "#8B5CF6", cols=len(config.FUR_LENGTHS), h=32)

        ctk.CTkLabel(body, text="소요시간", font=("", 15, "bold")).pack(anchor="w", pady=(8, 0))
        durations = [30, 60, 90, 120, 150, 180, 210, 240]
        def _dur_label(v):
            h, m = divmod(v, 60)
            if h == 0: return f"{m}분"
            if m == 0: return f"{h}시간"
            return f"{h}시간\n{m}분"
        make_btns(body, "dur", durations, "#3B82F6", cols=8, h=44, font_size=13,
                  display_fn=_dur_label)

        ctk.CTkLabel(body, text="예상 금액", font=("", 15, "bold")).pack(anchor="w", pady=(8, 0))
        amounts = [5000, 7000, 10000, 15000, 20000, 25000, 30000, 35000,
                   40000, 45000, 50000, 60000, 70000, 80000, 90000, 100000]
        make_btns(body, "amt", amounts, "#F59E0B", cols=8, h=34, font_size=15,
                  display_fn=lambda v: f"{v//10000}만" if v >= 10000 and v % 10000 == 0 else f"{v//1000}천")

        ctk.CTkLabel(body, text="메모", font=("", 15, "bold"),
                     text_color=LABEL_COLOR).pack(anchor="w", pady=(8, 0))
        memo_box = ctk.CTkTextbox(body, height=44, font=("", 15), border_width=1,
                              border_color=("gray75", "gray30"), corner_radius=5)
        memo_box.pack(fill="x", pady=(2, 8))
        memo_box.bind("<Tab>", lambda e: (e.widget.tk_focusNext().focus_set(), "break")[-1])

        ctk.CTkButton(body, text="예약 확정", height=40, font=("", 15, "bold"),
                       corner_radius=8, fg_color="#22C55E", hover_color="#16A34A",
                       command=lambda: self._save_bk(form, customer, time_str, sel,
                                                      memo_box.get("1.0", "end-1c"))
                       ).pack(fill="x")

        form.update_idletasks()
        fw, fh = form.winfo_width(), form.winfo_height()
        sx, sy = form.winfo_screenwidth(), form.winfo_screenheight()
        form.geometry(f"+{(sx-fw)//2}+{(sy-fh)//2 - 30}")

    def _save_bk(self, form, cust, ts, sel, memo_text):
        memo = memo_text.strip()
        data = {"customer_id": cust.id, "date": self._selected_date.strftime("%Y-%m-%d"),
                "time": ts, "service_type": sel.get("svc", ""),
                "duration": sel.get("dur", 60),
                "request": memo,
                "amount": sel.get("amt", 0),
                "fur_length": sel.get("fur", "")}
        if hasattr(self._parent, "_on_popup_reservation_saved"):
            self._parent._on_popup_reservation_saved(data)
        form.destroy()
        self._exit_booking_mode()
        self._on_date_selected(self._selected_date)
        self._calendar.refresh()

    def _on_reservation_click(self, r):
        sel = {"svc": r.service_type, "fur": r.fur_length or "",
               "dur": r.duration, "amt": r.amount}
        btn_refs = {"svc": [], "fur": [], "dur": [], "amt": []}

        OFF = ("gray85", "gray30")
        OFF_TEXT = ("gray30", "gray70")
        DEFAULTS = {"svc": "", "fur": "", "dur": 0, "amt": 0}

        def pick(group, value, color, toggle=True):
            if toggle and sel[group] == value:
                sel[group] = DEFAULTS[group]
                for b, v in btn_refs[group]:
                    b.configure(fg_color=OFF, text_color=OFF_TEXT)
                return
            sel[group] = value
            for b, v in btn_refs[group]:
                if v == value:
                    b.configure(fg_color=color, text_color="white")
                else:
                    b.configure(fg_color=OFF, text_color=OFF_TEXT)

        def make_btns(parent, group, items, color, cols, h=34, font_size=15, display_fn=None):
            frame = ctk.CTkFrame(parent, fg_color="transparent")
            frame.pack(fill="x", pady=(2, 0))
            for i, val in enumerate(items):
                txt = display_fn(val) if display_fn else str(val)
                b = ctk.CTkButton(frame, text=txt, height=h, font=("", font_size),
                                   corner_radius=5, fg_color=OFF, text_color=OFF_TEXT,
                                   hover_color=color, border_width=0,
                                   command=lambda v=val, c=color: pick(group, v, c))
                row, col_ = divmod(i, cols)
                b.grid(row=row, column=col_, sticky="ew", padx=1, pady=1)
                btn_refs[group].append((b, val))
            for c_ in range(cols):
                frame.columnconfigure(c_, weight=1)

        popup = ctk.CTkToplevel(self)
        popup.title("예약 상세")
        popup.geometry("620x700")
        popup.resizable(False, False)
        popup.grab_set()
        popup.attributes("-topmost", True)

        pet_info = f"{r.pet_name}({r.breed})" if r.breed else r.pet_name
        hdr = ctk.CTkFrame(popup, fg_color=ACCENT, corner_radius=0, height=46)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text=f" {r.date} {r.time}  {pet_info}",
                     font=("", 15, "bold"), text_color="white").pack(side="left", padx=10)
        ctk.CTkButton(hdr, text="예약변경", height=34, width=90, font=("", 15, "bold"),
                       corner_radius=4, fg_color="#F59E0B", hover_color="#D97706",
                       command=lambda: self._start_move_mode(r, popup)
                       ).pack(side="right", padx=10)

        body = ctk.CTkFrame(popup, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=12, pady=6)

        ctk.CTkLabel(body, text="미용 종류", font=("", 15, "bold")).pack(anchor="w")
        svc_names = [s[0] for s in config.DEFAULT_SERVICES]
        make_btns(body, "svc", svc_names, "#4F46E5", cols=len(svc_names), h=34, font_size=15)

        ctk.CTkLabel(body, text="털 길이", font=("", 15, "bold")).pack(anchor="w", pady=(6, 0))
        make_btns(body, "fur", config.FUR_LENGTHS, "#8B5CF6", cols=len(config.FUR_LENGTHS))

        ctk.CTkLabel(body, text="소요시간", font=("", 15, "bold")).pack(anchor="w", pady=(6, 0))
        durations = [30, 60, 90, 120, 150, 180, 210, 240]
        def _dur_label2(v):
            h, m = divmod(v, 60)
            if h == 0: return f"{m}분"
            if m == 0: return f"{h}시간"
            return f"{h}시간\n{m}분"
        make_btns(body, "dur", durations, "#3B82F6", cols=8, h=44, font_size=13,
                  display_fn=_dur_label2)

        ctk.CTkLabel(body, text="확정 금액", font=("", 15, "bold")).pack(anchor="w", pady=(6, 0))
        amounts = [5000, 7000, 10000, 15000, 20000, 25000, 30000, 35000,
                   40000, 45000, 50000, 60000, 70000, 80000, 90000, 100000]
        make_btns(body, "amt", amounts, "#F59E0B", cols=8,
                  display_fn=lambda v: f"{v//10000}만" if v >= 10000 and v % 10000 == 0 else f"{v//1000}천")

        if sel["svc"]:
            pick("svc", sel["svc"], "#4F46E5", toggle=False)
        if sel["fur"]:
            pick("fur", sel["fur"], "#8B5CF6", toggle=False)
        if sel["dur"]:
            pick("dur", sel["dur"], "#3B82F6", toggle=False)
        if sel["amt"]:
            pick("amt", sel["amt"], "#F59E0B", toggle=False)

        ctk.CTkLabel(body, text="메모", font=("", 15, "bold"),
                     text_color=LABEL_COLOR).pack(anchor="w", pady=(6, 0))
        memo_text = ctk.CTkTextbox(body, height=44, font=("", 15), border_width=1,
                                    border_color=("gray80", "gray30"), corner_radius=4)
        memo_text.pack(fill="x", pady=(2, 0))
        combined = ""
        if r.request and r.groomer_memo and r.request != r.groomer_memo:
            combined = f"{r.request}\n{r.groomer_memo}"
        elif r.groomer_memo:
            combined = r.groomer_memo
        elif r.request:
            combined = r.request
        if combined:
            memo_text.insert("1.0", combined)
        memo_text.bind("<Tab>", lambda e: (e.widget.tk_focusNext().focus_set(), "break")[-1])

        def save_all():
            memo = memo_text.get("1.0", "end-1c").strip()
            queries.update_reservation_with_history(
                self._db, r.id,
                service_type=sel["svc"], fur_length=sel["fur"],
                duration=sel["dur"], amount=sel["amt"],
                request=memo,
            )
            queries.update_reservation_memo(self._db, r.id, memo)
            save_btn.configure(text="저장됨", fg_color="#22C55E")
            self._on_date_selected(self._selected_date)
            self._calendar.refresh()
            self.after(1000, lambda: popup.destroy() if popup.winfo_exists() else None)

        save_btn = ctk.CTkButton(body, text="수정 저장", height=40, font=("", 15, "bold"),
                                  corner_radius=6, fg_color=ACCENT, hover_color="#4338CA",
                                  command=save_all)
        save_btn.pack(fill="x", pady=(8, 4))

        btn_row = ctk.CTkFrame(body, fg_color="transparent")
        btn_row.pack(fill="x")
        for a, t, c, hc in [("completed", "미용 완료", "#22C55E", "#16A34A"),
                             ("cancelled", "예약 취소", "#EF4444", "#DC2626"),
                             ("no_show", "노쇼", "#F59E0B", "#D97706")]:
            ctk.CTkButton(btn_row, text=t, height=38, font=("", 15),
                           corner_radius=5, fg_color=c, hover_color=hc,
                           command=lambda x=a, p=popup, mt=memo_text: self._act(r.id, x, p, mt)
                           ).pack(side="left", fill="x", expand=True, padx=1)

        popup.update_idletasks()
        pw, ph = popup.winfo_width(), popup.winfo_height()
        sx, sy = popup.winfo_screenwidth(), popup.winfo_screenheight()
        popup.geometry(f"+{(sx-pw)//2}+{(sy-ph)//2 - 30}")

    def _act(self, rid, action, popup, memo_text=None):
        if action in ("cancelled", "no_show"):
            labels = {"cancelled": "예약 취소", "no_show": "노쇼 처리"}
            self._confirm_dialog(
                title=labels[action],
                message=f"정말 {labels[action]}하시겠습니까?",
                on_confirm=lambda: self._do_act(rid, action, popup, memo_text),
            )
        else:
            self._do_act(rid, action, popup, memo_text)

    def _do_act(self, rid, action, popup, memo_text=None):
        if memo_text:
            try:
                memo = memo_text.get("1.0", "end-1c").strip()
                if memo:
                    queries.update_reservation_memo(self._db, rid, memo)
            except Exception:
                pass
        if action == "cancelled":
            queries.delete_reservation(self._db, rid)
        else:
            queries.update_reservation_status(self._db, rid, action)
        popup.destroy()
        self._on_date_selected(self._selected_date)
        self._calendar.refresh()

    def _confirm_dialog(self, title, message, on_confirm):
        dlg = ctk.CTkToplevel(self)
        dlg.title(title)
        dlg.geometry("400x200")
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.attributes("-topmost", True)

        ctk.CTkLabel(dlg, text=title, font=("", 15, "bold")).pack(pady=(18, 4))
        ctk.CTkLabel(dlg, text=message, font=("", 15),
                     text_color=LABEL_COLOR).pack(pady=(0, 12))

        bf = ctk.CTkFrame(dlg, fg_color="transparent")
        bf.pack()
        ctk.CTkButton(bf, text="확인", width=110, height=38, font=("", 15, "bold"),
                       corner_radius=6, fg_color="#EF4444", hover_color="#DC2626",
                       command=lambda: (dlg.destroy(), on_confirm())
                       ).pack(side="left", padx=4)
        ctk.CTkButton(bf, text="취소", width=110, height=38, font=("", 15),
                       corner_radius=6, fg_color=("gray70", "gray35"),
                       command=dlg.destroy).pack(side="left", padx=4)

        dlg.update_idletasks()
        sx, sy = dlg.winfo_screenwidth(), dlg.winfo_screenheight()
        dlg.geometry(f"+{(sx-400)//2}+{(sy-200)//2 - 30}")

    def _refresh_all(self):
        self._calendar.refresh()
        self._on_date_selected(self._selected_date)

    def refresh_reservations(self):
        self._refresh_all()

    def _on_search_customer(self):
        if hasattr(self._parent, "show_customer_search"): self._parent.show_customer_search()
    def _on_manual_reservation(self):
        if hasattr(self._parent, "show_customer_search_for_reservation"): self._parent.show_customer_search_for_reservation()
    def _on_new_customer(self):
        if hasattr(self._parent, "show_new_customer_form"): self._parent.show_new_customer_form()

    # ===== 전화수신 히스토리 =====
    def _call_hist_prev_day(self):
        from datetime import timedelta
        self._call_hist_date -= timedelta(days=1)
        self._render_call_history()

    def _call_hist_next_day(self):
        from datetime import timedelta
        self._call_hist_date += timedelta(days=1)
        self._render_call_history()

    def _render_call_history(self):
        d = self._call_hist_date
        wd = ["월", "화", "수", "목", "금", "토", "일"][d.weekday()]
        if d == date.today():
            self._call_hist_date_label.configure(text=f"수신기록 오늘 {d.month}/{d.day}({wd})")
        else:
            self._call_hist_date_label.configure(text=f"수신기록 {d.month}/{d.day}({wd})")

        for w in self._call_hist_scroll.winfo_children():
            w.destroy()

        rows = queries.get_call_history_by_date(self._db, d.strftime("%Y-%m-%d"))

        if not rows:
            ctk.CTkLabel(self._call_hist_scroll, text="수신 기록 없음",
                         font=("", 15), text_color=LABEL_COLOR).pack(pady=8)
            return

        for row in rows:
            phone = row.get("phone", "")
            short_phone = format_phone_display(phone)[-9:]

            created = row.get("created_at", "")
            time_str = ""
            if created:
                try:
                    dt = datetime.strptime(created, "%Y-%m-%d %H:%M:%S")
                    time_str = dt.strftime("%H:%M")
                except ValueError:
                    time_str = created[-8:-3] if len(created) >= 8 else ""

            pet = row.get("c_pet_name") or row.get("pet_name") or ""
            breed = row.get("breed", "")
            if pet:
                info = f"{pet}({breed})" if breed else pet
                line1 = f"{time_str} {info}"
                txt_color = ("#1E40AF", "#93C5FD")
            else:
                line1 = f"{time_str} 신규"
                txt_color = ("#DC2626", "#FCA5A5")

            label = f"{line1}\n{short_phone}"
            ctk.CTkButton(
                self._call_hist_scroll, text=label, anchor="w",
                height=42, font=("", 15), corner_radius=3,
                fg_color=("gray95", "gray20"), text_color=txt_color,
                hover_color=("gray88", "gray28"),
                command=lambda p=phone: self._on_call_hist_click(p)
            ).pack(fill="x", pady=1)

    def _on_call_hist_click(self, phone: str):
        customer = queries.find_customer_by_phone(self._db, phone)
        last_visit = None
        if customer:
            last_visit = queries.get_last_visit_date(self._db, customer.id)
        self.show_call_popup(phone, customer, last_visit)

    def refresh_call_history(self):
        self._call_hist_date = date.today()
        self._render_call_history()

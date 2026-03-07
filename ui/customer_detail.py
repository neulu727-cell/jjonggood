"""재방문 고객 상세 정보 화면"""

import customtkinter as ctk
from database.db_manager import DatabaseManager
from database.models import Customer, Reservation
from database import queries
from utils.phone_formatter import format_phone_display
from utils.date_utils import days_since, format_date_korean
from typing import List, Optional

ACCENT = "#4F46E5"
LABEL_COLOR = ("#64748B", "#94A3B8")

STATUS_DOT = {
    "confirmed": "#4F46E5",
    "completed": "#22C55E",
    "cancelled": "#EF4444",
    "no_show": "#F59E0B",
}
STATUS_TEXT = {
    "confirmed": "예약",
    "completed": "완료",
    "cancelled": "취소",
    "no_show": "노쇼",
}


class CustomerDetail(ctk.CTkToplevel):
    """기존 고객 정보 + 방문 이력을 보여주는 팝업"""

    def __init__(self, parent, customer: Customer, reservations: List[Reservation],
                 last_visit: Optional[str] = None, on_new_reservation=None,
                 on_update_memo=None, on_delete_customer=None, db=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.title(f"고객 정보 - {customer.name}")
        self.geometry("640x780")
        self.resizable(False, True)
        self.grab_set()

        self._customer = customer
        self._reservations = reservations
        self._last_visit = last_visit
        self._on_new_reservation = on_new_reservation
        self._on_update_memo = on_update_memo
        self._on_delete_customer = on_delete_customer
        self._db = db

        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.pack(fill="both", expand=True)
        self._build_ui()

    def _build_ui(self):
        c = self._customer
        container = self._scroll

        # ===== 고객 프로필 카드 =====
        profile = ctk.CTkFrame(container, corner_radius=14, fg_color=("#FFFFFF", "#1E293B"),
                                border_width=1, border_color=("gray85", "gray25"))
        profile.pack(fill="x", padx=20, pady=(20, 10))

        name_row = ctk.CTkFrame(profile, fg_color="transparent")
        name_row.pack(fill="x", padx=20, pady=(18, 0))

        ctk.CTkLabel(
            name_row, text=c.name, font=("", 24, "bold")
        ).pack(side="left")

        ctk.CTkLabel(
            name_row, text=format_phone_display(c.phone),
            font=("", 18), text_color=LABEL_COLOR
        ).pack(side="right")

        tag_row = ctk.CTkFrame(profile, fg_color="transparent")
        tag_row.pack(fill="x", padx=20, pady=(8, 0))

        tags = [c.pet_name, c.breed]
        if c.weight:
            tags.append(f"{c.weight}kg")
        if c.age:
            tags.append(c.age)

        for tag_text in tags:
            ctk.CTkLabel(
                tag_row, text=tag_text, font=("", 18),
                fg_color=("#F1F5F9", "#334155"), text_color=("gray30", "gray70"),
                corner_radius=6, height=28
            ).pack(side="left", padx=(0, 6))

        if self._last_visit:
            days = days_since(self._last_visit)
            ctk.CTkLabel(
                profile, text=f"마지막 방문: {format_date_korean(self._last_visit)} ({days}일 전)",
                font=("", 18), text_color=("#D97706", "#FBBF24")
            ).pack(anchor="w", padx=20, pady=(10, 0))

        if c.notes:
            notes_frame = ctk.CTkFrame(profile, fg_color=("#FEF2F2", "#451A1A"), corner_radius=8)
            notes_frame.pack(fill="x", padx=20, pady=(10, 0))
            ctk.CTkLabel(
                notes_frame, text=f"메모: {c.notes}",
                font=("", 18), text_color=("#DC2626", "#FCA5A5"), wraplength=520, anchor="w"
            ).pack(padx=10, pady=8)

        ctk.CTkFrame(profile, height=15, fg_color="transparent").pack()

        # ===== 매출 통계 =====
        if self._db:
            stats = queries.get_customer_sales_stats(self._db, c.id)
            if stats["count"] > 0:
                self._section_header(container, "매출 통계")
                stats_card = ctk.CTkFrame(container, corner_radius=12, border_width=1,
                                           border_color=("gray85", "gray25"),
                                           fg_color=("#FFFFFF", "#1E293B"))
                stats_card.pack(fill="x", padx=20, pady=(0, 10))

                stats_inner = ctk.CTkFrame(stats_card, fg_color="transparent")
                stats_inner.pack(fill="x", padx=16, pady=14)

                for i in range(3):
                    stats_inner.columnconfigure(i, weight=1)

                # 헤더
                for i, header_text in enumerate(["횟수", "총액", "평균"]):
                    ctk.CTkLabel(
                        stats_inner, text=header_text, font=("", 18),
                        text_color=LABEL_COLOR
                    ).grid(row=0, column=i, sticky="ew", pady=(0, 4))

                # 값
                values = [
                    f"{stats['count']}건",
                    f"{stats['total']:,}원",
                    f"{stats['avg']:,}원",
                ]
                for i, val_text in enumerate(values):
                    ctk.CTkLabel(
                        stats_inner, text=val_text, font=("", 18, "bold"),
                        text_color=("#1E293B", "#F1F5F9")
                    ).grid(row=1, column=i, sticky="ew")

        # ===== 미용사 메모 =====
        self._section_header(container, "미용사 메모")
        memo_card = ctk.CTkFrame(container, corner_radius=12, border_width=1,
                                  border_color=("gray85", "gray25"))
        memo_card.pack(fill="x", padx=20, pady=(0, 10))

        self._memo_text = ctk.CTkTextbox(memo_card, height=70, font=("", 18),
                                          fg_color="transparent", border_width=0)
        self._memo_text.pack(fill="x", padx=10, pady=(10, 5))
        self._memo_text.bind("<Tab>", lambda e: (e.widget.tk_focusNext().focus_set(), "break")[-1])
        if c.memo:
            self._memo_text.insert("1.0", c.memo)

        ctk.CTkButton(
            memo_card, text="메모 저장", width=100, height=34, font=("", 18),
            corner_radius=8, fg_color=ACCENT, hover_color="#4338CA",
            command=self._save_memo
        ).pack(anchor="e", padx=10, pady=(0, 10))

        # ===== 방문 이력 =====
        self._section_header(container, f"방문 이력 ({len(self._reservations)}건)")

        if self._reservations:
            for r in self._reservations:
                self._build_history_row(container, r)
        else:
            empty = ctk.CTkFrame(container, corner_radius=12, border_width=1,
                                  border_color=("gray85", "gray25"))
            empty.pack(fill="x", padx=20, pady=2)
            ctk.CTkLabel(
                empty, text="방문 이력이 없습니다",
                font=("", 18), text_color=LABEL_COLOR
            ).pack(pady=25)

        # ===== 미용사 메모 기록 =====
        if self._db:
            memo_history = queries.get_customer_groomer_memos(self._db, c.id)
            if memo_history:
                self._section_header(container, f"미용사 메모 기록 ({len(memo_history)}건)")
                memo_scroll = ctk.CTkScrollableFrame(container, height=140,
                                                      corner_radius=12, border_width=1,
                                                      border_color=("gray85", "gray25"))
                memo_scroll.pack(fill="x", padx=20, pady=(0, 5))
                self._build_memo_history(memo_scroll, memo_history)

        # ===== 하단 버튼 =====
        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(15, 25))

        ctk.CTkButton(
            btn_frame, text="새 예약 등록", width=190, height=46,
            font=("", 18, "bold"), corner_radius=10,
            fg_color="#22C55E", hover_color="#16A34A",
            command=self._on_new_reservation_click
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            btn_frame, text="닫기", width=110, height=46,
            font=("", 18), corner_radius=10,
            fg_color=("gray70", "gray35"), hover_color=("gray60", "gray45"),
            command=self.destroy
        ).pack(side="left")

        ctk.CTkButton(
            btn_frame, text="고객 삭제", width=110, height=46,
            font=("", 18), corner_radius=10,
            fg_color="#EF4444", hover_color="#DC2626",
            command=self._on_delete_click
        ).pack(side="right")

    def _section_header(self, parent, text):
        ctk.CTkLabel(
            parent, text=text, font=("", 18, "bold"), text_color=ACCENT
        ).pack(anchor="w", padx=24, pady=(15, 5))

    def _build_history_row(self, parent, r: Reservation):
        row = ctk.CTkFrame(parent, corner_radius=10, border_width=1,
                            border_color=("gray85", "gray25"),
                            fg_color=("#FFFFFF", "#1E293B"))
        row.pack(fill="x", padx=20, pady=2)

        inner = ctk.CTkFrame(row, fg_color="transparent")
        inner.pack(fill="x", padx=12, pady=10)

        dot_color = STATUS_DOT.get(r.status, "#94A3B8")
        ctk.CTkLabel(inner, text="●", font=("", 18), text_color=dot_color,
                     width=16).pack(side="left")

        ctk.CTkLabel(
            inner, text=f"{r.date}  {r.time}", font=("", 18, "bold"), anchor="w"
        ).pack(side="left", padx=(4, 10))

        ctk.CTkLabel(
            inner, text=r.service_type, font=("", 18), text_color=LABEL_COLOR, anchor="w"
        ).pack(side="left")

        if r.amount:
            ctk.CTkLabel(
                inner, text=f"{r.amount:,}원", font=("", 18, "bold"),
                text_color=("gray30", "gray70")
            ).pack(side="right")

        status_text = STATUS_TEXT.get(r.status, r.status)
        ctk.CTkLabel(
            inner, text=status_text, font=("", 18),
            text_color=dot_color
        ).pack(side="right", padx=(0, 10))

        # 완료 시간 표시
        if r.status == "completed" and getattr(r, "completed_at", None):
            ctk.CTkLabel(
                row, text=f"  완료: {r.completed_at}", font=("", 18),
                text_color=("#16A34A", "#86EFAC"), anchor="w"
            ).pack(fill="x", padx=12, pady=(0, 6))

    def _build_memo_history(self, parent, memo_history):
        grouped = {}
        for m in memo_history:
            key = f"{m.get('date', '')}|{m.get('time', '')}|{m.get('service_type', '')}"
            if key not in grouped:
                grouped[key] = {"date": m.get("date", ""), "time": m.get("time", ""),
                                "service_type": m.get("service_type", ""), "entries": []}
            grouped[key]["entries"].append(m)

        for key, g in grouped.items():
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x", pady=2)
            visit = f"{g['date']}  {g['time']}  {g['service_type']}"
            ctk.CTkLabel(row, text=visit, font=("", 18, "bold"),
                         text_color=ACCENT).pack(anchor="w")
            entries = g["entries"]
            if len(entries) == 1:
                text = entries[0].get("content", "")
            else:
                text = " / ".join(e.get("content", "") for e in entries)
            ctk.CTkLabel(row, text=text, font=("", 18),
                         text_color=("gray20", "gray80"),
                         wraplength=520, anchor="w", justify="left").pack(anchor="w", padx=(4, 0))
            ctk.CTkFrame(row, height=1, fg_color=("gray90", "gray25")).pack(fill="x", pady=(3, 0))

    def _save_memo(self):
        memo = self._memo_text.get("1.0", "end-1c").strip()
        if self._on_update_memo:
            self._on_update_memo(self._customer.id, memo)

    def _on_new_reservation_click(self):
        if self._on_new_reservation:
            self._on_new_reservation(self._customer)
        self.destroy()

    def _on_delete_click(self):
        c = self._customer
        dialog = ctk.CTkToplevel(self)
        dialog.title("고객 삭제")
        dialog.geometry("460x250")
        dialog.resizable(False, False)
        dialog.grab_set()
        dialog.attributes("-topmost", True)

        ctk.CTkLabel(
            dialog, text="정말 삭제하시겠습니까?",
            font=("", 18, "bold"), text_color="#EF4444"
        ).pack(pady=(25, 5))

        ctk.CTkLabel(
            dialog, text=f"{c.pet_name} ({c.breed}) - {len(self._reservations)}건의 예약도 함께 삭제됩니다",
            font=("", 18), text_color=("gray50", "gray55"), wraplength=320
        ).pack(pady=(0, 20))

        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack()

        ctk.CTkButton(
            btn_row, text="삭제", width=130, height=42,
            font=("", 18, "bold"), corner_radius=10,
            fg_color="#EF4444", hover_color="#DC2626",
            command=lambda: self._confirm_delete(dialog)
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_row, text="취소", width=130, height=42,
            font=("", 18), corner_radius=10,
            fg_color=("gray70", "gray35"),
            command=dialog.destroy
        ).pack(side="left", padx=5)

    def _confirm_delete(self, dialog):
        dialog.destroy()
        if self._on_delete_customer:
            self._on_delete_customer(self._customer.id)
        self.destroy()

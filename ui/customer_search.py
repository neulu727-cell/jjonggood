"""고객 검색 다이얼로그"""

import customtkinter as ctk
from database.db_manager import DatabaseManager
from database import queries
from utils.phone_formatter import format_phone_display

ACCENT = "#4F46E5"
LABEL_COLOR = ("#64748B", "#94A3B8")


class CustomerSearch(ctk.CTkToplevel):
    """고객 이름/전화번호/반려동물 이름으로 검색하는 팝업"""

    def __init__(self, parent, db: DatabaseManager, on_select=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.title("고객 검색")
        self.geometry("580x580")
        self.resizable(False, True)
        self.grab_set()

        self._db = db
        self._on_select = on_select
        self._search_timer = None
        self._build_ui()
        self.after(100, self._safe_focus)

    def _safe_focus(self):
        try:
            if self.winfo_exists():
                self._search_entry.focus_set()
        except Exception:
            pass

    def _build_ui(self):
        search_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_frame.pack(fill="x", padx=20, pady=(20, 10))

        self._search_entry = ctk.CTkEntry(
            search_frame,
            placeholder_text="이름, 전화번호, 반려동물 이름으로 검색...",
            height=44, font=("", 18), corner_radius=10
        )
        self._search_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self._search_entry.bind("<Return>", lambda e: self._do_search())
        self._search_entry.bind("<KeyRelease>", lambda e: self._debounced_search())

        ctk.CTkButton(
            search_frame, text="검색", width=90, height=44,
            font=("", 18), corner_radius=10,
            fg_color=ACCENT, hover_color="#4338CA",
            command=self._do_search
        ).pack(side="left")

        self._result_count = ctk.CTkLabel(
            self, text="", font=("", 18), text_color=LABEL_COLOR
        )
        self._result_count.pack(anchor="w", padx=24, pady=(0, 5))

        self._result_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._result_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        self._do_search()

    def _debounced_search(self):
        if self._search_timer:
            self.after_cancel(self._search_timer)
        self._search_timer = self.after(250, self._do_search)

    def _do_search(self):
        keyword = self._search_entry.get().strip()

        for widget in self._result_frame.winfo_children():
            widget.destroy()

        if keyword:
            customers = queries.search_customers(self._db, keyword)
        else:
            customers = queries.get_all_customers(self._db)

        self._result_count.configure(text=f"  {len(customers)}명의 고객")

        if not customers:
            ctk.CTkLabel(
                self._result_frame, text="검색 결과가 없습니다",
                font=("", 18), text_color=LABEL_COLOR
            ).pack(pady=40)
            return

        for c in customers:
            row = ctk.CTkFrame(
                self._result_frame, corner_radius=10, border_width=1,
                border_color=("gray85", "gray25"),
                fg_color=("#FFFFFF", "#1E293B"), cursor="hand2"
            )
            row.pack(fill="x", pady=3)

            inner = ctk.CTkFrame(row, fg_color="transparent")
            inner.pack(fill="x", padx=12, pady=10)

            ctk.CTkLabel(
                inner, text=c.name, font=("", 18, "bold"), anchor="w"
            ).pack(side="left")

            ctk.CTkLabel(
                inner, text=format_phone_display(c.phone),
                font=("", 18), text_color=LABEL_COLOR
            ).pack(side="left", padx=(12, 0))

            ctk.CTkLabel(
                inner, text=f"{c.pet_name} ({c.breed})",
                font=("", 18), text_color=LABEL_COLOR
            ).pack(side="right")

            for widget in [row, inner] + list(inner.winfo_children()):
                widget.bind("<Button-1>", lambda *_, cust=c: self._select(cust))

    def _select(self, customer):
        if self._on_select:
            self._on_select(customer)
        self.destroy()

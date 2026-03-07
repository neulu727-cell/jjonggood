"""신규 고객 등록 폼 - 간결한 1단 레이아웃"""

import customtkinter as ctk
from utils.phone_formatter import format_phone_display, normalize_phone
from ui.widgets.autocomplete_combo import AutocompleteCombo
import config

ACCENT = "#4F46E5"
ACCENT_HOVER = "#4338CA"
LABEL_COLOR = ("#64748B", "#94A3B8")
REQUIRED_COLOR = "#EF4444"


class CustomerForm(ctk.CTkToplevel):
    """신규 고객 등록 - 이름/견종/몸무게/나이만 빠르게"""

    def __init__(self, parent, phone: str = "", on_save=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.title("신규 고객 등록")
        self.geometry("480x460")
        self.resizable(False, False)
        self.grab_set()
        self.attributes("-topmost", True)

        self._phone = phone
        self._on_save = on_save
        self._build_ui()
        self.after(100, lambda: self._pet_name_entry.focus_set())

        # 중앙 배치
        self.update_idletasks()
        pw, ph = self.winfo_width(), self.winfo_height()
        sx, sy = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"+{(sx-pw)//2}+{(sy-ph)//2 - 30}")

    def _build_ui(self):
        # 헤더
        header = ctk.CTkFrame(self, fg_color=ACCENT, corner_radius=0, height=48)
        header.pack(fill="x")
        header.pack_propagate(False)

        title = "신규 고객 등록"
        if self._phone:
            title += f"   {format_phone_display(self._phone)}"
        ctk.CTkLabel(header, text=title, font=("", 18, "bold"),
                     text_color="white").pack(side="left", padx=16)

        # 본문
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=12)

        card = ctk.CTkFrame(body, corner_radius=12, border_width=1,
                             border_color=("gray85", "gray25"))
        card.pack(fill="both", expand=True)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=16, pady=12)

        # 전화번호 (수동 등록 시)
        if not self._phone:
            self._phone_entry = self._field(inner, "전화번호 *", "010-1234-5678")
        else:
            self._phone_entry = None

        # 이름
        self._pet_name_entry = self._field(inner, "이름 *", "반려동물 이름")

        # 견종
        ctk.CTkLabel(inner, text="견종 *", font=("", 18, "bold"),
                     text_color=("gray20", "gray80")).pack(anchor="w", pady=(8, 2))
        self._breed_combo = AutocompleteCombo(
            inner, values=config.COMMON_BREEDS,
            placeholder="예: 말티 → 말티즈, 말티푸...")
        self._breed_combo.pack(fill="x")

        # 몸무게 + 나이 (한 줄)
        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack(fill="x", pady=(10, 0))

        cl = ctk.CTkFrame(row, fg_color="transparent")
        cl.pack(side="left", fill="x", expand=True, padx=(0, 5))
        ctk.CTkLabel(cl, text="몸무게 (kg)", font=("", 18, "bold"),
                     text_color=("gray20", "gray80")).pack(anchor="w")
        self._weight_entry = ctk.CTkEntry(cl, height=38, font=("", 18),
                                           placeholder_text="예: 4.5")
        self._weight_entry.pack(fill="x", pady=(2, 0))

        cr = ctk.CTkFrame(row, fg_color="transparent")
        cr.pack(side="left", fill="x", expand=True, padx=(5, 0))
        ctk.CTkLabel(cr, text="나이", font=("", 18, "bold"),
                     text_color=("gray20", "gray80")).pack(anchor="w")
        self._age_entry = ctk.CTkEntry(cr, height=38, font=("", 18),
                                        placeholder_text="예: 5살")
        self._age_entry.pack(fill="x", pady=(2, 0))
        self._age_entry.bind("<Return>", lambda e: self._on_save_click())

        # 버튼
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(0, 14))

        ctk.CTkButton(btn_frame, text="등록", width=170, height=44,
                       font=("", 18, "bold"), corner_radius=8,
                       fg_color=ACCENT, hover_color=ACCENT_HOVER,
                       command=self._on_save_click).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_frame, text="취소", width=110, height=44,
                       font=("", 18), corner_radius=8,
                       fg_color=("gray70", "gray35"), hover_color=("gray60", "gray45"),
                       command=self.destroy).pack(side="left")

    def _field(self, parent, label, placeholder) -> ctk.CTkEntry:
        ctk.CTkLabel(parent, text=label, font=("", 18, "bold"),
                     text_color=("gray20", "gray80")).pack(anchor="w", pady=(8, 2))
        entry = ctk.CTkEntry(parent, height=38, font=("", 18),
                              placeholder_text=placeholder)
        entry.pack(fill="x")
        return entry

    def _on_save_click(self):
        pet_name = self._pet_name_entry.get().strip()
        breed = self._breed_combo.get().strip()

        if not pet_name:
            self._show_error("반려동물 이름을 입력해주세요.")
            return
        if not breed:
            self._show_error("견종을 입력해주세요.")
            return

        if self._phone_entry:
            phone = normalize_phone(self._phone_entry.get().strip())
            if not phone:
                self._show_error("전화번호를 입력해주세요.")
                return
        else:
            phone = self._phone

        weight_str = self._weight_entry.get().strip()
        try:
            weight = float(weight_str) if weight_str else None
        except ValueError:
            self._show_error("몸무게는 숫자로 입력해주세요.")
            return

        data = {
            "name": pet_name,
            "phone": phone,
            "pet_name": pet_name,
            "breed": breed,
            "weight": weight,
            "age": self._age_entry.get().strip() or None,
            "notes": "",
            "memo": "",
        }

        if self._on_save:
            self._on_save(data)
        self.destroy()

    def _show_error(self, message: str):
        dialog = ctk.CTkToplevel(self)
        dialog.title("입력 오류")
        dialog.geometry("400x170")
        dialog.resizable(False, False)
        dialog.grab_set()
        dialog.attributes("-topmost", True)
        ctk.CTkLabel(dialog, text="!", font=("", 24, "bold"),
                     text_color=REQUIRED_COLOR).pack(pady=(12, 4))
        ctk.CTkLabel(dialog, text=message, font=("", 18)).pack()
        ctk.CTkButton(dialog, text="확인", width=90, height=34,
                      corner_radius=8, command=dialog.destroy).pack(pady=8)

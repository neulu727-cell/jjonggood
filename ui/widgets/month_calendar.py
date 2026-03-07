"""월간 캘린더 위젯 - 예약자 이름 표시"""

import customtkinter as ctk
import calendar
from datetime import date

ACCENT = "#4F46E5"
TODAY_BG = ("#EEF2FF", "#312E81")
SELECTED_BG = (ACCENT, ACCENT)
NAME_BG = ("#E0E7FF", "#3730A3")
NAME_TEXT = ("#4338CA", "#C7D2FE")
MORE_TEXT = ("#6366F1", "#A5B4FC")

MAX_NAMES = 2  # 셀에 표시할 최대 이름 수


class MonthCalendar(ctk.CTkFrame):

    def __init__(self, parent, on_date_select=None,
                 get_counts_fn=None, get_names_fn=None, **kwargs):
        super().__init__(parent, corner_radius=8, border_width=1,
                         border_color=("gray85", "gray25"), **kwargs)

        self._on_date_select = on_date_select
        self._get_counts_fn = get_counts_fn
        self._get_names_fn = get_names_fn
        self._selected_date = date.today()
        self._current_year = date.today().year
        self._current_month = date.today().month
        self._cells = {}
        self._counts_cache = {}
        self._names_cache = {}

        self._build_header()
        self._grid_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._grid_frame.pack(fill="both", expand=True, padx=4, pady=(0, 4))
        self._render_month()

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=6, pady=(6, 2))

        ctk.CTkButton(
            header, text="<", width=34, height=32, font=("", 18, "bold"),
            fg_color="transparent", text_color=("gray30", "gray70"),
            hover_color=("gray90", "gray20"), corner_radius=4,
            command=self._prev_month
        ).pack(side="left")

        ctk.CTkButton(
            header, text="오늘", width=54, height=32, font=("", 18, "bold"),
            fg_color=ACCENT, hover_color="#4338CA", corner_radius=6,
            text_color="white", command=self._go_today
        ).pack(side="left", padx=(4, 0))

        self._month_label = ctk.CTkLabel(header, text="", font=("", 18, "bold"))
        self._month_label.pack(side="left", expand=True)

        ctk.CTkButton(
            header, text=">", width=34, height=32, font=("", 18, "bold"),
            fg_color="transparent", text_color=("gray30", "gray70"),
            hover_color=("gray90", "gray20"), corner_radius=4,
            command=self._next_month
        ).pack(side="right")

        # 요일 헤더
        days_frame = ctk.CTkFrame(self, fg_color="transparent")
        days_frame.pack(fill="x", padx=6, pady=(0, 1))
        for i, dn in enumerate(["월", "화", "수", "목", "금", "토", "일"]):
            c = "#EF4444" if i >= 5 else ("gray40", "gray60")
            ctk.CTkLabel(days_frame, text=dn, font=("", 18, "bold"),
                         text_color=c).grid(row=0, column=i, sticky="ew")
            days_frame.columnconfigure(i, weight=1)

    def _fetch_data(self):
        if self._get_counts_fn:
            self._counts_cache = self._get_counts_fn(self._current_year, self._current_month)
        else:
            self._counts_cache = {}
        if self._get_names_fn:
            self._names_cache = self._get_names_fn(self._current_year, self._current_month)
        else:
            self._names_cache = {}

    def _render_month(self):
        for w in self._grid_frame.winfo_children():
            w.destroy()
        self._cells = {}

        y, m = self._current_year, self._current_month
        self._month_label.configure(text=f"{y}년 {m}월")
        self._fetch_data()

        cal = calendar.monthcalendar(y, m)

        for col_i in range(7):
            self._grid_frame.columnconfigure(col_i, weight=1, uniform="cal")
        for row_i in range(len(cal)):
            self._grid_frame.rowconfigure(row_i, weight=1, uniform="calrow")

        for row_i, week in enumerate(cal):
            for col_i, day in enumerate(week):
                if day == 0:
                    continue

                d = date(y, m, day)
                date_str = d.strftime("%Y-%m-%d")
                count = self._counts_cache.get(date_str, 0)
                names = self._names_cache.get(date_str, [])

                cell = ctk.CTkFrame(self._grid_frame, fg_color="transparent",
                                     corner_radius=6, cursor="hand2")
                cell.grid(row=row_i, column=col_i, sticky="nsew", padx=1, pady=1)

                # 날짜 숫자
                day_lbl = ctk.CTkLabel(cell, text=str(day), font=("", 18, "bold"),
                                        text_color=("gray10", "gray90"),
                                        anchor="n", height=26)
                day_lbl.pack(fill="x")

                # 예약자 이름 표시 (최대 MAX_NAMES개)
                name_labels = []
                for entry in names[:MAX_NAMES]:
                    pet = entry.get("pet_name", "")
                    breed = entry.get("breed", "")
                    if breed:
                        txt = f"{pet}({breed})"
                    else:
                        txt = pet
                    # 글자수 제한 (셀 너비에 맞춤)
                    if len(txt) > 7:
                        txt = txt[:6] + ".."

                    nlbl = ctk.CTkLabel(cell, text=txt, font=("", 18),
                                         fg_color=NAME_BG, text_color=NAME_TEXT,
                                         corner_radius=3, height=26, anchor="center")
                    nlbl.pack(fill="x", padx=1, pady=(0, 1))
                    nlbl.bind("<Button-1>", lambda *_, dt=d: self._select_date(dt))
                    name_labels.append(nlbl)

                # 초과 건수 표시
                more_lbl = None
                if count > MAX_NAMES:
                    more_lbl = ctk.CTkLabel(cell, text=f"+{count - MAX_NAMES}",
                                             font=("", 18, "bold"),
                                             text_color=MORE_TEXT, height=22)
                    more_lbl.pack(fill="x")
                    more_lbl.bind("<Button-1>", lambda *_, dt=d: self._select_date(dt))

                # 클릭 바인딩
                for w in [cell, day_lbl]:
                    w.bind("<Button-1>", lambda *_, dt=d: self._select_date(dt))

                self._cells[d] = {
                    "cell": cell, "day_lbl": day_lbl,
                    "name_labels": name_labels, "more_lbl": more_lbl,
                    "col": col_i, "count": count,
                }

        self._apply_all_styles()

    def _apply_all_styles(self):
        today = date.today()
        for d, info in self._cells.items():
            self._style(d, info, today)

    def _style(self, d, info, today=None):
        if today is None:
            today = date.today()

        is_sel = (d == self._selected_date)
        is_today = (d == today)
        col = info["col"]

        if is_sel:
            bg = SELECTED_BG
            tc = "white"
            name_bg = ("#6366F1", "#4338CA")
            name_tc = "white"
            more_tc = ("#E0E7FF", "#C7D2FE")
        elif is_today:
            bg = TODAY_BG
            tc = (ACCENT, "#C7D2FE")
            name_bg = NAME_BG
            name_tc = NAME_TEXT
            more_tc = MORE_TEXT
        else:
            bg = "transparent"
            tc = ("#EF4444", "#FCA5A5") if col >= 5 else ("gray10", "gray90")
            name_bg = NAME_BG
            name_tc = NAME_TEXT
            more_tc = MORE_TEXT

        info["cell"].configure(fg_color=bg)
        info["day_lbl"].configure(text_color=tc)
        for nlbl in info.get("name_labels", []):
            nlbl.configure(fg_color=name_bg, text_color=name_tc)
        if info.get("more_lbl"):
            info["more_lbl"].configure(text_color=more_tc)

    def _select_date(self, d):
        prev = self._selected_date
        self._selected_date = d
        today = date.today()
        if prev in self._cells:
            self._style(prev, self._cells[prev], today)
        if d in self._cells:
            self._style(d, self._cells[d], today)
        if self._on_date_select:
            self._on_date_select(d)

    def _prev_month(self):
        if self._current_month == 1:
            self._current_month = 12
            self._current_year -= 1
        else:
            self._current_month -= 1
        self._render_month()

    def _next_month(self):
        if self._current_month == 12:
            self._current_month = 1
            self._current_year += 1
        else:
            self._current_month += 1
        self._render_month()

    def _go_today(self):
        today = date.today()
        self._current_year = today.year
        self._current_month = today.month
        self._render_month()
        self._select_date(today)

    def get_selected_date(self):
        return self._selected_date

    def refresh(self):
        """데이터만 다시 가져와서 전체 다시 렌더링"""
        self._render_month()

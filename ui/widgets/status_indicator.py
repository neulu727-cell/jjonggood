"""연결 상태 표시 위젯"""

import customtkinter as ctk


class StatusIndicator(ctk.CTkFrame):
    """전화 감지 연결 상태를 표시하는 인디케이터"""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)

        self._dot = ctk.CTkLabel(self, text="●", font=("", 18), width=22)
        self._dot.pack(side="left", padx=(0, 4))

        self._label = ctk.CTkLabel(self, text="연결 대기", font=("", 18))
        self._label.pack(side="left")

        self.set_disconnected()

    def set_connected(self, method: str = ""):
        self._dot.configure(text_color="#22C55E")
        text = f"연결됨 ({method})" if method else "연결됨"
        self._label.configure(text=text, text_color=("#22C55E", "#4ADE80"))

    def set_disconnected(self):
        self._dot.configure(text_color="#EF4444")
        self._label.configure(text="연결 대기", text_color=("#EF4444", "#FCA5A5"))

    def set_listening(self, method: str = ""):
        self._dot.configure(text_color="#FBBF24")
        text = f"감지 중 ({method})" if method else "감지 중"
        self._label.configure(text=text, text_color=("#FBBF24", "#FDE68A"))

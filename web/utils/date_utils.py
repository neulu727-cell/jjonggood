"""날짜 관련 유틸리티"""

from datetime import date, datetime


def days_since(past_date) -> int:
    if past_date is None:
        return -1
    if isinstance(past_date, str):
        past_date = datetime.strptime(past_date, "%Y-%m-%d").date()
    elif isinstance(past_date, datetime):
        past_date = past_date.date()
    return (date.today() - past_date).days


def format_date_korean(d) -> str:
    if isinstance(d, str):
        d = datetime.strptime(d, "%Y-%m-%d").date()
    elif isinstance(d, datetime):
        d = d.date()
    return f"{d.year}년 {d.month}월 {d.day}일"


def generate_time_slots(start: str = "09:00", end: str = "19:00", interval: int = 30) -> list:
    slots = []
    start_h, start_m = map(int, start.split(":"))
    end_h, end_m = map(int, end.split(":"))
    current = start_h * 60 + start_m
    last = end_h * 60 + end_m
    while current <= last:
        h = current // 60
        m = current % 60
        slots.append(f"{h:02d}:{m:02d}")
        current += interval
    return slots

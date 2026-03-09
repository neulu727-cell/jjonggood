"""전화번호 정규화 및 포맷팅 유틸리티"""

import re


def normalize_phone(phone: str) -> str:
    if not phone:
        return ""
    digits = re.sub(r"[^\d+]", "", phone)
    if digits.startswith("+82"):
        digits = "0" + digits[3:]
    elif digits.startswith("82") and len(digits) > 10:
        digits = "0" + digits[2:]
    digits = re.sub(r"\D", "", digits)
    if digits and (len(digits) < 9 or len(digits) > 11):
        return ""
    return digits


def format_phone_display(phone: str) -> str:
    digits = normalize_phone(phone)
    if len(digits) == 11 and digits[:3] in ("010", "011", "016", "017", "018", "019"):
        return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
    elif len(digits) == 10 and digits.startswith("02"):
        return f"02-{digits[2:6]}-{digits[6:]}"
    elif len(digits) == 10:
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    elif len(digits) == 9 and digits.startswith("02"):
        return f"02-{digits[2:5]}-{digits[5:]}"
    return digits

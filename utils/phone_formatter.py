"""전화번호 정규화 및 포맷팅 유틸리티"""

import re


def normalize_phone(phone: str) -> str:
    """
    전화번호를 숫자만 남긴 정규화 형식으로 변환.
    DB 저장 및 조회 시 이 형식을 사용.

    예시:
        '010-1234-5678'    -> '01012345678'
        '+82-10-1234-5678' -> '01012345678'
        '+821012345678'    -> '01012345678'
        '01012345678'      -> '01012345678'
    """
    if not phone:
        return ""

    # 숫자와 + 기호만 남김
    digits = re.sub(r"[^\d+]", "", phone)

    # 한국 국제번호 처리
    if digits.startswith("+82"):
        digits = "0" + digits[3:]
    elif digits.startswith("82") and len(digits) > 10:
        digits = "0" + digits[2:]

    # 나머지 비숫자 제거
    digits = re.sub(r"\D", "", digits)

    # 유효성: 한국 전화번호는 10~11자리
    if digits and (len(digits) < 9 or len(digits) > 11):
        return ""
    return digits


def format_phone_display(phone: str) -> str:
    """
    화면 표시용 전화번호 포맷.

    예시:
        '01012345678' -> '010-1234-5678'
        '0212345678'  -> '02-1234-5678'
    """
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

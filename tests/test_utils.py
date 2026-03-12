"""유틸리티 함수 유닛 테스트 — 전화번호, 날짜 파싱, 안전 변환"""

from web.utils.phone_formatter import normalize_phone, format_phone_display


# ==================== normalize_phone ====================

class TestNormalizePhone:
    def test_standard_mobile(self):
        assert normalize_phone("01012345678") == "01012345678"

    def test_with_dashes(self):
        assert normalize_phone("010-1234-5678") == "01012345678"

    def test_with_spaces(self):
        assert normalize_phone("010 1234 5678") == "01012345678"

    def test_plus82_format(self):
        assert normalize_phone("+821012345678") == "01012345678"

    def test_82_format(self):
        assert normalize_phone("821012345678") == "01012345678"

    def test_empty_string(self):
        assert normalize_phone("") == ""

    def test_none_value(self):
        assert normalize_phone(None) == ""

    def test_too_short(self):
        assert normalize_phone("1234") == ""

    def test_too_long(self):
        assert normalize_phone("012345678901234") == ""

    def test_landline_10digits(self):
        assert normalize_phone("0212345678") == "0212345678"

    def test_landline_9digits(self):
        assert normalize_phone("021234567") == "021234567"

    def test_special_chars(self):
        assert normalize_phone("(010)1234-5678") == "01012345678"


# ==================== format_phone_display ====================

class TestFormatPhoneDisplay:
    def test_mobile_11digits(self):
        assert format_phone_display("01012345678") == "010-1234-5678"

    def test_seoul_10digits(self):
        assert format_phone_display("0212345678") == "02-1234-5678"

    def test_seoul_9digits(self):
        assert format_phone_display("021234567") == "02-123-4567"

    def test_local_10digits(self):
        assert format_phone_display("0311234567") == "031-123-4567"

    def test_already_formatted(self):
        assert format_phone_display("010-1234-5678") == "010-1234-5678"

    def test_empty(self):
        assert format_phone_display("") == ""

    def test_plus82(self):
        assert format_phone_display("+821012345678") == "010-1234-5678"


# ==================== safe_int / safe_float (routes_backup) ====================

class TestSafeConversions:
    def test_safe_int_normal(self):
        from web.routes_backup import _safe_int
        assert _safe_int("42") == 42

    def test_safe_int_empty(self):
        from web.routes_backup import _safe_int
        assert _safe_int("") == 0

    def test_safe_int_none(self):
        from web.routes_backup import _safe_int
        assert _safe_int(None) == 0

    def test_safe_int_with_spaces(self):
        from web.routes_backup import _safe_int
        assert _safe_int("  100  ") == 100

    def test_safe_int_default(self):
        from web.routes_backup import _safe_int
        assert _safe_int("", 60) == 60

    def test_safe_float_normal(self):
        from web.routes_backup import _safe_float
        assert _safe_float("3.5") == 3.5

    def test_safe_float_empty(self):
        from web.routes_backup import _safe_float
        assert _safe_float("") is None

    def test_safe_float_none(self):
        from web.routes_backup import _safe_float
        assert _safe_float(None) is None


# ==================== date parsing (routes_backup) ====================

class TestDateParsing:
    def test_yyyy_mm_dd(self):
        from web.routes_backup import _parse_date
        assert _parse_date("2025-03-15") == "2025-03-15"

    def test_mm_dd_format(self):
        from web.routes_backup import _parse_date
        result = _parse_date("3/15")
        assert result.endswith("-03-15")

    def test_mm_dd_padded(self):
        from web.routes_backup import _parse_date
        result = _parse_date("12/5")
        assert result.endswith("-12-05")

    def test_invalid_format(self):
        from web.routes_backup import _parse_date
        import pytest
        with pytest.raises(ValueError):
            _parse_date("abc")

    def test_whitespace(self):
        from web.routes_backup import _parse_date
        assert _parse_date("  2025-01-01  ") == "2025-01-01"


# ==================== customer routes safe_float ====================

class TestCustomerSafeFloat:
    def test_normal(self):
        from web.routes_customer import _safe_float
        assert _safe_float("3.5") == 3.5

    def test_zero(self):
        from web.routes_customer import _safe_float
        assert _safe_float(0) == 0.0  # 0은 유효한 값

    def test_invalid(self):
        from web.routes_customer import _safe_float
        assert _safe_float("abc") is None

    def test_none(self):
        from web.routes_customer import _safe_float
        assert _safe_float(None) is None

    def test_empty_string(self):
        from web.routes_customer import _safe_float
        assert _safe_float("") is None

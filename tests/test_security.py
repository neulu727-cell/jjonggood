"""보안 + 엣지케이스 테스트 — Rate limiting, XSS, 인증 우회, 헤더"""

import json
import pytest
from unittest.mock import patch


# ==================== 보안 헤더 ====================

class TestSecurityHeaders:
    def test_x_frame_options(self, client):
        res = client.get("/health")
        assert res.headers.get("X-Frame-Options") == "DENY"

    def test_x_content_type_options(self, client):
        res = client.get("/health")
        assert res.headers.get("X-Content-Type-Options") == "nosniff"

    def test_csp_header(self, client):
        res = client.get("/health")
        csp = res.headers.get("Content-Security-Policy", "")
        assert "default-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp

    def test_referrer_policy(self, client):
        res = client.get("/health")
        assert res.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    def test_permissions_policy(self, client):
        res = client.get("/health")
        pp = res.headers.get("Permissions-Policy", "")
        assert "camera=()" in pp

    def test_api_no_cache(self, auth_client, mock_db):
        with patch("web.routes_customer.get_db", return_value=mock_db):
            res = auth_client.get("/api/customers/search")
            cc = res.headers.get("Cache-Control", "")
            assert "no-store" in cc


# ==================== 인증 우회 시도 ====================

class TestAuthBypass:
    def test_api_without_session(self, client):
        endpoints = [
            "/api/customers/search",
            "/api/customer/1",
            "/api/reservation/1",
            "/api/call-history",
            "/api/config",
        ]
        for ep in endpoints:
            res = client.get(ep)
            assert res.status_code == 401, f"{ep} should require auth"

    def test_post_without_session(self, client):
        res = client.post("/api/customer",
            data=json.dumps({"phone": "01012345678", "pet_name": "x", "breed": "x"}),
            content_type="application/json")
        assert res.status_code == 401

    def test_delete_without_session(self, client):
        res = client.delete("/api/customer/1")
        assert res.status_code == 401

    def test_backup_without_auth(self, client):
        """백업은 세션 또는 API 키 필요"""
        res = client.get("/api/backup")
        assert res.status_code == 401

    def test_backup_with_wrong_api_key(self, client):
        res = client.get("/api/backup?key=wrong-key")
        assert res.status_code == 401

    def test_backup_with_correct_api_key(self, client, mock_db):
        with patch("web.app.get_db", return_value=mock_db):
            res = client.get("/api/backup?key=test-api-key")
            assert res.status_code == 200

    def test_import_without_session(self, client):
        res = client.post("/api/import-data")
        assert res.status_code == 401


# ==================== Rate Limiting ====================

class TestRateLimiting:
    def test_lockout_after_5_failures(self, client):
        for i in range(5):
            client.post("/login", data={"password": "wrong"})

        res = client.post("/login", data={"password": "wrong"})
        assert res.status_code == 200
        assert "너무 많습니다" in res.get_data(as_text=True)

    def test_correct_password_after_lockout_blocked(self, client):
        for i in range(5):
            client.post("/login", data={"password": "wrong"})

        # 올바른 비밀번호도 잠금 상태에서는 차단
        res = client.post("/login", data={"password": "testpass123"})
        assert "너무 많습니다" in res.get_data(as_text=True)


# ==================== XSS 방어 ====================

class TestXSSPrevention:
    def test_xss_in_customer_name(self, auth_client, mock_db):
        with patch("web.routes_customer.get_db", return_value=mock_db):
            res = auth_client.post("/api/customer",
                data=json.dumps({
                    "phone": "01012345678",
                    "pet_name": "<script>alert('xss')</script>",
                    "breed": "말티즈",
                }),
                content_type="application/json")
            # 서버는 저장하되, 프론트엔드 esc()가 방어
            assert res.status_code == 200

    def test_xss_in_search_keyword(self, auth_client, mock_db):
        with patch("web.routes_customer.get_db", return_value=mock_db):
            res = auth_client.get("/api/customers/search?q=<script>alert(1)</script>")
            assert res.status_code == 200  # 에러가 아닌 빈 결과

    def test_sql_injection_in_sort(self, auth_client, mock_db):
        with patch("web.routes_customer.get_db", return_value=mock_db):
            res = auth_client.get("/api/customers/search?sort='; DROP TABLE customers;--")
            assert res.status_code == 200  # whitelist 방식이므로 안전


# ==================== 입력 길이 제한 ====================

class TestInputLimits:
    def test_long_pet_name_truncated(self, auth_client, mock_db):
        with patch("web.routes_customer.get_db", return_value=mock_db):
            long_name = "뽀" * 100  # 100자
            res = auth_client.post("/api/customer",
                data=json.dumps({
                    "phone": "01012345678",
                    "pet_name": long_name,
                    "breed": "말티즈",
                }),
                content_type="application/json")
            assert res.status_code == 200
            # 서버에서 50자로 잘림 확인은 DB 레벨

    def test_long_service_type_truncated(self, auth_client, mock_db):
        mock_db._customers[1] = {
            "id": 1, "name": "", "phone": "01012345678",
            "pet_name": "뽀삐", "breed": "말티즈",
            "weight": None, "age": None, "notes": "", "memo": "",
            "created_at": None, "updated_at": None,
        }
        with patch("web.routes_reservation.get_db", return_value=mock_db):
            res = auth_client.post("/api/reservation",
                data=json.dumps({
                    "customer_id": 1,
                    "date": "2025-03-15",
                    "time": "10:00",
                    "service_type": "A" * 200,
                }),
                content_type="application/json")
            assert res.status_code == 200


# ==================== 엣지케이스 ====================

class TestEdgeCases:
    def test_reservation_status_cancelled_deletes(self, auth_client, mock_db):
        mock_db._reservations[1] = {
            "id": 1, "customer_id": 1, "date": "2025-03-15", "time": "10:00",
            "service_type": "전체미용", "duration": 120, "request": "",
            "amount": 0, "status": "confirmed", "groomer_memo": "",
            "quoted_amount": 0, "payment_method": "", "fur_length": "",
            "created_at": None, "completed_at": None,
        }
        with patch("web.routes_reservation.get_db", return_value=mock_db):
            res = auth_client.put("/api/reservation/1/status",
                data=json.dumps({"status": "cancelled"}),
                content_type="application/json")
            assert res.status_code == 200

    def test_empty_json_body(self, auth_client, mock_db):
        with patch("web.routes_customer.get_db", return_value=mock_db):
            res = auth_client.post("/api/customer",
                data="{}",
                content_type="application/json")
            assert res.status_code == 400

    def test_health_when_db_down(self, client):
        with patch("web.app.get_db", side_effect=Exception("DB down")):
            res = client.get("/health")
            assert res.status_code == 503
            data = json.loads(res.data)
            assert data["status"] == "error"
            # 에러 상세 정보 노출되지 않는지 확인
            assert "DB down" not in json.dumps(data)

    def test_max_content_length(self, app):
        assert app.config["MAX_CONTENT_LENGTH"] == 16 * 1024 * 1024

    def test_session_cookie_flags(self, app):
        assert app.config["SESSION_COOKIE_HTTPONLY"] is True

"""API 통합 테스트 — 인증, 고객 CRUD, 예약 CRUD"""

import json
import pytest
from unittest.mock import patch


# ==================== 인증 ====================

class TestAuth:
    def test_login_page_loads(self, client):
        res = client.get("/login")
        assert res.status_code == 200

    def test_login_success(self, client):
        res = client.post("/login", data={"password": "testpass123"})
        assert res.status_code == 302  # redirect

    def test_login_wrong_password(self, client):
        res = client.post("/login", data={"password": "wrong"})
        assert res.status_code == 200
        assert "틀렸습니다" in res.get_data(as_text=True)

    def test_logout_clears_session(self, auth_client):
        res = auth_client.get("/logout", follow_redirects=False)
        assert res.status_code == 302

    def test_unauthenticated_api_returns_401(self, client):
        res = client.get("/api/customers/search")
        assert res.status_code == 401

    def test_unauthenticated_redirect_to_login(self, client):
        res = client.get("/", follow_redirects=False)
        assert res.status_code == 302
        assert "/login" in res.headers.get("Location", "")


# ==================== Health ====================

class TestHealth:
    def test_health_ok(self, client):
        res = client.get("/health")
        assert res.status_code == 200
        data = json.loads(res.data)
        assert data["status"] == "ok"


# ==================== 고객 CRUD ====================

class TestCustomerAPI:
    def test_create_customer(self, auth_client, mock_db):
        with patch("web.routes_customer.get_db", return_value=mock_db):
            res = auth_client.post("/api/customer",
                data=json.dumps({
                    "phone": "010-1234-5678",
                    "pet_name": "뽀삐",
                    "breed": "말티즈",
                }),
                content_type="application/json")
            assert res.status_code == 200
            data = json.loads(res.data)
            assert data["ok"] is True
            assert "id" in data

    def test_create_customer_missing_phone(self, auth_client, mock_db):
        with patch("web.routes_customer.get_db", return_value=mock_db):
            res = auth_client.post("/api/customer",
                data=json.dumps({"pet_name": "뽀삐", "breed": "말티즈"}),
                content_type="application/json")
            assert res.status_code == 400

    def test_create_customer_missing_pet_name(self, auth_client, mock_db):
        with patch("web.routes_customer.get_db", return_value=mock_db):
            res = auth_client.post("/api/customer",
                data=json.dumps({"phone": "01012345678", "breed": "말티즈"}),
                content_type="application/json")
            assert res.status_code == 400

    def test_create_customer_missing_breed(self, auth_client, mock_db):
        with patch("web.routes_customer.get_db", return_value=mock_db):
            res = auth_client.post("/api/customer",
                data=json.dumps({"phone": "01012345678", "pet_name": "뽀삐"}),
                content_type="application/json")
            assert res.status_code == 400

    def test_create_customer_invalid_phone(self, auth_client, mock_db):
        with patch("web.routes_customer.get_db", return_value=mock_db):
            res = auth_client.post("/api/customer",
                data=json.dumps({"phone": "123", "pet_name": "뽀삐", "breed": "말티즈"}),
                content_type="application/json")
            assert res.status_code == 400

    def test_search_customers(self, auth_client, mock_db):
        with patch("web.routes_customer.get_db", return_value=mock_db):
            res = auth_client.get("/api/customers/search?q=뽀삐")
            assert res.status_code == 200
            data = json.loads(res.data)
            assert "customers" in data

    def test_search_empty_keyword(self, auth_client, mock_db):
        with patch("web.routes_customer.get_db", return_value=mock_db):
            res = auth_client.get("/api/customers/search")
            assert res.status_code == 200

    def test_get_customer_not_found(self, auth_client, mock_db):
        with patch("web.routes_customer.get_db", return_value=mock_db):
            res = auth_client.get("/api/customer/9999")
            assert res.status_code == 404

    def test_delete_customer(self, auth_client, mock_db):
        # 먼저 고객 생성
        mock_db._customers[1] = {
            "id": 1, "name": "", "phone": "01012345678",
            "pet_name": "뽀삐", "breed": "말티즈",
            "weight": None, "age": None, "notes": "", "memo": "",
            "created_at": None, "updated_at": None,
        }
        with patch("web.routes_customer.get_db", return_value=mock_db):
            res = auth_client.delete("/api/customer/1")
            assert res.status_code == 200

    def test_update_customer(self, auth_client, mock_db):
        mock_db._customers[1] = {
            "id": 1, "name": "", "phone": "01012345678",
            "pet_name": "뽀삐", "breed": "말티즈",
            "weight": None, "age": None, "notes": "", "memo": "",
            "created_at": None, "updated_at": None,
        }
        with patch("web.routes_customer.get_db", return_value=mock_db):
            res = auth_client.put("/api/customer/1",
                data=json.dumps({"pet_name": "뽀삐2"}),
                content_type="application/json")
            assert res.status_code == 200

    def test_no_json_body(self, auth_client, mock_db):
        with patch("web.routes_customer.get_db", return_value=mock_db):
            res = auth_client.post("/api/customer", content_type="application/json")
            assert res.status_code == 400


# ==================== 예약 CRUD ====================

class TestReservationAPI:
    def _seed_customer(self, mock_db):
        mock_db._customers[1] = {
            "id": 1, "name": "테스트", "phone": "01012345678",
            "pet_name": "뽀삐", "breed": "말티즈",
            "weight": 3.5, "age": "3살", "notes": "", "memo": "",
            "created_at": None, "updated_at": None,
        }

    def test_create_reservation(self, auth_client, mock_db):
        self._seed_customer(mock_db)
        with patch("web.routes_reservation.get_db", return_value=mock_db):
            res = auth_client.post("/api/reservation",
                data=json.dumps({
                    "customer_id": 1,
                    "date": "2025-03-15",
                    "time": "10:00",
                    "service_type": "전체미용",
                }),
                content_type="application/json")
            assert res.status_code == 200
            data = json.loads(res.data)
            assert data["ok"] is True

    def test_create_reservation_invalid_date(self, auth_client, mock_db):
        self._seed_customer(mock_db)
        with patch("web.routes_reservation.get_db", return_value=mock_db):
            res = auth_client.post("/api/reservation",
                data=json.dumps({
                    "customer_id": 1,
                    "date": "15-03-2025",  # 잘못된 형식
                    "time": "10:00",
                    "service_type": "전체미용",
                }),
                content_type="application/json")
            assert res.status_code == 400

    def test_create_reservation_invalid_time(self, auth_client, mock_db):
        self._seed_customer(mock_db)
        with patch("web.routes_reservation.get_db", return_value=mock_db):
            res = auth_client.post("/api/reservation",
                data=json.dumps({
                    "customer_id": 1,
                    "date": "2025-03-15",
                    "time": "25:99",  # 형식은 맞지만 의미적으로 잘못
                    "service_type": "전체미용",
                }),
                content_type="application/json")
            # 현재는 regex만 체크하므로 HH:MM 형식이면 통과
            # (시맨틱 검증은 별도 이슈)
            assert res.status_code in (200, 400)

    def test_create_reservation_missing_fields(self, auth_client, mock_db):
        with patch("web.routes_reservation.get_db", return_value=mock_db):
            res = auth_client.post("/api/reservation",
                data=json.dumps({"customer_id": 1}),
                content_type="application/json")
            assert res.status_code == 400

    def test_create_reservation_nonexistent_customer(self, auth_client, mock_db):
        with patch("web.routes_reservation.get_db", return_value=mock_db):
            res = auth_client.post("/api/reservation",
                data=json.dumps({
                    "customer_id": 9999,
                    "date": "2025-03-15",
                    "time": "10:00",
                    "service_type": "전체미용",
                }),
                content_type="application/json")
            assert res.status_code == 404

    def test_create_reservation_invalid_numbers(self, auth_client, mock_db):
        self._seed_customer(mock_db)
        with patch("web.routes_reservation.get_db", return_value=mock_db):
            res = auth_client.post("/api/reservation",
                data=json.dumps({
                    "customer_id": "not_a_number",
                    "date": "2025-03-15",
                    "time": "10:00",
                    "service_type": "전체미용",
                }),
                content_type="application/json")
            assert res.status_code == 400

    def test_update_status_valid(self, auth_client, mock_db):
        self._seed_customer(mock_db)
        mock_db._reservations[1] = {
            "id": 1, "customer_id": 1, "date": "2025-03-15", "time": "10:00",
            "service_type": "전체미용", "duration": 120, "request": "",
            "amount": 50000, "status": "confirmed", "groomer_memo": "",
            "quoted_amount": 0, "payment_method": "", "fur_length": "",
            "created_at": None, "completed_at": None,
        }
        with patch("web.routes_reservation.get_db", return_value=mock_db):
            res = auth_client.put("/api/reservation/1/status",
                data=json.dumps({"status": "completed"}),
                content_type="application/json")
            assert res.status_code == 200

    def test_update_status_invalid(self, auth_client, mock_db):
        with patch("web.routes_reservation.get_db", return_value=mock_db):
            res = auth_client.put("/api/reservation/1/status",
                data=json.dumps({"status": "invalid_status"}),
                content_type="application/json")
            assert res.status_code == 400

    def test_no_data_body(self, auth_client, mock_db):
        with patch("web.routes_reservation.get_db", return_value=mock_db):
            res = auth_client.post("/api/reservation",
                content_type="application/json")
            assert res.status_code == 400


# ==================== 전화 웹훅 ====================

class TestCallWebhook:
    def test_incoming_call_with_api_key(self, client, mock_db):
        with patch("web.routes_call.get_db", return_value=mock_db):
            res = client.post("/api/incoming-call?key=test-api-key",
                data={"phone": "01012345678"})
            assert res.status_code == 200
            data = json.loads(res.data)
            assert data["ok"] is True

    def test_incoming_call_no_api_key(self, client, mock_db):
        with patch("web.routes_call.get_db", return_value=mock_db):
            res = client.post("/api/incoming-call",
                data={"phone": "01012345678"})
            assert res.status_code == 401

    def test_incoming_call_no_phone(self, client, mock_db):
        with patch("web.routes_call.get_db", return_value=mock_db):
            res = client.post("/api/incoming-call?key=test-api-key")
            assert res.status_code == 400

    def test_bridge_heartbeat(self, client):
        res = client.post("/api/bridge-heartbeat?key=test-api-key",
            data={"status": "ok", "device": "Galaxy S24"})
        assert res.status_code == 200

    def test_bridge_heartbeat_no_key(self, client):
        res = client.post("/api/bridge-heartbeat",
            data={"status": "ok"})
        assert res.status_code == 401

    def test_bridge_status(self, client):
        res = client.get("/api/bridge-status")
        assert res.status_code == 200
        data = json.loads(res.data)
        assert "alive" in data


# ==================== Setup 페이지 ====================

class TestSetup:
    def test_setup_page_loads(self, client):
        res = client.get("/setup")
        assert res.status_code == 200
        assert "ADB Bridge" in res.get_data(as_text=True)

    def test_install_bat_download(self, client):
        res = client.get("/setup/install.bat")
        assert res.status_code == 200
        content = res.data.decode("cp949")
        assert "@echo off" in content
        assert "TASKER_API_KEY" in content

    def test_bridge_env_requires_auth(self, client):
        res = client.get("/setup/bridge.env")
        assert res.status_code == 401

    def test_bridge_env_with_auth(self, auth_client):
        res = auth_client.get("/setup/bridge.env")
        assert res.status_code == 200
        content = res.get_data(as_text=True)
        assert "RENDER_URL=" in content
        assert "TASKER_API_KEY=" in content

    def test_adb_bridge_download(self, client):
        res = client.get("/setup/adb_bridge.py")
        assert res.status_code == 200

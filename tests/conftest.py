"""테스트 픽스처 — Flask test client + 인메모리 DB 모킹"""

import os
import pytest

# 테스트용 환경변수 (app import 전에 설정)
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("VIEWER_PASSWORD", "testpass123")
os.environ.setdefault("TASKER_API_KEY", "test-api-key")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

from unittest.mock import MagicMock, patch
from web.models import Customer, Reservation


# ---------- Mock DB ----------

class MockRow(dict):
    """dict처럼 접근하면서 attribute 접근도 가능한 Row 모킹"""
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)


class MockDB:
    """DatabaseManager를 대체하는 인메모리 Mock DB"""

    def __init__(self):
        self._pool = True  # pool 존재 표시
        self._customers = {}  # id -> dict
        self._reservations = {}  # id -> dict
        self._call_history = []
        self._next_cid = 1
        self._next_rid = 1

    def initialize(self):
        pass

    def fetch_one(self, query, params=None):
        q = query.lower().strip()
        if "select 1" in q:
            return MockRow({"?column?": 1})
        if "from customers where id" in q and params:
            cid = params[0]
            c = self._customers.get(cid)
            return MockRow(c) if c else None
        if "from customers where phone" in q and params:
            phone = params[0]
            for c in self._customers.values():
                if c["phone"] == phone:
                    return MockRow(c)
            return None
        if "from reservations" in q and "where id" in q and params:
            rid = params[0]
            r = self._reservations.get(rid)
            return MockRow(r) if r else None
        # 통계 쿼리
        if "count(*)" in q and "from reservations" in q:
            return MockRow({"cnt": 0, "total": 0, "avg_amt": 0,
                           "last_visit": None, "visit_count": 0,
                           "total_sales": 0, "avg_amount": 0})
        # customer detail 통합 쿼리
        if "from customers c" in q and "left join reservations" in q and params:
            cid = params[0]
            c = self._customers.get(cid)
            if c:
                row = dict(c)
                row.update({"last_visit": None, "visit_count": 0,
                           "total_sales": 0, "avg_amount": 0})
                return MockRow(row)
            return None
        return None

    def fetch_all(self, query, params=None):
        q = query.lower().strip()
        if "from customers" in q and "where phone" in q and params:
            phone = params[0]
            return [MockRow(c) for c in self._customers.values() if c["phone"] == phone]
        if "from customers" in q and "ilike" in q:
            return [MockRow(c) for c in self._customers.values()]
        if "from customers c" in q and "left join" in q:
            return [MockRow({**c, "last_visit": None, "visit_count": 0, "total_sales": 0})
                    for c in self._customers.values()]
        if "from reservations" in q and "where r.date" in q:
            return []
        if "from reservations" in q:
            return []
        if "from call_history" in q:
            return [MockRow(h) for h in self._call_history]
        if "from service_types" in q:
            return []
        return []

    def execute(self, query, params=None):
        q = query.lower().strip()
        mock_cursor = MagicMock()

        if q.startswith("insert into customers"):
            cid = self._next_cid
            self._next_cid += 1
            if params:
                self._customers[cid] = {
                    "id": cid, "name": params[0], "phone": params[1],
                    "pet_name": params[2], "breed": params[3],
                    "weight": params[4] if len(params) > 4 else None,
                    "age": params[5] if len(params) > 5 else None,
                    "notes": params[6] if len(params) > 6 else "",
                    "memo": params[7] if len(params) > 7 else "",
                    "created_at": None, "updated_at": None,
                }
            mock_cursor.lastrowid = cid
            mock_cursor.fetchone.return_value = (cid,)
            return mock_cursor

        if q.startswith("insert into reservations"):
            rid = self._next_rid
            self._next_rid += 1
            if params:
                self._reservations[rid] = {
                    "id": rid, "customer_id": params[0],
                    "date": params[1], "time": params[2],
                    "service_type": params[3], "duration": params[4] if len(params) > 4 else 60,
                    "request": params[5] if len(params) > 5 else "",
                    "amount": params[6] if len(params) > 6 else 0,
                    "quoted_amount": params[7] if len(params) > 7 else 0,
                    "payment_method": params[8] if len(params) > 8 else "",
                    "fur_length": params[9] if len(params) > 9 else "",
                    "status": "confirmed", "groomer_memo": "",
                    "created_at": None, "completed_at": None,
                }
            mock_cursor.lastrowid = rid
            return mock_cursor

        if q.startswith("insert into call_history"):
            self._call_history.append({
                "id": len(self._call_history) + 1,
                "phone": params[0] if params else "",
                "customer_id": params[1] if params and len(params) > 1 else None,
                "pet_name": params[2] if params and len(params) > 2 else "",
                "created_at": None,
            })
            mock_cursor.lastrowid = len(self._call_history)
            return mock_cursor

        if "on conflict" in q:
            mock_cursor.lastrowid = 0
            return mock_cursor

        if q.startswith("delete"):
            if "from customers" in q and params:
                self._customers.pop(params[0], None)
            if "from reservations" in q and "customer_id" not in q and params:
                self._reservations.pop(params[0], None)
            return mock_cursor

        if q.startswith("update"):
            return mock_cursor

        mock_cursor.lastrowid = 0
        return mock_cursor

    def get_conn(self):
        return MagicMock()

    def put_conn(self, conn):
        pass


# ---------- Fixtures ----------

@pytest.fixture
def mock_db():
    return MockDB()


@pytest.fixture
def app(mock_db):
    """Flask 앱 생성 (Mock DB 주입)"""
    with patch("web.app.get_db", return_value=mock_db):
        with patch("web.app.DatabaseManager"):
            from web.app import create_app
            application = create_app()
            application.config["TESTING"] = True
            application.config["SESSION_COOKIE_SECURE"] = False  # 테스트에서 HTTP 허용
            yield application


@pytest.fixture
def client(app):
    """Flask test client"""
    return app.test_client()


@pytest.fixture
def auth_client(client):
    """인증된 상태의 test client"""
    with client.session_transaction() as sess:
        sess["authenticated"] = True
    return client

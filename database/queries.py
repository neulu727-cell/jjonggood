"""데이터베이스 쿼리 함수 모음"""

from typing import Optional, List
from database.db_manager import DatabaseManager
from database.models import Customer, Reservation, GroomerMemo
from datetime import datetime


# ==================== 고객 관련 ====================

def find_customer_by_phone(db: DatabaseManager, phone: str) -> Optional[Customer]:
    """전화번호로 고객 조회"""
    row = db.fetch_one("SELECT * FROM customers WHERE phone = ?", (phone,))
    if row is None:
        return None
    return Customer(**dict(row))


def create_customer(db: DatabaseManager, name: str, phone: str, pet_name: str,
                    breed: str, weight=None, age=None, notes="", memo="") -> int:
    """신규 고객 등록. 생성된 고객 ID 반환."""
    cursor = db.execute(
        """INSERT INTO customers (name, phone, pet_name, breed, weight, age, notes, memo)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (name, phone, pet_name, breed, weight, age, notes, memo)
    )
    return cursor.lastrowid


_CUSTOMER_FIELDS = {"name", "phone", "pet_name", "breed", "weight", "age", "notes", "memo"}

def update_customer(db: DatabaseManager, customer_id: int, **fields) -> None:
    """고객 정보 수정. 변경할 필드만 키워드 인자로 전달."""
    if not fields:
        return
    safe_fields = {k: v for k, v in fields.items() if k in _CUSTOMER_FIELDS}
    if not safe_fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in safe_fields)
    values = list(safe_fields.values()) + [customer_id]
    db.execute(
        f"UPDATE customers SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        tuple(values)
    )


def search_customers(db: DatabaseManager, keyword: str) -> List[Customer]:
    """이름, 전화번호, 반려동물 이름으로 고객 검색"""
    like = f"%{keyword}%"
    rows = db.fetch_all(
        """SELECT * FROM customers
           WHERE name LIKE ? OR phone LIKE ? OR pet_name LIKE ?
           ORDER BY name""",
        (like, like, like)
    )
    return [Customer(**dict(row)) for row in rows]


def delete_customer(db: DatabaseManager, customer_id: int) -> None:
    """고객 삭제 (관련 예약도 함께 삭제)"""
    db.execute("DELETE FROM reservations WHERE customer_id = ?", (customer_id,))
    db.execute("DELETE FROM customers WHERE id = ?", (customer_id,))


def get_all_customers(db: DatabaseManager) -> List[Customer]:
    """전체 고객 목록"""
    rows = db.fetch_all("SELECT * FROM customers ORDER BY name")
    return [Customer(**dict(row)) for row in rows]


# ==================== 예약 관련 ====================

def create_reservation(db: DatabaseManager, customer_id: int, date: str,
                       time: str, service_type: str, duration: int = 60,
                       request: str = "", amount: int = 0,
                       fur_length: str = "") -> int:
    """예약 생성. 생성된 예약 ID 반환."""
    cursor = db.execute(
        """INSERT INTO reservations (customer_id, date, time, service_type, duration, request, amount, fur_length)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (customer_id, date, time, service_type, duration, request, amount, fur_length)
    )
    return cursor.lastrowid


def get_reservations_by_date(db: DatabaseManager, date: str) -> List[Reservation]:
    """특정 날짜의 예약 목록 (시간순, 취소/노쇼 제외)"""
    rows = db.fetch_all(
        """SELECT r.*, c.name as customer_name, c.pet_name, c.phone as customer_phone, c.breed
           FROM reservations r
           JOIN customers c ON r.customer_id = c.id
           WHERE r.date = ? AND r.status NOT IN ('cancelled', 'no_show')
           ORDER BY r.time""",
        (date,)
    )
    return [_row_to_reservation(row) for row in rows]


def get_customer_reservations(db: DatabaseManager, customer_id: int) -> List[Reservation]:
    """특정 고객의 예약 이력 (최근순)"""
    rows = db.fetch_all(
        """SELECT r.*, c.name as customer_name, c.pet_name, c.phone as customer_phone, c.breed
           FROM reservations r
           JOIN customers c ON r.customer_id = c.id
           WHERE r.customer_id = ?
           ORDER BY r.date DESC, r.time DESC""",
        (customer_id,)
    )
    return [_row_to_reservation(row) for row in rows]


def get_customer_sales_stats(db: DatabaseManager, customer_id: int) -> dict:
    """고객별 매출 통계: 횟수, 총액, 평균"""
    row = db.fetch_one(
        """SELECT COUNT(*) as cnt,
                  COALESCE(SUM(amount), 0) as total,
                  COALESCE(AVG(amount), 0) as avg_amt
           FROM reservations
           WHERE customer_id = ? AND status = 'completed' AND amount > 0""",
        (customer_id,)
    )
    if row:
        return {"count": row["cnt"], "total": int(row["total"]), "avg": int(row["avg_amt"])}
    return {"count": 0, "total": 0, "avg": 0}


def get_last_visit_date(db: DatabaseManager, customer_id: int) -> Optional[str]:
    """고객의 마지막 방문일 (완료된 예약 기준)"""
    row = db.fetch_one(
        """SELECT date FROM reservations
           WHERE customer_id = ? AND status = 'completed'
           ORDER BY date DESC LIMIT 1""",
        (customer_id,)
    )
    return row["date"] if row else None


def update_reservation_status(db: DatabaseManager, reservation_id: int, status: str) -> None:
    """예약 상태 변경 (confirmed, completed, cancelled, no_show).
    completed로 변경 시 completed_at 타임스탬프 기록."""
    if status == "completed":
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.execute(
            "UPDATE reservations SET status = ?, completed_at = ? WHERE id = ?",
            (status, now, reservation_id)
        )
    else:
        db.execute(
            "UPDATE reservations SET status = ?, completed_at = NULL WHERE id = ?",
            (status, reservation_id)
        )


_RESERVATION_FIELDS = {"date", "time", "service_type", "duration", "request",
                       "status", "amount", "fur_length", "groomer_memo"}

def update_reservation_with_history(db: DatabaseManager, reservation_id: int, **fields) -> None:
    """예약 수정 + 변경 히스토리 기록. 같은 날 수정은 마지막 것만 유지."""
    if not fields:
        return
    safe_fields = {k: v for k, v in fields.items() if k in _RESERVATION_FIELDS}
    if not safe_fields:
        return
    row = db.fetch_one("SELECT * FROM reservations WHERE id = ?", (reservation_id,))
    if not row:
        return
    current = dict(row)
    today = datetime.now().strftime("%Y-%m-%d")
    changed = {}
    for k, v in safe_fields.items():
        old_val = str(current.get(k, ""))
        new_val = str(v)
        if old_val != new_val:
            changed[k] = v
            db.execute(
                "DELETE FROM reservation_edits WHERE reservation_id = ? AND field_name = ? AND date(created_at) = ?",
                (reservation_id, k, today)
            )
            db.execute(
                "INSERT INTO reservation_edits (reservation_id, field_name, old_value, new_value) VALUES (?, ?, ?, ?)",
                (reservation_id, k, old_val, new_val)
            )
    if changed:
        set_clause = ", ".join(f"{k} = ?" for k in changed)
        values = list(changed.values()) + [reservation_id]
        db.execute(f"UPDATE reservations SET {set_clause} WHERE id = ?", tuple(values))


def get_reservation_edits(db: DatabaseManager, reservation_id: int) -> list:
    """예약 수정 히스토리 조회 (최신순)"""
    rows = db.fetch_all(
        "SELECT * FROM reservation_edits WHERE reservation_id = ? ORDER BY created_at DESC",
        (reservation_id,)
    )
    return [dict(row) for row in rows]


def get_customer_reservation_edits(db: DatabaseManager, customer_id: int) -> list:
    """고객의 전체 예약 수정 히스토리 (최신순)"""
    rows = db.fetch_all(
        """SELECT re.*, r.date, r.time, r.service_type
           FROM reservation_edits re
           JOIN reservations r ON re.reservation_id = r.id
           WHERE r.customer_id = ?
           ORDER BY re.created_at DESC""",
        (customer_id,)
    )
    return [dict(row) for row in rows]


def update_reservation_memo(db: DatabaseManager, reservation_id: int, memo: str) -> None:
    """예약별 미용사 메모 저장 + 히스토리 기록"""
    db.execute(
        "UPDATE reservations SET groomer_memo = ? WHERE id = ?",
        (memo, reservation_id)
    )
    if memo.strip():
        db.execute(
            "INSERT INTO groomer_memos (reservation_id, content) VALUES (?, ?)",
            (reservation_id, memo.strip())
        )


def get_groomer_memos(db: DatabaseManager, reservation_id: int) -> List[GroomerMemo]:
    """예약의 미용사 메모 히스토리 (최신순)"""
    rows = db.fetch_all(
        "SELECT * FROM groomer_memos WHERE reservation_id = ? ORDER BY created_at DESC",
        (reservation_id,)
    )
    return [GroomerMemo(**dict(row)) for row in rows]


def get_customer_groomer_memos(db: DatabaseManager, customer_id: int) -> List[dict]:
    """고객의 전체 미용사 메모 히스토리 (최신순, 예약정보 포함)"""
    rows = db.fetch_all(
        """SELECT gm.*, r.date, r.time, r.service_type
           FROM groomer_memos gm
           JOIN reservations r ON gm.reservation_id = r.id
           WHERE r.customer_id = ?
           ORDER BY gm.created_at DESC""",
        (customer_id,)
    )
    return [dict(row) for row in rows]


def delete_reservation(db: DatabaseManager, reservation_id: int) -> None:
    """예약 삭제"""
    db.execute("DELETE FROM reservations WHERE id = ?", (reservation_id,))


def get_reservation_counts_by_month(db: DatabaseManager, year: int, month: int) -> dict:
    """월별 날짜별 예약 건수를 한번에 조회 (취소/노쇼 제외). {date_str: count}"""
    rows = db.fetch_all(
        """SELECT date, COUNT(*) as cnt FROM reservations
           WHERE date LIKE ? AND status NOT IN ('cancelled', 'no_show')
           GROUP BY date""",
        (f"{year:04d}-{month:02d}-%",)
    )
    return {row["date"]: row["cnt"] for row in rows}


def get_reservation_names_by_month(db: DatabaseManager, year: int, month: int) -> dict:
    """월별 날짜별 예약자 이름 목록 조회. {date_str: [{"pet_name": ..., "breed": ..., "time": ...}, ...]}"""
    rows = db.fetch_all(
        """SELECT r.date, r.time, c.pet_name, c.breed
           FROM reservations r
           LEFT JOIN customers c ON r.customer_id = c.id
           WHERE r.date LIKE ? AND r.status NOT IN ('cancelled', 'no_show')
           ORDER BY r.date, r.time""",
        (f"{year:04d}-{month:02d}-%",)
    )
    result = {}
    for row in rows:
        d = row["date"]
        if d not in result:
            result[d] = []
        result[d].append({
            "pet_name": row["pet_name"] or "",
            "breed": row["breed"] or "",
            "time": row["time"] or "",
        })
    return result


# ==================== 서비스 타입 관련 ====================

def init_default_services(db: DatabaseManager, services: list) -> None:
    """기본 서비스 타입 초기화 (이미 있으면 무시)"""
    for name, duration, price in services:
        db.execute(
            """INSERT OR IGNORE INTO service_types (name, default_duration, default_price)
               VALUES (?, ?, ?)""",
            (name, duration, price)
        )


def get_service_types(db: DatabaseManager) -> list:
    """서비스 타입 목록 조회"""
    rows = db.fetch_all("SELECT * FROM service_types ORDER BY id")
    return [dict(row) for row in rows]


# ==================== 전화수신 기록 ====================

def add_call_history(db: DatabaseManager, phone: str, customer_id: int = None,
                     pet_name: str = "") -> int:
    """전화수신 기록 저장 (로컬 시간)"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor = db.execute(
        "INSERT INTO call_history (phone, customer_id, pet_name, created_at) VALUES (?, ?, ?, ?)",
        (phone, customer_id, pet_name, now)
    )
    return cursor.lastrowid


def get_call_history(db: DatabaseManager, limit: int = 30) -> list:
    """최근 전화수신 기록 (최신순)"""
    rows = db.fetch_all(
        """SELECT ch.*, c.pet_name as c_pet_name, c.breed
           FROM call_history ch
           LEFT JOIN customers c ON ch.customer_id = c.id
           ORDER BY ch.created_at DESC LIMIT ?""",
        (limit,)
    )
    return [dict(row) for row in rows]


def get_today_call_history(db: DatabaseManager) -> list:
    """오늘 전화수신 기록"""
    rows = db.fetch_all(
        """SELECT ch.*, c.pet_name as c_pet_name, c.breed
           FROM call_history ch
           LEFT JOIN customers c ON ch.customer_id = c.id
           WHERE date(ch.created_at) = date('now', 'localtime')
           ORDER BY ch.created_at DESC""",
        ()
    )
    return [dict(row) for row in rows]


def get_call_history_by_date(db: DatabaseManager, date_str: str) -> list:
    """특정 날짜 전화수신 기록"""
    rows = db.fetch_all(
        """SELECT ch.*, c.pet_name as c_pet_name, c.breed
           FROM call_history ch
           LEFT JOIN customers c ON ch.customer_id = c.id
           WHERE date(ch.created_at) = ?
           ORDER BY ch.created_at DESC""",
        (date_str,)
    )
    return [dict(row) for row in rows]


# ==================== 헬퍼 ====================

def _row_to_reservation(row) -> Reservation:
    """sqlite3.Row를 Reservation 객체로 변환"""
    d = dict(row)
    return Reservation(
        id=d["id"],
        customer_id=d["customer_id"],
        date=d["date"],
        time=d["time"],
        service_type=d["service_type"],
        duration=d.get("duration", 60),
        request=d.get("request", ""),
        status=d.get("status", "confirmed"),
        amount=d.get("amount", 0),
        fur_length=d.get("fur_length", ""),
        groomer_memo=d.get("groomer_memo", ""),
        created_at=d.get("created_at"),
        completed_at=d.get("completed_at"),
        customer_name=d.get("customer_name", ""),
        pet_name=d.get("pet_name", ""),
        customer_phone=d.get("customer_phone", ""),
        breed=d.get("breed", ""),
    )

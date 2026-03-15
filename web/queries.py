"""데이터베이스 쿼리 함수 모음 (PostgreSQL 호환)"""

from typing import Optional, List
from web.db import DatabaseManager
from web.models import Customer, Reservation, GroomerMemo
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))


# ==================== 고객 관련 ====================

def find_customer_by_phone(db: DatabaseManager, phone: str) -> Optional[Customer]:
    """전화번호로 첫 번째 고객 반환 (하위 호환)"""
    row = db.fetch_one("SELECT * FROM customers WHERE phone = ? ORDER BY id LIMIT 1", (phone,))
    if row is None:
        return None
    return Customer(**dict(row))


def find_customers_by_phone(db: DatabaseManager, phone: str) -> List[Customer]:
    """전화번호로 모든 고객(반려동물) 반환"""
    rows = db.fetch_all("SELECT * FROM customers WHERE phone = ? ORDER BY id", (phone,))
    return [Customer(**dict(row)) for row in rows]


def create_customer(db: DatabaseManager, name: str, phone: str, pet_name: str,
                    breed: str, weight=None, age=None, notes="", memo="") -> int:
    cursor = db.execute(
        """INSERT INTO customers (name, phone, pet_name, breed, weight, age, notes, memo)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (name, phone, pet_name, breed, weight, age, notes, memo)
    )
    return cursor.lastrowid


_CUSTOMER_FIELDS = {"name", "phone", "pet_name", "breed", "weight", "age", "notes", "memo"}

def update_customer(db: DatabaseManager, customer_id: int, **fields) -> None:
    if not fields:
        return
    safe_fields = {k: v for k, v in fields.items() if k in _CUSTOMER_FIELDS}
    if not safe_fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in safe_fields)
    values = list(safe_fields.values()) + [customer_id]
    db.execute(
        f"UPDATE customers SET {set_clause}, updated_at = NOW() WHERE id = ?",
        tuple(values)
    )


def search_customers(db: DatabaseManager, keyword: str) -> List[Customer]:
    like = f"%{keyword}%"
    rows = db.fetch_all(
        """SELECT * FROM customers
           WHERE name ILIKE ? OR phone ILIKE ? OR pet_name ILIKE ?
           ORDER BY name""",
        (like, like, like)
    )
    return [Customer(**dict(row)) for row in rows]


def delete_customer(db: DatabaseManager, customer_id: int) -> None:
    db.execute("DELETE FROM reservations WHERE customer_id = ?", (customer_id,))
    db.execute("DELETE FROM customers WHERE id = ?", (customer_id,))


def get_all_customers(db: DatabaseManager) -> List[Customer]:
    rows = db.fetch_all("SELECT * FROM customers ORDER BY name")
    return [Customer(**dict(row)) for row in rows]


def get_customer_by_id(db: DatabaseManager, customer_id: int) -> Optional[Customer]:
    row = db.fetch_one("SELECT * FROM customers WHERE id = ?", (customer_id,))
    if row is None:
        return None
    return Customer(**dict(row))


def get_siblings(db: DatabaseManager, phone: str, exclude_id: int = None) -> list:
    """같은 전화번호의 다른 반려동물 목록"""
    if exclude_id:
        rows = db.fetch_all(
            "SELECT id, pet_name, breed, memo FROM customers WHERE phone = ? AND id != ? ORDER BY id",
            (phone, exclude_id))
    else:
        rows = db.fetch_all(
            "SELECT id, pet_name, breed, memo FROM customers WHERE phone = ? ORDER BY id",
            (phone,))
    return [dict(r) for r in rows]


def get_customer_detail(db: DatabaseManager, customer_id: int) -> Optional[dict]:
    """고객 정보 + 통계 + 최근 예약을 단일 쿼리 2개로 조회 (기존 4쿼리 → 2쿼리)"""
    row = db.fetch_one("""
        SELECT c.*,
               MAX(CASE WHEN r.status='completed' THEN r.date END) AS last_visit,
               COUNT(CASE WHEN r.status='completed' AND r.amount>0 THEN 1 END) AS visit_count,
               COALESCE(SUM(CASE WHEN r.status='completed' AND r.amount>0 THEN r.amount END),0) AS total_sales,
               COALESCE(AVG(CASE WHEN r.status='completed' AND r.amount>0 THEN r.amount END),0) AS avg_amount
        FROM customers c
        LEFT JOIN reservations r ON r.customer_id = c.id
        WHERE c.id = ?
        GROUP BY c.id
    """, (customer_id,))
    if row is None:
        return None
    d = dict(row)
    lv = d.get("last_visit")
    if lv and hasattr(lv, 'strftime'):
        lv = lv.strftime("%Y-%m-%d")
    elif lv:
        lv = str(lv)
    d["last_visit"] = lv
    d["stats"] = {
        "count": d.pop("visit_count", 0),
        "total": int(d.pop("total_sales", 0)),
        "avg": int(d.pop("avg_amount", 0)),
    }
    return d


# ==================== 예약 관련 ====================

def create_reservation(db: DatabaseManager, customer_id: int, date: str,
                       time: str, service_type: str, duration: int = 60,
                       request: str = "", amount: int = 0,
                       fur_length: str = "", quoted_amount: int = 0,
                       payment_method: str = "", groomer_memo: str = "") -> int:
    cursor = db.execute(
        """INSERT INTO reservations (customer_id, date, time, service_type, duration, request, amount, quoted_amount, payment_method, fur_length, groomer_memo)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (customer_id, date, time, service_type, duration, request, amount, quoted_amount, payment_method, fur_length, groomer_memo)
    )
    return cursor.lastrowid


def get_reservations_by_date(db: DatabaseManager, date: str) -> List[Reservation]:
    rows = db.fetch_all(
        """SELECT r.*, c.name as customer_name, c.pet_name, c.phone as customer_phone, c.breed, c.memo as customer_memo
           FROM reservations r
           JOIN customers c ON r.customer_id = c.id
           WHERE r.date = ?::date AND r.status NOT IN ('cancelled', 'no_show')
           ORDER BY r.time""",
        (date,)
    )
    return [_row_to_reservation(row) for row in rows]


def get_reservations_by_date_with_memo(db: DatabaseManager, date: str) -> list:
    """타임라인용: 예약 + 고객 메모 포함"""
    rows = db.fetch_all(
        """SELECT r.id, TO_CHAR(r.time, 'HH24:MI') as time, r.duration,
                  r.customer_id, c.name as customer_name, c.pet_name,
                  c.phone as customer_phone, c.breed, c.weight, c.age,
                  c.memo as customer_memo,
                  r.service_type as service, r.amount, r.fur_length,
                  r.request, r.groomer_memo, r.status,
                  TO_CHAR(r.completed_at, 'YYYY-MM-DD HH24:MI:SS') as completed_at
           FROM reservations r
           JOIN customers c ON r.customer_id = c.id
           WHERE r.date = ?::date AND r.status NOT IN ('cancelled', 'no_show')
           ORDER BY r.time""",
        (date,)
    )
    return [dict(row) for row in rows]


def get_reservation_by_id(db: DatabaseManager, reservation_id: int) -> Optional[Reservation]:
    row = db.fetch_one(
        """SELECT r.*, c.name as customer_name, c.pet_name, c.phone as customer_phone, c.breed
           FROM reservations r
           JOIN customers c ON r.customer_id = c.id
           WHERE r.id = ?""",
        (reservation_id,)
    )
    if row is None:
        return None
    return _row_to_reservation(row)


def get_customer_reservations(db: DatabaseManager, customer_id: int) -> List[Reservation]:
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
    row = db.fetch_one(
        """SELECT date FROM reservations
           WHERE customer_id = ? AND status = 'completed'
           ORDER BY date DESC LIMIT 1""",
        (customer_id,)
    )
    if row:
        d = row["date"]
        return d.strftime("%Y-%m-%d") if hasattr(d, 'strftime') else str(d)
    return None


def update_reservation_status(db: DatabaseManager, reservation_id: int, status: str) -> None:
    if status == "completed":
        now = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
        db.execute(
            "UPDATE reservations SET status = ?, completed_at = ?::timestamp WHERE id = ?",
            (status, now, reservation_id)
        )
    else:
        db.execute(
            "UPDATE reservations SET status = ?, completed_at = NULL WHERE id = ?",
            (status, reservation_id)
        )


_RESERVATION_FIELDS = {"date", "time", "service_type", "duration", "request",
                       "status", "amount", "quoted_amount", "payment_method", "fur_length", "groomer_memo"}

def update_reservation_with_history(db: DatabaseManager, reservation_id: int, **fields) -> None:
    if not fields:
        return
    safe_fields = {k: v for k, v in fields.items() if k in _RESERVATION_FIELDS}
    if not safe_fields:
        return
    row = db.fetch_one("SELECT * FROM reservations WHERE id = ?", (reservation_id,))
    if not row:
        return
    current = dict(row)
    today = datetime.now(KST).strftime("%Y-%m-%d")
    changed = {}
    for k, v in safe_fields.items():
        old_val = str(current.get(k, ""))
        new_val = str(v)
        if old_val != new_val:
            changed[k] = v
            db.execute(
                "DELETE FROM reservation_edits WHERE reservation_id = ? AND field_name = ? AND created_at::date = ?::date",
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
    rows = db.fetch_all(
        "SELECT * FROM reservation_edits WHERE reservation_id = ? ORDER BY created_at DESC",
        (reservation_id,)
    )
    return [dict(row) for row in rows]


def get_customer_reservation_edits(db: DatabaseManager, customer_id: int) -> list:
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
    rows = db.fetch_all(
        "SELECT * FROM groomer_memos WHERE reservation_id = ? ORDER BY created_at DESC",
        (reservation_id,)
    )
    return [GroomerMemo(**dict(row)) for row in rows]


def get_customer_groomer_memos(db: DatabaseManager, customer_id: int) -> List[dict]:
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
    db.execute("DELETE FROM reservations WHERE id = ?", (reservation_id,))


def get_reservation_counts_by_month(db: DatabaseManager, year: int, month: int) -> dict:
    rows = db.fetch_all(
        """SELECT TO_CHAR(date, 'YYYY-MM-DD') as date_str, COUNT(*) as cnt
           FROM reservations
           WHERE EXTRACT(YEAR FROM date) = ? AND EXTRACT(MONTH FROM date) = ?
             AND status NOT IN ('cancelled', 'no_show')
           GROUP BY date""",
        (year, month)
    )
    return {row["date_str"]: row["cnt"] for row in rows}


def get_reservation_names_by_month(db: DatabaseManager, year: int, month: int) -> dict:
    rows = db.fetch_all(
        """SELECT TO_CHAR(r.date, 'YYYY-MM-DD') as date_str,
                  TO_CHAR(r.time, 'HH24:MI') as time_str,
                  c.pet_name, c.breed, r.status
           FROM reservations r
           LEFT JOIN customers c ON r.customer_id = c.id
           WHERE EXTRACT(YEAR FROM r.date) = ? AND EXTRACT(MONTH FROM r.date) = ?
             AND r.status NOT IN ('cancelled', 'no_show')
           ORDER BY r.date, r.time""",
        (year, month)
    )
    result = {}
    for row in rows:
        d = row["date_str"]
        if d not in result:
            result[d] = []
        result[d].append({
            "pet_name": row["pet_name"] or "",
            "breed": row["breed"] or "",
            "time": row["time_str"] or "",
            "status": row["status"] or "confirmed",
        })
    return result


# ==================== 서비스 타입 관련 ====================

def init_default_services(db: DatabaseManager, services: list) -> None:
    for name, duration, price in services:
        db.execute(
            """INSERT INTO service_types (name, default_duration, default_price)
               VALUES (?, ?, ?)
               ON CONFLICT (name) DO NOTHING""",
            (name, duration, price)
        )


def get_service_types(db: DatabaseManager) -> list:
    rows = db.fetch_all("SELECT * FROM service_types ORDER BY id")
    return [dict(row) for row in rows]


# ==================== 전화수신 기록 ====================

def add_call_history(db: DatabaseManager, phone: str, customer_id: int = None,
                     pet_name: str = "") -> int:
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    cursor = db.execute(
        "INSERT INTO call_history (phone, customer_id, pet_name, created_at) VALUES (?, ?, ?, ?::timestamp)",
        (phone, customer_id, pet_name, now)
    )
    return cursor.lastrowid


def get_call_history(db: DatabaseManager, limit: int = 30) -> list:
    rows = db.fetch_all(
        """SELECT ch.*, c.pet_name as c_pet_name, c.breed
           FROM call_history ch
           LEFT JOIN customers c ON ch.customer_id = c.id
           ORDER BY ch.created_at DESC LIMIT ?""",
        (limit,)
    )
    return [dict(row) for row in rows]


def get_today_call_history(db: DatabaseManager) -> list:
    rows = db.fetch_all(
        """SELECT ch.*, c.pet_name as c_pet_name, c.breed
           FROM call_history ch
           LEFT JOIN customers c ON ch.customer_id = c.id
           WHERE ch.created_at::date = CURRENT_DATE
           ORDER BY ch.created_at DESC"""
    )
    return [dict(row) for row in rows]


def get_call_history_by_date(db: DatabaseManager, date_str: str) -> list:
    rows = db.fetch_all(
        """SELECT ch.*, c.pet_name as c_pet_name, c.breed
           FROM call_history ch
           LEFT JOIN customers c ON ch.customer_id = c.id
           WHERE ch.created_at::date = ?::date
           ORDER BY ch.created_at DESC""",
        (date_str,)
    )
    return [dict(row) for row in rows]


# ==================== 데이터 초기화 ====================

def clear_all_data(db: DatabaseManager) -> None:
    """모든 데이터 삭제 (FK 순서 준수)"""
    db.execute("DELETE FROM reservation_edits")
    db.execute("DELETE FROM groomer_memos")
    db.execute("DELETE FROM call_history")
    db.execute("DELETE FROM reservations")
    db.execute("DELETE FROM customers")


# ==================== 매출 관련 ====================

def get_sales_month_data(db: DatabaseManager, year: int, month: int) -> dict:
    """월별 매출 데이터: 일별매출, 월간요약, 반려동물별 TOP10, 결제수단별 집계"""
    # 1) 일별 매출 합계 + 건수
    daily_rows = db.fetch_all(
        """SELECT TO_CHAR(date, 'YYYY-MM-DD') as date_str,
                  SUM(amount) as total, COUNT(*) as cnt
           FROM reservations
           WHERE EXTRACT(YEAR FROM date) = ? AND EXTRACT(MONTH FROM date) = ?
             AND status = 'completed' AND amount > 0
           GROUP BY date
           ORDER BY date""",
        (year, month)
    )
    daily = {row["date_str"]: {"total": int(row["total"]), "cnt": row["cnt"]}
             for row in daily_rows}

    # 2) 월간 요약
    summary_row = db.fetch_one(
        """SELECT COALESCE(SUM(amount), 0) as total_sales,
                  COUNT(*) as completed_cnt,
                  COALESCE(AVG(amount), 0) as avg_amount
           FROM reservations
           WHERE EXTRACT(YEAR FROM date) = ? AND EXTRACT(MONTH FROM date) = ?
             AND status = 'completed' AND amount > 0""",
        (year, month)
    )
    summary = {
        "total_sales": int(summary_row["total_sales"]),
        "completed_cnt": summary_row["completed_cnt"],
        "avg_amount": int(summary_row["avg_amount"]),
    }

    # 3) 반려동물별 방문 TOP 10
    top_rows = db.fetch_all(
        """SELECT c.id as customer_id, c.pet_name, c.breed,
                  COUNT(*) as visit_cnt, SUM(r.amount) as visit_sales
           FROM reservations r
           JOIN customers c ON r.customer_id = c.id
           WHERE EXTRACT(YEAR FROM r.date) = ? AND EXTRACT(MONTH FROM r.date) = ?
             AND r.status = 'completed' AND r.amount > 0
           GROUP BY c.id, c.pet_name, c.breed
           ORDER BY visit_cnt DESC, visit_sales DESC
           LIMIT 10""",
        (year, month)
    )
    top_pets = [{"customer_id": row["customer_id"],
                 "pet_name": row["pet_name"] or "",
                 "breed": row["breed"] or "",
                 "visit_cnt": row["visit_cnt"],
                 "visit_sales": int(row["visit_sales"])}
                for row in top_rows]

    # 4) 결제수단별 집계
    pay_rows = db.fetch_all(
        """SELECT COALESCE(NULLIF(payment_method, ''), '미지정') as method,
                  COUNT(*) as cnt, COALESCE(SUM(amount), 0) as total
           FROM reservations
           WHERE EXTRACT(YEAR FROM date) = ? AND EXTRACT(MONTH FROM date) = ?
             AND status = 'completed' AND amount > 0
           GROUP BY method
           ORDER BY total DESC""",
        (year, month)
    )
    payment = [{"method": row["method"], "cnt": row["cnt"], "total": int(row["total"])}
               for row in pay_rows]

    # 5) 견종별 집계
    breed_rows = db.fetch_all(
        """SELECT COALESCE(NULLIF(c.breed, ''), '미지정') as breed,
                  COUNT(*) as visit_cnt, COALESCE(SUM(r.amount), 0) as total,
                  COALESCE(AVG(r.amount), 0) as avg_amount
           FROM reservations r
           JOIN customers c ON r.customer_id = c.id
           WHERE EXTRACT(YEAR FROM r.date) = ? AND EXTRACT(MONTH FROM r.date) = ?
             AND r.status = 'completed' AND r.amount > 0
           GROUP BY breed
           ORDER BY visit_cnt DESC""",
        (year, month)
    )
    breeds = [{"breed": row["breed"], "visit_cnt": row["visit_cnt"],
               "total": int(row["total"]), "avg": int(row["avg_amount"])}
              for row in breed_rows]

    # 6) 서비스별 집계
    service_rows = db.fetch_all(
        """SELECT COALESCE(NULLIF(service_type, ''), '미지정') as service,
                  COUNT(*) as cnt, COALESCE(SUM(amount), 0) as total,
                  COALESCE(AVG(amount), 0) as avg_amount
           FROM reservations
           WHERE EXTRACT(YEAR FROM date) = ? AND EXTRACT(MONTH FROM date) = ?
             AND status = 'completed' AND amount > 0
           GROUP BY service
           ORDER BY total DESC""",
        (year, month)
    )
    services = [{"service": row["service"], "cnt": row["cnt"],
                 "total": int(row["total"]), "avg": int(row["avg_amount"])}
                for row in service_rows]

    # 7) 요일별 집계
    dow_rows = db.fetch_all(
        """SELECT EXTRACT(DOW FROM date)::int as dow,
                  COUNT(*) as cnt, COALESCE(SUM(amount), 0) as total
           FROM reservations
           WHERE EXTRACT(YEAR FROM date) = ? AND EXTRACT(MONTH FROM date) = ?
             AND status = 'completed' AND amount > 0
           GROUP BY dow
           ORDER BY dow""",
        (year, month)
    )
    by_dow = [{"dow": row["dow"], "cnt": row["cnt"], "total": int(row["total"])}
              for row in dow_rows]

    return {"daily": daily, "summary": summary, "top_pets": top_pets,
            "payment": payment, "breeds": breeds, "services": services, "by_dow": by_dow}


# ==================== 헬퍼 ====================

def _row_to_reservation(row) -> Reservation:
    d = dict(row)
    # PostgreSQL date/time → string 변환
    date_val = d["date"]
    time_val = d["time"]
    if hasattr(date_val, 'strftime'):
        date_val = date_val.strftime("%Y-%m-%d")
    if hasattr(time_val, 'strftime'):
        time_val = time_val.strftime("%H:%M")
    elif hasattr(time_val, 'isoformat'):
        time_val = time_val.isoformat()[:5]

    completed_at = d.get("completed_at")
    if completed_at and hasattr(completed_at, 'strftime'):
        completed_at = completed_at.strftime("%Y-%m-%d %H:%M:%S")

    created_at = d.get("created_at")
    if created_at and hasattr(created_at, 'strftime'):
        created_at = created_at.strftime("%Y-%m-%d %H:%M:%S")

    return Reservation(
        id=d["id"],
        customer_id=d["customer_id"],
        date=str(date_val),
        time=str(time_val),
        service_type=d["service_type"],
        duration=d.get("duration", 60),
        request=d.get("request", ""),
        status=d.get("status", "confirmed"),
        amount=d.get("amount", 0),
        quoted_amount=d.get("quoted_amount", 0),
        payment_method=d.get("payment_method", ""),
        fur_length=d.get("fur_length", ""),
        groomer_memo=d.get("groomer_memo", ""),
        created_at=str(created_at) if created_at else None,
        completed_at=str(completed_at) if completed_at else None,
        customer_name=d.get("customer_name", ""),
        pet_name=d.get("pet_name", ""),
        customer_phone=d.get("customer_phone", ""),
        breed=d.get("breed", ""),
    )

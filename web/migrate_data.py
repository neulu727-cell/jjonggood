"""SQLite → PostgreSQL 데이터 이관 스크립트 (1회성)

사용법:
    DATABASE_URL=postgresql://... python -m web.migrate_data [sqlite_path]
"""

import os
import sys
import sqlite3

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web.db import DatabaseManager


def migrate(sqlite_path: str, pg_url: str):
    print(f"SQLite: {sqlite_path}")
    print(f"PostgreSQL: {pg_url[:50]}...")

    # SQLite 연결
    src = sqlite3.connect(sqlite_path)
    src.row_factory = sqlite3.Row

    # PostgreSQL 연결 + 테이블 생성
    dst = DatabaseManager(pg_url)
    dst.initialize()

    # 1. 고객
    rows = src.execute("SELECT * FROM customers").fetchall()
    print(f"고객: {len(rows)}건")
    for row in rows:
        r = dict(row)
        try:
            dst.execute(
                """INSERT INTO customers (id, name, phone, pet_name, breed, weight, age, notes, memo, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?::timestamp, ?::timestamp)
                   ON CONFLICT (phone) DO NOTHING""",
                (r["id"], r.get("name",""), r["phone"], r["pet_name"], r["breed"],
                 r.get("weight"), r.get("age"), r.get("notes",""), r.get("memo",""),
                 r.get("created_at"), r.get("updated_at"))
            )
        except Exception as e:
            print(f"  고객 {r.get('name','')} ({r['phone']}) 실패: {e}")

    # 시퀀스 리셋
    max_id = src.execute("SELECT MAX(id) FROM customers").fetchone()[0] or 0
    if max_id:
        dst.execute(f"SELECT setval('customers_id_seq', {max_id})")

    # 2. 예약
    rows = src.execute("SELECT * FROM reservations").fetchall()
    print(f"예약: {len(rows)}건")
    for row in rows:
        r = dict(row)
        try:
            dst.execute(
                """INSERT INTO reservations (id, customer_id, date, time, service_type, duration,
                   request, status, amount, fur_length, groomer_memo, completed_at, created_at)
                   VALUES (?, ?, ?::date, ?::time, ?, ?, ?, ?, ?, ?, ?, ?::timestamp, ?::timestamp)
                   ON CONFLICT (id) DO NOTHING""",
                (r["id"], r["customer_id"], r["date"], r["time"], r["service_type"],
                 r.get("duration", 60), r.get("request",""), r.get("status","confirmed"),
                 r.get("amount", 0), r.get("fur_length",""), r.get("groomer_memo",""),
                 r.get("completed_at"), r.get("created_at"))
            )
        except Exception as e:
            print(f"  예약 #{r['id']} 실패: {e}")

    max_id = src.execute("SELECT MAX(id) FROM reservations").fetchone()[0] or 0
    if max_id:
        dst.execute(f"SELECT setval('reservations_id_seq', {max_id})")

    # 3. 서비스 타입
    try:
        rows = src.execute("SELECT * FROM service_types").fetchall()
        print(f"서비스: {len(rows)}건")
        for row in rows:
            r = dict(row)
            dst.execute(
                """INSERT INTO service_types (id, name, default_duration, default_price)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT (name) DO NOTHING""",
                (r["id"], r["name"], r.get("default_duration", 60), r.get("default_price", 0))
            )
        max_id = src.execute("SELECT MAX(id) FROM service_types").fetchone()[0] or 0
        if max_id:
            dst.execute(f"SELECT setval('service_types_id_seq', {max_id})")
    except Exception as e:
        print(f"  서비스 이관 건너뜀: {e}")

    # 4. 미용사 메모
    try:
        rows = src.execute("SELECT * FROM groomer_memos").fetchall()
        print(f"메모: {len(rows)}건")
        for row in rows:
            r = dict(row)
            dst.execute(
                """INSERT INTO groomer_memos (id, reservation_id, content, created_at)
                   VALUES (?, ?, ?, ?::timestamp)
                   ON CONFLICT (id) DO NOTHING""",
                (r["id"], r["reservation_id"], r["content"], r.get("created_at"))
            )
        max_id = src.execute("SELECT MAX(id) FROM groomer_memos").fetchone()[0] or 0
        if max_id:
            dst.execute(f"SELECT setval('groomer_memos_id_seq', {max_id})")
    except Exception as e:
        print(f"  메모 이관 건너뜀: {e}")

    # 5. 전화이력
    try:
        rows = src.execute("SELECT * FROM call_history").fetchall()
        print(f"전화이력: {len(rows)}건")
        for row in rows:
            r = dict(row)
            dst.execute(
                """INSERT INTO call_history (id, phone, customer_id, pet_name, call_type, created_at)
                   VALUES (?, ?, ?, ?, ?, ?::timestamp)
                   ON CONFLICT (id) DO NOTHING""",
                (r["id"], r["phone"], r.get("customer_id"), r.get("pet_name",""),
                 r.get("call_type","incoming"), r.get("created_at"))
            )
        max_id = src.execute("SELECT MAX(id) FROM call_history").fetchone()[0] or 0
        if max_id:
            dst.execute(f"SELECT setval('call_history_id_seq', {max_id})")
    except Exception as e:
        print(f"  전화이력 이관 건너뜀: {e}")

    # 6. 수정이력
    try:
        rows = src.execute("SELECT * FROM reservation_edits").fetchall()
        print(f"수정이력: {len(rows)}건")
        for row in rows:
            r = dict(row)
            dst.execute(
                """INSERT INTO reservation_edits (id, reservation_id, field_name, old_value, new_value, created_at)
                   VALUES (?, ?, ?, ?, ?, ?::timestamp)
                   ON CONFLICT (id) DO NOTHING""",
                (r["id"], r["reservation_id"], r["field_name"],
                 r.get("old_value",""), r.get("new_value",""), r.get("created_at"))
            )
        max_id = src.execute("SELECT MAX(id) FROM reservation_edits").fetchone()[0] or 0
        if max_id:
            dst.execute(f"SELECT setval('reservation_edits_id_seq', {max_id})")
    except Exception as e:
        print(f"  수정이력 이관 건너뜀: {e}")

    src.close()
    dst.close()
    print("이관 완료!")


if __name__ == "__main__":
    sqlite_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "grooming_shop.db"
    )
    pg_url = os.environ.get("DATABASE_URL", "")
    if not pg_url:
        print("DATABASE_URL 환경변수를 설정하세요")
        sys.exit(1)
    if not os.path.exists(sqlite_path):
        print(f"SQLite 파일을 찾을 수 없습니다: {sqlite_path}")
        sys.exit(1)

    migrate(sqlite_path, pg_url)

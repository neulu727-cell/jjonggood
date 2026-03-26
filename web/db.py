"""PostgreSQL 데이터베이스 관리자

SQLite DatabaseManager와 동일한 인터페이스 제공.
- execute(query, params) → cursor-like object
- fetch_one(query, params) → dict or None
- fetch_all(query, params) → list of dicts
- ?를 %s로 자동 변환
"""

import os
import psycopg2
import psycopg2.pool
import psycopg2.extras


class CursorResult:
    """execute() 반환용. lastrowid 호환."""
    def __init__(self, lastrowid=None, rowcount=0):
        self.lastrowid = lastrowid
        self.rowcount = rowcount


class DatabaseManager:
    def __init__(self, database_url: str = None):
        self._url = database_url or os.environ.get("DATABASE_URL", "")
        self._pool = None

    def initialize(self):
        """커넥션 풀 생성 + 테이블 초기화"""
        # connect_timeout: 연결 시도 최대 10초
        # keepalives: TCP keepalive로 죽은 연결 감지
        # options: statement_timeout으로 쿼리 최대 30초
        dsn = self._url
        if "?" not in dsn:
            dsn += "?"
        else:
            dsn += "&"
        dsn += "connect_timeout=10&keepalives=1&keepalives_idle=30&keepalives_interval=10&keepalives_count=3&options=-c%20statement_timeout%3D30000"

        self._pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=2, maxconn=10, dsn=dsn
        )
        self._create_tables()

    def _get_conn(self):
        """풀에서 커넥션을 꺼내되, 죽은 연결이면 재생성."""
        conn = self._pool.getconn()
        try:
            # 연결 상태 확인 (죽은 연결 감지)
            conn.isolation_level
            if conn.closed:
                raise psycopg2.OperationalError("closed")
            # 실제 ping + KST 설정
            with conn.cursor() as cur:
                cur.execute("SET timezone = 'Asia/Seoul'")
                cur.execute("SELECT 1")
        except Exception:
            # 죽은 연결 → 버리고 새로 만들기
            try:
                self._pool.putconn(conn, close=True)
            except Exception:
                pass
            conn = self._pool.getconn()
        return conn

    def _put_conn(self, conn):
        self._pool.putconn(conn)

    @staticmethod
    def _convert_query(query: str) -> str:
        """SQLite ? 플레이스홀더를 PostgreSQL %s로 변환.
        문자열 리터럴 안의 ?는 건드리지 않음."""
        result = []
        in_string = False
        quote_char = None
        for ch in query:
            if in_string:
                result.append(ch)
                if ch == quote_char:
                    in_string = False
            else:
                if ch in ("'", '"'):
                    in_string = True
                    quote_char = ch
                    result.append(ch)
                elif ch == '?':
                    result.append('%s')
                else:
                    result.append(ch)
        return ''.join(result)

    def execute(self, query: str, params: tuple = ()) -> CursorResult:
        """INSERT, UPDATE, DELETE 등 쓰기 작업"""
        query = self._convert_query(query)
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                # INSERT에 RETURNING id 추가 (lastrowid 지원)
                if query.strip().upper().startswith("INSERT") and "RETURNING" not in query.upper():
                    query = query.rstrip().rstrip(';') + " RETURNING id"
                cur.execute(query, params)
                conn.commit()
                lastrowid = None
                if cur.description:
                    row = cur.fetchone()
                    if row:
                        lastrowid = row[0]
                return CursorResult(lastrowid=lastrowid, rowcount=cur.rowcount)
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_conn(conn)

    def execute_no_commit(self, conn, query: str, params: tuple = ()):
        """트랜잭션 내 쓰기 작업 (commit 안 함). conn은 transaction()에서 받은 것."""
        query = self._convert_query(query)
        with conn.cursor() as cur:
            if query.strip().upper().startswith("INSERT") and "RETURNING" not in query.upper():
                query = query.rstrip().rstrip(';') + " RETURNING id"
            cur.execute(query, params)
            lastrowid = None
            if cur.description:
                row = cur.fetchone()
                if row:
                    lastrowid = row[0]
            return CursorResult(lastrowid=lastrowid, rowcount=cur.rowcount)

    def get_conn(self):
        """트랜잭션용 커넥션 획득"""
        return self._get_conn()

    def put_conn(self, conn):
        """트랜잭션용 커넥션 반환"""
        self._put_conn(conn)

    def fetch_one(self, query: str, params: tuple = ()):
        """단일 행 조회. dict 반환 또는 None."""
        query = self._convert_query(query)
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, params)
                return cur.fetchone()
        finally:
            self._put_conn(conn)

    def fetch_all(self, query: str, params: tuple = ()):
        """여러 행 조회. list of dicts."""
        query = self._convert_query(query)
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, params)
                return cur.fetchall()
        finally:
            self._put_conn(conn)

    def _create_tables(self):
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SET timezone = 'Asia/Seoul'")
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS customers (
                        id          SERIAL PRIMARY KEY,
                        name        TEXT DEFAULT '',
                        phone       TEXT NOT NULL,
                        pet_name    TEXT NOT NULL,
                        breed       TEXT NOT NULL,
                        weight      REAL,
                        age         TEXT,
                        notes       TEXT DEFAULT '',
                        memo        TEXT DEFAULT '',
                        channel     TEXT DEFAULT '',
                        created_at  TIMESTAMP DEFAULT NOW(),
                        updated_at  TIMESTAMP DEFAULT NOW()
                    );

                    CREATE TABLE IF NOT EXISTS reservations (
                        id            SERIAL PRIMARY KEY,
                        customer_id   INTEGER NOT NULL REFERENCES customers(id),
                        date          DATE NOT NULL,
                        time          TIME NOT NULL,
                        service_type  TEXT NOT NULL,
                        duration      INTEGER DEFAULT 60,
                        request       TEXT DEFAULT '',
                        status        TEXT DEFAULT 'confirmed',
                        amount        INTEGER DEFAULT 0,
                        quoted_amount INTEGER DEFAULT 0,
                        payment_method TEXT DEFAULT '',
                        fur_length    TEXT DEFAULT '',
                        groomer_memo  TEXT DEFAULT '',
                        completed_at  TIMESTAMP DEFAULT NULL,
                        created_at    TIMESTAMP DEFAULT NOW()
                    );

                    CREATE TABLE IF NOT EXISTS service_types (
                        id                SERIAL PRIMARY KEY,
                        name              TEXT NOT NULL UNIQUE,
                        default_duration  INTEGER DEFAULT 60,
                        default_price     INTEGER DEFAULT 0
                    );

                    CREATE TABLE IF NOT EXISTS groomer_memos (
                        id              SERIAL PRIMARY KEY,
                        reservation_id  INTEGER NOT NULL REFERENCES reservations(id) ON DELETE CASCADE,
                        content         TEXT NOT NULL,
                        created_at      TIMESTAMP DEFAULT NOW()
                    );

                    CREATE TABLE IF NOT EXISTS call_history (
                        id          SERIAL PRIMARY KEY,
                        phone       TEXT NOT NULL,
                        customer_id INTEGER,
                        pet_name    TEXT DEFAULT '',
                        call_type   TEXT DEFAULT 'incoming',
                        created_at  TIMESTAMP DEFAULT NOW()
                    );

                    CREATE TABLE IF NOT EXISTS reservation_edits (
                        id              SERIAL PRIMARY KEY,
                        reservation_id  INTEGER NOT NULL REFERENCES reservations(id) ON DELETE CASCADE,
                        field_name      TEXT NOT NULL,
                        old_value       TEXT DEFAULT '',
                        new_value       TEXT DEFAULT '',
                        created_at      TIMESTAMP DEFAULT NOW()
                    );

                    CREATE TABLE IF NOT EXISTS grooming_requests (
                        id              SERIAL PRIMARY KEY,
                        breed           TEXT NOT NULL,
                        weight          REAL,
                        service_type    TEXT NOT NULL,
                        actual_service  TEXT DEFAULT '',
                        clipping_length TEXT DEFAULT '',
                        face_cut        BOOLEAN DEFAULT FALSE,
                        matting         TEXT DEFAULT 'none',
                        fur_length      TEXT DEFAULT '',
                        estimated_price INTEGER DEFAULT 0,
                        customer_name   TEXT DEFAULT '',
                        customer_phone  TEXT DEFAULT '',
                        memo            TEXT DEFAULT '',
                        status          TEXT DEFAULT 'pending',
                        created_at      TIMESTAMP DEFAULT NOW()
                    );

                    CREATE INDEX IF NOT EXISTS idx_reservations_date ON reservations(date);
                    CREATE INDEX IF NOT EXISTS idx_reservations_customer ON reservations(customer_id);
                    CREATE INDEX IF NOT EXISTS idx_reservations_date_customer ON reservations(date, customer_id);
                    -- 통계 쿼리용 커버링 인덱스 (status+amount 필터)
                    CREATE INDEX IF NOT EXISTS idx_reservations_customer_status ON reservations(customer_id, status, date DESC);
                    CREATE INDEX IF NOT EXISTS idx_call_history_date ON call_history(created_at);
                    CREATE INDEX IF NOT EXISTS idx_call_history_phone ON call_history(phone);
                    CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone);
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_customers_phone_pet ON customers(phone, pet_name);
                    CREATE INDEX IF NOT EXISTS idx_reservation_edits_rid ON reservation_edits(reservation_id, created_at DESC);
                """)
                # 마이그레이션: quoted_amount 컬럼 추가
                cur.execute("""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_name = 'reservations' AND column_name = 'quoted_amount'
                        ) THEN
                            ALTER TABLE reservations ADD COLUMN quoted_amount INTEGER DEFAULT 0;
                        END IF;
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_name = 'reservations' AND column_name = 'payment_method'
                        ) THEN
                            ALTER TABLE reservations ADD COLUMN payment_method TEXT DEFAULT '';
                        END IF;
                    END $$;
                """)
                # 마이그레이션: phone UNIQUE → (phone, pet_name) UNIQUE
                cur.execute("""
                    DO $$
                    BEGIN
                        -- 기존 phone UNIQUE 제약 제거
                        IF EXISTS (
                            SELECT 1 FROM information_schema.table_constraints
                            WHERE table_name = 'customers' AND constraint_type = 'UNIQUE'
                              AND constraint_name = 'customers_phone_key'
                        ) THEN
                            ALTER TABLE customers DROP CONSTRAINT customers_phone_key;
                        END IF;
                    END $$;
                """)
                # 마이그레이션: Google 연락처 연동
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS google_tokens (
                        id            SERIAL PRIMARY KEY,
                        access_token  TEXT NOT NULL,
                        refresh_token TEXT NOT NULL,
                        expires_at    TIMESTAMP,
                        created_at    TIMESTAMP DEFAULT NOW()
                    );
                """)
                cur.execute("""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_name = 'customers' AND column_name = 'google_contact_id'
                        ) THEN
                            ALTER TABLE customers ADD COLUMN google_contact_id TEXT;
                        END IF;
                    END $$;
                """)
                # 마이그레이션: 유입경로(channel) 필드
                cur.execute("""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_name = 'customers' AND column_name = 'channel'
                        ) THEN
                            ALTER TABLE customers ADD COLUMN channel TEXT DEFAULT '';
                        END IF;
                    END $$;
                """)
                # 마이그레이션: 보조연락처/비상연락처 필드
                cur.execute("""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_name = 'customers' AND column_name = 'phone2'
                        ) THEN
                            ALTER TABLE customers ADD COLUMN phone2 TEXT DEFAULT '';
                        END IF;
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_name = 'customers' AND column_name = 'phone3'
                        ) THEN
                            ALTER TABLE customers ADD COLUMN phone3 TEXT DEFAULT '';
                        END IF;
                    END $$;
                """)
                # 마이그레이션: 고객 변경이력 테이블
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS customer_history (
                        id            SERIAL PRIMARY KEY,
                        customer_id   INTEGER NOT NULL,
                        action        TEXT NOT NULL,
                        field_name    TEXT DEFAULT '',
                        old_value     TEXT DEFAULT '',
                        new_value     TEXT DEFAULT '',
                        created_at    TIMESTAMP DEFAULT NOW()
                    );
                    CREATE INDEX IF NOT EXISTS idx_customer_history_cid
                        ON customer_history(customer_id, created_at DESC);
                """)
                # 마이그레이션: 전체얼컷 기본 소요시간 90→120분
                cur.execute("""
                    UPDATE service_types SET default_duration = 120
                    WHERE name = '전체얼컷' AND default_duration = 90;
                """)
            conn.commit()
        finally:
            self._put_conn(conn)

    def close(self):
        if self._pool:
            self._pool.closeall()
            self._pool = None

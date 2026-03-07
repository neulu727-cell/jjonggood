"""SQLite 데이터베이스 관리자"""

import os
import sqlite3
import threading


class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._connection = None

    def initialize(self):
        """DB 파일 생성 및 테이블 초기화"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._connection = sqlite3.connect(self.db_path, check_same_thread=False, timeout=10)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._create_tables()

    def _create_tables(self):
        with self._lock:
            cursor = self._connection.cursor()
            cursor.executescript("""
                CREATE TABLE IF NOT EXISTS customers (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    name        TEXT DEFAULT '',
                    phone       TEXT NOT NULL UNIQUE,
                    pet_name    TEXT NOT NULL,
                    breed       TEXT NOT NULL,
                    weight      REAL,
                    age         TEXT,
                    notes       TEXT DEFAULT '',
                    memo        TEXT DEFAULT '',
                    created_at  DATETIME DEFAULT (datetime('now','localtime')),
                    updated_at  DATETIME DEFAULT (datetime('now','localtime'))
                );

                CREATE TABLE IF NOT EXISTS reservations (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_id   INTEGER NOT NULL,
                    date          DATE NOT NULL,
                    time          TIME NOT NULL,
                    service_type  TEXT NOT NULL,
                    duration      INTEGER DEFAULT 60,
                    request       TEXT DEFAULT '',
                    status        TEXT DEFAULT 'confirmed',
                    amount        INTEGER DEFAULT 0,
                    created_at    DATETIME DEFAULT (datetime('now','localtime')),
                    FOREIGN KEY (customer_id) REFERENCES customers(id)
                );

                CREATE TABLE IF NOT EXISTS service_types (
                    id                INTEGER PRIMARY KEY AUTOINCREMENT,
                    name              TEXT NOT NULL UNIQUE,
                    default_duration  INTEGER DEFAULT 60,
                    default_price     INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS groomer_memos (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    reservation_id  INTEGER NOT NULL,
                    content         TEXT NOT NULL,
                    created_at      DATETIME DEFAULT (datetime('now','localtime')),
                    FOREIGN KEY (reservation_id) REFERENCES reservations(id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS call_history (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    phone       TEXT NOT NULL,
                    customer_id INTEGER,
                    pet_name    TEXT DEFAULT '',
                    call_type   TEXT DEFAULT 'incoming',
                    created_at  DATETIME DEFAULT (datetime('now','localtime'))
                );

                CREATE TABLE IF NOT EXISTS reservation_edits (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    reservation_id  INTEGER NOT NULL,
                    field_name      TEXT NOT NULL,
                    old_value       TEXT DEFAULT '',
                    new_value       TEXT DEFAULT '',
                    created_at      DATETIME DEFAULT (datetime('now','localtime')),
                    FOREIGN KEY (reservation_id) REFERENCES reservations(id)
                        ON DELETE CASCADE
                );
            """)
            self._connection.commit()
            self._migrate(cursor)
            self._connection.commit()

    def _migrate(self, cursor):
        """기존 DB에 새 컬럼 추가 (없으면 무시)"""
        migrations = [
            "ALTER TABLE reservations ADD COLUMN groomer_memo TEXT DEFAULT ''",
            "ALTER TABLE reservations ADD COLUMN fur_length TEXT DEFAULT ''",
            "ALTER TABLE reservations ADD COLUMN completed_at DATETIME DEFAULT NULL",
            "CREATE INDEX IF NOT EXISTS idx_reservations_date ON reservations(date)",
            "CREATE INDEX IF NOT EXISTS idx_reservations_customer ON reservations(customer_id)",
            "CREATE INDEX IF NOT EXISTS idx_call_history_date ON call_history(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone)",
        ]
        for sql in migrations:
            try:
                cursor.execute(sql)
            except sqlite3.OperationalError:
                pass  # 이미 존재하면 무시

    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """INSERT, UPDATE, DELETE 등 쓰기 작업용"""
        with self._lock:
            cursor = self._connection.cursor()
            cursor.execute(query, params)
            self._connection.commit()
            return cursor

    def fetch_one(self, query: str, params: tuple = ()):
        """단일 행 조회"""
        with self._lock:
            cursor = self._connection.cursor()
            cursor.execute(query, params)
            return cursor.fetchone()

    def fetch_all(self, query: str, params: tuple = ()):
        """여러 행 조회"""
        with self._lock:
            cursor = self._connection.cursor()
            cursor.execute(query, params)
            return cursor.fetchall()

    def close(self):
        """연결 종료"""
        if self._connection:
            self._connection.close()
            self._connection = None

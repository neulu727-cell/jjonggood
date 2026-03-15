"""
Supabase DB 자동 백업 스크립트

컴퓨터 시작 시 실행되어 1시간마다 백업합니다.
- backup/ 폴더에 날짜별 SQL 파일 생성
- 모든 백업 파일 영구 보관

사용법:
    python backup_db.py

환경변수 (.env 파일):
    DATABASE_URL=postgresql://user:pass@host:port/dbname
"""

import os
import sys
import time
import subprocess
import urllib.parse
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKUP_DIR = os.path.join(BASE_DIR, "backup")
BACKUP_INTERVAL = 3600  # 1시간 (초)


def load_env():
    env_path = os.path.join(BASE_DIR, ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def parse_db_url(url):
    """DATABASE_URL을 파싱하여 pg_dump용 환경변수 딕셔너리 반환"""
    parsed = urllib.parse.urlparse(url)
    return {
        "host": parsed.hostname,
        "port": str(parsed.port or 5432),
        "dbname": parsed.path.lstrip("/"),
        "user": parsed.username,
        "password": parsed.password or "",
    }


def run_backup(db):
    """백업 1회 실행. 성공 시 파일명 반환, 실패 시 에러 메시지 반환"""
    now = datetime.now()
    filename = f"backup_{now.strftime('%Y%m%d_%H%M%S')}.sql"
    filepath = os.path.join(BACKUP_DIR, filename)

    env = os.environ.copy()
    env["PGPASSWORD"] = db["password"]

    cmd = [
        "pg_dump",
        "-h", db["host"],
        "-p", db["port"],
        "-U", db["user"],
        "-d", db["dbname"],
        "--no-owner",
        "--no-acl",
        "-f", filepath,
    ]

    print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] 백업 시작...")

    try:
        result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            size = os.path.getsize(filepath)
            print(f"  완료! ({size:,} bytes) → {filename}")
        else:
            print(f"  [ERROR] pg_dump 실패: {result.stderr.strip()}")
    except FileNotFoundError:
        print("  [ERROR] pg_dump를 찾을 수 없습니다.")
        print("  PostgreSQL 클라이언트를 설치하세요:")
        print("  https://www.postgresql.org/download/windows/")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print("  [ERROR] 백업 시간 초과 (120초)")


def main():
    load_env()

    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("[ERROR] DATABASE_URL이 설정되지 않았습니다. .env 파일을 확인하세요.")
        sys.exit(1)

    os.makedirs(BACKUP_DIR, exist_ok=True)
    db = parse_db_url(db_url)

    print("=" * 40)
    print("  DB 자동 백업 (1시간 간격)")
    print(f"  서버: {db['host']}:{db['port']}")
    print(f"  저장: {BACKUP_DIR}")
    print("=" * 40)

    # 시작 즉시 1회 백업 + 이후 1시간마다 반복
    while True:
        run_backup(db)
        time.sleep(BACKUP_INTERVAL)


if __name__ == "__main__":
    main()

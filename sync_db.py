"""
DB 동기화 스크립트 (가게 PC에서 실행)

SQLite DB 파일 변경을 감지해서 Render 서버로 자동 업로드.
데스크탑 앱(main.py)과 함께 실행하면 됨.

사용법:
  1. .env 파일에 설정 (또는 직접 아래 값 수정):
       RENDER_URL=https://내앱.onrender.com
       SYNC_KEY=내비밀키
  2. python sync_db.py
"""

import os
import sys
import time
import shutil
import requests

# 프로젝트 루트
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# === 설정 ===
RENDER_URL = os.environ.get("RENDER_URL", "").rstrip("/")
SYNC_KEY = os.environ.get("SYNC_KEY", "change-me")
DB_PATH = os.path.join(BASE_DIR, "data", "grooming_shop.db")
CHECK_INTERVAL = 30  # 초 (DB 변경 체크 주기)


def load_env():
    """프로젝트 루트의 .env 파일에서 환경변수 로드 (dotenv 없이)"""
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


def sync_db():
    """DB 파일을 Render 서버로 업로드."""
    # DB 파일 복사 (사용 중 잠금 방지)
    tmp_path = DB_PATH + ".sync_tmp"
    shutil.copy2(DB_PATH, tmp_path)

    try:
        with open(tmp_path, "rb") as f:
            resp = requests.post(
                f"{RENDER_URL}/api/sync",
                files={"db": ("grooming_shop.db", f)},
                headers={"X-Sync-Key": SYNC_KEY},
                timeout=30,
            )
        if resp.ok:
            data = resp.json()
            print(f"  동기화 완료: {data.get('size_kb', '?')}KB ({data.get('synced_at', '')})")
            return True
        else:
            print(f"  동기화 실패: HTTP {resp.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("  연결 실패 (Render 서버가 깨어나는 중일 수 있음)")
        return False
    except Exception as e:
        print(f"  오류: {e}")
        return False
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def main():
    global RENDER_URL, SYNC_KEY

    load_env()
    RENDER_URL = os.environ.get("RENDER_URL", RENDER_URL).rstrip("/")
    SYNC_KEY = os.environ.get("SYNC_KEY", SYNC_KEY)

    # 설정 확인
    if not RENDER_URL or RENDER_URL == "":
        print("오류: RENDER_URL이 설정되지 않았습니다.")
        print("  .env 파일에 RENDER_URL=https://내앱.onrender.com 추가하세요.")
        sys.exit(1)

    if SYNC_KEY == "change-me":
        print("경고: SYNC_KEY가 기본값입니다. .env에서 변경하세요.")

    if not os.path.exists(DB_PATH):
        print(f"오류: DB 파일을 찾을 수 없습니다: {DB_PATH}")
        sys.exit(1)

    print("=" * 50)
    print("  DB 동기화 시작")
    print(f"  DB: {DB_PATH}")
    print(f"  서버: {RENDER_URL}")
    print(f"  체크 주기: {CHECK_INTERVAL}초")
    print("  종료: Ctrl+C")
    print("=" * 50)

    last_mtime = 0

    # 시작할 때 한 번 즉시 동기화
    print("\n초기 동기화 중...")
    sync_db()
    last_mtime = os.path.getmtime(DB_PATH)

    # 변경 감지 루프
    while True:
        try:
            time.sleep(CHECK_INTERVAL)
            current_mtime = os.path.getmtime(DB_PATH)
            if current_mtime != last_mtime:
                now = time.strftime("%H:%M:%S")
                print(f"\n[{now}] DB 변경 감지!")
                if sync_db():
                    last_mtime = current_mtime
        except KeyboardInterrupt:
            print("\n동기화 종료.")
            break
        except Exception as e:
            print(f"  오류: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()

"""
ADB 전화 감지 → 웹앱 알림 브릿지

가게 PC에서 실행. 폰이 USB로 연결된 상태에서:
- ADB로 전화 수신 감지
- 웹앱 API로 전화번호 전송 (Tasker 대신)
- 브라우저에 알림 팝업 표시됨

사용법:
    python adb_bridge.py

환경변수 (.env 파일 또는 직접 설정):
    RENDER_URL=https://jjonggood.onrender.com
    TASKER_API_KEY=내비밀키
"""

import os
import re
import sys
import time
import subprocess
import urllib.request
import urllib.parse

# === 설정 ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
POLL_INTERVAL = 1.5  # 초
HEARTBEAT_INTERVAL = 60  # 초


def load_env():
    """프로젝트 루트의 .env 파일에서 환경변수 로드"""
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


def find_adb():
    """ADB 실행 경로 탐색 (PATH 또는 로컬 설치)"""
    # 로컬 platform-tools 폴더 확인
    local_adb = os.path.join(BASE_DIR, "platform-tools", "adb.exe")
    if os.path.exists(local_adb):
        return local_adb
    # PATH에서 탐색
    try:
        subprocess.run(["adb", "version"], capture_output=True, timeout=5)
        return "adb"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def check_adb(adb_cmd):
    """ADB 연결 상태 확인"""
    try:
        r = subprocess.run([adb_cmd, "devices"], capture_output=True, text=True, timeout=5)
        lines = r.stdout.strip().split("\n")
        for line in lines[1:]:
            if "\tdevice" in line:
                return True, line.split("\t")[0]
        return False, ""
    except FileNotFoundError:
        return False, ""
    except subprocess.TimeoutExpired:
        return False, ""


def send_to_web(render_url, api_key, phone_number):
    """웹앱에 전화 수신 알림 전송"""
    url = f"{render_url}/api/incoming-call?key={urllib.parse.quote(api_key, safe='')}"
    data = urllib.parse.urlencode({"phone": phone_number}).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                print(f"  → 웹앱 알림 전송 성공")
            else:
                print(f"  → 웹앱 응답: {resp.status}")
    except Exception as e:
        print(f"  → 웹앱 알림 실패: {e}")


def send_heartbeat(render_url, api_key, status, device=""):
    """서버에 하트비트 전송"""
    url = f"{render_url}/api/bridge-heartbeat?key={urllib.parse.quote(api_key, safe='')}"
    data = urllib.parse.urlencode({"status": status, "device": device}).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            pass
    except Exception:
        pass  # 하트비트 실패는 무시


def main():
    load_env()

    render_url = os.environ.get("RENDER_URL", "").rstrip("/")
    api_key = os.environ.get("TASKER_API_KEY", "")

    if not render_url:
        print("오류: RENDER_URL이 설정되지 않았습니다.")
        print("  .env 파일에 RENDER_URL=https://내앱.onrender.com 추가하세요.")
        sys.exit(1)

    if not api_key:
        print("오류: TASKER_API_KEY가 설정되지 않았습니다.")
        print("  .env 파일에 TASKER_API_KEY=내비밀키 추가하세요.")
        sys.exit(1)

    # ADB 실행파일 탐색
    adb_cmd = find_adb()
    if not adb_cmd:
        print("오류: ADB를 찾을 수 없습니다.")
        print("  platform-tools 폴더가 같은 디렉토리에 있는지 확인하세요.")
        sys.exit(1)

    print("=" * 50)
    print("  ADB 전화 감지 → 웹앱 알림 브릿지")
    print(f"  ADB: {adb_cmd}")
    print(f"  서버: {render_url}")
    print(f"  감지 주기: {POLL_INTERVAL}초")
    print("  종료: Ctrl+C")
    print("=" * 50)

    previous_state = 0
    last_heartbeat = 0

    while True:
        try:
            now = time.time()

            # ADB 연결 확인
            connected, device = check_adb(adb_cmd)

            # 하트비트 전송 (60초마다)
            if now - last_heartbeat > HEARTBEAT_INTERVAL:
                if connected:
                    send_heartbeat(render_url, api_key, "ok", device)
                    print(f"[{time.strftime('%H:%M:%S')}] ♥ 하트비트 (기기: {device})")
                else:
                    send_heartbeat(render_url, api_key, "no_device")
                    print(f"[{time.strftime('%H:%M:%S')}] ♥ 하트비트 (기기 없음 - 재시도 중)")
                last_heartbeat = now

            if not connected:
                time.sleep(POLL_INTERVAL)
                continue

            # 전화 상태 감지
            result = subprocess.run(
                [adb_cmd, "shell", "dumpsys", "telephony.registry"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                output = result.stdout
                state_match = re.search(r"mCallState=(\d+)", output)
                number_match = re.search(r"mCallIncomingNumber=([\d+\-]+)", output)

                if state_match:
                    current_state = int(state_match.group(1))

                    # 1(RINGING)으로 전환될 때만 감지
                    if current_state == 1 and previous_state != 1:
                        if number_match:
                            phone = number_match.group(1)
                            if phone and phone != "0":
                                ts = time.strftime("%H:%M:%S")
                                print(f"\n[{ts}] 전화 수신: {phone}")
                                send_to_web(render_url, api_key, phone)

                    previous_state = current_state

        except subprocess.TimeoutExpired:
            pass
        except KeyboardInterrupt:
            print("\n종료.")
            break
        except Exception as e:
            print(f"오류: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()

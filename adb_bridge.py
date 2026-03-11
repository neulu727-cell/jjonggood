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


def check_adb():
    """ADB 연결 상태 확인"""
    try:
        r = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=5)
        lines = r.stdout.strip().split("\n")
        for line in lines[1:]:
            if "\tdevice" in line:
                return True, line.split("\t")[0]
        return False, ""
    except FileNotFoundError:
        print("오류: adb가 설치되어 있지 않습니다.")
        sys.exit(1)
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

    # ADB 연결 확인
    connected, device = check_adb()
    if not connected:
        print("오류: ADB에 연결된 기기가 없습니다.")
        print("  폰을 USB로 연결하고, USB 디버깅을 활성화하세요.")
        sys.exit(1)

    print("=" * 50)
    print("  ADB 전화 감지 → 웹앱 알림 브릿지")
    print(f"  기기: {device}")
    print(f"  서버: {render_url}")
    print(f"  감지 주기: {POLL_INTERVAL}초")
    print("  종료: Ctrl+C")
    print("=" * 50)

    previous_state = 0

    while True:
        try:
            result = subprocess.run(
                ["adb", "shell", "dumpsys", "telephony.registry"],
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
                                now = time.strftime("%H:%M:%S")
                                print(f"\n[{now}] 전화 수신: {phone}")
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

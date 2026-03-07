"""ADB(USB)를 통한 전화 수신 감지"""

import re
import subprocess
import threading
import time

from phone.call_detector import CallDetector
import config


class AdbCallMonitor(CallDetector):
    """
    ADB를 통해 Android 전화 수신을 감지합니다.

    동작 방식:
    - `adb shell dumpsys telephony.registry` 명령을 주기적으로 실행
    - mCallState 값이 1(RINGING)으로 변경되면 전화 수신으로 판단
    - mCallIncomingNumber에서 발신자 번호를 추출하여 콜백 호출

    사전 조건:
    - Android 폰이 USB로 연결되어 있어야 함
    - 폰에서 '개발자 옵션' > 'USB 디버깅' 활성화 필요
    - PC에 adb가 설치되어 있어야 함 (Android SDK Platform Tools)
    """

    def __init__(self, callback, poll_interval=None):
        super().__init__(callback)
        self._poll_interval = poll_interval or config.ADB_POLL_INTERVAL
        self._thread = None
        self._previous_state = 0

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)

    def _poll_loop(self):
        """주기적으로 ADB를 통해 전화 상태를 확인"""
        while self._running:
            try:
                result = subprocess.run(
                    ["adb", "shell", "dumpsys", "telephony.registry"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    self._parse_output(result.stdout)
            except FileNotFoundError:
                break  # adb 미설치 - 루프 종료
            except subprocess.TimeoutExpired:
                pass
            except Exception as e:
                print(f"  ADB 감지 오류: {e}")

            time.sleep(self._poll_interval)

    def _parse_output(self, output: str):
        """dumpsys 출력에서 전화 상태와 번호 추출"""
        state_match = re.search(r"mCallState=(\d+)", output)
        number_match = re.search(r"mCallIncomingNumber=([\d+\-]+)", output)

        if not state_match:
            return

        current_state = int(state_match.group(1))

        # 상태가 1(RINGING)으로 전환될 때만 감지
        if current_state == 1 and self._previous_state != 1:
            if number_match:
                phone_number = number_match.group(1)
                if phone_number and phone_number != "0":
                    try:
                        self.callback(phone_number)
                    except Exception as e:
                        print(f"  전화 콜백 오류: {e}")

        self._previous_state = current_state


def check_adb_connection() -> dict:
    """ADB 연결 상태 확인. 디버깅/상태 표시용."""
    result = {"adb_installed": False, "device_connected": False, "device_name": ""}
    try:
        r = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=5)
        result["adb_installed"] = True
        lines = r.stdout.strip().split("\n")
        for line in lines[1:]:
            if "\tdevice" in line:
                result["device_connected"] = True
                result["device_name"] = line.split("\t")[0]
                break
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return result

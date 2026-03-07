"""전화 수신 시뮬레이션 테스트 스크립트

이 스크립트를 실행하면 실제 전화 없이도 전화 수신을 테스트할 수 있습니다.

사용법:
  python test_call.py              # 기본 테스트 번호로 테스트
  python test_call.py 01098765432  # 특정 번호로 테스트

Tasker 모드일 때는 HTTP 요청을 보내고,
ADB 모드일 때는 앱의 콜백을 직접 호출합니다.
"""

import sys
import requests


def test_tasker_call(phone: str = "01055551234", host: str = "127.0.0.1", port: int = 5000):
    """Tasker 서버에 테스트 전화 수신 요청 전송"""
    url = f"http://{host}:{port}/incoming-call"
    try:
        resp = requests.post(url, data={"phone": phone}, timeout=5)
        print(f"전송 완료! 상태: {resp.status_code}, 응답: {resp.text}")
    except requests.exceptions.ConnectionError:
        # requests 없으면 urllib로 시도
        print("requests 모듈 없음, urllib로 시도...")
        _test_with_urllib(url, phone)
    except Exception as e:
        print(f"오류: {e}")
        print("앱이 실행 중인지 확인해주세요.")


def _test_with_urllib(url, phone):
    import urllib.request
    import urllib.parse
    data = urllib.parse.urlencode({"phone": phone}).encode()
    try:
        req = urllib.request.Request(url, data=data)
        resp = urllib.request.urlopen(req, timeout=5)
        print(f"전송 완료! 상태: {resp.status}, 응답: {resp.read().decode()}")
    except Exception as e:
        print(f"오류: {e}")
        print("앱이 실행 중인지 확인해주세요.")


if __name__ == "__main__":
    phone = sys.argv[1] if len(sys.argv) > 1 else "01055551234"
    print(f"테스트 전화 시뮬레이션: {phone}")
    test_tasker_call(phone)

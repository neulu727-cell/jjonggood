"""Tasker HTTP 웹훅을 수신하는 Flask 서버"""

import threading
import socket
from flask import Flask, request

from phone.call_detector import CallDetector
import config


class TaskerCallServer(CallDetector):
    """
    Tasker에서 보내는 HTTP 요청을 수신하여 전화번호를 추출합니다.

    동작 방식:
    - Flask 서버가 백그라운드 스레드에서 실행
    - POST /incoming-call 엔드포인트에서 전화번호 수신
    - 전화번호를 추출하여 콜백 호출

    Tasker 설정:
    1. Profile: Event > Phone > Phone Ringing
    2. Task: Net > HTTP Request
       - Method: POST
       - URL: http://<PC_IP>:5000/incoming-call
       - Body: phone=%CNUM
       - Content Type: application/x-www-form-urlencoded
    """

    def __init__(self, callback, host=None, port=None):
        super().__init__(callback)
        self._host = host or config.TASKER_SERVER_HOST
        self._port = port or config.TASKER_SERVER_PORT
        self._thread = None
        self._app = Flask(__name__)
        self._setup_routes()

    def _setup_routes(self):
        @self._app.route("/incoming-call", methods=["POST", "GET"])
        def handle_incoming_call():
            # POST body 또는 URL 파라미터에서 번호 추출
            phone = request.form.get("phone") or request.args.get("phone") or ""
            if not phone and request.is_json and request.json:
                phone = request.json.get("phone", "")
            if phone:
                try:
                    self.callback(phone)
                except Exception as e:
                    print(f"  Tasker 콜백 오류: {e}")
                    return "Callback error", 500
                return "OK", 200
            return "No phone number provided", 400

        @self._app.route("/health", methods=["GET"])
        def health_check():
            return "Running", 200

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=lambda: self._app.run(
                host=self._host,
                port=self._port,
                use_reloader=False,
                debug=False,
            ),
            daemon=True,
        )
        self._thread.start()

    def stop(self):
        self._running = False
        # Flask 데몬 스레드는 프로세스 종료 시 자동 정리됨


def get_local_ip() -> str:
    """PC의 로컬 IP 주소를 반환 (Tasker 설정용)"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

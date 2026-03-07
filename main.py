"""애견미용샵 예약관리 시스템 - 메인 진입점"""

# Windows DPI 스케일링 보정 (tkinter/CTk 임포트 전에 실행)
import sys
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

import config
from database.db_manager import DatabaseManager
from database.queries import init_default_services
from phone.call_detector import create_call_detector


def main():
    # 1. 데이터베이스 초기화
    db = DatabaseManager(config.DB_PATH)
    db.initialize()
    init_default_services(db, config.DEFAULT_SERVICES)

    print(f"  {config.WINDOW_TITLE} 시작...")
    print(f"  DB: {config.DB_PATH}")
    print(f"  감지 방식: {config.DETECTION_METHOD}")

    # 2. UI 시작
    from ui.app_window import AppWindow
    app = AppWindow(db)

    # 3. 전화 감지 시작
    detector = create_call_detector(config.DETECTION_METHOD, app.on_call_detected)
    detector.start()

    method_name = "ADB (USB)" if config.DETECTION_METHOD == "adb" else "Tasker (WiFi)"
    app.main_screen.status_indicator.set_listening(method_name)
    print(f"  전화 감지 시작: {method_name}")

    if config.DETECTION_METHOD == "tasker":
        from phone.tasker_server import get_local_ip
        ip = get_local_ip()
        print(f"  Tasker URL: http://{ip}:{config.TASKER_SERVER_PORT}/incoming-call")

    # 4. 앱 실행
    app.mainloop()

    # 5. 종료
    detector.stop()
    db.close()
    print("  앱 종료.")


if __name__ == "__main__":
    main()

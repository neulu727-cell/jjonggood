"""전화 감지 추상 클래스 및 팩토리"""

from abc import ABC, abstractmethod
from typing import Callable


class CallDetector(ABC):
    """전화 감지의 공통 인터페이스"""

    def __init__(self, callback: Callable[[str], None]):
        """
        Args:
            callback: 전화번호(str)를 인자로 받는 콜백 함수.
                      전화 수신 감지 시 호출됨.
        """
        self.callback = callback
        self._running = False

    @abstractmethod
    def start(self):
        """백그라운드 스레드에서 전화 감지 시작"""
        pass

    @abstractmethod
    def stop(self):
        """전화 감지 중지"""
        pass

    @property
    def is_running(self) -> bool:
        return self._running


def create_call_detector(method: str, callback: Callable[[str], None]) -> CallDetector:
    """설정에 따라 적절한 감지기 생성"""
    if method == "adb":
        from phone.adb_monitor import AdbCallMonitor
        return AdbCallMonitor(callback)
    elif method == "tasker":
        from phone.tasker_server import TaskerCallServer
        return TaskerCallServer(callback)
    else:
        raise ValueError(f"지원하지 않는 감지 방식: {method}")

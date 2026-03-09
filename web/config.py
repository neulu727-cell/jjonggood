"""웹 앱 설정"""

import os

# === 데이터베이스 ===
DATABASE_URL = os.environ.get("DATABASE_URL", "")

# === 인증 ===
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
VIEWER_PASSWORD = os.environ.get("VIEWER_PASSWORD", "")
TASKER_API_KEY = os.environ.get("TASKER_API_KEY", "")

# === 미용 서비스 종류 (이름, 기본소요시간(분), 기본가격(원)) ===
DEFAULT_SERVICES = [
    ("위생목욕", 60, 30000),
    ("전체미용", 120, 50000),
    ("전체얼컷", 90, 45000),
    ("스포팅", 120, 60000),
]

# === 털 길이 옵션 ===
FUR_LENGTHS = ["3mm", "6mm", "9mm", "13mm", "1cm", "2cm"]

# === 영업 시간 ===
BUSINESS_HOURS_START = "10:00"
BUSINESS_HOURS_END = "19:00"
TIME_SLOT_INTERVAL = 30  # 분 단위

# === 견종 목록 (자주 사용되는 견종) ===
COMMON_BREEDS = [
    "말티즈", "말티푸", "푸들", "토이푸들", "미니푸들",
    "비숑 프리제", "포메라니안", "시츄", "요크셔테리어", "치와와",
    "미니어처 슈나우저", "코커스패니얼", "골든리트리버", "진돗개",
    "웰시코기", "닥스훈트", "비글", "프렌치불독", "시바이누",
    "스피츠", "페키니즈", "파피용", "보더콜리", "래브라도 리트리버",
    "사모예드", "허스키", "믹스견",
]

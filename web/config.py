"""웹 앱 설정"""

import os
from dotenv import load_dotenv
load_dotenv()

# === 데이터베이스 ===
DATABASE_URL = os.environ.get("DATABASE_URL", "")

# === 인증 ===
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
VIEWER_PASSWORD = os.environ.get("VIEWER_PASSWORD", "")
TASKER_API_KEY = os.environ.get("TASKER_API_KEY", "")

# === 관리자 비밀 경로 ===
ADMIN_SECRET_PATH = os.environ.get("ADMIN_SECRET_PATH", "mgmt-x7k9m2p4")

# === Google OAuth ===
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")

# === 미용 서비스 종류 (이름, 기본소요시간(분), 기본가격(원)) ===
DEFAULT_SERVICES = [
    ("위생목욕", 60, 30000),
    ("전체미용", 120, 50000),
    ("전체얼컷", 90, 45000),
    ("스포팅", 120, 60000),
    ("기타", 30, 0),
]

# === 털 길이 옵션 ===
FUR_LENGTHS = ["3mm", "6mm", "9mm", "13mm", "1cm", "2cm"]

# === 견적 계산기 요금표 ===
PRICE_TABLE = {
    (1, 3):   {"위생목욕": 35000, "전체미용": 45000, "전체얼컷": 60000, "스포팅": 100000},
    (3, 5):   {"위생목욕": 40000, "전체미용": 50000, "전체얼컷": 65000, "스포팅": 105000},
    (5, 7):   {"위생목욕": 45000, "전체미용": 55000, "전체얼컷": 70000, "스포팅": 110000},
    (7, 9):   {"위생목욕": 50000, "전체미용": 60000, "전체얼컷": 75000, "스포팅": 115000},
    (9, 11):  {"위생목욕": 60000, "전체미용": 70000, "전체얼컷": 85000, "스포팅": 125000},
    (11, 13): {"위생목욕": 70000, "전체미용": 80000, "전체얼컷": 95000, "스포팅": 135000},
    (13, 15): {"위생목욕": 80000, "전체미용": 90000, "전체얼컷": 105000, "스포팅": 145000},
}

SURCHARGES = {
    "clipping_1.3cm": 10000,
    "clipping_2cm": 20000,
    "face_cut": 15000,
    "matting_light": 5000,
    "matting_heavy": 10000,
    "fur_medium": 5000,
    "fur_long": 10000,
}

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

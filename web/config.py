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

# === 샵 연락처 (견적 상담 연결용) ===
SHOP_PHONE = os.environ.get("SHOP_PHONE", "01084247395")
SHOP_KAKAO_URL = os.environ.get("SHOP_KAKAO_URL", "http://pf.kakao.com/qjNxhX/chat")
SHOP_NAVER_URL = os.environ.get("SHOP_NAVER_URL", "https://talk.naver.com/WILRAWG")

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
    "일반": {
        (0, 4):  {"위생목욕": 35000, "클리핑": 45000, "클리핑+얼굴컷": 60000, "스포팅": 100000},
        (4, 6):  {"위생목욕": 40000, "클리핑": 50000, "클리핑+얼굴컷": 65000, "스포팅": 105000},
        (6, 8):  {"위생목욕": 45000, "클리핑": 55000, "클리핑+얼굴컷": 70000, "스포팅": 110000},
        (8, 10): {"위생목욕": 55000, "클리핑": 65000, "클리핑+얼굴컷": 80000, "스포팅": 115000},
    },
    "비숑": {
        (0, 4):  {"위생목욕": 45000, "클리핑": 45000, "클리핑+비숑컷": 80000, "스포팅": 110000},
        (4, 6):  {"위생목욕": 50000, "클리핑": 50000, "클리핑+비숑컷": 85000, "스포팅": 115000},
        (6, 8):  {"위생목욕": 55000, "클리핑": 55000, "클리핑+비숑컷": 90000, "스포팅": 120000},
        (8, 10): {"위생목욕": 65000, "클리핑": 65000, "클리핑+비숑컷": 95000, "스포팅": 125000},
    },
}

SURCHARGES = {
    "clipping_13mm": 10000,
    "clipping_20mm": 20000,
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

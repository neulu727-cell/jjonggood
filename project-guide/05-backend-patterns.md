# 백엔드 아키텍처 & API 패턴

## 기술 스택

- **Flask** (Python 웹 프레임워크)
- **PostgreSQL** (Supabase 호스팅)
- **psycopg2** (DB 드라이버, 커넥션 풀링)
- **gevent** (SSE 블로킹 해결용 워커)
- **Cloudtype** (배포 플랫폼)

---

## 프로젝트 구조

```
web/
├── app.py              # Flask 앱 생성, get_db(), require_auth
├── queries.py          # 모든 SQL 쿼리 함수 (ORM 없음)
├── routes_customer.py  # 고객 CRUD API (Blueprint)
├── routes_reservation.py  # 예약 CRUD API (Blueprint)
├── utils/
│   └── phone_formatter.py  # 전화번호 정규화/포맷
├── templates/
│   └── index.html      # SPA 메인 페이지
└── static/
    ├── app.js          # 프론트엔드 전체 로직
    └── style.css       # 디자인 시스템
```

---

## API 설계 원칙

### URL 패턴
```
GET    /api/customers/search?q=키워드&sort=name|recent
POST   /api/customer                    # 생성
GET    /api/customer/<id>               # 상세 조회
PUT    /api/customer/<id>               # 수정
DELETE /api/customer/<id>               # 삭제
GET    /api/customer/by-phone?phone=    # 전화번호로 조회

POST   /api/reservation                 # 예약 생성
GET    /api/reservation/<id>            # 예약 상세
PUT    /api/reservation/<id>            # 예약 수정
PUT    /api/reservation/<id>/status     # 상태 변경
PUT    /api/reservation/<id>/memo       # 메모 업데이트
GET    /api/reservation/<id>/edits      # 수정 이력
```

### 응답 형식
```json
// 성공
{"ok": true, "id": 42}

// 에러
{"error": "유효한 전화번호를 입력하세요"}, 400

// 목록
{"customers": [...]}
{"reservations": [...]}
```

---

## 데이터 모델

### customers 테이블
```sql
id          SERIAL PRIMARY KEY
name        VARCHAR(50)     -- 보호자 이름 (선택)
phone       VARCHAR(20)     -- 전화번호 (필수, 정규화됨: 01012345678)
pet_name    VARCHAR(50)     -- 강아지 이름 (필수)
breed       VARCHAR(50)     -- 견종 (선택)
weight      FLOAT           -- 몸무게 (선택)
age         VARCHAR(20)     -- 나이 (사용 안 함, 레거시)
notes       TEXT            -- 특이사항 (memo로 통합됨, 레거시)
memo        TEXT            -- 통합 메모
-- UNIQUE(phone, pet_name) → 같은 보호자의 같은 이름 강아지 불가
```

### reservations 테이블
```sql
id              SERIAL PRIMARY KEY
customer_id     INTEGER REFERENCES customers
date            DATE
time            VARCHAR(5)      -- "09:00"
service_type    VARCHAR(50)
duration        INTEGER         -- 분 단위
amount          INTEGER         -- 원 단위
quoted_amount   INTEGER         -- 상담 금액 (레거시, 사용 안 함)
payment_method  VARCHAR(30)     -- 카드/현금 (완료 시 입력)
fur_length      VARCHAR(20)     -- 털 길이
request         TEXT            -- 요청사항
groomer_memo    TEXT            -- 미용사 메모
status          VARCHAR(20)     -- confirmed/completed/cancelled/no_show
completed_at    TIMESTAMP
```

### 레거시 필드 참고
- `age`: UI에서 제거됨. 입력 안 받지만 DB에 존재
- `notes`: `memo`로 통합됨. DB에 존재하지만 빈값
- `quoted_amount`: `amount`로 통합됨. DB에 존재하지만 0

---

## 쿼리 패턴

### N+1 쿼리 방지
```python
# ❌ 고객마다 방문 수 개별 조회
for c in customers:
    count = db.fetch_one("SELECT COUNT(*) FROM reservations WHERE customer_id=?", (c.id,))

# ✅ JOIN으로 한번에 조회
SELECT c.*, COUNT(CASE WHEN r.status='completed' THEN 1 END) AS visit_count
FROM customers c LEFT JOIN reservations r ON r.customer_id = c.id
GROUP BY c.id
```

### 멀티펫 통계 (같은 보호자)
```python
# 같은 전화번호의 모든 강아지 ID를 모아서 한번에 조회
customer_ids = [cu.id for cu in customers]
placeholders = ",".join("?" for _ in customer_ids)
stats = db.fetch_one(f"""
    SELECT COUNT(*) as cnt, MAX(CASE WHEN status='completed' THEN date END) as last_visit
    FROM reservations WHERE customer_id IN ({placeholders})
""", tuple(customer_ids))
```

### 안전한 타입 변환
```python
def _safe_float(val):
    if not val and val != 0:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
```

---

## 전화번호 처리

### 정규화 (저장용)
```python
normalize_phone("010-1234-5678")  → "01012345678"
normalize_phone("010 1234 5678")  → "01012345678"
```

### 표시용 포맷
```python
format_phone_display("01012345678")  → "010-1234-5678"
```

API 응답에 `phone` (정규화)과 `phone_display` (하이픈) 둘 다 제공.

---

## 인증

```python
@require_auth
def my_endpoint():
    ...
```
- 간단한 토큰 기반 인증
- `bridge-status` API는 인증 제외 (설치 페이지 접근 허용)

---

## 예약 수정 이력

```python
def update_reservation_with_history(db, rid, **fields):
    # 변경 전 값 저장 → reservation_edits 테이블에 기록
    # 변경 적용
```
모든 예약 수정은 이력 남김. 언제 뭐가 바뀌었는지 추적 가능.

---

## 상태 변경 흐름

```python
@reservation_bp.route("/api/reservation/<int:rid>/status", methods=["PUT"])
def update_status(rid):
    status = data.get("status")
    if status == "cancelled":
        queries.delete_reservation(db, rid)      # 취소 = 삭제
    else:
        queries.update_reservation_status(db, rid, status)
        if payment_method:                         # 완료 시 결제방법
            queries.update_reservation_with_history(db, rid, payment_method=payment_method)
```

- cancelled → 예약 자체를 삭제
- completed → 상태 변경 + 결제방법 저장
- no_show → 상태만 변경

---

## DB 연결 최적화

```python
# keepalive로 죽은 연결 감지
# 시작 시 미리 연결 (lazy init 아님)
# 커넥션 풀링으로 요청마다 연결 생성 방지
```

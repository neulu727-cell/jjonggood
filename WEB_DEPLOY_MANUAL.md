# 웹 버전 배포 매뉴얼

PC 프로그램 → 웹으로 전환 완료. 이 매뉴얼대로 하면 **폰 브라우저만으로** 어디서든 예약관리 가능.

월 비용: **0원** (Supabase 무료 + Render 무료)

---

## 1단계: Supabase DB 생성 (5분)

1. https://supabase.com 접속 → **Start your project** → GitHub 계정으로 가입
2. **New Project** 클릭
   - Organization: 기본값
   - Name: `jjonggood` (아무거나)
   - Database Password: 기억할 수 있는 비번 입력 (나중에 필요)
   - Region: **Northeast Asia (Tokyo)** 선택
   - **Create new project** 클릭
3. 프로젝트 생성 완료되면 (1~2분 대기)
4. 왼쪽 메뉴 **Project Settings** (⚙️) → **Database**
5. **Connection string** 섹션에서 **URI** 탭 클릭
6. 연결 문자열 복사 (아래 형태):
   ```
   postgresql://postgres.xxxxx:[YOUR-PASSWORD]@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres
   ```
7. `[YOUR-PASSWORD]` 부분을 **아까 입력한 비밀번호**로 바꿔서 메모장에 저장

---

## 2단계: GitHub에 코드 푸시 (5분)

GitHub 계정이 없으면 https://github.com 에서 가입.

### 방법 A: GitHub에서 직접 (쉬움)

1. https://github.com/new → Repository name: `jjonggood`
2. **Private** 선택 → **Create repository**
3. PC에서 명령 프롬프트 열기:

```bash
cd E:\jjonggood
git remote add origin https://github.com/내아이디/jjonggood.git
git add web/ Procfile render.yaml
git commit -m "웹 버전 배포"
git push -u origin master
```

> GitHub 로그인 창이 뜨면 로그인

---

## 3단계: Render 배포 (10분)

1. https://render.com 접속 → **Get Started for Free** → GitHub 계정으로 가입
2. Dashboard → **New** → **Web Service**
3. **Connect a repository** → GitHub 연결 → `jjonggood` 선택
4. 설정 화면:
   - **Name**: `jjonggood` (이게 URL이 됨: `jjonggood.onrender.com`)
   - **Region**: Singapore (가장 가까움)
   - **Branch**: `master`
   - **Build Command**: `pip install -r web/requirements.txt`
   - **Start Command**: `gunicorn 'web.app:create_app()' --bind 0.0.0.0:$PORT --workers 2 --timeout 120`
   - **Instance Type**: **Free** 선택

5. **Environment Variables** (환경변수) 추가 — 5개:

| Key | Value | 설명 |
|-----|-------|------|
| `DATABASE_URL` | 1단계에서 복사한 연결 문자열 | Supabase DB 주소 |
| `SECRET_KEY` | 아무 긴 문자열 (예: `mYsEcRet123!@#abcXYZ`) | 세션 암호화 키 |
| `VIEWER_PASSWORD` | 로그인 비밀번호 (예: `myshop2024!`) | **"0000" 사용 불가** |
| `TASKER_API_KEY` | 아무 비밀 키 (예: `tasker-key-abc123`) | Tasker 인증용 |
| `TZ` | `Asia/Seoul` | 한국 시간대 |

6. **Deploy Web Service** 클릭
7. 빌드 로그 확인 — 3~5분 소요
8. 완료되면 `https://jjonggood.onrender.com` 으로 접속 가능

### 배포 확인

- `https://jjonggood.onrender.com/health` 접속 → **OK** 표시되면 성공
- `https://jjonggood.onrender.com` 접속 → 로그인 화면 나오면 성공
- 환경변수에 설정한 `VIEWER_PASSWORD`로 로그인

---

## 4단계: 기존 데이터 이관 (5분)

기존 PC에 있는 예약/고객 데이터를 웹 DB로 옮기기.

### PC에서 실행 (명령 프롬프트):

```bash
cd E:\jjonggood
venv\Scripts\activate
set DATABASE_URL=postgresql://postgres.xxxxx:비밀번호@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres
pip install psycopg2-binary
python -m web.migrate_data data/grooming_shop.db
```

### 정상 출력 예시:

```
SQLite: data/grooming_shop.db
PostgreSQL: postgresql://postgres.xxxxx...
고객: 42건
예약: 187건
서비스: 4건
메모: 23건
전화이력: 156건
수정이력: 12건
이관 완료!
```

> 이미 이관한 데이터를 다시 이관해도 중복 삽입 안 됨 (ON CONFLICT DO NOTHING)

---

## 5단계: UptimeRobot 설정 — 서버 슬립 방지 (3분)

Render 무료 서버는 15분간 요청 없으면 잠듦. UptimeRobot이 5분마다 깨워줌.

1. https://uptimerobot.com 접속 → **Register for FREE**
2. 가입 완료 후 Dashboard → **+ Add New Monitor**
3. 설정:
   - Monitor Type: **HTTP(s)**
   - Friendly Name: `jjonggood`
   - URL: `https://jjonggood.onrender.com/health`
   - Monitoring Interval: **5 minutes**
4. **Create Monitor** 클릭

> 이제 서버가 안 잠들어서 항상 빠르게 접속 가능

---

## 6단계: Tasker 전화 알림 설정 (폰, 5분)

전화가 오면 웹 브라우저에 알림 팝업을 띄우는 기능.

### Tasker 앱 설정 (Android):

1. **프로필 탭** → **+** → **이벤트** → **전화** → **전화 수신** → 뒤로
2. 새 태스크 이름: `웹훅` → 체크
3. **+** → **네트워크** → **HTTP 요청**:
   - 방식: **POST**
   - URL: `https://jjonggood.onrender.com/api/incoming-call?key=tasker-key-abc123`
     (key= 뒤에 환경변수 `TASKER_API_KEY`에 설정한 값)
   - Body: `phone=%CNUM`
   - Content Type: `application/x-www-form-urlencoded`
4. 뒤로 → 완료

### 테스트:

다른 폰으로 전화 걸기 → 웹 브라우저에 알림 팝업이 뜨면 성공.

---

## 사용법 요약

### 접속
- 폰 브라우저에서 `https://jjonggood.onrender.com` 접속
- 비밀번호 입력 → **"이 기기 기억하기"** 체크하면 30일간 자동 로그인

### 주요 기능
| 기능 | 방법 |
|------|------|
| 예약 등록 | 캘린더에서 날짜 탭 → 타임라인에서 빈 슬롯 **+** 탭 |
| 예약 확인/수정 | 타임라인에서 예약 카드 탭 |
| 완료/취소/노쇼 | 예약 상세에서 상태 버튼 |
| 고객 관리 | 하단 **고객** 탭 → 검색/등록/수정 |
| 백업 | 헤더 오른쪽 ⬇️ 아이콘 → JSON 파일 다운로드 |
| 전화 알림 | 자동 (Tasker 설정 완료 시) |

### 보안
- 비밀번호 5회 연속 오입력 → **10분간 차단**
- "이 기기 기억하기" 체크 → 30일간 로그인 유지
- 백업 다운로드 시 로그인 필수

---

## 문제 해결

| 증상 | 해결 |
|------|------|
| 접속 시 로딩 오래 걸림 (30초~) | UptimeRobot 설정 확인 (5단계) |
| "비밀번호가 틀렸습니다" | 환경변수 `VIEWER_PASSWORD` 값 확인 |
| "잠시 후 다시 시도하세요" | 5회 실패로 10분 차단됨, 기다리기 |
| 서버 에러 (500) | Render Dashboard → Logs 확인 |
| DB 연결 실패 | `DATABASE_URL` 환경변수 확인, Supabase 프로젝트 활성 상태 확인 |
| 전화 알림 안 뜸 | Tasker URL/API키 확인, 브라우저 알림 권한 허용 |
| 데이터 이관 실패 | `DATABASE_URL` 오타 확인, `psycopg2-binary` 설치 확인 |

---

## 비용

| 서비스 | 플랜 | 월 비용 | 제한 |
|--------|------|---------|------|
| Supabase | Free | 0원 | DB 500MB |
| Render | Free | 0원 | 750시간/월 |
| UptimeRobot | Free | 0원 | 50개 모니터 |
| **합계** | | **0원** | |

---

## 나중에 코드 수정 후 재배포

PC에서:
```bash
cd E:\jjonggood
git add web/
git commit -m "수정 내용"
git push
```

Render가 자동으로 감지해서 재배포함 (3~5분).

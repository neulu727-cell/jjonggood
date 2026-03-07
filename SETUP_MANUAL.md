# 애견미용샵 예약관리 시스템 - 설치 및 사용 매뉴얼

---

## 1. 준비물

| 항목 | 설명 |
|------|------|
| PC (Windows) | Windows 10/11, 1366x768 이상 해상도 |
| Android 폰 | USB 디버깅 가능한 폰 |
| USB 케이블 | 데이터 전송 가능한 케이블 (충전전용 X) |
| Python | 3.10 이상 (3.12 권장) |

---

## 2. PC 환경 설정

### 2-1. Python 설치

1. https://www.python.org/downloads/ 에서 Python 다운로드
2. 설치 시 **"Add Python to PATH"** 반드시 체크
3. 설치 확인:
```
python --version
```

### 2-2. 프로젝트 의존성 설치

프로젝트 폴더(`E:\jjonggood`)에서 명령 프롬프트 열기:

```bash
cd E:\jjonggood
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

**설치되는 패키지:**
- `customtkinter` - UI 프레임워크
- `tkcalendar` - 캘린더 위젯
- `flask` - Tasker 모드 서버

---

## 3. ADB 설치 (USB 전화감지용)

### 3-1. ADB 다운로드

1. 구글에서 **"Android SDK Platform Tools 다운로드"** 검색
   - 또는 직접: https://developer.android.com/studio/releases/platform-tools
2. **Windows용** ZIP 다운로드
3. `C:\adb` 폴더에 압축 해제 (폴더 안에 `adb.exe`가 있어야 함)

### 3-2. ADB를 시스템 PATH에 추가

1. **윈도우 키** → "환경 변수" 검색 → **"시스템 환경 변수 편집"** 클릭
2. **"환경 변수"** 버튼 클릭
3. **시스템 변수**에서 `Path` 선택 → **편집**
4. **새로 만들기** → `C:\adb` 입력 → **확인**
5. 확인 누르기

### 3-3. ADB 설치 확인

새 명령 프롬프트를 열고:
```
adb version
```
버전이 나오면 성공.

---

## 4. Android 폰 설정 (ADB용)

### 4-1. 개발자 옵션 활성화

1. **설정** → **휴대전화 정보** (또는 **소프트웨어 정보**)
2. **빌드번호**를 **7번 연속** 터치
3. "개발자 모드가 활성화되었습니다" 메시지 확인

### 4-2. USB 디버깅 켜기

1. **설정** → **개발자 옵션**
2. **USB 디버깅** 활성화 (ON)
3. 보안 경고가 뜨면 **확인** 터치

### 4-3. PC와 연결

1. USB 케이블로 폰과 PC 연결
2. 폰에 **"USB 디버깅을 허용하시겠습니까?"** 팝업이 뜸
3. **"이 컴퓨터에서 항상 허용"** 체크 → **허용** 터치

### 4-4. 연결 확인

PC 명령 프롬프트에서:
```
adb devices
```

**정상 출력:**
```
List of devices attached
XXXXXXXX    device
```

**문제 시:**
- `unauthorized` → 폰에서 USB 디버깅 허용 팝업 확인
- `offline` → USB 케이블 뽑았다 다시 연결
- 아무것도 안 나옴 → 케이블이 데이터 전송용인지 확인, 드라이버 설치 필요할 수 있음

### 4-5. 전화 감지 테스트

```
adb shell dumpsys telephony.registry | findstr mCallState
```
- `mCallState=0` → 대기 상태 (정상)
- `mCallState=1` → 전화 오는 중

---

## 5. 프로그램 설정

### 5-1. config.py 확인

`E:\jjonggood\config.py` 파일에서 주요 설정:

```python
# 전화 감지 방식 선택
DETECTION_METHOD = "adb"        # ADB(USB) 사용 시
# DETECTION_METHOD = "tasker"   # Tasker(WiFi) 사용 시

# ADB 감지 간격 (초)
ADB_POLL_INTERVAL = 1.5

# 영업 시간
BUSINESS_HOURS_START = "09:00"
BUSINESS_HOURS_END = "19:00"
TIME_SLOT_INTERVAL = 30         # 30분 간격

# UI 테마
APPEARANCE_MODE = "light"       # "light" 또는 "dark"
```

---

## 6. 프로그램 실행

### 6-1. 실행 방법

```bash
cd E:\jjonggood
venv\Scripts\activate
python main.py
```

### 6-2. 정상 실행 시 콘솔 출력

```
  🐾 애견미용샵 예약관리 시작...
  DB: E:\jjonggood\data\grooming_shop.db
  감지 방식: adb
  전화 감지 시작: ADB (USB)
```

### 6-3. 빠른 실행 (바탕화면 바로가기)

1. 바탕화면에서 우클릭 → **새로 만들기** → **바로 가기**
2. 위치에 다음 입력:
```
cmd /k "cd /d E:\jjonggood && venv\Scripts\activate && python main.py"
```
3. 이름: `예약관리` → 마침

---

## 7. 사용 방법

### 7-1. 전화 수신 시

1. 전화가 오면 **팝업**이 자동으로 뜸
2. **재방문 고객**: 이름/펫 정보 표시 → **"예약하기"** 클릭
3. **신규 고객**: 전화번호만 표시 → **"고객등록"** 클릭

### 7-2. 예약하기 (재방문)

1. 팝업에서 **"예약하기"** 클릭
2. 상단에 "OO 예약 중 - 시간 선택" 표시됨
3. 캘린더에서 **날짜 선택**
4. 타임라인에서 **빈 시간대(초록색)** 클릭
5. 서비스/금액 입력 후 **"예약 확정"**

### 7-3. 고객 등록 (신규)

1. 팝업에서 **"고객등록"** 클릭
2. 고객정보 입력 (펫이름, 견종, 전화번호 등)
3. 저장하면 자동으로 예약 모드로 전환

### 7-4. 수동 예약/검색

- **고객 검색**: 사이드바 "고객 검색" 버튼
- **예약 등록**: 사이드바 "예약 등록" 버튼
- **고객 등록**: 사이드바 "고객 등록" 버튼

### 7-5. 예약 관리

- 타임라인에서 **예약된 시간대(파란색)** 클릭
- **미용 완료** / **예약 취소** / **노쇼 처리** 선택

### 7-6. 타임라인 색상 안내

| 색상 | 의미 |
|------|------|
| 초록 배경 | 빈 시간대 (예약 가능) |
| 파란 배경 | 확정된 예약 |
| 연두 배경 | 완료된 예약 |

---

## 8. Tasker 모드 (WiFi 무선 감지)

USB 연결 없이 WiFi로 전화 감지하려면:

### 8-1. config.py 변경

```python
DETECTION_METHOD = "tasker"
```

### 8-2. Tasker 앱 설치 (안드로이드)

1. Play 스토어에서 **Tasker** 설치 (유료)
2. Tasker 실행 → 권한 허용

### 8-3. Tasker 프로필 설정

1. **프로필 탭** → **+** → **이벤트** → **전화** → **전화 수신**
2. 태스크 만들기:
   - **+** → **네트워크** → **HTTP 요청**
   - 방식: `POST`
   - URL: `http://PC의IP:5000/incoming-call`
   - Body: `phone=%CNUM`
   - Content Type: `application/x-www-form-urlencoded`

### 8-4. PC IP 확인

프로그램 실행 시 콘솔에 표시됨:
```
Tasker URL: http://192.168.0.XX:5000/incoming-call
```

---

## 9. 테스트

### 전화 수신 시뮬레이션

```bash
python test_call.py                  # 기본 번호로 테스트
python test_call.py 01012345678      # 특정 번호로 테스트
```

### ADB 연결 상태 확인

```
adb devices
```

---

## 10. 문제 해결

| 증상 | 해결 |
|------|------|
| 프로그램 창이 화면 밖에 표시됨 | Windows 디스플레이 배율 확인 (125% 권장) |
| ADB 연결 안 됨 | USB 케이블 교체, 폰 USB 디버깅 재활성화 |
| `adb devices`에서 unauthorized | 폰 잠금 해제 후 USB 디버깅 허용 팝업 확인 |
| 전화가 와도 팝업 안 뜸 | 콘솔에서 "전화 감지 시작" 메시지 확인, `adb devices` 확인 |
| 데이터베이스 오류 | `data/grooming_shop.db` 파일 삭제 후 재실행 (초기화) |
| pip install 실패 | `venv\Scripts\activate` 했는지 확인 |
| Tasker 전화 감지 안 됨 | PC와 폰이 같은 WiFi인지 확인, 방화벽 포트 5000 허용 |

---

## 11. 다른 PC/폰에서 새로 세팅할 때 요약

```
1. Python 설치 (PATH 추가)
2. ADB 설치 (C:\adb, PATH 추가)
3. 프로젝트 폴더 복사
4. cmd에서:
   cd E:\jjonggood
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
5. 폰: 개발자 옵션 → USB 디버깅 ON
6. USB 연결 → 폰에서 허용
7. adb devices 로 연결 확인
8. python main.py 실행
```

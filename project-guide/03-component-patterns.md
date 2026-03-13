# 컴포넌트 & 레이아웃 패턴

## 아키텍처: 바닐라 JS 싱글페이지 앱

### 모듈 구조
```javascript
const App = (() => {
    // 내부 상태 (클로저)
    let currentYear, currentMonth;
    let selectedDate = null;

    // private 함수들
    function renderCalendar() { ... }

    // public API
    return {
        init,
        showView,
        closeSheet,
        goToday,
        // ...
    };
})();  // IIFE 패턴
```
- 프레임워크 없이 IIFE 모듈 패턴
- 전역 `App` 객체에 public 메서드만 노출
- HTML onclick에서 `App.method()` 호출

### 이벤트 위임
고객 리스트처럼 동적으로 생성되는 요소는 **이벤트 위임** 사용:
```javascript
// ❌ 각 항목에 onclick (동적 생성 시 작동 안 할 수 있음)
card.onclick = () => showDetail(id);

// ✅ 부모에 이벤트 위임
customerList.addEventListener('click', (e) => {
    const card = e.target.closest('.customer-card');
    if (card) showDetail(card.dataset.id);
});
```

---

## 바텀시트 (모달)

### HTML 구조
```html
<div id="mySheet" class="bottom-sheet-overlay" style="display:none"
     onclick="if(event.target===this) App.closeSheet('mySheet')">
    <div class="bottom-sheet tall">       <!-- 기본: max-height 85vh -->
    <!-- 또는 -->
    <div class="bottom-sheet wide-sheet"> <!-- 넓은 모달: max-width 800px -->
        <div class="sheet-handle" onclick="App.closeSheet('mySheet')"></div>
        <div class="sheet-header">
            <h3>제목</h3>
            <button class="sheet-close" onclick="App.closeSheet('mySheet')">&times;</button>
        </div>
        <div class="sheet-body">
            <!-- 내용 -->
        </div>
    </div>
</div>
```

### 동작
- **모바일**: 하단에서 슬라이드 업 (slideUp 애니메이션)
- **PC**: 화면 중앙 모달 (`align-items: center`)
- 오버레이 클릭 = 닫기 (`if(event.target===this)` 조건 필수)
- `sheet-handle` 클릭 = 닫기

### wide-sheet 클래스 (PC 전용)
```css
/* 모바일: 변화 없음 (width: 100%) */
/* PC: */
.bottom-sheet.wide-sheet {
    max-width: 800px;
    max-height: 90vh;
}
```
예약 등록/수정/상세, 고객 상세에 사용.

### 열기/닫기 함수
```javascript
function openSheet(id) {
    document.getElementById(id).style.display = 'flex';
}
function closeSheet(id) {
    document.getElementById(id).style.display = 'none';
}
```

---

## 2열 그리드 레이아웃

### 폼용 (res-form-grid)
```html
<div class="res-form-grid">
    <div class="form-group">...</div>  <!-- 왼쪽 -->
    <div class="form-group">...</div>  <!-- 오른쪽 -->
    <div class="form-group res-form-full">...</div>  <!-- 전체 너비 -->
</div>
```
```css
/* 모바일: 1열 */
.res-form-grid { grid-template-columns: 1fr; }
/* PC: 2열 */
@media (min-width: 900px) {
    .res-form-grid { grid-template-columns: 1fr 1fr; gap: 0 20px; }
    .res-form-full { grid-column: 1 / -1; }
}
```

### 통합 상세뷰 (unified-grid)
```html
<div class="unified-grid">
    <div><!-- 좌: 인라인 통계 + 메모(편집+퀵추가) --></div>
    <div><!-- 우: 아코디언 이력 (activeRes 자동 펼침) --></div>
</div>
```
```css
.unified-grid { grid-template-columns: 1fr; gap: 8px 0; }
@media (min-width: 900px) {
    .unified-grid { grid-template-columns: 1fr 1fr; gap: 0 20px; }
}
```

---

## 캘린더

### 구조: 7열 그리드
```css
.calendar-grid {
    display: grid;
    grid-template-columns: repeat(7, minmax(0, 1fr));
}
```

### 셀 구조
```html
<div class="cal-cell today selected">
    <div class="cal-day">13</div>
    <div class="cal-badges">
        <span class="cal-badge confirmed">루미</span>
        <span class="cal-badge completed">두리</span>
    </div>
</div>
```

### 모바일 접기
타임라인을 볼 때 캘린더를 접어서 공간 확보:
```css
.calendar-section.collapsed .calendar-grid {
    max-height: 0; overflow: hidden;
}
```

---

## 타임라인

### 모바일: 리스트
```html
<div class="timeline-list">
    <!-- 빈 슬롯 -->
    <div class="slot-item">
        <span class="slot-time">09:00</span>
        <span class="slot-label">예약 가능</span>
        <span class="slot-add">+</span>
    </div>
    <!-- 예약 카드 -->
    <div class="res-card">
        <div class="res-time-col">
            <div class="res-time-start">10:00</div>
            <div class="res-time-end">12:00</div>
        </div>
        <div class="res-info">
            <div class="res-pet">루미 <span class="breed">말티푸</span></div>
            <div class="res-service">전체미용 · 2시간</div>
        </div>
        <span class="res-status confirmed">예약</span>
    </div>
</div>
```

### PC: 2열 그리드
```html
<div class="tl-grid">
    <div class="tl-col"><!-- 오전 슬롯 --></div>
    <div class="tl-col"><!-- 오후 슬롯 --></div>
</div>
```

---

## 통합 상세 — 컴팩트 컴포넌트

### 헤더 바 (ud-header-bar)
모든 펫을 전체 너비로 크게 표시. 펫 스위처(pill 전환) 없음.
```html
<div class="ud-header-bar">
    <div class="ud-header-main">
        <span class="ud-pet-name">두리</span><span class="ud-pet-info">비숑 · 5kg</span>
        <span class="ud-pet-divider">/</span>
        <span class="ud-pet-name">몽실</span><span class="ud-pet-info">시츄 · 4.5kg</span>
        <button class="pet-pill pet-pill-add">+</button>
        <span class="ud-pet-divider">|</span>
        <a href="tel:..." class="ud-pet-phone">010-1234-5678</a>
        <button class="ud-edit-link">수정</button>
    </div>
</div>
```

### 인라인 통계 (ud-stats)
박스/카드 금지. 전체 가족 합산. strong 태그로 숫자만 강조.
```html
<div class="ud-stats">
    <strong>3</strong>건 이력 · 완료 <strong>2</strong>건 · 매출 <strong>190,000원</strong>
    <br>첫 01.15 · 최근 03.13(0일전) · 주기 28일
</div>
```

### 아코디언 이력 (ud-acc-item)
모든 예약이 이력에 통합. 별도 하이라이트 섹션 없음.
타임라인에서 클릭한 예약은 **자동 펼침 + 보라색 액센트바**로 강조.
```html
<!-- 일반 이력 -->
<div class="ud-acc-item" id="acc_123">
    <button class="ud-acc-header" aria-expanded="false">
        <span class="res-status completed">완료</span>
        <div>03.13(목) 10:00 / 전체얼컷/9mm · 6만</div>
        <span class="arrow">›</span>
    </button>
    <div class="ud-acc-body">
        <!-- 서비스/금액/메모 상세 + [수정][날짜변경][완료] 버튼 -->
    </div>
</div>

<!-- 타임라인에서 클릭한 활성 예약 (자동 펼침 + 강조) -->
<div class="ud-acc-item open active-res" id="acc_456">
    <!-- .active-res: border-left: 3px solid #7C3AED; background: #F5F3FF -->
    ...
</div>
```

### 정보 수정 — 텍스트 링크
full-width 버튼 금지. 헤더 우측에 텍스트 링크로 최소 공간 사용.
```html
<button class="ud-edit-link" aria-label="고객 정보 수정">수정</button>
```

---

## 멀티펫 표시

펫 스위처(pill 전환) 방식은 **폐기**됨. 통합 페이지에서 모든 펫을 한번에 나열:
- 헤더: 모든 펫 이름/견종/체중을 `/`로 구분하여 나열
- 메모: 강아지별 섹션으로 모두 표시
- 이력: 모든 펫의 예약을 시간순 합산 (펫이름 태그로 구분)
- `+` 버튼: 형제펫 추가 (추가 후에도 통합 페이지 유지)

---

## 전화 알림 팝업

ADB Bridge에서 전화 수신 시 상단 슬라이드다운:
```html
<div class="call-popup">
    <div class="call-popup-inner">
        <div class="call-info-existing">  <!-- 기존 고객: 초록 좌측 바 -->
        <!-- 또는 -->
        <div class="call-info-new">       <!-- 신규: 노란 좌측 바 -->
            <div class="call-phone">010-1234-5678</div>
            <div class="call-customer">루미 (말티푸)</div>
        </div>
        <div class="call-actions">
            <button class="call-btn-reserve">예약하기</button>
            <button class="call-btn-dismiss">닫기</button>
        </div>
    </div>
</div>
```

---

## 북킹/이동 모드 상태바

```html
<div class="mode-bar booking">  <!-- 초록 배경 -->
    <span>루미 예약 중 — 날짜와 시간을 선택하세요</span>
    <button onclick="App.cancelBooking()">취소</button>
</div>
```
캘린더 상단에 컨텍스트 안내 바 표시.

# 반응형 레이아웃 가이드

## 브레이크포인트

```
< 900px  → 모바일 (세로형, 단일 컬럼)
≥ 900px  → PC (가로형, 3컬럼)
```

단 하나의 브레이크포인트. 단순하게 유지.

```javascript
function isPC() { return window.innerWidth >= 900; }
```

---

## 모바일 레이아웃

```
┌──────────────────────┐
│ 헤더 (월 네비게이션)    │
├──────────────────────┤
│ 캘린더 (7열 그리드)     │  ← 접기 가능
├──────────────────────┤
│ 타임라인 (리스트)       │  ← 스크롤
├──────────────────────┤
│ 하단 네비 (3탭)        │
└──────────────────────┘
```

### 핵심
- `max-width: 480px; margin: 0 auto` → 모바일 최적 폭
- 캘린더 접기: 타임라인 보면서 캘린더 공간 확보
- 바텀시트: 하단에서 올라옴 (`align-items: flex-end`)
- 그리드 레이아웃: 모두 `1fr` 단일 컬럼

---

## PC 레이아웃 (1366x768 기준)

```
┌──────────────────────────────────────────────────┐
│ PC 헤더 (인디고 배경, 시계 표시)                      │
├──────────┬──────────┬────────────────────────────┤
│ 좌: 캘린더 │ 중: 수신기록 │ 우: 타임라인                │
│ (420px)   │ (220px)    │ (flex: 1)                  │
│           │            │                            │
│ 캘린더     │ 전화목록    │ 2열 슬롯 그리드              │
│ 그리드     │ (색상 구분)  │ (오전/오후)                 │
│           │            │                            │
│           │ ────────── │                            │
│           │ 액션버튼    │                            │
└──────────┴──────────┴────────────────────────────┘
```

### PC 전용 요소
```css
.pc-only { display: none !important; }
@media (min-width: 900px) {
    .mobile-only { display: none !important; }
    .pc-only { display: flex !important; }
}
```

### PC 헤더
```css
.pc-header {
    background: var(--primary); color: #fff;
    padding: 4px 18px;
}
```
- 앱 이름 + 실시간 시계
- 높이 최소화 (`min-height: 0`)

### 3컬럼 구성
```css
.main-content { flex-direction: row; }  /* PC에서 가로 배치 */
.left-panel { width: 420px; background: #F8F9FB; }
.call-sidebar { width: 220px; }
.timeline-section { flex: 1; }
```

### PC 바텀시트 → 중앙 모달
```css
@media (min-width: 900px) {
    .bottom-sheet-overlay { align-items: center; }  /* 중앙 정렬 */
    .bottom-sheet {
        max-width: 520px;
        border-radius: var(--radius-lg);  /* 전체 라운딩 */
        max-height: 80vh;
    }
    .bottom-sheet.wide-sheet {
        max-width: 800px;
        max-height: 90vh;
    }
}
```

### PC 타임라인: 2열 그리드
```css
.tl-grid {
    display: flex; gap: 4px; padding: 6px;
}
.tl-col { flex: 1; display: flex; flex-direction: column; gap: 4px; }
.tl-slot { height: 42px; min-height: 42px; }
```
오전/오후 나눠서 한 화면에 표시.

### PC 고객 뷰 패널
```css
.view-panel {
    max-width: 520px;
    left: 50%; transform: translateX(-50%);
    box-shadow: var(--shadow-lg);
}
```
전체화면이 아닌 중앙 패널로 표시.

---

## 반응형 폼 패턴

### 모바일: 1열 스택
```css
.res-form-grid { grid-template-columns: 1fr; }
```

### PC: 2열 그리드
```css
@media (min-width: 900px) {
    .res-form-grid { grid-template-columns: 1fr 1fr; gap: 0 20px; }
}
```

### 전체 너비 요소
메모 textarea 등 양 컬럼에 걸쳐야 하는 요소:
```css
.res-form-full { grid-column: 1 / -1; }
```

---

## 상세뷰 반응형 패턴

### 모바일: 세로 스택
정보 섹션 → 메모 → 액션 버튼 순서로 아래로 쌓임.

### PC: 2열 분할
```
┌─────────────────┬──────────────────┐
│ 정보 섹션        │ 메모 영역         │
│ (detail-section) │ (textarea)       │
│                  │                  │
│ 액션 버튼        │                  │
└─────────────────┴──────────────────┘
```
`align-items: start`로 양쪽 높이 독립.

---

## 주의사항

1. **PC 캘린더 크기**: `420px` 고정 — 1366x768 화면에서 최적화됨
2. **PC 시트 높이**: `max-height: 80vh` (wide: 90vh) — 화면 밖으로 나가지 않게
3. **overflow**: PC에서 `html, body { overflow: hidden }` — 전체 앱이 뷰포트에 맞춤
4. **safe-area**: 모바일 하단 네비에 `padding-bottom: env(safe-area-inset-bottom)` — 노치 대응

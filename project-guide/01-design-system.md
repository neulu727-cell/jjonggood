# 디자인 시스템 레퍼런스

## 컬러 팔레트 (Toss-inspired)

```css
:root {
    --primary: #4F46E5;        /* 인디고 — 주요 액션, 강조 */
    --primary-light: #EEF2FF;  /* 배경 하이라이트, hover */
    --primary-badge: #E0E7FF;  /* 뱃지, 태그 배경 */
    --primary-dark: #4338CA;   /* 버튼 :active */
    --bg: #F7F8FA;             /* 전체 배경 */
    --card: #ffffff;           /* 카드/시트 배경 */
    --text: #191F28;           /* 본문 텍스트 */
    --text-secondary: #4E5968; /* 보조 텍스트 */
    --text-light: #8B95A1;     /* 레이블, 힌트 */
    --border: #F2F3F5;         /* 얇은 구분선 */
    --border-strong: #E5E8EB;  /* 입력필드 테두리 */
    --green: #22C55E;          /* 완료/성공 */
    --red: #EF4444;            /* 삭제/에러/취소 */
    --yellow: #F59E0B;         /* 경고/노쇼/메모 강조 */
}
```

### 상태 색상 체계
| 상태 | 뱃지 배경 | 텍스트 | 용도 |
|------|-----------|--------|------|
| confirmed (예약) | #DBEAFE / #3B82F6 | #1E40AF / #fff | 캘린더 뱃지, 상태 태그 |
| completed (완료) | #DCFCE7 / #22C55E | #166534 / #fff | 캘린더 뱃지, 상태 태그 |
| cancelled (취소) | #FEE2E2 | #991B1B | 상태 태그 |
| no_show (노쇼) | #FEF3C7 | #92400E | 상태 태그 |

### 그림자 3단계
```css
--shadow-sm: 0 1px 3px rgba(0,0,0,0.06);   /* 미세한 입체감 */
--shadow-md: 0 4px 12px rgba(0,0,0,0.08);  /* 드롭다운, 자동완성 */
--shadow-lg: 0 8px 24px rgba(0,0,0,0.12);  /* 모달, 토스트, 팝업 */
```

### 라운딩 3단계
```css
--radius-sm: 8px;   /* 입력필드, 버튼, 작은 카드 */
--radius-md: 12px;  /* 메인 버튼, 섹션 카드 */
--radius-lg: 16px;  /* 바텀시트, 팝업, 모달 */
```

## 타이포그래피

```css
font-family: -apple-system, 'Apple SD Gothic Neo', 'Noto Sans KR', sans-serif;
letter-spacing: -0.02em;
-webkit-font-smoothing: antialiased;
```

| 요소 | 크기 | 굵기 | 색상 |
|------|------|------|------|
| 시트 제목 (h3) | 18px | 700 | --text |
| 섹션 제목 (h4) | 13px | 700 | --text-secondary |
| 본문 | 14-15px | 400-600 | --text |
| 보조 텍스트 | 12-13px | 400-500 | --text-light |
| 캘린더 뱃지 | 9-10px | 400 | 상태별 |
| 통계 숫자 (인라인) | 14px | 700 | --primary | `<strong>12</strong>회 방문` 형태 |

## 트랜지션

```css
--transition: 0.2s cubic-bezier(0.33, 1, 0.68, 1);
```
모든 인터랙티브 요소에 동일한 이징 커브 사용. 자연스럽고 빠른 느낌.

## 접근성

- `prefers-reduced-motion: reduce` 미디어 쿼리로 모든 애니메이션 0.01ms로 축소
- `:focus-visible`에 `outline: 2px solid var(--primary)` 통일
- `-webkit-tap-highlight-color: transparent`로 모바일 탭 하이라이트 제거
- `user-select: none`으로 앱 느낌 유지

## 버튼 시스템

### Primary (주요 액션)
```css
.btn-primary {
    width: 100%; padding: 14px;
    background: var(--primary); color: #fff;
    border-radius: var(--radius-md);
    font-size: 16px; font-weight: 700;
}
```

### Primary Small (인라인 액션)
```css
.btn-primary-sm {
    padding: 8px 16px;
    font-size: 13px; font-weight: 600;
}
```

### 상태 버튼 (완료/취소/노쇼)
```css
.btn-status.green { background: var(--green); }  /* 미용 완료 */
.btn-status.red { background: var(--red); }      /* 예약 취소 */
.btn-status.yellow { background: var(--yellow); } /* 노쇼 */
```

### 버튼 그리드 (선택형 입력)
드롭다운 대신 버튼 그리드로 서비스/소요시간/금액 선택:
```css
.btn-grid { display: flex; flex-wrap: wrap; gap: 8px; }
.btn-grid-item.active {
    background: var(--primary); color: #fff;
    border-color: var(--primary); font-weight: 600;
}
```

## 입력 필드

```css
.form-group input {
    padding: 12px 14px;
    border: 1.5px solid var(--border-strong);
    border-radius: var(--radius-sm);
    font-size: 15px;
    background: #FAFBFC;  /* 비활성 상태 약간 회색 */
}
.form-group input:focus {
    border-color: var(--primary);
    box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);  /* 포커스 링 */
    background: #fff;  /* 활성 시 순백 */
}
```

## 로딩 상태

### 스피너
```css
.loading::after {
    border: 2px solid var(--primary-badge);
    border-top-color: var(--primary);
    animation: spin 0.8s linear infinite;
}
```

### 스켈레톤 (Shimmer)
```css
.skeleton {
    background: linear-gradient(90deg, var(--border) 25%, #e8e8e8 50%, var(--border) 75%);
    background-size: 200%; animation: shimmer 1.5s ease-in-out infinite;
}
```

## 토스트 알림
```css
.toast {
    position: fixed; bottom: 80px; left: 50%;
    transform: translateX(-50%);
    background: var(--text); color: #fff;
    padding: 12px 24px; border-radius: var(--radius-md);
    font-size: 14px; font-weight: 600; z-index: 300;
}
```
하단 네비 바로 위에 떠서 화면 가리지 않음.

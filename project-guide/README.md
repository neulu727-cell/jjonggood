# jjonggood 프로젝트 가이드

애견미용샵 예약관리 웹앱의 UI/UX 철학, 디자인 시스템, 개발 패턴을 정리한 문서.
다음 프로젝트에서 이 패턴을 그대로 이어갈 수 있도록 작성됨.

## 문서 목차

| 파일 | 내용 |
|------|------|
| [01-design-system.md](01-design-system.md) | 컬러 팔레트, 타이포, 버튼, 입력필드, 로딩, 토스트 등 디자인 토큰 |
| [02-ui-ux-philosophy.md](02-ui-ux-philosophy.md) | 오너 피드백에서 추출한 8가지 UX 원칙 |
| [03-component-patterns.md](03-component-patterns.md) | 바텀시트, 2열 그리드, 캘린더, 타임라인, 펫스위처 등 컴포넌트 |
| [04-responsive-layout.md](04-responsive-layout.md) | 모바일/PC 반응형 레이아웃, 브레이크포인트, 3컬럼 구성 |
| [05-backend-patterns.md](05-backend-patterns.md) | Flask API 구조, DB 모델, 쿼리 패턴, 인증, 상태 흐름 |
| [06-lessons-learned.md](06-lessons-learned.md) | 실수에서 배운 교훈, UI 피드백 히스토리, 기능 진화 순서 |

## 핵심 철학 한 줄 요약

> **빠르고 간결하게 — 최소 필드, 빈틈 없는 밀도, 시점에 맞는 입력, 강아지 중심**

## 기술 스택

- **프론트**: 바닐라 JS (IIFE 모듈), CSS 변수 디자인 시스템
- **백엔드**: Flask + PostgreSQL (Supabase) + gevent
- **배포**: Cloudtype
- **특수 기능**: ADB Bridge (안드로이드 전화 수신 연동)

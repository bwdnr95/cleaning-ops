<!--
핸드오프 스펙. 루프 계약: `.claude/rules/codex-loop.md`
-->

# 도급사 요청 260917 — 정기 주문 리스트 복원 · 캘린더 정기 제외 · 날짜 셀 전체 클릭   | Tier: B

## 배경 (도급사 원문 → 코드 대조)
1. "정기청소 주문관리 리스트에서도 동일하게 들어갔다가 뒤로가기해도 그대로 복원" — 주문관리는 `b8a9bd8`(9/4)로 URL 해시 복원됨.
   정기청소 > 정기 주문 탭(`RecurringOrdersList` → `OrdersPage(orderScope="recurring")`)은 `OrdersPage.tsx:505`의
   `orderScope !== 'regular'` 가드로 `onViewChange`가 막혀 있고 `adminRouteState.ts`가 `recurring` 페이지 뷰를 직렬화하지 않아 전부 초기화.
   상단 탭(계약/월 트래커/정기 주문)도 내부 state라 브라우저 뒤로가기 시 '계약' 탭으로 떨어짐.
2. "일정 캘린더에 정기청소는 제외하고 일반 주문관리건들만" — `repositories/orders.py list_scheduled_between`에
   `recurring_contract_id IS NULL` 필터가 없음(주문관리 `scope=regular`는 `order_page.py:276`에서 이미 필터).
3. 스크린샷: 날짜 셀에서 날짜 배지/일정 항목(빨강)만 클릭됨, 셀 하단 빈 여백(노랑)은 반응 없음 —
   `CalendarPage.tsx:237` 셀 div에 onClick 없음.

## 완료정의 (성공기준 — 실표면 증거로 증명)
- [ ] #1 정기 주문 탭에서 검색어+협력사 필터+2페이지 → 상세 → 브라우저 `goBack()` → **정기 주문 탭 + 동일 필터/페이지** 복원 (e2e + URL 해시 `#recurring?view=orders&…`)
- [ ] #1 상세 "뒤로" 버튼도 동일 복원, 새로고침 후에도 정기 리스트로 복귀 (`from=recurring` 라우트 파라미터)
- [ ] #1 사이드바 "정기청소" 재클릭 시 계약 탭·기본 필터로 초기화 (주문관리와 동일 동작)
- [ ] #2 `/api/admin/calendar`에 `recurring_contract_id` 비-NULL 건 0 (pytest + 8002 실서버 curl)
- [ ] #3 날짜 셀 하단 여백 클릭 → 우측 패널이 해당 날짜로 전환 (e2e + 스크린샷)

## 스코프 (건드릴 파일)
- backend: `app/repositories/orders.py`(list_scheduled_between 1줄), `tests/test_recurring_auto_generation.py`(캘린더 제외 케이스)
- frontend #1: `src/app/adminRouteState.ts`, `src/app/App.tsx`, `src/features/admin/orders/OrdersPage.tsx`(505행 가드),
  `src/features/admin/recurring/RecurringOrdersList.tsx`, `RecurringContractsPage.tsx`, `e2e/admin-orders-route-state-e2e.spec.ts`
- frontend #3: `src/features/admin/calendar/CalendarPage.tsx`, `src/styles/global.css`, `e2e/admin-e2e.spec.ts`

## 불변유지
- 주문관리(`#orders`) 라우트/복원 동작·해시 파라미터 이름 불변(기존 e2e `admin-orders-route-state-e2e.spec.ts` 4건 green 유지).
- 주문 상세 '정기' 배지 → 계약 상세 역링크(`initialContractId`) 동작 유지.
- 캘린더: 취소 건 숨김·`deleted_at IS NULL`·협력사 필터·다중 방문일 occurrence 전개 불변.
- 날짜 배지 버튼의 키보드 접근성(`aria-pressed`, focus ring) 유지. 일정 항목/더보기 버튼 `stopPropagation` 유지.
- 모바일 `@media (max-width: 768px)` 블록의 캘린더 스타일 불변.

## 게이트
- [x] 격리/회귀 — `list_scheduled_between` 호출자는 calendar 라우트 1곳뿐(grep 확인).
- [ ] soft-delete 가드 — 기존 유지(신규 조회 없음).
- 마이그/타임라인/발송 해당 없음.

## ⚠️ 위험지대
- 해당 없음(숫자 산출·DTO·권한·발송 미접촉).

## 검증 커맨드
```
cd backend && python -m pytest tests/test_recurring_auto_generation.py tests/test_auth_integration.py -k calendar
cd frontend && npm run typecheck && npm run lint && npm run build
cd frontend && npx playwright test e2e/admin-orders-route-state-e2e.spec.ts e2e/admin-e2e.spec.ts
```

## 리뷰
- 빌더: Opus 5 서브에이전트(backend/frontend) · 리뷰: Fable(다른 모델) 1회 → fix 배치 ≤3회.

## 상태표
| 증분 | 상태 | 증거/커밋 |
|---|---|---|
| #2 캘린더 정기 제외 (backend) | 완료 | pytest `test_calendar_excludes_recurring_contract_orders`(필터 제거 시 실패 재현) · backend 전체 566 passed · **8002 실서버** 2026-09 캘린더 33건, 정기 회차 id 누출 0 (변경 전엔 정기 109건 추가 노출) |
| #3 날짜 셀 전체 클릭 (frontend) | 완료 | e2e `calendar day cell empty area click selects that day` (배지 박스 아래 좌표 + elementFromPoint=셀 div 확인 후 클릭 → 패널 날짜 전환) |
| #1 정기 주문 리스트 상태 복원 (frontend) | 완료 | e2e `recurring orders tab restores … after browser back` / `… back button … after reload` / `browser back from an open contract detail …`(Fable M1 회귀) · 해시 `#recurring?view=orders&q=…&page=2`, 상세 `#orders/<id>?…&from=recurring` |

## 리뷰 결과 (Fable 서로소, 1회)
- BLOCKER/HIGH 0 · MEDIUM 1 · LOW 4 · NIT 4 → fix 배치 1회로 M1 + L1~L4 반영, NIT는 미반영(3중 union 정의·`_returnPage` 파라미터명·hover 투톤).
  - M1: popstate로 상단 탭이 바뀌어도 계약 상세/등록 폼이 남던 회귀 → `RecurringContractsPage`에 tab 변경 시 목록 복귀 effect(마운트 제외).
  - L2: 정기 출처 상세에서 복제 → 결과는 일반 주문이므로 복귀처를 주문관리 기본 뷰로.
  - L3: 목록 해시의 수제 `from=`이 뷰 기본값 해석에 끼지 않게 하위 라우트에서만 읽음.
  - L1/L4: 셀 클릭 e2e를 "오늘 아닌 일정 0건 첫 셀" 동적 선택 + `getAppTodayDate()`(KST)로.

## 이월 / 교훈
- 스크롤 위치 복원은 주문관리(9/4)와 동일하게 미포함.
- 8002 uvicorn `--reload` + dist 서빙이라 backend 편집·`npm run build` 즉시 로컬 운영 인스턴스에 반영됨(이번엔 1줄 변경이라 무해했으나 큰 backend 변경은 워크트리에서).

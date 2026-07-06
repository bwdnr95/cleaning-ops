# M1 저위험 구현 작업 지시서 (Codex 코드 작업자용)

- **상위 문서**: `docs/plans/2026-06-02-260601-client-requests-work-order.md` (전체 15건). 본 문서는 그중 **M1(저위험, 클라이언트 확인 불필요)만** 구현 대상.
- **작업일**: 2026-06-02
- **범위 제한(엄수)**: 아래 #1·#12·#6·#8 **4건만** 구현. M2~M4(#2~#5,#7,#9~#11,#13~#15) **절대 손대지 말 것**. 상태/결제 enum, 가격정책, 마이그레이션, 라우팅 변경 금지.

## 공통 규칙
- AGENTS.md / CLAUDE.md / `.claude/rules/*` 준수. 역할별 DTO 화이트리스트, soft-delete, timeline 규칙 유지.
- 프론트: Tailwind/shadcn 금지, `global.css` 토큰 + plain CSS. 로딩/에러/빈 상태 유지. KST는 `getAppTodayDate()`/`getAppTodayValue()`.
- **DB 스키마 변경/마이그레이션 없음**(M1 전 항목 불필요). `customer_phone`은 이미 모델에 존재 → DTO 노출만.
- 검증: `cd backend && python -m pytest`, `cd frontend && npm run typecheck && npm run lint`, 그리고 영향 E2E(`npm run e2e`로 calendar/orders 관련). 안전 포트 5176/8003.
- 커밋: 한국어, 항목별로 분리 권장.

---

## #1. 주문목록 오늘부터 정렬 — **검증만 (구현 불필요)**
- 이미 커밋 `52e3591`에 구현됨: `App.tsx:64`(`datePreset:'upcoming'`), `OrdersPage.tsx`의 `sortOrders/compareVisitOrder/visitOrderGroup/matchesVisitDateFilter`, 방문일 `오늘부터` 프리셋.
- **할 일**: 회귀만 확인. 진입 시 방문일 기본 `오늘부터`, 오늘→미래 정렬, `전체` 클릭 시 과거 포함. 추가 수정 금지.

---

## #12. 상품/수량 ".0" 제거 (공용 포맷터)

**문제**: 엑셀 임포트가 숫자 셀을 `"3.0"` 문자열로 저장 → 화면에 "에어컨청소 3.0"으로 노출.

**구현**:
1. **공용 포맷터 추가** — `frontend/src/domain/` 에 `formatQuantity(value: string | null | undefined): string` 신설(예: `format.ts` 신규 또는 기존 적절 유틸 파일).
   - 규칙: 값이 **정수값을 가진 소수 문자열**이면 소수점/꼬리 0 제거. `"3.0"→"3"`, `"3.50"→"3.5"`, `"3.00"→"3"`. 숫자가 아닌 단위 텍스트(`"32py"`, `"4대"`)·빈값은 **그대로 반환**. 숫자+단위 혼합("3.0대")도 숫자부만 정리(여력 되면), 안전이 우선이면 순수 숫자 문자열만 처리.
   - 단위 테스트 추가(프론트 테스트 컨벤션 따름).
2. **적용 지점(표시 전용, 아래 전부)** — `size_or_quantity`를 화면에 출력하는 곳에 `formatQuantity` 적용:
   - `features/admin/orders/OrdersPage.tsx:1316`(product), `:1318`(sizeOrQuantity), 그리고 테이블 셀 렌더(`o.sizeOrQuantity` 출력부)
   - `features/admin/orders/OrderDetailPage.tsx:306`(수량/규격), `:861`(`formatService`)
   - `features/admin/calendar/CalendarPage.tsx:492`(title)
   - `features/admin/dashboard/Dashboard.tsx:368`, `:379`
   - `features/admin/photo-review/PhotoReviewPage.tsx:561`
   - `features/partner/PartnerJobDetail.tsx:175`
   - `features/customer/CustomerReservation.tsx:227`
3. **제외**: `features/admin/orders/OrderFormPage.tsx`의 입력 필드(`:456`, `:651` 등)는 **편집값이라 변환 금지**(저장 데이터 훼손 방지).
4. **백엔드(권장, 선택)**: 임포트 시 정규화 — `backend/scripts/import_cleanjob_spreadsheet.py:371` 부근에서 `size_or_quantity`가 정수값 소수면 정리. 메시지 템플릿에서 `size_or_quantity`를 쓰면(`backend/app/domain/message_templates.py` grep 확인) 동일 정리.

**수용 기준**: 관리자(목록/상세/캘린더/대시보드/사진검수)·협력사·고객 화면에서 `3.0`→`3`. `3.5`/`32py` 보존. 폼 편집값 불변. typecheck/lint/테스트 통과.

---

## #6. 협력사 + 일정별 선택 시 해당 건 합계 표시

**현재**: `OrdersPage.tsx` 상단 Insight는 전체 `orders` 기준. 협력사 필터(`partnerFilter`, `:219`)·방문일 필터(`dateFilter`)·`filtered` 배열(`:425-447`) 존재.

**구현**:
1. **현재 필터 결과(`filtered`, 페이지네이션 이전 전체) 기준 합계** 계산:
   - 건수(`filtered.length`), 소비자가 합(`sum(total_amount)`), 도급가 합(`sum(partner_price ?? partner_payment_amount)`). 여력 되면 이윤 합(소비자가-도급가)도.
2. **표시**: 협력사 필터가 활성(`partnerFilter !== 'all'`)이거나 방문일 필터가 활성일 때, **필터 요약 줄**을 노출(상단 인사이트 영역 또는 협력사 탭 줄 바로 아래). 예: `FM파트너스 · 2026-06 · 8건 · 소비자가 ₩3,200,000 · 도급가 ₩1,840,000`.
   - 페이지네이션과 무관하게 `filtered` **전체** 합산(현재 페이지만 합산 금지).
   - 기존 전체 기준 Insight 바는 유지(혼동 없게 라벨 구분).
3. testid 부여(예: `orders-filter-summary`)로 E2E 가능하게.

**수용 기준**: 협력사/방문일 선택 시 그 조건의 건수·금액 합계가 정확히 갱신. 필터 해제 시 요약 줄 숨김 또는 전체 기준. 금액 포맷(`₩` 천단위) 일관.

---

## #8. 일정 캘린더 우측 패널 — 협력사 / 연락처 노출

**목표 표시**:
```
에어컨청소 3 | FM파트너스
허재원 · 010-2023-9386
~주소~
```

**구현**:
1. **백엔드 DTO에 연락처 추가** — `backend/app/schemas/order.py:148` `AdminCalendarOrderRead`에 `customer_phone: str | None = None` 추가. (관리자 전용 DTO이므로 화이트리스트 위반 아님.)
2. **캘린더 라우터 매핑** — `backend/app/api/routes/admin/calendar.py:34-47`의 `AdminCalendarOrderRead(...)`에 `customer_phone=(group.customer_phone if group else order.customer_phone)` 추가.
3. **프론트 타입** — `frontend/src/api/admin.ts`의 캘린더 주문 타입에 `customer_phone?: string | null` 추가.
4. **프론트 표시** — `CalendarPage.tsx`:
   - `groupOrdersByDay`(`:482-502`) event에 `phone: order.customer_phone` 추가, `team`은 기존대로.
   - `title`(`:492`)을 `에어컨청소 3 | FM파트너스` 형태로: `${service_name} ${formatQuantity(size_or_quantity)}` + 협력사 있으면 ` | ${team}`. (#12 포맷터 사용)
   - `DaySchedulePanel`(`:442-449`) 둘째 줄을 `{customer} · {formatPhone(phone)}`로 변경(`formatPhone`는 `domain/phone`). 셋째 줄 주소 유지. 협력사/연락처 없음 방어(`미배정`/`-`).

**수용 기준**: 캘린더 우측 패널 제목에 `서비스 수량 | 협력사`, 둘째 줄에 `고객명 · 연락처`. 수량 `.0` 없음. 미배정/연락처 없음 방어. 백엔드 응답에 `customer_phone` 포함, 협력사/고객 DTO에는 변화 없음(관리자만). 기존 캘린더 E2E(`admin-e2e.spec.ts`의 calendar 패널 테스트) 통과.

---

## 작업 순서 / 검증
1. #12 공용 포맷터 + 적용(+테스트) → 2. #8 백엔드 DTO/라우터 + 프론트 → 3. #6 합계 → 4. #1 회귀 확인.
2. 각 단계 후 `npm run typecheck && npm run lint`, 백엔드 `python -m pytest`(특히 #8 DTO 영향 `test_role_dtos`/calendar 관련).
3. 캘린더·주문목록 E2E 실행. 회귀 없으면 항목별 커밋(한국어 메시지).
4. **M2~M4 절대 미착수.** 모호하면 멈추고 질문.

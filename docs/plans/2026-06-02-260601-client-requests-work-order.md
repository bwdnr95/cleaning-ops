# 작업 지시서 — 260601 클린잡 운영 시스템 수정 요청 (15건)

- **작성**: CTO (Claude)
- **수신**: Codex 코드 작업자 (CTO 리뷰 컨펌 후 착수)
- **요청서 출처**: `++260601 클린잡 운영 시스템 수정 사항 요청서`, `260521_2 ...`
- **대상 코드베이스**: `C:\Users\A\Desktop\design_handoff_cleaning_ops`
- **작성일**: 2026-06-02

---

## 0. 공통 규칙 (모든 항목 공통, 위반 시 리뷰 반려)

1. **AGENTS.md / CLAUDE.md / .claude/rules 가 최상위 규칙.** 역할별 DTO 화이트리스트, 협력사/고객 비노출 필드, soft-delete(`deleted_at IS NULL`) 강제, 운영 변경 시 timeline 기록을 반드시 지킬 것.
2. **상태/결제/메시지/사진 타입은 중앙 상수만 사용** — `backend/app/domain/constants.py`, `payment_status.py`, 프론트 `src/domain/*`. 문자열 하드코딩 신규 도입 금지.
3. **스키마 변경 시 Alembic 리비전 필수.** 현재 head = `0010_pricing_partner_base_and_discount`. **다음 번호는 `0011_`부터.** 마이그레이션 작성 후 코드 수정 전에 `alembic upgrade head` 먼저 실행(.claude/rules/backend.md).
4. **DB는 PostgreSQL(운영 환경 기준).** SQLite(`backend/cleaning_ops.db`)는 무시. `SAEnum`은 `values_callable=lambda x: [e.value for e in x]` 규칙 준수.
5. **KST**: `datetime.now(KST).date()` / 프론트 `getAppTodayDate()`·`getAppTodayValue()` 사용. `date.today()` 금지.
6. **프론트는 Tailwind/shadcn 금지.** `global.css` 디자인 토큰 + plain CSS. 데스크탑/모바일 분기 768px, 로딩/에러/빈 상태 3종 처리.
7. **검증 필수**: 백엔드 `python -m pytest`, 프론트 `npm run typecheck && npm run lint`, 영향 범위 E2E(`npm run e2e`, 안전 포트 5176/8003). 상태/결제 enum 변경 건은 신규 테스트 추가.
8. **언어**: 주석/커밋/PR 한국어.
9. 각 항목은 **독립 PR 또는 독립 커밋**으로 분리. 한 PR에 여러 대형 항목을 섞지 말 것(특히 #3/#4 enum, #13 데이터 마이그레이션).

> 분류 표기: 🟢 즉시 착수 가능 / 🟡 설계·결정 필요(착수 전 CTO 승인) / 🔴 클라이언트 추가 확인 필요(착수 보류)

> **리뷰 이력**: 2026-06-02 Codex CTO 리뷰 = **APPROVE_WITH_CHANGES**. 반영 사항: #3 버킷 산식 명시(status+payment_status+잔금안내 여부), #5·#10 분류 🟢→🟡 하향, #5/#13/#14 이윤 VAT 기준(공급가/세액/합계) 명시, #13 settled·반올림·snapshot·dry-run·rollback 수용기준화, #12·#15 적용범위 확대. (Codex가 #12 import 경로를 `services/imports.py`로 인용했으나 실제는 `scripts/import_cleanjob_spreadsheet.py` — 원문 유지.)

---

## 1. 🟢(완료·검증) 주문관리 목록 — 오늘 일정부터 정렬

**요청**: 주문관리 클릭 시 오늘 일정부터. 작업 예정순으로(전체 눌렀을 때만 전체). 5/21엔 21일건부터, 22일 되면 자동으로 22일건부터.

**상태**: **이미 구현·커밋 완료(`52e3591`).** 작업자는 신규 구현 불필요, **회귀 검증만** 수행.
- `frontend/src/app/App.tsx:64` `DEFAULT_ORDERS_VIEW.datePreset='upcoming'`
- `frontend/src/features/admin/orders/OrdersPage.tsx`: `sortOrders`/`compareVisitOrder`/`visitOrderGroup`(today-first: 미수금연체→오늘·이후·미정→과거), `matchesVisitDateFilter`(`upcoming`=오늘 이후+미정), 방문일 프리셋 `오늘부터` 추가, 기준일 `getAppTodayValue()`(KST, 매일 자동 롤오버).
- 백엔드는 `OrderRepository.list_orders`(`order_visit_sort_key` + `business_today()`)로 이미 today-first 지원.

**수용 기준**: 진입 시 방문일 기본 `오늘부터`, 목록이 오늘→미래 순. `전체` 클릭 시 과거 포함 전체. 날짜 경과 시 자동 롤오버. (참고: 클라이언트가 "안 보인다"고 한 건은 **브라우저 캐시(옛 번들)** 이슈였음 — `frontend/dist` 재빌드 후 강력 새로고침으로 해결됨.)

**리스크**: 낮음. 단, 데모/실데이터가 과거(5월)뿐이면 기본 화면이 비어 보일 수 있음 → 의도된 동작(전체 클릭 안내).

---

## 2. 🟡 월별 미결제(미수금) 확인

**요청**: 월별로 미결제 부분을 확인할 수 있게.

**현재**:
- 주문관리 상단 인사이트 바에 `미수금`(결제확인 필요 합계)·`이번 달` 합계 표시(`OrdersPage.tsx` Insight 영역). 단 "이번 달" 기준은 명확치 않고 월 선택 불가.
- 보고서 페이지 `frontend/src/features/admin/reports/ReportsPage.tsx` + 백엔드 `backend/app/api/routes/admin/reports.py`(revenue/partners/services/settlements export 존재). 월별 집계 로직은 reports 서비스에 있음.
- 미수금 판정: `payment_status ∈ PAYMENT_CHECK_STATUSES`(pending/balance_pending/unpaid) — `payment_status.py:20`.

**변경 목표(권장안)**: 보고서(매출) 탭에 **월 선택 + 미결제(미수금) 월별 집계** 뷰 추가. 또는 주문관리 인사이트의 `미수금`을 **월 필터 연동** 값으로.
- 백엔드: `reports` 서비스(`backend/app/services/reports.py:33-205`)에 월별 미수금 집계(월별 미납 건수/금액) 추가, 기존 export 패턴 재사용 가능.
- 프론트: ReportsPage(`:41-105`)에 월 선택 UI + 표/카드(로딩·에러·빈 상태 3종).

**수용 기준(집계 규칙 명시)**: 특정 월의 미결제 건수·합계가 정확히 표시. **(a) 월 기준** = 방문 예정일(`scheduled_date`)인지 접수일인지 확정, **(b) 미수금 정의** = `PAYMENT_CHECK_STATUSES`(pending/balance_pending/unpaid)와 일치, **(c) 환불(refunded)·취소(CANCELLED)·soft-deleted 제외**.

**🔴 확인 필요**: "월별 미결제" 위치를 (a) 보고서 탭 / (b) 주문관리 상단 / (c) 별도 화면 중 어디로 원하는지. 미수금 기준이 #4 결제상태 축소(미납)와 일치해야 함 → **#4 확정 후 진행 권장**.

---

## 3. 🟡🔴 주문 상태 5개로 축소 (최대 난이도·리스크)

**요청 5개**: ① 일정/협력사 확인중 ② 작업확정 ③ 작업완료/잔금미안내 ④ 작업완료/잔금안내 ⑤ 최종결제완료

**현재**: `OrderStatus` 13종(`constants.py:9-22`): 신규접수/상담중/협력사확인중/일정확정/전날안내필요/전날안내완료/작업예정/작업진행/사진검수대기/고객전달필요/고객전달완료/서비스완료/취소.
- 상태는 **운영 플로우 전반에 깊게 결합**: 사진 자동공개/검수 invariant(IN_PROGRESS↔고객전달필요), timeline `status_changed`, 메시지 타입(일정확정/전날/사진), 프론트 탭 필터·배지(`OrdersPage.tsx` STATUS_DOT/TODAY_JOB_STATUSES/toPhotoState/toDeliveredState), 캘린더 `statusTone`(`CalendarPage.tsx:526`), 협력사/고객 화면 매핑.
- DB 저장: 문자열(한글 값). `ORDER_STATUSES` 튜플 파생.

**CTO 판단·권장 설계**: 내부 13상태를 **물리적으로 삭제하지 말 것.** 사진/메시지/타임라인 invariant가 깨진다(작업 시작/완료 전환은 `services/orders.py:359-393`, 사진 자동공개는 `services/photos.py:28-57`, 메시지 side effect는 `services/messages.py`가 내부 상태 문자열에 직접 결합). 대신 **표시(presentation) 레이어에 "운영 표시 상태" 5버킷 매핑**을 추가하고, 목록/상세/캘린더의 노출만 5개로 단순화한다. (가역적·저위험)
- 신설: `frontend/src/domain/orderStatus.ts`에 `OPERATIONAL_STAGES`(5) + `toOperationalStage(...)` 매핑 함수. 필요 시 백엔드 DTO에 파생 필드 `operational_stage` 추가(화이트리스트 준수).
- **버킷 산식은 `status` 단독으로 만들지 말 것(Codex CR).** 특히 ③/④는 잔금 "안내 여부"가 핵심이라 **`status + payment_status + 잔금안내 메시지 발송 여부(message_logs의 customer_day_before/잔금 안내 이벤트)`** 조합으로 판정해야 한다. 예: `고객전달완료`라도 잔금 안내 메시지가 없으면 ③, 있으면 ④. 표시단계 산식을 백엔드에서 계산해 파생 필드로 내려주는 편이 프론트 중복을 줄임.

**매핑 초안(클라이언트 확정 필요)**:

| 표시 상태(5) | 내부 OrderStatus | 비고 |
|---|---|---|
| ① 일정/협력사 확인중 | 신규접수, 상담중, 협력사확인중, 일정확정, 전날안내필요, 전날안내완료 | 방문 전 단계 |
| ② 작업확정 | 작업예정, 작업진행, 사진검수대기 | 당일/진행 |
| ③ 작업완료·잔금미안내 | 고객전달필요 | 작업 끝, 잔금 안내 전 |
| ④ 작업완료·잔금안내 | 고객전달완료 | 잔금 안내 완료 |
| ⑤ 최종결제완료 | 서비스완료 | (+ 결제 완납) |
| (취소) | 취소 | 별도 유지 권장 |

**🔴 확인 필요**:
- ③/④의 "잔금 미안내/안내"는 **결제·안내 여부(메시지 발송)** 와 결합된 개념. 단순 status 매핑으로 충분한지, 아니면 "잔금 안내 메시지 발송 여부"로 판정할지 확정 필요.
- 5개로 **줄인 뒤에도 협력사/고객 화면·메시지 트리거가 동작**해야 함(내부 상태 유지 전제).
- "취소"는 5개에 없음 → 별도 표기 유지 가능한지.

**수용 기준**: 목록/상세/캘린더에서 5개 버킷으로 노출, 내부 플로우·사진·메시지·타임라인 정상 동작, 기존 테스트 통과 + 매핑 단위테스트 추가.

> ⛔ 착수 전 매핑표 클라이언트 확정 필수. #4/#7과 함께 설계.

---

## 4. 🟡🔴 고객 결제 상태 3개로 축소

**요청 3개**: 계약금 입금 / 완납 / 미납

**현재**: `PaymentStatus` 6종(`payment_status.py:4-10`): pending/deposit_paid/balance_pending/paid/unpaid/refunded. 프론트 `paymentStatus.ts` `PAYMENT_STATUSES`(6) + `PAYMENT_CHECK_STATUSES`. 폼 select·`PaidPill`(OrdersPage)·`paymentStatusLabel`(OrderDetailPage)에서 사용.

**변경 목표(권장안)**: 결제상태는 비교적 결합이 적어 **선택 가능 옵션을 3개로 축소 + 레거시 값 매핑**이 현실적.
- 신규 입력/표시는 3개: `계약금입금`, `완납`, `미납`.
- 레거시 매핑: deposit_paid→계약금입금, paid→완납, pending/balance_pending/unpaid→미납.
- `PAYMENT_CHECK_STATUSES`(미수금 판정), `PaidPill`, reports와 정합성 유지(#2 연동).

**🔴 확인 필요**: `refunded`(환불) 처리 방식 — 4번째로 유지? "미납"에 합칠 수 없음(의미 충돌). 별도 유지 권장 여부 확정.

**수용 기준**: 폼/목록/상세 모두 3(+환불) 상태로 표시, 레거시 데이터 매핑 정확, 미수금 집계(#2)와 일치.

---

## 5. 🟡 주문상세 금액/결제 — 도급가 + 회사 이윤 표시 (M2 가격정책 묶음)

**요청**: 소비자가·계약금·잔금 밑에 도급가, 그리고 회사 이윤이 함께 보이게.

**현재**: `OrderDetailPage.tsx:313-329` "금액/결제" 5열 그리드(소비자가/할인가/계약금/잔금/현장추가). 도급가는 **별도 "협력사 배정" 섹션**(`:340` `도급가 formatWon(partner_price ?? partner_payment_amount)`)에만 존재. 이윤 표시 없음.
- 데이터: `consumer_price`(=total_amount), `partner_price`(=partner_payment_amount) 모두 `to_admin_order_dto`에서 제공(`services/orders.py:538-539`). `AdminOrderRead`에 이미 포함.

**변경 목표**: "금액/결제" 영역에 **도급가**와 **회사 이윤** 행을 추가(소비자가/계약금/잔금과 같은 시각 그룹).
- 이윤 = `소비자가 - 도급가`. 이윤은 강조 색/굵게로 "눈에 들어오게".
- 음수/누락 방어(도급가 미입력 시 `-`).

**이윤 계산 VAT 기준(Codex CR — 확정 필요)**: 코드에 이윤 정의가 없으므로 **모호하게 두지 말 것.** 아래를 확정해 수용기준에 명시한다.
- **gross/net 기준**: 소비자가·도급가가 각각 부가세 포함/별도인지(고객가 `vat_type`, 도급가 `partner_vat_type`(#14))에 따라 이윤을 **공급가 기준**으로 정규화할지, **세금포함 합계 기준**으로 단순 차감할지.
- 표시 단위: 공급가 / 세액 / 합계 중 무엇을 보일지(최소 합계 기준 이윤, 권장 공급가 기준 이윤 병기).

**수용 기준**: 한 화면에서 소비자가·계약금·잔금·**도급가·이윤**이 함께 보임. 확정된 VAT 기준대로 이윤 계산 정확, 빈값/음수 안전.

**의존성(분류 🟡 사유)**: 이윤의 VAT 기준은 #13/#14 결정에 직접 영향 → **#13/#14 가격정책 확정 후 착수**(M2). 표시 골격(레이아웃)만 선행 가능하나 수치 확정은 정책 후.

---

## 6. 🟢 협력사+일정별 선택 시 해당 건 합계 금액

**요청**: 주문관리에서 협력사 클릭(+일정별)했을 때 해당 건 합계 금액 확인. 상단(미수금/이번달) 영역 변경 또는 별도 표시.

**현재**: `OrdersPage.tsx`에 `partnerFilter`/`dateFilter` 상태와 최종 `filtered` 배열 존재. 상단 Insight는 **전체 `orders`** 기준(필터 미반영).

**변경 목표(프론트 단독)**: 협력사 필터/방문일 필터가 활성일 때, **`filtered` 기준 합계(소비자가 합/도급가 합/건수, 가능하면 이윤 합)** 를 상단 인사이트 또는 별도 요약 줄에 표시. 필터 해제 시 기존 전체 기준으로 복귀.

**수용 기준**: 협력사·일정 선택 시 그 조건의 합계가 정확히 갱신. 필터 미적용 시 기존과 동일.

**리스크**: 낮음(클라이언트 사이드 집계). 단 페이지네이션과 무관하게 `filtered` 전체 합산할 것(현재 페이지만 합산 금지).

---

## 7. 🟡 진행/상태 표시 디자인 검토

**요청**: 진행/상태에 무엇을 띄울지 고민 필요(미확정).

**현재**: 목록의 `진행` 열 = `toPhotoState`/`toDeliveredState` 파생 칩(사진/전달). `상태` 열 = OrderStatus 배지.

**처리**: **#3 확정과 묶어서 설계.** 5버킷 표시 상태가 정해지면 "진행" 열의 정보(사진/전달/잔금안내 여부 등)와 중복/정합성을 재정의. 단독 착수 금지 — #3 매핑 확정 후 디자인 시안 1~2개 제시 → 클라이언트 선택.

**🔴 확인 필요**: "진행" 열에서 보고 싶은 핵심 신호(사진 검수? 잔금 안내? 정산?) 우선순위.

---

## 8. 🟢 일정 캘린더 우측 패널 — 협력사/연락처 노출

**요청**:
```
[현재]  에어컨청소 3.0 / 허재원 · FM파트너스 / 주소
[변경]  에어컨청소 3 | FM파트너스 / 허재원 · 010-2023-9386 / 주소
```

**현재**: `CalendarPage.tsx` `DaySchedulePanel`(:380~) 렌더 — 제목 `eventItem.title`(=`service_name + size_or_quantity`), 둘째 줄 `{customer} · {team}`, 셋째 줄 주소. `groupOrdersByDay`(:482)가 event 구성.
- **연락처 데이터 없음**: `AdminCalendarOrderRead`(`schemas/order.py:148-159`)에 `customer_phone` **미포함** → 백엔드 DTO 추가 필요.

**변경 목표**:
- 제목 줄: `에어컨청소 3 | FM파트너스`(서비스+수량 `|` 협력사). 수량 `.0` 제거(#12와 동일 규칙 적용).
- 둘째 줄: `허재원 · 010-2023-9386`(고객명 · 연락처, `formatPhone` 사용).
- 백엔드: `AdminCalendarOrderRead`(`schemas/order.py:148-159`)에 `customer_phone` 추가 + 캘린더 라우터(`backend/app/api/routes/admin/calendar.py:35-47`) 응답 매핑 보강. (관리자 전용이므로 화이트리스트 위반 아님 — 단 admin DTO에만.)

**수용 기준**: 패널에 협력사명·연락처 표시, 수량 `.0` 없음, 미배정/연락처 없음 방어(`미배정`/`-`).

---

## 9. 🟡🔴 고객 카카오톡 비즈니스 바로 연결 버튼

**요청**: 고객정보 내 해당 고객 카카오톡 비즈니스로 바로 연결 버튼.

**현재**: `OrderDetailPage.tsx:288-301` "고객 정보" 섹션(연락처 `formatPhone`). 카카오 연동 없음.

**변경 목표**: 고객 정보 섹션에 "카카오톡 상담" 버튼 추가 → 카카오 채널/비즈니스 연결 URL로 이동.

**🔴 확인 필요(착수 보류)**:
- 연결 방식: (a) 카카오톡 채널 1:1 채팅 URL(`http://pf.kakao.com/_xxx/chat`) — 고객별이 아니라 **회사 채널** 단일 링크인지, (b) 고객 전화번호 기반 딥링크인지. 카카오 비즈니스는 일반적으로 **회사 채널 단일 링크**라 "해당 고객" 1:1 자동 매칭은 불가할 수 있음.
- 필요한 채널 ID/URL을 클라이언트로부터 받아야 함. 받기 전 구현 불가.

**수용 기준**: 버튼 클릭 시 지정된 카카오 채널/링크로 새 탭 이동. (고객별 자동 식별은 카카오 정책상 제약 — 클라이언트와 기대치 합의 필요.)

---

## 10. 🟡 주문관리 내보내기 버튼 활성화 (컬럼/개인정보/필터 계약 확정 후)

**요청**: 주문관리 내보내기 버튼이 동작 안 함 → 활성화.

**현재**: `OrdersPage.tsx`의 `내보내기` 버튼에 `onClick` 없음(무동작). 백엔드에 **주문 목록 export 엔드포인트 없음**. 단 export 인프라는 존재: `backend/app/services/exporters.py`(`to_xlsx_bytes`/`to_csv_bytes`), reports에 export 4종(`routes/admin/reports.py`).

**변경 목표**:
- 백엔드: `GET /api/admin/orders/export`(현재 정렬/필터 파라미터 반영, xlsx) 신규 — `exporters.py` 재사용, `require_admin`.
- 프론트: 내보내기 버튼 → 현재 화면의 필터(협력사/방문일/탭/검색) 조건으로 다운로드. 헤더는 목록 컬럼 기준.

**수용 기준**: 버튼 클릭 시 현재 필터(협력사/방문일/탭/검색) 반영된 xlsx 다운로드, 권한 가드 적용, 빈 결과 안전.

**🔴 착수 전 확정(분류 🟡 사유, Codex CR)**: 내보낼 **컬럼 목록**과 **개인정보/민감정보 범위**(도급가·결제/증빙 메모·고객 연락처 포함 여부), 필터 계약(프론트 필터를 서버 export 파라미터로 어떻게 매핑할지)을 먼저 확정해야 함. 무계약 즉시 구현 금지.

---

## 11. 🔴 주문관리 상단 협력사 탭 정리(중복/불필요)

**요청**: 협력사 탭 부분 수정 가능한지, 중복·불필요가 많음.

**현재**: `OrdersPage.tsx` 협력사 탭 = `listPartners`의 활성 협력사 전체를 칩으로 나열(`sortedActivePartners`).

**처리(🔴 확인 필요)**: "중복·불필요"의 구체 사례 확보 필요. 추정 원인: (a) 협력사 데이터 중복 등록, (b) 비활성/미사용 협력사 노출, (c) 칩이 너무 많아 가독성 저하.
- 후보안: ① 비활성/주문 0건 협력사 숨김 ② 칩 → 검색 가능한 드롭다운 전환 ③ 협력사 마스터 중복 정리(별도 데이터 작업).

**수용 기준**: 클라이언트가 지목한 중복/불필요 항목 제거 + 가독성 개선. **사례 수집 후 안 확정.**

---

## 12. 🟢 상품/수량 ".0" 제거

**요청**: 상품에 `.0` 삭제(예 "에어컨청소 3.0" → "3").

**현재**: `size_or_quantity`는 자유 문자열. 출처는 엑셀 임포트(`backend/scripts/import_cleanjob_spreadsheet.py:371,526`) — openpyxl이 숫자 셀(3)을 `3.0` float→`"3.0"` 문자열로 읽어 저장된 것으로 추정. 표시처: OrdersPage 목록, OrderDetailPage(`:306`, `formatService :860-861`), CalendarPage 제목(`:492`).

**변경 목표**:
- 표시 보정(즉시): 수량 렌더 시 정수형 `.0` 꼬리 제거하는 **공용 포맷터**를 만들어 **모든 노출 지점에 적용** — 관리자 목록/상세/캘린더뿐 아니라 **협력사 화면·고객 화면·메시지 템플릿·내보내기(#10)** 까지 동일 포맷터 사용(Codex CR: "모든 화면" 기준 충족).
- 근본 보정(권장): 임포트 시 `size_or_quantity` 정규화(소수점 0 제거). 기존 저장 데이터 일괄 정리 스크립트는 선택(있으면 좋음).

**수용 기준**: 관리자/협력사/고객/메시지/export 전 화면에서 `3.0`이 `3`으로 표시. `3.5` 등 실제 소수는 보존. 단위 텍스트(`32py`)는 영향 없음.

---

## 13. 🟡🔴 도급가 부가세 포함 금액으로 일괄 변경

**요청**: 도급가를 부가세 포함 금액으로 일괄 고칠 수 있는지.

**현재**: 도급가 = `partner_payment_amount`(주문) / `partner_base_price`(`service_item`, 0010 마이그레이션). 부가세는 고객가 `vat_type`만 존재(`constants.py:31 VatType`). 도급가에 VAT 개념 없음.

**처리(🔴 확인 + 데이터 마이그레이션, 고위험)**:
- "일괄 변경"은 **되돌리기 어려운 데이터 변경**. 일회성 스크립트 + 백업 + dry-run 필수.
- **확인 필요**: ① 현재 저장된 도급가가 "부가세 별도"라는 전제가 맞는지(전부? 일부?), ② 적용 세율(10%), ③ 대상 범위(`service_item.partner_base_price`만? 기존 `order.partner_payment_amount`도?), ④ 적용 시점(소급/신규만).
- **권장**: #14(도급가 VAT 표시)와 함께 설계. 무지성 일괄 ×1.1 금지 — 이미 포함분 중복 과세 위험.

**수용 기준(필수, Codex CR — 모두 충족해야 적용)**:
- **대상 범위 가드**: 이미 정산 완료(`partner_settled_at` 존재)/지급 완료(`PartnerPaymentStatus.PAID`) 주문 **제외 여부 명시** — 정산 끝난 건의 도급가 변경은 정산/보고서 정합성 파괴. 기본 제외 권장.
- **Decimal 반올림 규칙 명시**(원 단위 반올림/버림), 부동소수점 금지.
- **before-snapshot**: 변경 전 값 백업 테이블/CSV 저장.
- **dry-run diff**: 적용 전 변경 대상·전후 값·합계 차이 리포트 출력, 검토 후 실제 적용.
- **rollback**: 되돌리는 SQL/스크립트와 절차 문서화.
- 적용 후 `reports.py`/`partner_settlements.py` 집계 합계 전후 비교 리포트.

> ⛔ 데이터 마이그레이션은 클라이언트·CTO 승인 + 백업 + dry-run 통과 후에만 실행. 무지성 ×1.1 금지(이미 포함분 중복과세).

---

## 14. 🟡 도급가 부가세 별도/포함 표시 추가

**요청**: 도급가도 부가세 별도/포함 표시.

**현재**: 도급가 전용 VAT 필드 없음. 고객가 `vat_type`만 존재.

**변경 목표**:
- 데이터: `order`(및 필요 시 `service_item`)에 `partner_vat_type`(VatType, 기본 included/excluded 결정) 컬럼 추가 — Alembic `0011_`(또는 #13과 묶음). 백엔드 admin DTO·폼에 노출(협력사/고객 비노출 유지).
- 프론트: 도급가 표시(OrderDetailPage #5, 협력사 배정 섹션, 목록 'VAT 별도' 배지 옆)에서 도급가 VAT 별도/포함 뱃지.

**수용 기준**: 도급가에 별도/포함 표시가 일관되게 노출, 이윤(#5) 계산 시 VAT 기준 반영.

**의존성**: #5(이윤)·#13(일괄변경)과 정합. 세 항목 **하나의 가격 정책 설계**로 묶어 진행 권장.

---

## 15. 🟡 뒤로가기 시 운영 시스템 이탈

**요청**: 브라우저 뒤로가기를 누르면 첫 화면(로그인)으로 빠져 시스템을 벗어남. 목록 버튼으로만 복귀 가능 → 개선.

**현재**: 프론트는 **라우터/히스토리 미사용**(`react-router`/`history`/`pushState`/`popstate` 전무, grep 0건). `App.tsx`가 `useState`(page/detailOrderId/orderForm/ordersView)로 화면 전환. 따라서 브라우저 뒤로가기는 SPA 진입 이전으로 이동 → 이탈.

**변경 목표(권장)**: **URL 상태 기반**으로 연동(Codex CR). `history.pushState`만으로는 새로고침 시 상태가 날아가므로, **hash 또는 query로 화면 상태를 URL에 인코딩**(예: `#/orders`, `#/orders/{id}`)하고 `popstate` 구독 + 초기 로드 시 URL→상태 복원. 기존 고객/협력사 경로(`/c/{token}`, `/customer?t=`, `/partner`)는 **반드시 보존**. (대규모 react-router 전환은 범위 큼 → URL 상태 직접 연동 우선.)
- 최소: 주문상세/폼/캘린더 진입 시 URL 갱신, 뒤로가기 시 목록으로 복귀(로그인 이탈 방지).

**수용 기준**: 상세/폼/캘린더에서 브라우저 뒤로가기가 운영 시스템 내 이전 화면으로 복귀(로그인 이탈 X). **새로고침 시에도 같은 화면 유지**(URL 상태). `/c/{token}`·`/partner` 진입 경로 정상.

**리스크**: 중. 인증 가드/`ordersView` 상태와 충돌 주의. E2E의 네비게이션 흐름 영향 점검.

---

## 우선순위 / 마일스톤 제안

**M1 — 즉시(저위험, 단독 가능)**: #1(검증), #12(.0 공용 포맷터), #6(필터 합계), #8(캘린더 패널·연락처)
**M2 — 가격 정책 묶음(설계 후)**: #5 + #13 + #14 (이윤/도급가 VAT) — 하나의 설계로
**M3 — 상태 체계(설계+합의 후, 최대 리스크)**: #3 + #4 + #7 + #2(미수금 정의 연동)
**M4 — UX/연동(확인 후)**: #15(뒤로가기·URL 상태), #9(카카오·정보 수령 후), #11(사례 수집 후), #10(주문 export·컬럼/개인정보/필터 계약 확정 후)

## 착수 전 클라이언트 확인 필요 목록 (🔴)
- #3 상태 5버킷 매핑표 확정(③/④ 잔금 안내 판정 = `status + payment_status + 잔금안내 메시지 발송 여부`, 취소 처리)
- #4 환불(refunded) 처리 방식(4번째 유지 여부)
- #2 미결제 노출 위치 + 월 기준(방문일/접수일)·환불·취소 제외 규칙
- #5 이윤 계산 VAT 기준(gross/net, 공급가/세액/합계 표시)
- #7 "진행"/"오늘 처리" 열 핵심 신호 우선순위(상태 vs 방문예정일 vs 메시지 미발송)
- #9 카카오 채널 URL/연결 방식(고객별 식별 가능 여부 합의)
- #10 export 포함 컬럼/민감정보(도급가·메모·연락처) 범위 + 필터 계약
- #11 중복·불필요 협력사 구체 사례
- #13 도급가 VAT 일괄 변경 전제/세율/범위/소급여부 + 정산완료분 제외·반올림·snapshot·dry-run·rollback
- #15 뒤로가기 새로고침 시 상태 유지 범위(URL 상태)

## 참고: 변경 영향 핵심 파일
- 백엔드: `domain/constants.py`, `domain/payment_status.py`, `models/order.py`·`models/service_item.py`, `services/orders.py`·`reports.py`·`messages.py`·`photos.py`·`partner_settlements.py`, `schemas/order.py`, `api/routes/admin/orders.py`·`reports.py`·`calendar.py`, `services/exporters.py`, `scripts/import_cleanjob_spreadsheet.py`, `alembic/versions/0011_*`
- 프론트: `app/App.tsx`, `features/admin/orders/OrdersPage.tsx`·`OrderDetailPage.tsx`·`OrderFormPage.tsx`, `features/admin/calendar/CalendarPage.tsx`, `features/admin/reports/ReportsPage.tsx`, `domain/orderStatus.ts`·`paymentStatus.ts`, `api/admin.ts`

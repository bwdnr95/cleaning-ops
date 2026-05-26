# R7 — 다중 상품 주문 + 라인별 협력사 배정 (Brief)

> **이력**
> - v1 (2026-05-18): 사용자 요청 + 7개 default 확정 후 brief 작성

이 brief는 R7 명세서의 전초 단계다. R6 명세서 review 10라운드의 학습을 반영해 **명세서 들어가기 전에 데이터 모델·영향 범위·비변경 영역**을 먼저 잡아둔다.

---

## Goal

"한 주문 = 한 상품 = 한 협력사 = 한 결제 = 한 상태" 모델을  
→ "주문 묶음 안에 라인 N개, **라인별로 모든 운영 단위가 독립**" 모델로 전환.

운영 시나리오: 운영자가 한 고객으로부터 "사무실 청소 (32평) + 화장실 청소 (4칸)" 같은 묶음 주문을 받아 협력사 A·B에 나눠 배정. 결제·정산·진행 상태·사진·메시지·취소 모두 **라인 단위**로 굴리고, 고객은 한 링크에서 각 라인의 진행을 따로따로 확인.

---

## 핵심 결정 (R7 데이터 모델)

> **`Order` = 1개의 작업 라인을 그대로 유지한다.** R6 자동공개 정책, 사진 흐름, 메시지 흐름, 권한 분리, DTO 분리, 13개 status enum, 협력사 모바일 흐름은 **전부 그대로 유지**된다. R7은 그 위에 새 묶음 개념 `OrderGroup`을 1개 추가하는 작업이다.

### 대안 비교

| 옵션 | Order 의미 | 영향 범위 | 채택 여부 |
|---|---|---|---|
| **A (채택)** | Order = 1 line. 새 `OrderGroup` 묶음. | 모델·폼·고객 페이지 위주 | ✅ |
| B | Order는 빈 껍데기. 모든 운영 컬럼을 새 `OrderLine` 테이블로. | 모든 라우터·서비스·DTO·테스트·E2E 갈아엎음 | ❌ (운영 의미 동일, 위험만 큼) |

### 사용자가 답변한 라인 독립성 요구사항 → 옵션 A로 충족

| 요구 | A에서 어떻게 |
|---|---|
| 라인별 협력사 배정 | `Order.partner_id`가 이미 line당 1개 |
| 라인별 사진 격리 | `OrderPhoto.order_id`가 이미 line(=Order)에 묶임. R6 권한 그대로 |
| 라인별 결제 | `Order.total_amount`/`payment_status` 등이 이미 line당 1개 |
| 라인별 상태 | `Order.status`가 이미 line당 1개 |
| 라인별 협력사 정산 | `Order.partner_payment_amount` 그대로 |
| 라인별 메시지 발송 | `MessageLog.order_id`가 line에 묶임 |
| 부분 취소 | line 1개만 `OrderStatus.CANCELLED`로 전환 |
| 고객은 line별 카드 | 그룹의 customer_token으로 들어가서 group 안 line 리스트 노출 |

---

## CTO 결정 사항 (사용자 확정)

- **D1.** 묶음 단위는 `OrderGroup` 1개만 신설. status enum, 사진, 결제는 절대 그룹 레벨로 올리지 않는다.
- **D2.** `customer_token`은 그룹 단위로 발급. 같은 링크로 들어가면 line N개 카드 노출.
- **D3.** 협력사 모바일은 본인 배정된 Order(=line)만 본다. R6 권한 그대로. 그룹 정보는 협력사 DTO에 노출되지 않음.
- **D4.** timeline은 line별로 유지. 그룹 통합 timeline은 만들지 않는다.
- **D5.** 신규 주문 폼: 고객 정보·주소는 그룹 1번만 입력. 라인 추가 시 그 정보 자동 상속.
- **D6.** 부분 취소: 라인 1개만 `OrderStatus.CANCELLED`로 전환 가능. "그룹 취소"는 모든 라인이 취소됐을 때의 시각 표시만 (별도 상태 enum 안 만듦).
- **D7.** 레거시 데이터는 기존 Order들이 각자 자기 자신만 담은 1-line 그룹으로 자동 묶음 (Alembic data migration).

---

## 데이터 모델 변경

### 신규 테이블

```
order_groups
  id                       str (PK, uuid)
  customer_token           str (unique, indexed)    -- D2: 그룹 단위 발급
  customer_name            str
  customer_phone           str (normalized)
  customer_address         str
  source_channel           str | null               -- 그룹 1번만 입력 (D5)
  customer_visible_payment bool                     -- 그룹 기본값. line별 override는 R7 범위 밖
  notes                    text | null
  created_at, updated_at
```

### 기존 `orders` 테이블 변경

```
+ group_id   str (FK → order_groups.id, NOT NULL)
  ~ customer_token, customer_name, customer_phone, customer_address, source_channel, customer_visible_payment
    → R7 마이그레이션 시점에 그룹으로 데이터 이동. 단 컬럼 자체는 **deprecated로 일단 유지**하고
      drop은 R7 다음 cleanup PR(R7.5)에서 한다.
```

**왜 컬럼을 곧장 안 지우는가**: import_cleanjob_spreadsheet 같은 외부 통합과 기존 row의 데이터 보존을 위해 일단 컬럼만 유지. 신규 코드는 그룹에서 읽도록 점진 전환.

---

## 영향 범위 (개략 — 명세서에서 task 단위로 쪼갬)

| 영역 | 강도 | 비고 |
|---|---|---|
| `backend/app/models/order.py`, 신규 `order_group.py` | ◯◯◯ | group_id FK 추가, OrderGroup 모델 신설 |
| `backend/app/repositories/orders.py`, 신규 `order_groups.py` | ◯◯◯ | get_by_group, list_by_group, customer_token으로 group 조회 |
| `backend/app/services/orders.py` | ◯◯◯ | create_group, create_line, customer 정보 위치 변경 |
| `backend/app/api/routes/admin/orders.py` | ◯◯◯ | POST /groups (멀티 line 묶음 생성), GET /groups/{id} |
| `backend/app/api/routes/customer/orders.py` | ◯◯ | customer_token → group → group 안 line 리스트 |
| `backend/app/api/routes/partner/jobs.py` | — | **변경 없음** (D3: Order 단위 그대로) |
| `backend/app/schemas/order.py` | ◯◯ | AdminGroupRead, CustomerGroupRead 등 그룹 DTO 신설. AdminOrderRead는 group_id 노출만 |
| `backend/app/services/dashboard.py` | ◯ | line 단위 카운트 그대로. 변경 작음 |
| `backend/app/services/photos.py`, `messages.py` | — | **변경 없음** (R6 그대로) |
| `frontend/src/features/admin/orders/OrderFormPage.tsx` | ◯◯◯ | line list 편집 UI ("+상품 추가") |
| `frontend/src/features/admin/orders/OrdersPage.tsx` | ◯◯ | 같은 group_id끼리 시각 묶음 표시 (왼쪽 색띠 등) |
| `frontend/src/features/admin/orders/OrderDetailPage.tsx` | ◯◯ | "이 그룹의 다른 라인" 패널 |
| `frontend/src/features/customer/CustomerReservation.tsx` | ◯◯ | line N개 카드 표시 |
| `frontend/src/features/partner/PartnerJobDetail.tsx` | — | **변경 없음** (D3) |
| `backend/alembic/versions/0008_*.py` | ◯◯ | 신규 테이블 + 기존 Order 1:1 그룹 백필 |
| `backend/tests/`, `frontend/e2e/` | ◯◯◯ | 멀티라인 주문 시나리오 신규, 기존 단일 주문 가정 갱신 |

---

## 비변경 영역 (명확히 못박음)

R6에서 합의된 다음 항목은 **R7에서 절대 손대지 않는다**:

- R6 자동공개 정책 (`PhotoService.upload_for_partner`의 `is_customer_visible=True`)
- R6 revoke 라우트 + `with_for_update` 정합성 로직
- R6 `customer_photo_ready` 자동 status advance 제거
- 협력사 모바일 화면 흐름 (사진 업로드 → 자동공개 → "작업 완료" → CUSTOMER_DELIVERY_NEEDED)
- 13개 OrderStatus enum 자체 (line 단위로 그대로 굴림)
- 메시지 발송 로직 (line별 발송, 그룹 무관)
- 협력사 권한 분리 (`require_partner` + `ensure_partner_scope`)
- 협력사·고객 DTO 민감정보 차단 목록 (AGENTS.md)

R6 코드 리뷰에서 잡힌 high 2건(complete vs revoke race, revoke timeline 중복)은 **R7 진입 전에 hotfix로 별도 처리** 권장. R7과 같이 묶으면 review가 다시 복잡해진다.

---

## 시나리오 예시

운영자가 신규 주문 등록:
- 고객: 박고객, 010-8899-7766, 서울시 강남구 …
- **라인 1**: 입주청소 32평, 협력사 A, 총액 360,000원, 일정 2026-05-14 09:30
- **라인 2**: 에어컨청소 1대, 협력사 B, 총액 80,000원, 일정 2026-05-14 14:00

→ 시스템:
1. `OrderGroup` 1개 생성 (customer_token=…, customer 정보 1번)
2. `Order` 2개 생성 (둘 다 group_id 동일, 각자 partner_id/total_amount/status 따로)
3. 협력사 A·B에게 각자 배정 안내 메시지 따로 발송
4. 각자 모바일에서 본인 line만 보임
5. 라인 1만 먼저 사진 업로드·완료 → 자동공개 → 고객전달필요. 라인 2는 작업진행 중
6. 고객이 그룹 customer_token 링크로 들어가면 카드 2개: [라인 1: 사진 N장 노출] / [라인 2: 작업 중]
7. 운영자가 라인 2를 취소하면 `Order.status=CANCELLED`. 라인 1은 그대로 진행
8. 라인 1만 완료된 상태에서 결제는 라인 1·라인 2 따로

---

## 다음 단계

1. 이 brief 승인 (사용자 yes 한 번)
2. R7 명세서 v1 작성 — task 단위로 쪼개 + 핵심 코드 사전 grep + 데이터 마이그레이션 SQL까지 명세
3. Codex CTO review → approved 받을 때까지 갱신
4. 명세서 approved 후 Codex/사용자가 task 실행

**예상 명세서 task 개수**: 15~20개 (R6의 17개와 비슷한 규모). 단 영향 범위가 R6보다 넓으므로 review 라운드는 3~5회 정도 예상.

**예상 PR 순서**:
- R6 hotfix (race 2건) → 머지
- R7 명세서 → Codex 실행 → 머지
- R7.5 cleanup (deprecated customer_* 컬럼 drop) → 머지
- R8 체크리스트 + 정기관리 + 계약서 (클리니어 자료 받은 후 별도)

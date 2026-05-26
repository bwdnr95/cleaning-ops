# 클린잡 운영 시스템 수정사항 구현 명세 v2 (R6: 2026-05-18)

> **이력**  
> - v1 (2026-05-18 PM): 초안 작성.  
> - v2 (2026-05-18 PM): Codex CTO 리뷰 반영. blocking 5건 + should fix 7건 모두 반영. task 12 → 17개로 확장.  
> - v3 (2026-05-18 PM): v2 review에서 발견된 신규 blocking 해소 — Task 5의 `PARTNER_JOB_COMPLETABLE_STATUSES` 가드 복원, Task 3에 운영 runbook 파일 작성 step 추가.  
> - v4 (2026-05-18 PM): v3 review에서 발견된 모순 해소 — **사진 업로드는 상태를 바꾸지 않는다**. 상태 전환은 협력사 "작업 완료" 시점에서만. legacy migration에 사진 0장 사진검수대기 주문 처리 추가. 작업 완료 422 테스트는 IN_PROGRESS 셋업 후 실행.  
> - v5 (2026-05-18 PM): v4 review에서 발견된 4건 해소 — (1) 로그인 fixture payload를 `identifier`/`password`로 정정, (2) revoke 테스트가 start+complete까지 호출해 `고객전달필요` 셋업 후 revoke, (3) legacy `approve()` 메서드도 상태 advance 제거 (Task 4 Step 2), (4) Self-review의 "조건부 STATUS_CHANGED" 문구 제거.  
> - v6 (2026-05-18 PM): v5 review에서 발견된 2건 해소 — (1) `conftest.py`에 `client` fixture 명세 추가 (기존 `make_test_client` factory 재사용), (2) `frontend/e2e/helpers.ts`의 `partnerUploadPhoto`/`openAdminPhotoReview` placeholder를 실제 동작 코드로 교체.  
> - v7 (2026-05-18 PM): v6 review에서 발견된 3건 해소 — (1) `helpers.ts`의 testid를 실제 코드와 일치(`${role}-login-identifier`/`-password`/`-submit`, `admin-shell`, `admin-dashboard-page`)시킴, (2) `partnerUploadPhoto`가 업로드 후 `partner-complete-job`까지 호출해 `CUSTOMER_DELIVERY_NEEDED` 전환 보장, (3) Task 16 신규 spec의 호출부도 `partnerUploadPhoto(browser, ...)` 시그니처로 정렬.  
> - v8 (2026-05-18 PM): v7 review에서 발견된 4건 해소 — (1) Task 7의 `MessageRepository.last_sent_at`에 `datetime`/`MessageType`/`MessageStatus`/`MessageLog` import 추가 명세, (2) Task 16 Step 2의 고객 사진 assertion을 실제 testid(`customer-photo-${photo.id}`)와 기존 업로드 갯수(비포 2장+애프터 1장 = 3장)에 맞춤, (3) Task 16 신규 spec 두 개가 각자 `createAssignedOrder(request)`로 새 주문을 만들어 seed 주문 재사용 race 차단, (4) `partnerUploadPhoto`가 `partner-status-locked` "작업 완료 처리됨"을 기다린 뒤 context를 닫도록 보강.  
> - v9 (2026-05-18 PM): v8 review에서 발견된 1건 해소 — Task 16 Step 2의 고객 페이지 변수 흐름을 `beforeApproval`/`afterApproval` 패턴 (partner-customer-e2e.spec.ts:74-124의 실제 구조)에 맞춰 다시 작성. `customerPage` 미정의 변수 제거.  
> - v10 (2026-05-18 PM): v9 review에서 발견된 1건 해소 — Task 16 Step 2의 치환 범위를 더 좁게 명시. `adminContext`/`adminPage` 생성·로그인·`admin-nav-photos` 진입·`photo-review-item-${flow.orderId}` 클릭은 **유지**, 그 뒤의 승인/검수 단계만 자동 공개 시나리오로 치환.

> **Codex 작업자에게**: 이 문서는 `docs/클린잡 운영 시스템 수정 사항 요청서.pdf`의 3개 수정 요청을 task 단위로 분해한 구현 명세서다. 각 task는 독립 커밋 단위이며, 위에서 아래로 순서대로 진행한다. 작업 전 `CLAUDE.md` § "Working Style for This Repo"와 `AGENTS.md` 전체를 먼저 읽는다.

**Goal:** PDF 요청서 3건 반영:
1. 신규 주문 등록 폼: 단일 '카탈로그 상품' 드롭다운 → '카테고리' + '상세상품' 2단계 드롭다운.
2. 주문관리: 협력사 탭 + 접수일 필터 추가 (방문일 필터와 동일 UX).
3. 사진검수: 자동 공개 승인(이전 가능) 정책 전환, UI를 모니터링 + 재발송 위주로 단순화.

**Architecture:**
- R1·R2는 프론트엔드 단독 변경. 백엔드 모델/API는 이미 분리(`service_categories` ↔ `service_items`, `partners`, `orders.received_date`)되어 있어 그대로 활용.
- R3은 **제품 정책 변경**이다. 4개 layer를 함께 손댄다: (a) 정책 문서(CLAUDE.md + AGENTS.md), (b) 백엔드 상태 전이 로직(`PhotoService.upload_for_partner`, `OrderService.complete_partner_job`, `MessageService.customer_photo_ready` 분기), (c) 프론트 화면 4종(`PhotoReviewPage`, `OrderDetailPage` timeline 라벨, `PartnerJobDetail`, `CustomerReservation`), (d) 기존 backend/E2E 테스트의 정책 가정 갱신.
- 모든 상태 변경/사진 액션은 기존 패턴대로 `order_timeline` 이벤트를 기록한다. 새 이벤트 타입 `PHOTO_REVOKED` 1개를 추가한다.

**Tech Stack:** FastAPI · SQLAlchemy 2.0 · Pydantic · React 19 + TypeScript (no Tailwind) · Playwright · Alembic.

---

## CTO 결정 사항 (사용자 확인 + Codex review 반영)

- **D1. 사진 공개 정책**: **자동 공개 + 이전 가능**. 협력사 업로드 시 시스템이 자동 승인. timeline에 `photo_approved` (system actor) 기록. 관리자가 잘못 올라온 사진을 `비공개로 되돌리기(revoke)` 가능.
- **D2. '사진 재전송' 버튼**: **고객 사진 링크 재발송** (`customer_photo_ready` 메시지). 한 번 이상 보낸 후에도 다시 보낼 수 있다.
- **D3. 협력사 탭 정렬**: **활성 협력사(`is_active=true`) 가나다순**. 필터는 `partner_id` 기준 비교 (Codex review #should-fix 반영, `team_name` 비교 X).
- **D4 (신규). `OrderStatus.PHOTO_REVIEW_PENDING` enum 처리**: enum 자체는 **유지**(brief의 13개 status 박혀 있음). 단, **자동 전환 경로를 모두 제거**한다. `complete_partner_job`은 사진이 1장 이상이면 `CUSTOMER_DELIVERY_NEEDED`로 직접 전환. 0장이면 422 에러로 "사진 1장 이상 업로드 후 완료 처리하라"고 안내. `dashboard` 카운터는 enum만 잠시 둔 채 0으로 유지된다.
- **D4.5 (v4 추가, v3 review #P1 해소). 업로드와 상태 전환의 분리**: 협력사 사진 업로드는 `is_customer_visible=true` + timeline 기록만 한다. **주문 상태는 변경하지 않는다.** 상태 전환(`IN_PROGRESS → CUSTOMER_DELIVERY_NEEDED`)은 협력사가 명시적으로 "작업 완료"를 누른 시점에서만 발생한다. 이렇게 하면 `PARTNER_JOB_COMPLETABLE_STATUSES={IN_PROGRESS}` 가드와 자동 공개 흐름이 충돌하지 않는다. 운영 의미상으로도: "사진 올림 = 작업 진행 일부", "작업 완료 누름 = 협력사가 업로드 끝났다고 선언". 두 단계가 명확히 분리된다.
- **D5 (신규). `customer_photo_ready` 발송과 상태 전환 분리**: 현재 `MessageService`는 발송 성공 시 상태를 `CUSTOMER_DELIVERY_DONE`으로 advance한다. 이로 인해 "재전송" 의도와 충돌한다(첫 발송 후 버튼이 잠긴다). **이 자동 전환을 제거**하고, 상태는 운영자가 주문 상세에서 직접 변경 또는 차후(R7) 고객 페이지 방문 시 자동화. 본 PR에서는 자동 전환만 끊는다.
- **D6 (신규). revoke 정합성**: SQLAlchemy 2.0 `select().with_for_update()`로 주문 row를 lock한 뒤 공개 사진 수를 atomic하게 count한다. revoke 시 주문이 이미 `CUSTOMER_DELIVERY_DONE`/`COMPLETED`였다면 상태는 그대로 두고 timeline 이벤트(`photo_revoked`)만 남긴다.
- **D7 (신규). Legacy 데이터 처리**: 기존에 `사진검수대기` 상태로 멈춰 있는 주문 + `is_customer_visible=false` 사진이 존재할 수 있다. 데이터 마이그레이션 1회 실행으로 일괄 자동 공개 처리 (Task 2.5에서 작성).

---

## File Map — 무엇을 어디서 바꾸는가

| 영역 | 파일 | 종류 |
|---|---|---|
| 정책 | `AGENTS.md` | 수정 (사진 공개 정책 line 46, 158) |
| 정책 | `CLAUDE.md` | 수정 (§ Photo flow invariant) |
| DB 마이그레이션 | `backend/alembic/versions/0004_auto_publish_legacy_photos.py` | 신규 (legacy data 자동 공개) |
| 백엔드 도메인 | `backend/app/domain/constants.py` | 수정 (`TimelineEventType.PHOTO_REVOKED` 추가) |
| 백엔드 서비스 | `backend/app/services/photos.py` | 수정 (`upload_for_partner` 자동 승인, `revoke_visibility` 추가) |
| 백엔드 서비스 | `backend/app/services/orders.py` | 수정 (`complete_partner_job`이 `CUSTOMER_DELIVERY_NEEDED`로 직접 전환) |
| 백엔드 서비스 | `backend/app/services/messages.py` | 수정 (`customer_photo_ready` 분기에서 status advance 제거) |
| 백엔드 서비스 | `backend/app/services/dashboard.py` | 검토 + 갱신 (`photo_review_pending` 카운터는 0 수렴 — 단순 유지) |
| 백엔드 라우터 | `backend/app/api/routes/admin/photos.py` | 수정 (`POST /{photo_id}/revoke` 추가, `last_customer_link_sent_at` 응답) |
| 백엔드 스키마 | `backend/app/schemas/photo.py` | 수정 (`AdminPhotoReviewItem.last_customer_link_sent_at`) |
| 백엔드 레포 | `backend/app/repositories/messages.py` | 수정 (`last_sent_at(order_id, message_type, statuses=...)` 추가) |
| 백엔드 테스트 | `backend/tests/conftest.py` | 신규 또는 보강 (fixture: `seed_admin_token` / `seed_partner_token` / `seed_order_id`) |
| 백엔드 테스트 | `backend/tests/test_partner_photo_evidence.py` | 수정 (자동 공개 가정으로 갱신) |
| 백엔드 테스트 | `backend/tests/test_auth_integration.py` | 수정 (line 149, 163, 166, 1011, 1072, 1086, 1111, 1259, 1284, 1291, 1374, 1495 등 정책 단언 갱신) |
| 백엔드 테스트 | `backend/tests/test_photo_auto_visibility.py` | 신규 |
| 백엔드 테스트 | `backend/tests/test_photo_revoke.py` | 신규 (race condition + 상태별 동작) |
| 프론트 신규주문폼 | `frontend/src/features/admin/orders/OrderFormPage.tsx` | 수정 (카테고리/상세 2단계) |
| 프론트 주문관리 | `frontend/src/features/admin/orders/OrdersPage.tsx` | 수정 (협력사 탭 + 접수일 필터, `partner_id` 기준) |
| 프론트 주문상세 | `frontend/src/features/admin/orders/OrderDetailPage.tsx` | 수정 (`timelineEventLabel`에 `photo_revoked` 추가) |
| 프론트 사진검수 | `frontend/src/features/admin/photo-review/PhotoReviewPage.tsx` | 대폭 수정 (단순화) |
| 프론트 협력사 | `frontend/src/features/partner/PartnerJobDetail.tsx` | 수정 (검수/승인 후 공개 안내 문구) |
| 프론트 고객 | `frontend/src/features/customer/CustomerReservation.tsx` | 수정 ("사진 준비 중" 문구 검토) |
| 프론트 사진 API | `frontend/src/api/photos.ts` | 수정 (`revokePhoto` 추가) |
| 프론트 E2E | `frontend/e2e/admin-e2e.spec.ts` | 수정 (line 343–355 photo-approve-selected/photo-filter-review 갱신) |
| 프론트 E2E | `frontend/e2e/partner-customer-e2e.spec.ts` | 수정 (line 88–101 갱신) |
| 프론트 E2E | `frontend/e2e/admin-photo-review-e2e.spec.ts` | 신규 (재전송/revoke 시나리오) |
| 프론트 E2E | `frontend/e2e/helpers.ts` | 신규 또는 보강 (`partnerUploadPhoto`, `openAdminPhotoReview`) |
| 핸드오프 | `.master/next_session_plan.md` | 수정 (R6 마감 후) |

---

## Task 1 — 정책 문서 갱신: AGENTS.md + CLAUDE.md

**Files:**
- Modify: `AGENTS.md` (line 46–47 인근, line 156–162 "Photo Rules" 블록)
- Modify: `CLAUDE.md` (§ "Photo flow invariant" 블록)

협력사 업로드 사진의 기본값을 "비공개"에서 "자동 공개(이전 가능)"으로 바꾼다. **정책 문서가 코드보다 먼저 갱신되어야 후속 task에서 코드/테스트 가정이 정렬된다.** Codex review에서 CLAUDE.md 누락이 blocking으로 지적되어 v2에서 함께 처리한다.

- [ ] **Step 1: AGENTS.md의 Photo Rules 블록 치환**

현재 "## Photo Rules" 블록(line 156–162)을 아래로 통째 치환.

```markdown
## Photo Rules

- 사진 타입은 `before`, `after`, `etc`만 사용한다.
- 협력사가 업로드한 사진은 기본적으로 고객에게 즉시 노출된다 (자동 공개). 별도 관리자 검수 단계 없이 `is_customer_visible=true`로 저장된다.
- 자동 공개는 시스템 액션으로 처리하되 `order_timeline`에 `photo_approved` 이벤트를 system actor로 기록한다. 운영 추적 가능성을 잃지 않는다.
- 잘못 올라온 사진은 관리자가 "비공개로 되돌리기(revoke)"로 즉시 가릴 수 있다. revoke 시 `is_customer_visible=false`로 되돌리고 `order_timeline`에 `photo_revoked` 이벤트를 남긴다.
- **사진 업로드 자체로는 주문 상태가 바뀌지 않는다.** 협력사가 명시적으로 "작업 완료" 액션을 실행한 시점에서만 `IN_PROGRESS → 고객전달필요`로 전환된다 (사진검수대기 단계를 거치지 않는다).
- 협력사 "작업 완료" 동작은 사진이 1장 이상일 때만 허용한다. 사진 0장이면 422로 거부하고 "사진을 1장 이상 업로드한 뒤 완료 처리하세요" 메시지를 반환한다. 또한 주문이 `작업진행` 상태가 아니면 409 `invalid_status_transition`을 반환한다.
- `사진검수대기` enum 자체는 brief에 박힌 13개 status enum 호환을 위해 유지되지만, 신규 자동 전환 경로는 없다. 향후 운영자가 명시적으로 이 상태로 되돌릴 수 있는 액션이 추가될 수 있다.
- `customer_photo_ready` 메시지 발송과 주문 상태 전환은 분리되어 있다. 발송 자체로는 `고객전달완료`로 advance하지 않는다 — 운영자가 주문 상세에서 명시적으로 변경하거나 차후 자동화 트리거가 처리한다.
- 고객 사진 링크 발송(`customer_photo_ready`)은 명시적으로 여러 번 호출할 수 있다. 매 발송마다 `message_logs`와 `customer_link_sent` timeline 이벤트를 새로 남긴다.
- 사진 업로드 실패, 파일 형식 오류, 용량 초과는 사용자에게 명확히 표시한다.
- 고객 페이지는 `is_customer_visible=true`인 사진만 보여준다.
```

- [ ] **Step 2: AGENTS.md의 Security And Privacy Rules line 46 정정**

```markdown
- 협력사가 업로드한 사진은 기본값이 `is_customer_visible=false`여야 한다.
```

를 아래로 치환.

```markdown
- 협력사가 업로드한 사진은 자동 공개 정책(자세한 내용은 Photo Rules 참조)에 따라 처리한다. 관리자는 언제든 revoke로 가릴 수 있다.
```

- [ ] **Step 3: CLAUDE.md의 § "Photo flow invariant" 블록 치환**

현재 `CLAUDE.md`의 "### Photo flow invariant" 블록을 찾아 아래로 치환.

```markdown
### Photo flow invariant
Partner upload → `is_customer_visible=true` (자동 공개). **상태는 변경되지 않는다** (협력사가 사진을 여러 번 나눠 올려도 IN_PROGRESS 그대로). timeline에는 `photo_uploaded` + `photo_approved`(system actor)만 기록된다. 협력사가 명시적으로 "작업 완료" 액션을 실행하면 비로소 `IN_PROGRESS → 고객전달필요`로 전환(사진 1장 이상 + IN_PROGRESS 가드 통과 시). 관리자는 잘못 올라온 사진을 `POST /api/admin/photos/{id}/revoke`로 비공개로 되돌릴 수 있고, 이 때 `photo_revoked` 이벤트가 남는다. 마지막 공개 사진이 사라지고 주문이 `고객전달필요` 상태였다면 `작업진행`으로 되돌아간다(`고객전달완료`/`서비스완료`는 유지). 파일 타입은 **byte signature**로 검증한다 (`services/photos.py`).
```

- [ ] **Step 4: 커밋**

```bash
git add AGENTS.md CLAUDE.md
git commit -m "docs: 사진 자동 공개 정책으로 룰북 갱신 (AGENTS.md, CLAUDE.md)"
```

---

## Task 2 — 도메인 상수: `TimelineEventType.PHOTO_REVOKED`

**Files:** Modify `backend/app/domain/constants.py:57-65`

- [ ] **Step 1: enum 추가**

```python
class TimelineEventType(StrEnum):
    CREATED = "created"
    STATUS_CHANGED = "status_changed"
    PARTNER_ASSIGNED = "partner_assigned"
    MESSAGE_SENT = "message_sent"
    PHOTO_UPLOADED = "photo_uploaded"
    PHOTO_APPROVED = "photo_approved"
    PHOTO_REVOKED = "photo_revoked"          # 추가
    CUSTOMER_LINK_SENT = "customer_link_sent"
    MEMO_ADDED = "memo_added"
```

- [ ] **Step 2: 컴파일 확인 + 커밋**

```powershell
python -m compileall backend/app/domain/constants.py
```

```bash
git add backend/app/domain/constants.py
git commit -m "feat(domain): 사진 비공개 되돌리기 timeline 이벤트 타입 추가"
```

---

## Task 3 — Legacy 데이터 마이그레이션 (Alembic)

**Files:** Create `backend/alembic/versions/0004_auto_publish_legacy_photos.py`

**구현 의도 (D7):**
- 기존 운영에서 `is_customer_visible=false`인 사진을 일괄 `true`로 갱신.
- `사진검수대기` 상태의 주문을 `고객전달필요`로 일괄 전환 (사진이 1장 이상인 경우).
- timeline에 마이그레이션 이벤트는 남기지 않음 (대량 row 폭증 방지). 운영자에게 README/runbook으로 안내한다.

- [ ] **Step 1: 직전 revision 파악**

```powershell
python -c "import os; print([f for f in os.listdir('backend/alembic/versions') if f.endswith('.py')])"
```

가장 최근 revision id를 `down_revision`으로 사용한다 (예: `0003_...`). 본 명세에서는 자리표시자로 `0003_message_metadata`로 표기.

- [ ] **Step 2: 마이그레이션 파일 작성**

```python
"""Auto-publish legacy partner photos and clear photo_review_pending status.

Revision ID: 0004_auto_publish_legacy_photos
Revises: 0003_message_metadata
Create Date: 2026-05-18
"""
from alembic import op
import sqlalchemy as sa


revision = "0004_auto_publish_legacy_photos"
down_revision = "0003_message_metadata"  # 실제 직전 revision id로 교체
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) 모든 비공개 사진을 일괄 공개.
    op.execute(
        "UPDATE order_photos SET is_customer_visible = TRUE WHERE is_customer_visible = FALSE"
    )
    # 2) 사진이 1장 이상인 '사진검수대기' 주문은 '고객전달필요'로.
    op.execute(
        """
        UPDATE orders
        SET status = '고객전달필요'
        WHERE status = '사진검수대기'
          AND id IN (
              SELECT DISTINCT order_id FROM order_photos
          )
        """
    )
    # 3) v4 추가: 사진이 0장인 '사진검수대기' 주문은 '작업진행'으로 되돌린다.
    #    (legacy complete_partner_job이 사진 없이도 사진검수대기로 보냈을 수 있다.)
    op.execute(
        """
        UPDATE orders
        SET status = '작업진행'
        WHERE status = '사진검수대기'
          AND id NOT IN (
              SELECT DISTINCT order_id FROM order_photos
          )
        """
    )


def downgrade() -> None:
    # 의도적으로 no-op: 자동 공개는 의도된 정책 변경이며 되돌리지 않는다.
    pass
```

- [ ] **Step 3: SQL 렌더 확인**

```powershell
cd backend; python -m alembic upgrade head --sql > $env:TEMP/migration_check.sql
Get-Content $env:TEMP/migration_check.sql | Select-String -Pattern "is_customer_visible|사진검수대기"
```

기대: 두 UPDATE 문이 출력된다.

- [ ] **Step 4: 실제 dev DB에 적용 + 검증**

```powershell
cd backend; python -m alembic upgrade head
python -c "from app.db.session import SessionLocal; from sqlalchemy import text; s = SessionLocal(); print(s.execute(text(\"SELECT COUNT(*) FROM order_photos WHERE is_customer_visible = FALSE\")).scalar()); print(s.execute(text(\"SELECT COUNT(*) FROM orders WHERE status = '사진검수대기'\")).scalar())"
```

기대: 둘 다 `0`.

- [ ] **Step 5: 운영 runbook 파일 작성 (v3 추가)**

`docs/runbooks/r6-photo-policy-migration.md` 파일을 신규 작성한다. AGENTS.md Photo Rules 블록에서 "데이터 마이그레이션 1회 실행으로 일괄 자동 공개 처리"라고 안내했으니, 운영자가 실제로 무엇을 어떻게 실행하는지 한 페이지로 정리한다.

```markdown
# R6 — 사진 자동 공개 정책 전환 운영 runbook

## 배경
2026-05-18부터 협력사가 업로드한 사진은 관리자 검수 없이 즉시 고객에게 공개된다. 잘못 올라온 사진은 관리자가 "비공개로 되돌리기"로 즉시 가릴 수 있다 (POST /api/admin/photos/{id}/revoke).

## 배포 전 체크
1. backend, frontend 코드 R6 PR이 main에 머지됐는가?
2. 운영팀에 "검수 단계가 사라지고 자동 공개로 바뀐다"는 사실이 사전 공유됐는가?
3. 기존 비공개 사진 / 사진검수대기 주문 개수를 미리 확인:
   ```sql
   SELECT COUNT(*) FROM order_photos WHERE is_customer_visible = FALSE;
   SELECT COUNT(*) FROM orders WHERE status = '사진검수대기';
   ```

## 배포 절차
1. 운영 DB 백업.
2. `alembic upgrade head` 실행 — `0004_auto_publish_legacy_photos` 마이그레이션이 자동 적용된다.
3. 배포 직후 확인:
   ```sql
   SELECT COUNT(*) FROM order_photos WHERE is_customer_visible = FALSE; -- 0이어야 함
   SELECT COUNT(*) FROM orders WHERE status = '사진검수대기';            -- 0이어야 함
   ```
4. 관리자 페이지에서 "사진 전달 현황" 메뉴 진입 후 좌측 필터 `링크 미발송` 탭에 주문이 정상 노출되는지 확인.
5. 1개 주문에 대해 협력사 모바일로 사진 1장 업로드 → 즉시 고객 페이지에서 보이는지 smoke test.
6. 같은 사진을 관리자 페이지에서 `비공개로 되돌리기` 클릭 → 고객 페이지에서 사라지는지 확인.

## 롤백
- `0004_auto_publish_legacy_photos`는 `downgrade()`가 의도적으로 no-op이다 (자동 공개는 비가역적인 정책 변경). 코드 롤백이 필요하면 R6 직전 커밋으로 git revert 후 배포한다. 단, 이미 자동 공개된 사진은 그대로 공개 상태로 남는다는 점에 유의.

## FAQ
- **Q. 협력사가 잘못된 사진을 올리면?**  
  관리자가 사진 전달 현황에서 해당 사진을 선택 후 `비공개로 되돌리기` 클릭. timeline에 `photo_revoked` 이벤트가 남고, 마지막 공개 사진이 사라지면 상태가 `작업진행`으로 되돌아간다 (단, 이미 `고객전달완료`/`서비스완료`였다면 상태 유지).
- **Q. 협력사가 "작업 완료"를 누르려는데 사진을 아직 안 올렸으면?**  
  422 응답 + "사진을 1장 이상 업로드한 뒤 완료 처리하세요" 안내. 협력사 화면에 그대로 노출됨.
- **Q. `customer_photo_ready` 메시지를 한 번 보낸 후 또 보낼 수 있나?**  
  가능. 관리자 페이지의 같은 버튼 라벨이 "재전송"으로 토글된다.
```

- [ ] **Step 6: 커밋**

```bash
git add backend/alembic/versions/0004_auto_publish_legacy_photos.py docs/runbooks/r6-photo-policy-migration.md
git commit -m "chore(db,docs): legacy 사진 일괄 공개 마이그레이션 + 운영 runbook"
```

---

## Task 4 — 백엔드: `PhotoService` 자동 공개 + `revoke_visibility`

**Files:**
- Modify: `backend/app/services/photos.py:28-60` (`upload_for_partner` 본문)
- Modify: `backend/app/services/photos.py:82-113` (`approve` 본문 idempotent 보장)
- Add: `backend/app/services/photos.py` 끝부분에 `revoke_visibility`

**구현 의도 + Codex review #4 반영 + v4 변경 (D4.5):**
- 업로드 시 `is_customer_visible=True`로 저장.
- **주문 상태는 변경하지 않는다.** v3까지는 업로드 시점에 `CUSTOMER_DELIVERY_NEEDED`로 자동 전환했지만, 이게 `PARTNER_JOB_COMPLETABLE_STATUSES={IN_PROGRESS}` 가드와 충돌해 협력사가 "작업 완료"를 못 누르는 모순이 생긴다. v4부터는 상태 전환을 `complete_partner_job`(Task 5)에 전적으로 위임.
- timeline에 `PHOTO_UPLOADED` + `PHOTO_APPROVED`(system actor=None) 2건만 기록. **STATUS_CHANGED는 기록하지 않는다.**
- `approve()`는 후방 호환 + idempotent.
- 새 `revoke_visibility`: **row lock** + atomic count로 race 차단. 마지막 공개 사진 0장 + 상태가 `CUSTOMER_DELIVERY_NEEDED`였다면 `IN_PROGRESS`로 되돌림. `CUSTOMER_DELIVERY_DONE`/`COMPLETED`였다면 상태 그대로 두고 timeline만 남김.

- [ ] **Step 1: `upload_for_partner` 본문 치환**

```python
def upload_for_partner(self, payload: PhotoCreate, *, user_id: str, partner_id: str) -> OrderPhoto:
    order = self.orders.get(payload.order_id)
    if order is None or order.partner_id != partner_id:
        raise ValueError("order_not_found")

    photo = OrderPhoto(
        id=str(uuid4()),
        uploaded_by_user_id=user_id,
        is_customer_visible=True,
        **payload.model_dump(),
    )
    self.photos.add(photo)
    self.timeline.record(
        order_id=payload.order_id,
        actor_user_id=user_id,
        event_type=TimelineEventType.PHOTO_UPLOADED,
        title="사진 업로드",
        metadata={"photo_id": photo.id, "photo_type": payload.photo_type},
    )
    self.timeline.record(
        order_id=payload.order_id,
        actor_user_id=None,
        event_type=TimelineEventType.PHOTO_APPROVED,
        title="사진 자동 공개",
        description="협력사 업로드 사진이 정책에 따라 자동 공개되었습니다.",
        metadata={"photo_id": photo.id, "auto": True},
    )
    # v4 변경(D4.5): 상태는 여기서 바꾸지 않는다. 협력사가 "작업 완료"를 누를 때 OrderService에서 처리.
    self.db.commit()
    self.db.refresh(photo)
    return photo
```

- [ ] **Step 2: `approve` 메서드 idempotent 보장**

```python
def approve(self, photo_id: str, *, actor_user_id: str | None = None) -> OrderPhoto:
    """
    v5 (D4.5 강화): legacy 호출 호환용. 사진을 공개 처리하고 timeline에 PHOTO_APPROVED만 남긴다.
    상태 변경(IN_PROGRESS → CUSTOMER_DELIVERY_NEEDED)은 협력사 '작업 완료' 액션만 수행한다.
    revoke 후 관리자가 다시 공개로 되돌리는 경우에도 상태는 건드리지 않는다.
    """
    photo = self.photos.get(photo_id)
    if photo is None:
        raise ValueError("photo_not_found")
    if photo.is_customer_visible:
        return photo
    photo.is_customer_visible = True
    self.timeline.record(
        order_id=photo.order_id,
        actor_user_id=actor_user_id,
        event_type=TimelineEventType.PHOTO_APPROVED,
        title="사진 고객 공개 승인",
        metadata={"photo_id": photo.id},
    )
    self.db.commit()
    self.db.refresh(photo)
    return photo
```

- [ ] **Step 3: `revoke_visibility` 메서드 추가 (row lock + atomic count)**

`PhotoService` 클래스 안, `approve` 메서드 바로 아래.

```python
def revoke_visibility(self, photo_id: str, *, actor_user_id: str | None = None) -> OrderPhoto:
    from sqlalchemy import select, func
    from app.models.order import Order
    from app.models.photo import OrderPhoto as OrderPhotoModel

    photo = self.photos.get(photo_id)
    if photo is None:
        raise ValueError("photo_not_found")
    if not photo.is_customer_visible:
        return photo

    # 주문 row lock으로 동시 revoke race 차단.
    order = self.db.execute(
        select(Order).where(Order.id == photo.order_id).with_for_update()
    ).scalar_one_or_none()

    photo.is_customer_visible = False
    self.db.flush()

    self.timeline.record(
        order_id=photo.order_id,
        actor_user_id=actor_user_id,
        event_type=TimelineEventType.PHOTO_REVOKED,
        title="사진 비공개로 되돌림",
        metadata={"photo_id": photo.id},
    )

    if order is not None:
        old_status = order.status
        remaining_visible = self.db.execute(
            select(func.count(OrderPhotoModel.id)).where(
                OrderPhotoModel.order_id == order.id,
                OrderPhotoModel.is_customer_visible.is_(True),
            )
        ).scalar_one()

        # `CUSTOMER_DELIVERY_NEEDED` 상태에서만 IN_PROGRESS로 되돌림.
        # `CUSTOMER_DELIVERY_DONE`/`COMPLETED`는 운영 의미상 잠금 처리하므로 timeline만 남기고 status 유지.
        if remaining_visible == 0 and order.status == OrderStatus.CUSTOMER_DELIVERY_NEEDED:
            order.status = OrderStatus.IN_PROGRESS
            self.timeline.record(
                order_id=photo.order_id,
                actor_user_id=actor_user_id,
                event_type=TimelineEventType.STATUS_CHANGED,
                title="작업 진행으로 되돌림",
                description="공개 사진이 모두 비공개로 처리되어 작업 진행 상태로 되돌렸습니다.",
                metadata={"from": old_status, "to": order.status},
            )

    self.db.commit()
    self.db.refresh(photo)
    return photo
```

- [ ] **Step 4: 컴파일 + 커밋**

```powershell
python -m compileall backend/app/services/photos.py
```

```bash
git add backend/app/services/photos.py
git commit -m "feat(photos): 자동 공개 정책 + row lock 기반 비공개 되돌리기"
```

---

## Task 5 — 백엔드: `OrderService.complete_partner_job` 흐름 재설계 (D4)

**Files:** Modify `backend/app/services/orders.py:171-190` (`complete_partner_job` 본문)

**구현 의도:**
- 협력사 "작업 완료" 클릭 시 사진이 1장 이상이면 곧장 `CUSTOMER_DELIVERY_NEEDED`로.
- 사진이 0장이면 `ValueError("photo_required_for_completion")`을 raise → 라우터에서 422로 변환.
- 결과적으로 `PHOTO_REVIEW_PENDING` 자동 생성 경로가 사라진다.

- [ ] **Step 1: 메서드 본문 치환**

`backend/app/services/orders.py`의 `complete_partner_job` 본문(line 171–190 인근)을 다음으로 치환.

```python
def complete_partner_job(
    self,
    order_id: str,
    *,
    actor_user_id: str,
    partner_id: str,
) -> Order:
    order = self.get_for_partner(order_id, partner_id=partner_id)

    # 기존 가드 유지: 작업 진행 중인 주문만 완료 처리 가능.
    # 취소/일정확정/이미 완료된 주문에서 잘못 호출되면 409 invalid_status_transition.
    if order.status not in PARTNER_JOB_COMPLETABLE_STATUSES:
        raise ValueError("invalid_status_transition")

    photo_count = self.photos.count_visible_for_order(order.id)
    if photo_count == 0:
        raise ValueError("photo_required_for_completion")

    self._change_status(
        order,
        OrderStatus.CUSTOMER_DELIVERY_NEEDED,
        actor_user_id=actor_user_id,
        title="작업 완료",
        description="협력사가 작업 완료를 처리했습니다. 자동 공개된 사진으로 고객 전달이 가능합니다.",
    )
    self.db.commit()
    self.db.refresh(order)
    return order
```

> **주의 1:** `OrderService`의 생성자에서 `self.photos = PhotoRepository(db)`가 이미 있는지 확인. 없으면 생성자에 추가한다.
> **주의 2 (v3 추가):** `PARTNER_JOB_COMPLETABLE_STATUSES`는 `backend/app/services/orders.py:33-35`에 이미 정의되어 있고 현재 `{OrderStatus.IN_PROGRESS.value}` 1개만 포함한다. **이 set은 그대로 둔다.** v2 명세 초안에서 가드 자체를 제거한 것을 v3에서 복원했다. 사진 자동 공개(Task 4)는 업로드 시점에 발동하므로 완료 진입 가드와 무관하다.

- [ ] **Step 2: `PhotoRepository.count_visible_for_order` 메서드 확인/추가**

```powershell
python -c "from backend.app.repositories.photos import PhotoRepository; print(hasattr(PhotoRepository, 'count_visible_for_order'))"
```

`False`면 `backend/app/repositories/photos.py`에 추가.

```python
def count_visible_for_order(self, order_id: str) -> int:
    from sqlalchemy import select, func
    from app.models.photo import OrderPhoto

    return self.db.execute(
        select(func.count(OrderPhoto.id)).where(
            OrderPhoto.order_id == order_id,
            OrderPhoto.is_customer_visible.is_(True),
        )
    ).scalar_one()
```

- [ ] **Step 3: 라우터에서 422 매핑**

`backend/app/api/routes/partner/jobs.py`의 `complete_my_job` 핸들러에 `photo_required_for_completion` 케이스를 추가.

```python
except ValueError as exc:
    if str(exc) == "invalid_status_transition":
        raise HTTPException(status_code=409, detail="invalid_status_transition") from exc
    if str(exc) == "photo_required_for_completion":
        raise HTTPException(status_code=422, detail="photo_required_for_completion") from exc
    raise HTTPException(status_code=404, detail="order_not_found") from exc
```

- [ ] **Step 4: 협력사 화면 에러 메시지 매핑**

`frontend/src/features/partner/PartnerJobDetail.tsx`의 에러 처리 영역에서 `photo_required_for_completion` → "사진을 1장 이상 업로드한 뒤 완료 처리해주세요." 표시.

- [ ] **Step 5: 커밋**

```bash
git add backend/app/services/orders.py backend/app/repositories/photos.py backend/app/api/routes/partner/jobs.py frontend/src/features/partner/PartnerJobDetail.tsx
git commit -m "feat(orders): 협력사 완료 처리 시 사진 필수 + 사진검수대기 자동 전환 제거"
```

---

## Task 6 — 백엔드: `customer_photo_ready` 상태 advance 제거 (D5)

**Files:** Modify `backend/app/services/messages.py:981-989`

**구현 의도:**
- 첫 발송 후 자동으로 `CUSTOMER_DELIVERY_DONE`으로 advance하는 동작을 끊는다 → 재전송 의도와 부합.
- timeline 이벤트(`CUSTOMER_LINK_SENT`)와 `message_logs` 기록은 그대로 유지.

- [ ] **Step 1: 분기 치환**

`backend/app/services/messages.py`의 `MessageType.CUSTOMER_PHOTO_READY` 분기(line 981–989)를 아래로 치환.

```python
if payload.message_type == MessageType.CUSTOMER_PHOTO_READY:
    # 정책 변경(2026-05-18): 사진 링크 발송은 메시지/timeline만 남기고
    # 주문 상태는 자동 advance 하지 않는다. 재전송 가능성을 보장하기 위함.
    self._record_customer_link_sent(order, payload, log, actor_user_id=actor_user_id)
    return
```

- [ ] **Step 2: 영향 받는 테스트 search**

```powershell
cd backend; python -m pytest tests/test_auth_integration.py -k "photo_ready or customer_link" -v 2>&1 | Select-String -Pattern "FAILED|PASSED"
```

`고객전달완료`로 자동 전환되는 것을 기대하는 테스트는 v2 정책에서는 실패해야 정상. Task 8에서 일괄 갱신한다.

- [ ] **Step 3: 커밋**

```bash
git add backend/app/services/messages.py
git commit -m "feat(messages): customer_photo_ready 발송 후 상태 자동 advance 제거"
```

---

## Task 7 — 백엔드: `last_customer_link_sent_at` metadata 노출

**Files:**
- Modify: `backend/app/schemas/photo.py:42-54` (`AdminPhotoReviewItem`)
- Modify: `backend/app/repositories/messages.py` (`last_sent_at` 추가)
- Modify: `backend/app/api/routes/admin/photos.py:13-38` (queue list 핸들러에서 값 채움)

**구현 의도 (Codex review #should-fix 반영):**
- `last_customer_link_sent_at`을 `datetime | None` 타입으로 노출 (str 아님).
- `MessageRepository.last_sent_at(order_id, message_type, statuses=...)`은 성공 상태(`sent`/`delivered`)만 카운트.

- [ ] **Step 1: 스키마 갱신**

```python
from datetime import datetime

class AdminPhotoReviewItem(ApiModel):
    order_id: str
    status: str
    service_name: str
    size_or_quantity: str | None = None
    customer_name: str
    team_name: str | None = None
    scheduled_date: str | None = None
    requested_time: str | None = None
    pending_photo_count: int = 0
    approved_photo_count: int = 0
    can_send_customer_link: bool = False
    last_customer_link_sent_at: datetime | None = None       # 추가
    photos: list[PhotoRead]
```

- [ ] **Step 2: `MessageRepository.last_sent_at` 추가**

**v8: 모듈 상단 import 추가 명세.** 현재 `backend/app/repositories/messages.py`는 `datetime`/`MessageType`/`MessageStatus`/`MessageLog`를 import하지 않으므로 시그니처/본문을 그대로 넣으면 컴파일이 깨진다. 먼저 모듈 상단에 다음 import를 추가한다 (이미 있는 항목은 skip).

```python
from datetime import datetime

from app.domain.constants import MessageStatus, MessageType
from app.models.message import MessageLog
```

그 다음 클래스에 메서드를 추가한다:

```python
def last_sent_at(
    self,
    *,
    order_id: str,
    message_type: MessageType,
) -> datetime | None:
    from sqlalchemy import select

    return self.db.execute(
        select(MessageLog.sent_at)
        .where(
            MessageLog.order_id == order_id,
            MessageLog.message_type == message_type,
            MessageLog.status.in_([MessageStatus.SENT, MessageStatus.DELIVERED]),
        )
        .order_by(MessageLog.sent_at.desc())
        .limit(1)
    ).scalar_one_or_none()
```

> `MessageLog.sent_at` 컬럼명이 다르면(`created_at`/`delivered_at` 등) 실제 컬럼명에 맞춘다. 가장 정확한 시각을 우선.
>
> **컴파일 확인 (v8 추가):** `python -m compileall backend/app/repositories/messages.py` — 출력에 `NameError` 없이 깨끗하게 통과해야 한다.

- [ ] **Step 3: queue list 핸들러에서 값 채움 + `can_send_customer_link` 완화**

`backend/app/api/routes/admin/photos.py`의 `list_photo_review_queue`를 다음으로 갱신.

```python
@router.get("/review-queue", response_model=list[AdminPhotoReviewItem])
def list_photo_review_queue(
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> list[AdminPhotoReviewItem]:
    message_repo = MessageRepository(db)
    items = []
    for order, photos, approved_count in PhotoRepository(db).list_review_queue():
        pending_count = len([photo for photo in photos if not photo.is_customer_visible])
        items.append(
            AdminPhotoReviewItem(
                order_id=order.id,
                status=order.status,
                service_name=order.service_name,
                size_or_quantity=order.size_or_quantity,
                customer_name=order.customer_name,
                team_name=order.team_name,
                scheduled_date=order.scheduled_date.isoformat() if order.scheduled_date else None,
                requested_time=order.requested_time,
                pending_photo_count=pending_count,
                approved_photo_count=approved_count,
                # 정책 변경(2026-05-18): 재전송 가능성을 보장하기 위해
                # 완료 상태에서도 사진이 1장 이상이면 발송 가능.
                can_send_customer_link=approved_count > 0
                and order.status != OrderStatus.CANCELLED,
                last_customer_link_sent_at=message_repo.last_sent_at(
                    order_id=order.id,
                    message_type=MessageType.CUSTOMER_PHOTO_READY,
                ),
                photos=photos,
            )
        )
    return items
```

import 보강 (파일 상단):

```python
from app.domain.constants import MessageType, OrderStatus
from app.repositories.messages import MessageRepository
```

- [ ] **Step 4: 컴파일 + 커밋**

```powershell
python -m compileall backend/app/schemas/photo.py backend/app/repositories/messages.py backend/app/api/routes/admin/photos.py
```

```bash
git add backend/app/schemas/photo.py backend/app/repositories/messages.py backend/app/api/routes/admin/photos.py
git commit -m "feat(photo-review): 마지막 사진 링크 발송 시각 노출 + 완료 상태 재전송 허용"
```

---

## Task 8 — 백엔드: `revoke_photo` 라우트 + 테스트 갱신

**Files:**
- Modify: `backend/app/api/routes/admin/photos.py` (revoke 라우트 추가)
- Modify: `backend/tests/conftest.py` (fixture 신규 또는 보강)
- Modify: `backend/tests/test_partner_photo_evidence.py` (정책 가정 갱신)
- Modify: `backend/tests/test_auth_integration.py` (line 149, 163, 166, 1011, 1072, 1086, 1111, 1259, 1284, 1291, 1374, 1495 갱신)
- Create: `backend/tests/test_photo_auto_visibility.py`
- Create: `backend/tests/test_photo_revoke.py`

**구현 의도 (Codex review #5 blocking 반영):**
- v1에서 누락됐던 `test_auth_integration.py`의 정책 단언을 모두 갱신.
- 신규 시나리오(자동공개/revoke/재전송) 전용 테스트 분리.

- [ ] **Step 1: revoke 라우트 추가**

`backend/app/api/routes/admin/photos.py`의 `approve_photo` 핸들러 아래.

```python
@router.post("/{photo_id}/revoke", response_model=PhotoRead)
def revoke_photo(
    photo_id: str,
    db: Session = Depends(get_session),
    user: CurrentUser = Depends(require_admin),
):
    try:
        return PhotoService(db).revoke_visibility(photo_id, actor_user_id=user.id)
    except ValueError as exc:
        if str(exc) == "photo_not_found":
            raise HTTPException(status_code=404, detail="photo_not_found") from exc
        raise
```

- [ ] **Step 2: conftest.py에 fixture 추가 (필요 시)**

```powershell
Get-Content -LiteralPath backend/tests/conftest.py | Select-String -Pattern "seed_admin_token|seed_partner_token|seed_order_id"
```

**v6 갱신:** 현재 `backend/tests/conftest.py`는 사실상 비어 있고, `client`는 fixture가 아니라 `test_auth_integration.py:45`의 `make_test_client()` factory를 직접 호출하는 패턴이다. 신규 테스트 4종(`test_photo_auto_visibility.py`, `test_photo_revoke.py`, 기타)이 fixture를 요구하므로, **`make_test_client`를 그대로 호출하는 `client` fixture를 conftest에 신규 명세한다.** 기존 패턴을 깨지 않는다.

```python
# backend/tests/conftest.py
import pytest
from fastapi.testclient import TestClient

from app.db.seed import (
    DEV_ORDER_ID,
    DEV_ADMIN_EMAIL,
    DEV_ADMIN_PASSWORD,
    DEV_PARTNER_PHONE,
    DEV_PARTNER_PASSWORD,
)
# 기존 패턴 재사용. make_test_client는 test_auth_integration.py에서 import 가능하지만
# 순환 import를 피하기 위해 동일한 factory를 conftest로 내려서 단일 위치로 통합한다.
# 단, v6 명세에서는 기존 함수를 옮기지 않고 그대로 import해 사용한다.
from tests.test_auth_integration import make_test_client


@pytest.fixture
def client() -> TestClient:
    """In-memory SQLite seed DB + FastAPI app을 한 묶음으로 제공한다.
    매 테스트마다 새 engine/session을 만들어 격리한다.
    """
    return make_test_client()


@pytest.fixture
def seed_admin_token(client: TestClient) -> str:
    # LoginRequest는 identifier/password 형태. (backend/app/schemas/auth.py:5-7 참조)
    response = client.post(
        "/api/auth/admin/login",
        json={"identifier": DEV_ADMIN_EMAIL, "password": DEV_ADMIN_PASSWORD},
    )
    return response.json()["access_token"]


@pytest.fixture
def seed_partner_token(client: TestClient) -> str:
    response = client.post(
        "/api/auth/partner/login",
        json={"identifier": DEV_PARTNER_PHONE, "password": DEV_PARTNER_PASSWORD},
    )
    return response.json()["access_token"]


@pytest.fixture
def seed_order_id() -> str:
    return DEV_ORDER_ID
```

> **순환 import 주의:** `tests.test_auth_integration`이 conftest의 fixture를 직접 import하지는 않으니 안전하다. pytest 실행 시 conftest는 collection 단계에서 한 번만 로드되고, test_auth_integration의 다른 import는 `make_test_client` 정의 후에 평가된다. 만약 미래에 `test_auth_integration`이 conftest fixture를 사용하기 시작하면 `make_test_client`를 별도 모듈(`backend/tests/_factories.py`)로 분리하는 것을 검토한다.

> **확인 명령:**
> ```powershell
> python -m pytest backend/tests/test_photo_auto_visibility.py -v 2>&1 | Select-String -Pattern "PASSED|FAILED|fixture"
> ```
> 기대: 4개 테스트 모두 PASSED. "fixture 'client' not found" 출력 없음.

- [ ] **Step 3: `test_auth_integration.py` 정책 단언 일괄 갱신**

다음 라인들을 의미에 맞춰 수정한다. 정확한 위치는 grep으로 다시 확인.

| line | 현재 | 갱신 |
|---|---|---|
| 149 | `assert complete_response.json()["status"] == "사진검수대기"` | `assert complete_response.json()["status"] == "고객전달필요"` |
| 163 | `assert body["status"] == "사진검수대기"` | `assert body["status"] == "고객전달필요"` |
| 166 | `assert {"작업진행", "사진검수대기"}.issubset(status_targets)` | `assert {"작업진행", "고객전달필요"}.issubset(status_targets)` |
| 1011 | `status=OrderStatus.PHOTO_REVIEW_PENDING` (seed 상태 설정) | `status=OrderStatus.CUSTOMER_DELIVERY_NEEDED` |
| 1072 / 1086 | seed 사진 `is_customer_visible=False` | `True` (자동 공개 정책 반영) |
| 1111 | `assert body["photos"][0]["is_customer_visible"] is False` | `assert body["photos"][0]["is_customer_visible"] is True` |
| 1259 | `assert uploaded["is_customer_visible"] is False` | `assert uploaded["is_customer_visible"] is True` |
| 1284 | `assert queue_item["can_send_customer_link"] is False` (사진 0장일 때) | 의미 유지: 사진이 0장일 때 false. 단 사진 1장 + 상태가 `고객전달완료`일 때 `True`인 케이스(line 1374)도 함께 갱신. |
| 1291 | `assert detail["status"] == "사진검수대기"` | `assert detail["status"] == "고객전달필요"` |
| 1374 | `assert delivered_item["can_send_customer_link"] is False` (완료 상태에서 false 기대) | `assert delivered_item["can_send_customer_link"] is True` (재전송 허용) |
| 1495 | `assert uploaded["is_customer_visible"] is False` | `True` |

> 라인 번호는 grep 시점 기준이라 작업 중에 변경될 수 있다. 각 라인을 grep으로 한 번 더 확인 후 수정.

> "관리자 승인 흐름"을 명시적으로 검증하던 케이스는 Task 8 Step 5(신규 `test_photo_auto_visibility.py`)로 이전. revoke 시나리오는 `test_photo_revoke.py`로.

- [ ] **Step 4: `test_partner_photo_evidence.py` 갱신**

```powershell
Select-String -LiteralPath backend/tests/test_partner_photo_evidence.py -Pattern "is_customer_visible|approve|승인"
```

매치되는 단언/주석을 자동 공개 기준으로 갱신한다. "협력사 사진 기본 비공개" 단언이 있으면 모두 자동 공개로.

- [ ] **Step 5: `test_photo_auto_visibility.py` 신규**

```python
from fastapi.testclient import TestClient

from app.domain.constants import OrderStatus, TimelineEventType


def _jpeg_bytes() -> bytes:
    return b"\xff\xd8\xff\xe0" + b"\x00" * 64 + b"\xff\xd9"


def test_partner_upload_is_auto_visible(client: TestClient, seed_partner_token: str, seed_order_id: str) -> None:
    response = client.post(
        f"/api/partner/jobs/{seed_order_id}/photos",
        headers={"Authorization": f"Bearer {seed_partner_token}"},
        files={"file": ("after.jpg", _jpeg_bytes(), "image/jpeg")},
        data={"photo_type": "after"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_customer_visible"] is True


def test_partner_upload_does_not_change_status(client: TestClient, seed_partner_token: str, seed_admin_token: str, seed_order_id: str) -> None:
    """v4 정책(D4.5): 사진 업로드는 상태를 바꾸지 않는다. timeline에만 photo_uploaded/photo_approved가 남는다."""
    pre_status = client.get(
        f"/api/admin/orders/{seed_order_id}",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    ).json()["status"]

    client.post(
        f"/api/partner/jobs/{seed_order_id}/photos",
        headers={"Authorization": f"Bearer {seed_partner_token}"},
        files={"file": ("after.jpg", _jpeg_bytes(), "image/jpeg")},
        data={"photo_type": "after"},
    )

    order = client.get(
        f"/api/admin/orders/{seed_order_id}",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    ).json()
    assert order["status"] == pre_status  # 변경되지 않음
    timeline_events = [event["event_type"] for event in order["timeline"]]
    assert TimelineEventType.PHOTO_UPLOADED.value in timeline_events
    assert TimelineEventType.PHOTO_APPROVED.value in timeline_events


def test_complete_partner_job_advances_to_delivery_needed(client: TestClient, seed_partner_token: str, seed_admin_token: str, seed_order_id: str) -> None:
    """v4 정책(D4.5): IN_PROGRESS 상태 + 사진 1장 이상에서 complete를 호출하면 CUSTOMER_DELIVERY_NEEDED로 전환."""
    # seed 주문을 IN_PROGRESS로 셋업.
    client.post(
        f"/api/partner/jobs/{seed_order_id}/start",
        headers={"Authorization": f"Bearer {seed_partner_token}"},
    )
    client.post(
        f"/api/partner/jobs/{seed_order_id}/photos",
        headers={"Authorization": f"Bearer {seed_partner_token}"},
        files={"file": ("after.jpg", _jpeg_bytes(), "image/jpeg")},
        data={"photo_type": "after"},
    )

    response = client.post(
        f"/api/partner/jobs/{seed_order_id}/complete",
        headers={"Authorization": f"Bearer {seed_partner_token}"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == OrderStatus.CUSTOMER_DELIVERY_NEEDED.value


def test_complete_partner_job_requires_photo(client: TestClient, seed_partner_token: str, seed_order_id: str) -> None:
    """v4 정책: IN_PROGRESS 상태이지만 사진이 0장이면 422."""
    # seed 주문을 IN_PROGRESS로 셋업 (사진은 올리지 않는다).
    client.post(
        f"/api/partner/jobs/{seed_order_id}/start",
        headers={"Authorization": f"Bearer {seed_partner_token}"},
    )
    response = client.post(
        f"/api/partner/jobs/{seed_order_id}/complete",
        headers={"Authorization": f"Bearer {seed_partner_token}"},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "photo_required_for_completion"


def test_complete_partner_job_blocked_outside_in_progress(client: TestClient, seed_partner_token: str, seed_order_id: str) -> None:
    """v4 정책: IN_PROGRESS 이외 상태에서 complete를 호출하면 409 invalid_status_transition. 가드 통과 전에는 photo 검사로 넘어가지 않는다."""
    # seed 주문은 기본적으로 '일정확정' 등 IN_PROGRESS가 아닌 상태로 시작한다.
    response = client.post(
        f"/api/partner/jobs/{seed_order_id}/complete",
        headers={"Authorization": f"Bearer {seed_partner_token}"},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "invalid_status_transition"
```

- [ ] **Step 6: `test_photo_revoke.py` 신규**

```python
from fastapi.testclient import TestClient

from app.domain.constants import OrderStatus, TimelineEventType


def _jpeg_bytes() -> bytes:
    return b"\xff\xd8\xff\xe0" + b"\x00" * 64 + b"\xff\xd9"


def _upload(client: TestClient, partner_token: str, order_id: str) -> str:
    res = client.post(
        f"/api/partner/jobs/{order_id}/photos",
        headers={"Authorization": f"Bearer {partner_token}"},
        files={"file": ("after.jpg", _jpeg_bytes(), "image/jpeg")},
        data={"photo_type": "after"},
    )
    return res.json()["id"]


def _setup_delivery_needed(client: TestClient, partner_token: str, order_id: str) -> str:
    """v5: 사진 업로드만으로는 상태가 안 바뀌므로 start+upload+complete까지 호출해 CUSTOMER_DELIVERY_NEEDED 상태를 만든다."""
    client.post(
        f"/api/partner/jobs/{order_id}/start",
        headers={"Authorization": f"Bearer {partner_token}"},
    )
    photo_id = _upload(client, partner_token, order_id)
    client.post(
        f"/api/partner/jobs/{order_id}/complete",
        headers={"Authorization": f"Bearer {partner_token}"},
    )
    return photo_id


def test_admin_revoke_returns_to_in_progress_when_no_photos_left(client, seed_partner_token, seed_admin_token, seed_order_id) -> None:
    """v5: 고객전달필요 상태에서 마지막 공개 사진을 revoke하면 작업진행으로 되돌아간다."""
    photo_id = _setup_delivery_needed(client, seed_partner_token, seed_order_id)
    res = client.post(
        f"/api/admin/photos/{photo_id}/revoke",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )
    assert res.status_code == 200
    assert res.json()["is_customer_visible"] is False

    detail = client.get(
        f"/api/admin/orders/{seed_order_id}",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    ).json()
    events = [event["event_type"] for event in detail["timeline"]]
    assert TimelineEventType.PHOTO_REVOKED.value in events
    assert detail["status"] == OrderStatus.IN_PROGRESS.value


def test_revoke_keeps_status_when_other_visible_photos_exist(client, seed_partner_token, seed_admin_token, seed_order_id) -> None:
    """v5: 다른 공개 사진이 남아있으면 상태는 그대로 유지."""
    client.post(
        f"/api/partner/jobs/{seed_order_id}/start",
        headers={"Authorization": f"Bearer {seed_partner_token}"},
    )
    photo_id_a = _upload(client, seed_partner_token, seed_order_id)
    _upload(client, seed_partner_token, seed_order_id)
    client.post(
        f"/api/partner/jobs/{seed_order_id}/complete",
        headers={"Authorization": f"Bearer {seed_partner_token}"},
    )

    res = client.post(
        f"/api/admin/photos/{photo_id_a}/revoke",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )
    assert res.status_code == 200
    detail = client.get(
        f"/api/admin/orders/{seed_order_id}",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    ).json()
    assert detail["status"] == OrderStatus.CUSTOMER_DELIVERY_NEEDED.value


def test_revoke_keeps_delivery_done_status(client, seed_partner_token, seed_admin_token, seed_order_id) -> None:
    """v5: CUSTOMER_DELIVERY_DONE 상태에서 마지막 공개 사진까지 revoke해도 상태는 유지하고 timeline에 photo_revoked만 남긴다."""
    photo_id = _setup_delivery_needed(client, seed_partner_token, seed_order_id)
    # 운영자가 명시적으로 상태를 CUSTOMER_DELIVERY_DONE로 옮긴 상황을 가정.
    client.patch(
        f"/api/admin/orders/{seed_order_id}",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
        json={"status": OrderStatus.CUSTOMER_DELIVERY_DONE.value},
    )

    res = client.post(
        f"/api/admin/photos/{photo_id}/revoke",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )
    assert res.status_code == 200
    detail = client.get(
        f"/api/admin/orders/{seed_order_id}",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    ).json()
    assert detail["status"] == OrderStatus.CUSTOMER_DELIVERY_DONE.value


def test_revoke_idempotent_when_already_hidden(client, seed_partner_token, seed_admin_token, seed_order_id) -> None:
    photo_id = _setup_delivery_needed(client, seed_partner_token, seed_order_id)
    client.post(
        f"/api/admin/photos/{photo_id}/revoke",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )
    # 두 번째 revoke: 200 + is_customer_visible False, 새 timeline 안 남김.
    res = client.post(
        f"/api/admin/photos/{photo_id}/revoke",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )
    assert res.status_code == 200
    assert res.json()["is_customer_visible"] is False
```

- [ ] **Step 7: 전체 테스트 + 커밋**

```powershell
cd backend; python -m pytest -q
```

전체 통과 확인.

```bash
git add backend/app/api/routes/admin/photos.py backend/tests/
git commit -m "test(photos): 자동 공개/revoke/재전송 시나리오 + 기존 테스트 정책 가정 갱신"
```

---

## Task 9 — 백엔드: dashboard 카운터 정리

**Files:** Modify `backend/app/services/dashboard.py:30-44`

- [ ] **Step 1: 코드 단순화**

`photo_review_pending` 카운터는 그대로 두되 (Schema 호환), 자동공개 정책상 0으로 수렴한다. 단, 오늘 작업 카운터(`today_in_progress` 등)에서 `PHOTO_REVIEW_PENDING`을 포함하던 줄(line 34)을 제거.

기존:
```python
status_in(
    [
        OrderStatus.SCHEDULED,
        OrderStatus.IN_PROGRESS,
        OrderStatus.PHOTO_REVIEW_PENDING,
    ]
),
```

갱신:
```python
status_in(
    [
        OrderStatus.SCHEDULED,
        OrderStatus.IN_PROGRESS,
    ]
),
```

- [ ] **Step 2: 컴파일 + 테스트 + 커밋**

```powershell
python -m compileall backend/app/services/dashboard.py
cd backend; python -m pytest tests/test_auth_integration.py -k dashboard -q
```

```bash
git add backend/app/services/dashboard.py
git commit -m "feat(dashboard): 오늘 작업 큐에서 사진검수대기 제거"
```

---

## Task 10 — 프론트: 사진 API 클라이언트에 `revokePhoto` 추가

**Files:** Modify `frontend/src/api/photos.ts`

- [ ] **Step 1: 함수 추가**

```typescript
export function revokePhoto(photoId: string) {
  return apiRequest(`/admin/photos/${encodeURIComponent(photoId)}/revoke`, {
    method: 'POST',
  });
}
```

- [ ] **Step 2: typecheck + 커밋**

```powershell
cd frontend; npm run typecheck
```

```bash
git add frontend/src/api/photos.ts
git commit -m "feat(api-client): revokePhoto 추가"
```

---

## Task 11 — 프론트: 신규 주문 등록 폼 카테고리/상세 2단계 (요청 #1)

**Files:** Modify `frontend/src/features/admin/orders/OrderFormPage.tsx`

(v1 Task 7과 동일. v2에서 변경 없음.)

- [ ] **Step 1: 카테고리 변경 핸들러 추가**

```javascript
const handleServiceCategoryChange = (categoryId) => {
  setForm((current) => ({
    ...current,
    service_category_id: categoryId,
    service_item_id: '',
  }));
};
```

- [ ] **Step 2: `handleServiceItemChange` 단순화** (v1 Task 7 Step 2 동일 — 명세 본문 참조)

- [ ] **Step 3: "상품 / 일정" Section 첫 Field 치환**

```jsx
<Field label="카테고리">
  <select
    className="input"
    data-testid="order-service-category"
    value={form.service_category_id}
    onChange={(event) => handleServiceCategoryChange(event.target.value)}
  >
    <option value="">직접 입력</option>
    {(serviceCatalog.data || [])
      .filter((category) => category.is_active)
      .map((category) => (
        <option key={category.id} value={category.id}>{category.name}</option>
      ))}
  </select>
</Field>
<Field label="상세상품">
  <select
    className="input"
    data-testid="order-service-item"
    value={form.service_item_id}
    onChange={(event) => handleServiceItemChange(event.target.value)}
    disabled={!form.service_category_id}
  >
    <option value="">직접 입력</option>
    {(serviceCatalog.data || [])
      .filter((category) => category.id === form.service_category_id && category.is_active)
      .flatMap((category) => (category.items || []).filter((item) => item.is_active))
      .map((item) => (
        <option key={item.id} value={item.id}>
          {item.name} · {formatWon(item.base_price)}
        </option>
      ))}
  </select>
</Field>
```

- [ ] **Step 4: typecheck/lint + 수동 확인 + 커밋**

```bash
git add frontend/src/features/admin/orders/OrderFormPage.tsx
git commit -m "feat(orders): 신규 주문 등록 폼 카테고리/상세상품 2단계 드롭다운"
```

---

## Task 12 — 프론트: 주문관리 협력사 탭 + 접수일 필터 (요청 #2, partner_id 기준)

**Files:** Modify `frontend/src/features/admin/orders/OrdersPage.tsx`

**v1 → v2 변경 (Codex review #should-fix):**
- 협력사 매칭은 `order.team === partner.name`(team_name 비교)이 아니라 **`order.partner_id === partner.id`** 기준.
- `Icon name="users"` 미존재 → **`user`**로 대체.

- [ ] **Step 1: state 추가**

```javascript
const [partnerFilter, setPartnerFilter] = React.useState('all');
const [receivedDateFilter, setReceivedDateFilter] = React.useState(() => createDateFilter('all'));
```

- [ ] **Step 2: 활성 협력사 가나다 정렬 메모**

```javascript
const sortedActivePartners = React.useMemo(() => {
  return partners
    .filter((partner) => partner.is_active !== false)
    .slice()
    .sort((a, b) => String(a.name || '').localeCompare(String(b.name || ''), 'ko'));
}, [partners]);
```

- [ ] **Step 3: `toOrderRow`에 `receivedRaw` + `partnerId` 보존**

```javascript
function toOrderRow(order) {
  return {
    id: order.id,
    partnerId: order.partner_id || null,      // 추가 (D3 + Codex #should-fix)
    status: order.status,
    receivedRaw: order.received_date,         // 추가
    received: formatDate(order.received_date),
    // ... 나머지 유지 ...
  };
}
```

- [ ] **Step 4: helper 함수 추가**

```javascript
function matchesReceivedDateFilter(receivedValue, dateFilter) {
  if (!dateFilter.start && !dateFilter.end) return true;
  if (!receivedValue) return false;
  const { start, end } = normalizeDateRange(dateFilter.start, dateFilter.end);
  if (start && receivedValue < start) return false;
  if (end && receivedValue > end) return false;
  return true;
}

function matchesPartnerFilter(order, partnerFilter) {
  if (!partnerFilter || partnerFilter === 'all') return true;
  return order.partnerId === partnerFilter;
}
```

- [ ] **Step 5: filtered 체인에 두 필터 추가**

```javascript
.filter((o) => matchesDateFilter(o.scheduledDate, dateFilter))
.filter((o) => matchesReceivedDateFilter(o.receivedRaw, receivedDateFilter))
.filter((o) => matchesPartnerFilter(o, partnerFilter))
.filter((o) => matchesOrderQuery(o, query)),
```

- [ ] **Step 6: 협력사 탭 + 접수일 행 UI 삽입**

기존 `{/* Tabs — minimal underline */}` 블록 바로 위에 다음을 삽입.

```jsx
{/* 협력사 탭 (PDF 요청 #2) */}
<div style={{ padding: '0 24px 8px', background: 'var(--bg)', display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, color: 'var(--text-tertiary)', fontSize: 12, fontWeight: 600, whiteSpace: 'nowrap' }}>
    <Icon name="user" size={12}/> 협력사
  </span>
  <button
    type="button"
    data-testid="orders-partner-tab-all"
    aria-pressed={partnerFilter === 'all'}
    onClick={() => setPartnerFilter('all')}
    style={datePresetButton(partnerFilter === 'all')}
  >
    전체
  </button>
  {sortedActivePartners.map((partner) => (
    <button
      key={partner.id}
      type="button"
      data-testid={`orders-partner-tab-${partner.id}`}
      aria-pressed={partnerFilter === partner.id}
      onClick={() => setPartnerFilter(partner.id)}
      style={datePresetButton(partnerFilter === partner.id)}
    >
      {partner.name}
    </button>
  ))}
</div>

{/* 접수일 필터 (PDF 요청 #2) */}
<div style={{ padding: '0 24px 12px', background: 'var(--bg)', display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, color: 'var(--text-tertiary)', fontSize: 12, fontWeight: 600, whiteSpace: 'nowrap' }}>
    <Icon name="calendar" size={12}/> 접수일
  </span>
  {[
    ['all', '전체'],
    ['today', '오늘'],
    ['tomorrow', '내일'],
    ['week', '이번주'],
    ['month', '이번달'],
  ].map(([key, label]) => (
    <button
      key={key}
      type="button"
      data-testid={`orders-received-preset-${key}`}
      aria-pressed={receivedDateFilter.preset === key}
      onClick={() => setReceivedDateFilter(createDateFilter(key))}
      style={datePresetButton(receivedDateFilter.preset === key)}
    >
      {label}
    </button>
  ))}
  <DatePicker compact testId="orders-received-start" ariaLabel="접수일 시작" placeholder="시작일"
    value={receivedDateFilter.start}
    onChange={(value) => setReceivedDateFilter((current) => ({ ...current, preset: 'range', start: value }))}
  />
  <span style={{ color: 'var(--text-quaternary)', fontSize: 12 }}>~</span>
  <DatePicker compact testId="orders-received-end" ariaLabel="접수일 종료" placeholder="종료일"
    value={receivedDateFilter.end}
    onChange={(value) => setReceivedDateFilter((current) => ({ ...current, preset: 'range', end: value }))}
  />
  {(receivedDateFilter.start || receivedDateFilter.end) && (
    <button type="button" data-testid="orders-received-clear" style={softGhostBtn} onClick={() => setReceivedDateFilter(createDateFilter('all'))}>
      해제
    </button>
  )}
</div>
```

- [ ] **Step 7: typecheck/lint + 수동 확인 + 커밋**

```bash
git add frontend/src/features/admin/orders/OrdersPage.tsx
git commit -m "feat(orders): 주문관리에 협력사(partner_id 기준) 탭과 접수일 필터 추가"
```

---

## Task 13 — 프론트: OrderDetailPage `timelineEventLabel`에 `photo_revoked` 추가

**Files:** Modify `frontend/src/features/admin/orders/OrderDetailPage.tsx:874-885` (`timelineEventLabel`)

- [ ] **Step 1: 라벨 추가**

```javascript
function timelineEventLabel(type) {
  const labels = {
    created: '주문 생성',
    status_changed: '상태 변경',
    partner_assigned: '협력사 배정',
    message_sent: '안내 발송',
    photo_uploaded: '사진 업로드',
    photo_approved: '사진 공개',          // 라벨 의미 변경 (자동공개 시대)
    photo_revoked: '사진 비공개 처리',     // 추가
    customer_link_sent: '고객 링크 발송',
    memo_added: '메모 추가',
  };
  return labels[type] || type;
}
```

- [ ] **Step 2: typecheck + 커밋**

```bash
git add frontend/src/features/admin/orders/OrderDetailPage.tsx
git commit -m "feat(order-detail): 사진 비공개 이벤트 타임라인 라벨 추가"
```

---

## Task 14 — 프론트: 사진검수 화면 단순화 + 재전송 + revoke (요청 #3)

**Files:** Rewrite `frontend/src/features/admin/photo-review/PhotoReviewPage.tsx`

(v1 Task 9 + Codex review #should-fix 반영. 핵심: 재전송 버튼 활성 조건이 `last_customer_link_sent_at` 기반 + `status != 취소`로 단순화. `selectedStage?.key !== 'done'` 조건 제거.)

- [ ] **Step 1: 파일 헤더의 FILTERS 단순화**

```javascript
const FILTERS = [
  { key: 'all', label: '전체' },
  { key: 'pending_link', label: '링크 미발송' },
  { key: 'done', label: '전달완료' },
];
```

- [ ] **Step 2: import 갱신**

```typescript
import { listPhotoReviewQueue, revokePhoto } from '../../../api/photos';
```

(`approvePhoto`는 새 UI에서 호출하지 않으므로 import 제거.)

- [ ] **Step 3: handler 재정비**

기존 `handleApprove`, `handleApproveAll` 통째 삭제. 추가:

```javascript
const handleRevoke = async (photoId) => {
  setError(null);
  setSentMessage(null);
  setIsApproving(true);
  try {
    await revokePhoto(photoId);
    queue.reload();
  } catch {
    setError('사진 비공개 처리에 실패했습니다.');
  } finally {
    setIsApproving(false);
  }
};
```

- [ ] **Step 4: `reviewStage` 단순화 + 재전송 조건 수정**

```javascript
function reviewStage(item) {
  if (item.status === '취소') {
    return { key: 'done', label: '취소', tone: 'success' };
  }
  if (item.approved_photo_count > 0 && !item.last_customer_link_sent_at) {
    return { key: 'pending_link', label: '링크 미발송', tone: 'warn' };
  }
  if (item.approved_photo_count > 0 && item.last_customer_link_sent_at) {
    return { key: 'done', label: '전달완료', tone: 'success' };
  }
  return { key: 'pending_link', label: '대기', tone: 'brand' };
}
```

```javascript
// 재전송 조건 (v2): 사진 1장 이상 + 취소 아님. 완료 상태에서도 재전송 허용.
const canSendCustomerLink = Boolean(
  selected
    && selected.status !== '취소'
    && approvedPhotos.length > 0,
);
```

- [ ] **Step 5: `GateSteps` 호출/정의 제거** (v1 Task 9 Step 5 동일)

- [ ] **Step 6: 우측 액션 패널 버튼 치환**

```jsx
<button
  data-testid="photo-send-customer-link"
  className="btn btn--primary btn--block btn--lg"
  disabled={isSending || !selected || !canSendCustomerLink}
  onClick={() => void handleSendCustomerLink()}
>
  <Icon name="send" size={14}/>
  {selected?.last_customer_link_sent_at ? '고객 사진 링크 재전송' : '고객 사진 링크 발송'}
</button>
<button
  data-testid="photo-revoke-selected"
  className="btn btn--secondary btn--block"
  disabled={!activePhoto || !activePhoto.is_customer_visible || isApproving}
  onClick={() => activePhoto && void handleRevoke(activePhoto.id)}
>
  <Icon name="eyeOff" size={13}/> 선택 사진 비공개로 되돌리기
</button>
```

> Icon name "eyeOff" 미존재 시 `eye` 또는 다른 정의된 아이콘으로 대체.

- [ ] **Step 7: KVRow + 인라인 헬퍼 + 타이틀 갱신** (v1 Task 9 Step 7~9 동일)

- [ ] **Step 8: typecheck/lint + 수동 확인 + 커밋**

```bash
git add frontend/src/features/admin/photo-review/PhotoReviewPage.tsx
git commit -m "feat(photo-review): 검수 단계 제거, 재전송 + 비공개 되돌리기 액션"
```

---

## Task 15 — 프론트: 협력사/고객 화면 안내 문구 갱신

**Files:**
- Modify: `frontend/src/features/partner/PartnerJobDetail.tsx`
- Modify: `frontend/src/features/customer/CustomerReservation.tsx`

**구현 의도 (Codex review #should-fix 반영):** "관리자 승인 후 공개"라는 기존 안내가 자동 공개 정책과 충돌. 사용자에게 잘못된 멘탈모델을 심으므로 갱신한다.

- [ ] **Step 1: PartnerJobDetail의 안내 문구 갱신**

```powershell
Select-String -LiteralPath frontend/src/features/partner/PartnerJobDetail.tsx -Pattern "검수|승인|관리자가|공개"
```

매치되는 안내 문구를 다음과 같이 갱신:

| 기존 의미 | 갱신 의미 |
|---|---|
| "관리자 검수 후 고객에게 공개됩니다." | "업로드 즉시 고객에게 공개됩니다. 잘못 올렸다면 관리자에게 비공개 처리 요청을 하세요." |
| "검수 대기 중입니다." | (해당 문구 제거) |

- [ ] **Step 2: CustomerReservation의 "사진 준비 중" 표시 검토**

```powershell
Select-String -LiteralPath frontend/src/features/customer/CustomerReservation.tsx -Pattern "사진|준비|승인|검수"
```

"승인 전 사진은 보이지 않습니다" 같은 안내가 있으면 "협력사가 사진을 올리면 이곳에 표시됩니다"로 갱신.

- [ ] **Step 3: typecheck + 커밋**

```bash
git add frontend/src/features/partner/PartnerJobDetail.tsx frontend/src/features/customer/CustomerReservation.tsx
git commit -m "feat(ui): 협력사/고객 화면 자동 공개 정책 안내 문구"
```

---

## Task 16 — E2E 테스트 갱신

**Files:**
- Modify: `frontend/e2e/admin-e2e.spec.ts` (line 343–355, 신규 주문 폼 카테고리 단계)
- Modify: `frontend/e2e/partner-customer-e2e.spec.ts` (line 88–101)
- Create: `frontend/e2e/admin-photo-review-e2e.spec.ts`
- Create or augment: `frontend/e2e/helpers.ts`

**구현 의도 (Codex review #5 blocking):** v1에서 누락됐던 `photo-approve-selected`, `photo-filter-review` 사용처를 명시적으로 갱신.

- [ ] **Step 1: `admin-e2e.spec.ts:343-355` 갱신**

```typescript
// 변경 전 (line 343–355 부근, 사진검수 시나리오):
await expect(page.getByTestId('photo-filter-review')).toHaveAttribute('aria-pressed', 'false');
await page.getByTestId('photo-filter-review').click();
// ... 중략 ...
await page.getByTestId('photo-approve-selected').click();

// 변경 후 (자동 공개 + revoke로 시나리오 전환):
await expect(page.getByTestId('photo-filter-pending_link')).toBeVisible();
await page.getByTestId('photo-filter-pending_link').click();
// ... 사진이 자동 공개 상태로 등록되어 있는지 확인 후 ...
const sendButton = page.getByTestId('photo-send-customer-link');
await expect(sendButton).toBeEnabled();
await sendButton.click();
await expect(page.getByTestId('photo-send-notice')).toContainText('고객 링크를 발송');
```

신규 주문 폼 시나리오에는 카테고리 select 단계를 추가:

```typescript
await page.getByTestId('order-service-category').selectOption({ label: '청소' });
await page.getByTestId('order-service-item').selectOption({ label: /입주청소/ });
```

> label 텍스트는 seed 데이터(`backend/app/db/seed.py:DEV_SERVICE_CATEGORY_ID` / `DEV_SERVICE_ITEM_ID`)에 맞춘다.

- [ ] **Step 2: `partner-customer-e2e.spec.ts:88-101` 갱신**

```typescript
// 변경 전 (line 88 부근):
await adminPage.getByTestId('photo-filter-review').click();
// ... 사진 승인 흐름 ...
await adminPage.getByTestId('photo-approve-selected').click();

// line 101 부근:
visiblePhotos: detail.photos.filter((photo) => photo.is_customer_visible).length,

// 변경 후 (v10): 자동 공개 정책에 맞춰 partner-customer-e2e.spec.ts의 line 74-124를 부분 치환한다.
// 통째 치환 금지. 아래 두 블록만 손댄다:
//   (A) line 74-80 "beforeApproval" 블록 → 자동 공개 3장 확인하는 `autoVisible` 블록으로 치환.
//   (B) line 88-94의 `photo-filter-review`/`photo-approve-selected`/`photo-send-customer-link` disabled
//       단언과 line 93의 `photo-approve-selected.click()`만 삭제하고, 같은 위치에 사진 1장 revoke 흐름을 넣는다.
//   (C) line 95-113의 `photo-send-customer-link.click()` + expect.poll(visiblePhotos: 1) 블록은
//       expect.poll(visiblePhotos: 2 + 'photo_revoked' timeline) 단언으로 갱신.
//   (D) line 115-124의 `afterApproval` 블록 → `afterRevoke` 블록으로 치환.
// 기존 line 82-87의 `adminContext = browser.newContext()`, `adminPage = adminContext.newPage()`,
// `loginAsAdmin(adminPage)`, `admin-nav-photos` 클릭, `admin-photo-review-page` visible 확인,
// `photo-review-item-${flow.orderId}` 클릭은 **그대로 유지한다** (adminPage 변수가 (B) 단계에서 필요).
// 또한 line 113의 `adminContext.close()`도 유지.
//
// 적용 후 흐름 (논리적 순서):
// - 기존: 협력사 업로드 → "승인 전 고객 비노출(beforeApproval)" → admin context 진입 →
//         photo-filter-review → photo-approve-selected → photo-send-customer-link → afterApproval
// - 변경 후: 협력사 업로드 → autoVisible(자동 공개 3장) → admin context 진입 →
//         photo-revoke-selected(1장) → expect.poll(visiblePhotos: 2 + photo_revoked) → afterRevoke(2장)
//
// CustomerReservation의 사진 testid는 `customer-photo-${photo.id}` (frontend/src/features/customer/CustomerReservation.tsx:307).
// `customerVerifyInNewContext`는 기존 helper를 그대로 재사용 (`{ context, page }` 반환).

// 협력사 업로드 직후 첫 고객 컨텍스트로 자동 공개 3장 확인.
const autoVisible = await customerVerifyInNewContext(browser, flow.customerToken, flow.phoneSuffix);
await expect(autoVisible.page.getByTestId('customer-order-page')).toBeVisible();
await expect(autoVisible.page.getByTestId('customer-photo-pending')).toHaveCount(0);  // 자동 공개라 "준비 중" 표시 없음
await expect(
  autoVisible.page.locator('[data-testid^="customer-photo-"]:not([data-testid="customer-photo-pending"])')
).toHaveCount(3);
// 협력사 화면에 노출되던 내부 메모/협력사 정산액은 여전히 고객 DTO에 비노출.
await expect(autoVisible.page.getByText('Internal payment memo')).toHaveCount(0);
await expect(autoVisible.page.getByText('partner_payment_amount')).toHaveCount(0);
await autoVisible.context.close();

// 관리자 페이지에서 첫 사진 썸네일을 선택해 revoke (v9: photo-approve-selected 사용처를 photo-revoke-selected로 치환).
await adminPage.locator('[data-testid^="photo-thumb-"]').first().click();
await adminPage.getByTestId('photo-revoke-selected').click();
await expect(adminPage.locator('[data-testid^="photo-thumb-"]').first().getByText('비공개')).toBeVisible();

// 백엔드 단언: timeline에 photo_revoked, 공개 사진 수 2.
await expect.poll(async () => {
  const detail = await getAdminOrder(request, flow.orderId);
  return {
    visiblePhotos: detail.photos.filter((photo) => photo.is_customer_visible).length,
    timeline: detail.timeline.map((event) => event.event_type),
  };
}).toEqual(expect.objectContaining({
  visiblePhotos: 2,
  timeline: expect.arrayContaining([
    'photo_uploaded',
    'photo_approved',
    'photo_revoked',
  ]),
}));

// 고객 재방문 컨텍스트: 1장이 사라져 2장만 노출.
const afterRevoke = await customerVerifyInNewContext(browser, flow.customerToken, flow.phoneSuffix);
await expect(afterRevoke.page.getByTestId('customer-order-page')).toBeVisible();
await expect(
  afterRevoke.page.locator('[data-testid^="customer-photo-"]:not([data-testid="customer-photo-pending"])')
).toHaveCount(2);
await afterRevoke.context.close();

// 주의: 기존 line 88-94의 `photo-filter-review` 클릭, `photo-approve-selected` 클릭, `photo-send-customer-link`
// disabled 단언은 모두 삭제한다. v4/v5/v6 정책에서는 검수 필터/승인 단계 자체가 사라졌고
// 송신 버튼은 사진 1장 이상이면 즉시 enabled다.
```

- [ ] **Step 3: `admin-photo-review-e2e.spec.ts` 신규**

```typescript
import { test, expect } from '@playwright/test';
import { adminLogin, partnerUploadPhoto, openAdminPhotoReview, createAssignedOrder } from './helpers';

// v8: 각 테스트가 새 주문을 만들어 seed 주문 재사용으로 인한 상태 잔존을 차단.
test('관리자가 사진 링크를 재전송할 수 있다', async ({ browser, page, request }) => {
  const flow = await createAssignedOrder(request);
  await partnerUploadPhoto(browser, { orderId: flow.orderId, photoType: 'after' });
  await adminLogin(page);
  await openAdminPhotoReview(page, flow.orderId);

  const sendButton = page.getByTestId('photo-send-customer-link');
  await expect(sendButton).toContainText('고객 사진 링크 발송');
  await sendButton.click();
  await expect(page.getByTestId('photo-send-notice')).toContainText('고객 링크를 발송');

  // 재전송 라벨로 토글되는지
  await expect(sendButton).toContainText('재전송');
  await sendButton.click();
  await expect(page.getByTestId('photo-send-notice')).toContainText('고객 링크를 발송');
});

test('관리자가 사진을 비공개로 되돌릴 수 있다', async ({ browser, page, request }) => {
  const flow = await createAssignedOrder(request);
  await partnerUploadPhoto(browser, { orderId: flow.orderId, photoType: 'after' });
  await adminLogin(page);
  await openAdminPhotoReview(page, flow.orderId);

  const thumbs = page.locator('[data-testid^="photo-thumb-"]');
  await thumbs.first().click();
  await page.getByTestId('photo-revoke-selected').click();
  await expect(thumbs.first().getByText('비공개')).toBeVisible();
});
```

- [ ] **Step 4: `helpers.ts` 신규 또는 보강**

```powershell
Test-Path frontend/e2e/helpers.ts
```

없으면 생성. **v6 변경:** 기존 `partner-customer-e2e.spec.ts:1-90`에서 검증된 실제 testid/플로우를 그대로 사용한다 (placeholder 없이 동작 가능):

```typescript
import { Browser, Page, expect } from '@playwright/test';

const ONE_PIXEL_PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=',
  'base64',
);

export async function adminLogin(page: Page) {
  await page.goto('/');
  await page.getByTestId('app-mode-admin').click();
  // 실제 testid (frontend/src/features/auth/LoginPages.tsx:70,83,94)
  await page.getByTestId('admin-login-identifier').fill('admin@cleanops.kr');
  await page.getByTestId('admin-login-password').fill('AdminPass123!');
  await page.getByTestId('admin-login-submit').click();
  // 로그인 성공 시 admin-shell이 나타나고 (frontend/src/components/layout/AdminShell.tsx:25),
  // 첫 진입 화면이 admin-dashboard-page (frontend/src/features/admin/dashboard/Dashboard.tsx:24).
  await expect(page.getByTestId('admin-shell')).toBeVisible();
  await expect(page.getByTestId('admin-dashboard-page')).toBeVisible();
}

export async function partnerLogin(page: Page) {
  await page.goto('/');
  await page.getByTestId('app-mode-partner').click();
  await page.getByTestId('partner-login-identifier').fill('01012345678');
  await page.getByTestId('partner-login-password').fill('PartnerPass123!');
  await page.getByTestId('partner-login-submit').click();
  await expect(page.getByTestId('partner-jobs-page')).toBeVisible();
}

/**
 * 협력사 컨텍스트에서 작업 시작 → 사진 업로드 → 작업 완료까지 수행한다.
 *
 * v7 변경 (필수): R6 정책에서 사진 업로드는 상태를 바꾸지 않고, `CUSTOMER_DELIVERY_NEEDED`
 * 전환은 협력사 '작업 완료' 액션에서만 발생한다. 그래서 이 helper는 업로드만 하면 사진검수
 * 큐에 주문이 안 잡히는 모순이 있다. 따라서 업로드 후 반드시 `partner-complete-job`까지
 * 클릭해 큐에 진입시킨다.
 *
 * Browser를 받아 별도 context를 열어 협력사 세션을 끝낸 뒤 정리한다. 호출부는
 * `await partnerUploadPhoto(browser, { ... })` 형태로 호출한다 (page 인자 없음).
 */
export async function partnerUploadPhoto(
  browser: Browser,
  { orderId, photoType }: { orderId: string; photoType: 'before' | 'after' | 'etc' },
) {
  const context = await browser.newContext();
  const page = await context.newPage();
  try {
    await partnerLogin(page);
    await page.getByTestId(`partner-job-row-${orderId}`).click();
    await expect(page.getByTestId('partner-job-detail-page')).toBeVisible();

    // 작업 시작 (이미 IN_PROGRESS면 버튼이 없을 수 있음 — 그 경우 skip).
    const startButton = page.getByTestId('partner-start-job');
    if ((await startButton.count()) > 0) {
      await startButton.click();
    }

    const inputId = `partner-${photoType}-photo-input`;
    await page.getByTestId(inputId).setInputFiles({
      name: `${photoType}-e2e.png`,
      mimeType: 'image/png',
      buffer: ONE_PIXEL_PNG,
    });
    const labelMap = { before: '비포', after: '애프터', etc: '기타' } as const;
    await expect(
      page.getByText(`${labelMap[photoType]} 사진 1장이 업로드되었습니다.`)
    ).toBeVisible({ timeout: 5_000 });

    // v7 추가: 작업 완료까지 호출해 CUSTOMER_DELIVERY_NEEDED 전환.
    // (frontend/src/features/partner/PartnerJobDetail.tsx:255)
    await page.getByTestId('partner-complete-job').click();
    // v8 추가: 완료 응답 + 상태 잠금이 끝날 때까지 기다린 뒤 context를 닫는다.
    // 그렇지 않으면 React의 completePartnerJob 요청이 context.close()에 의해 취소돼
    // photo-review queue에 주문이 안 잡힐 수 있다.
    // (partner-customer-e2e.spec.ts:53에서 검증된 패턴)
    await expect(page.getByTestId('partner-status-locked')).toContainText('작업 완료 처리됨', { timeout: 10_000 });
  } finally {
    await context.close();
  }
}

/**
 * v8 추가: API 호출로 새 주문을 만들고 협력사를 배정한다.
 * 기존 partner-customer-e2e.spec.ts:156-218의 동명 함수와 보조 헬퍼들을 helpers.ts로 옮긴다.
 * 매 테스트가 격리된 주문 ID를 갖도록 보장한다.
 *
 * 호출부: `const flow = await createAssignedOrder(request);` 후 `flow.orderId` 사용.
 *
 * 동작 시 partner-customer-e2e.spec.ts에서 같은 함수가 사라지므로, 그 spec에서도
 * `import { createAssignedOrder } from './helpers';`로 import를 바꾸는 작업이 함께 필요.
 */
import type { APIRequestContext, APIResponse } from '@playwright/test';

const backendPort = Number(process.env.E2E_BACKEND_PORT ?? 8003);
const backendUrl = `http://127.0.0.1:${backendPort}`;
const ADMIN_EMAIL = 'admin@cleanops.kr';
const ADMIN_PASSWORD = 'AdminPass123!';
const PARTNER_PHONE = '01012345678';
const PARTNER_PASSWORD = 'PartnerPass123!';
const SEED_PARTNER_ID = 'seed-partner-01';
const SEED_SERVICE_ITEM_ID = 'seed-service-item-move-in';

export async function createAssignedOrder(request: APIRequestContext) {
  const adminSession = await loginViaApi(request, 'admin');
  const created = await checkedJson(await request.post(`${backendUrl}/api/admin/orders`, {
    headers: authHeaders(adminSession.access_token),
    data: {
      status: '일정확정',
      received_date: '2026-05-05',
      scheduled_date: '2026-05-14',
      requested_time: '09:30',
      partner_id: SEED_PARTNER_ID,
      team_name: 'R6 Photo Review E2E Team',
      service_item_id: SEED_SERVICE_ITEM_ID,
      service_name: 'R6 Photo Review E2E',
      size_or_quantity: '32py',
      service_detail: 'R6 auto-publish + revoke flow',
      special_request: 'Use only approved photos for customer view',
      source_channel: 'E2E internal source',
      customer_name: 'R6 Photo Review',
      customer_phone: '010-8899-7766',
      customer_address: 'Seoul R6 Photo Review E2E 1',
      total_amount: 360000,
      payment_status: 'deposit_paid',
      payment_memo: 'Internal payment memo',
      evidence_memo: 'Internal evidence memo',
      partner_payment_amount: 210000,
      partner_payment_status: 'unpaid',
      customer_visible_payment: false,
    },
  }));
  return {
    orderId: created.id as string,
    customerToken: created.customer_token as string,
    phoneSuffix: '7766',
  };
}

async function loginViaApi(request: APIRequestContext, role: 'admin' | 'partner') {
  const endpoint = role === 'admin' ? 'admin/login' : 'partner/login';
  const identifier = role === 'admin' ? ADMIN_EMAIL : PARTNER_PHONE;
  const password = role === 'admin' ? ADMIN_PASSWORD : PARTNER_PASSWORD;
  return checkedJson(await request.post(`${backendUrl}/api/auth/${endpoint}`, {
    data: { identifier, password },
  }));
}

async function checkedJson(response: APIResponse) {
  expect(response.ok(), await response.text()).toBe(true);
  return response.json();
}

function authHeaders(accessToken: string) {
  return { Authorization: `Bearer ${accessToken}` };
}

export async function openAdminPhotoReview(page: Page, orderId: string) {
  // 사이드 네비의 사진검수 진입 버튼은 partner-customer-e2e.spec.ts:85의 'admin-nav-photos'와 동일.
  await page.getByTestId('admin-nav-photos').click();
  await expect(page.getByTestId('admin-photo-review-page')).toBeVisible();
  await page.getByTestId(`photo-review-item-${orderId}`).click();
}
```

> **v6 검증 단계:** `frontend/e2e/admin-photo-review-e2e.spec.ts` 실행 후 모든 step이 timeout 없이 통과하는지 확인. 한 번이라도 셀렉터가 안 잡히면 partner-customer-e2e.spec.ts의 실제 사용 testid와 대조해 정정. (현재 명세는 line 1–90을 직접 참조해 작성한 것이라 안전.)

- [ ] **Step 5: E2E 실행 + 커밋**

```powershell
cd frontend; npm run e2e
```

```bash
git add frontend/e2e/
git commit -m "test(e2e): 자동 공개·재전송·revoke 시나리오 + 카테고리 2단계 폼"
```

---

## Task 17 — 검증 + 핸드오프

- [ ] **Step 1: 전체 검증 명령**

```powershell
cd backend; python -m pytest -q
cd ../frontend; npm run typecheck; npm run lint; npm run build; npm run e2e
```

전부 통과해야 한다.

- [ ] **Step 2: `.master/next_session_plan.md` 갱신**

R6 항목 완료 처리. 다음 권장 작업을 R7 후보로 적는다 (예: "사진 링크 발송 후 자동 상태 전환을 어떤 트리거로 부활시킬지", "feature flag 도입").

- [ ] **Step 3: 최종 커밋**

```bash
git add .master/next_session_plan.md
git commit -m "docs(handoff): R6 마감 및 다음 세션 안내"
```

---

## Self-Review 체크리스트 (Codex가 모든 task 끝낸 뒤 본인이 확인)

- [ ] **CLAUDE.md + AGENTS.md** 두 정책 문서가 모두 자동 공개로 갱신됐는가? (v2 blocking #1)
- [ ] `OrderService.complete_partner_job()`이 `PHOTO_REVIEW_PENDING` 대신 `CUSTOMER_DELIVERY_NEEDED`로 전환하는가? 사진 0장이면 422를 반환하는가? IN_PROGRESS 가드 통과 전에는 photo 검사로 넘어가지 않는가? (v2 blocking #2 + v4 D4.5)
- [ ] **(v4 D4.5)** `PhotoService.upload_for_partner()`가 사진 저장 + timeline만 기록하고 **주문 상태는 건드리지 않는가**? `STATUS_CHANGED` timeline 이벤트가 업로드 흐름에서 더 이상 발생하지 않는가?
- [ ] `MessageService`의 `customer_photo_ready` 분기가 더 이상 상태를 advance 하지 않는가? `last_customer_link_sent_at`만 갱신되는가? (v2 blocking #3)
- [ ] `PhotoService.revoke_visibility`가 `with_for_update()` row lock + atomic count로 race를 차단하는가? `CUSTOMER_DELIVERY_DONE` 상태에서 revoke 시 상태가 유지되는가? (v2 blocking #4)
- [ ] `test_auth_integration.py`의 12개 정책 단언(line 149, 163, 166, 1011, 1072, 1086, 1111, 1259, 1284, 1291, 1374, 1495)이 모두 갱신됐는가? (v2 blocking #5)
- [ ] `frontend/e2e/admin-e2e.spec.ts:343-355`와 `partner-customer-e2e.spec.ts:88-101`의 photo-approve-selected/photo-filter-review 사용처가 모두 갱신됐는가? (v2 blocking #5)
- [ ] `dashboard.py`의 `today_in_progress` 카운터에서 `PHOTO_REVIEW_PENDING`이 제거됐는가? (D4)
- [ ] `OrderDetailPage`의 `timelineEventLabel`에 `photo_revoked` 라벨이 추가됐는가? (Codex #should-fix)
- [ ] 협력사 필터가 `partner_id` 기준이고 `team_name` 비교가 없는가? (Codex #should-fix)
- [ ] `PartnerJobDetail` / `CustomerReservation`의 "관리자 승인 후 공개" 문구가 갱신됐는가? (Codex #should-fix)
- [ ] Legacy 마이그레이션(`0004_auto_publish_legacy_photos.py`)이 정상 적용되는가? (D7)
- [ ] 권한 분리: revoke 라우트는 `require_admin` 의존성을 거치는가?
- [ ] DTO: `last_customer_link_sent_at`은 admin DTO에만 노출되고 partner/customer DTO에 흘러가지 않는가?
- [ ] Timeline: 업로드 시 `PHOTO_UPLOADED` + `PHOTO_APPROVED`(auto) 2건만 (v4/v5: **STATUS_CHANGED 없음**). 협력사 "작업 완료" 시 `STATUS_CHANGED` 1건. revoke 시 `PHOTO_REVOKED` + 마지막 공개 사진이 사라지고 상태가 `CUSTOMER_DELIVERY_NEEDED`였다면 `STATUS_CHANGED` 1건 더. 모두 한 트랜잭션에서 기록되는가?
- [ ] 실패 케이스: 사진 업로드 실패 메시지 변경 없음. revoke `photo_not_found` 404. 협력사 완료 시 사진 0장이면 422 + 한국어 안내.
- [ ] 디자인 토큰: 새 협력사 탭/접수일 행이 기존 `datePresetButton` 스타일을 재사용해 일관성을 유지하는가?

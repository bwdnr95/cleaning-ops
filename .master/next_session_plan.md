# Cleaning Ops Control Center 다음 세션 인수인계

작성일: 2026-05-20  
목적: R8 Ops UX Hardening 이후 상태를 빠르게 파악하고, 다음 cleanup/운영 기능을 안전하게 이어가기 위한 handoff.

최신 업데이트:

- `R14 Pricing and Settlement` 완료
  - 상품 도급가(`partner_base_price`), 주문 할인가(`discount_amount`), 협력사 정산일(`partner_settled_at`) 추가
  - 주문 목록 기본 정렬: 과거 미납 우선, 오늘/미래순, `include_past_paid`로 과거 완료 포함
  - 고객 견적 알림톡 / 협력사 고객정보 전송 / 정산 완료·되돌리기 timeline 기록
  - 협력사 상세 정산 UI, 주문 가격 자동계산, 상품관리 도급가, 사이드바 신규 주문 버튼 추가
  - 검증 완료: backend `pytest -q` -> `151 passed`, frontend `npm run typecheck`, `npm run lint`, `npm run build`, `npm run e2e` -> `33 passed`
  - 제약: 현재 로컬 Python 환경에 `ruff` 미설치. Alembic offline SQL 출력은 기존 0006 migration 이슈로 실패하지만, 임시 DB online upgrade/downgrade/re-upgrade는 통과.
- `R13 Operational Reporting` 완료
  - 매출/협력사/서비스/정산 4 보고서 + CSV/xlsx export
  - xlsx 일괄 주문 등록 (group_key 묶음) + 행별 부분 성공
  - Python aggregation (DB dialect 무관)
- `R6 Photo Auto Publish + Revoke` 완료 후 race-condition hotfix까지 반영됐다.
- `R7 Multi-line Orders` 완료.
- `R8 Ops UX Hardening` 완료.
  - 카카오 우편번호 + 상세주소 분리 입력
  - Access token TTL 60분 + 폼 draft 자동 저장 (자동 로그아웃 안전망)
  - 주문 목록 전체선택 + 일괄 삭제
  - 주문 상세 단건 삭제
  - 삭제는 soft-delete, timeline은 보존
- `Order`는 계속 1개의 작업 line이다.
- 신규 `OrderGroup`이 고객 정보, 주소, `customer_token`, `source_channel`, `customer_visible_payment`를 가진다.
- 관리자 신규 주문 폼은 line N개를 생성할 수 있다.
- 주문 목록은 같은 `group_id`의 line들을 시각적으로 묶어 보여준다.
- 주문 상세는 sibling line 패널을 제공한다.
- 고객 링크는 그룹 token 하나로 들어가 line 카드 N개를 보여준다.
- 협력사 화면은 변경 없이 본인에게 배정된 line만 본다.
- 검증 완료:
  - backend `python -m pytest -q` -> `119 passed`
  - frontend `npm run typecheck`
  - frontend `npm run lint`
  - frontend `npm run build` -> Vite chunk size warning만 있음
  - frontend `npm run e2e` -> `27 passed`

---

## 1. 기준 문서

먼저 읽을 파일:

- `AGENTS.md`
- `CLAUDE.md`
- `.master/cleaning_ops_control_center_project_brief.md`
- `.master/codex_claude_code_dev_brief.md`
- `README.md`
- `docs/runbooks/r7-multi-line-orders-migration.md`
- `docs/runbooks/r8-session-policy.md`

핵심 규칙:

- 관리자/협력사/고객 권한은 서버 단에서 분리한다.
- 협력사는 자기 `partner_id`에 배정된 line만 본다.
- 고객은 `customer_token` + 전화번호 뒷자리 인증 후 그룹 내 line들을 본다.
- 고객/협력사 DTO는 whitelist 방식으로 만든다.
- 사진/메시지/status/timeline은 line(`orders.id`) 단위로 유지한다.

---

## 2. R7 구현 요약

백엔드:

- `backend/app/models/order_group.py`
- `orders.group_id` FK
- `backend/alembic/versions/0008_order_groups.py`
- `backend/app/repositories/order_groups.py`
- `OrderService.create_group`, `add_line_to_group`, `update_group`
- `POST /api/admin/orders/groups`
- `GET /api/admin/orders/groups/{group_id}`
- `PATCH /api/admin/orders/groups/{group_id}`
- `POST /api/admin/orders/groups/{group_id}/lines`
- 고객 verify 응답: `CustomerOrderGroupRead(lines=[...])`
- 신규 테스트: `backend/tests/test_order_groups.py`

프론트:

- `frontend/src/api/admin.ts` order group 함수 추가
- `OrderFormPage` line list 편집 UI
- `OrdersPage` group 묶음 표시
- `OrderDetailPage` sibling line 패널
- `CustomerReservation` line 카드 N개
- 신규 E2E: `frontend/e2e/admin-multi-line-e2e.spec.ts`

운영 문서:

- `docs/runbooks/r7-multi-line-orders-migration.md`

---

## 3. 다음 세션 추천 작업

다음 세션 이름:

**R14.1 Verification Cleanup + Payment Provider Contract Prep**

목표:

R14 배포 전 검증 도구/마이그레이션 offline 이슈를 정리하고, 셀프페이/결제선생 상세 계약 스펙 수령 후 결제 링크 provider를 붙일 준비를 한다. 동시에 R7에서 호환을 위해 남겨둔 `orders.customer_token`, `orders.customer_name`, `orders.customer_phone`, `orders.customer_address`, `orders.source_channel`, `orders.customer_visible_payment` cleanup 계획을 이어간다.

권장 순서:

1. backend dev dependency 설치 경로를 정리하고 `ruff check .`가 CI/로컬에서 동일하게 실행되게 만든다.
2. 기존 `0006_default_partner_categories.py` data migration의 offline SQL 비호환성을 별도 PR에서 보정하거나, 프로젝트 검증 기준을 online migration 중심으로 명확히 문서화한다.
3. 셀프페이/결제선생 계약 스펙을 확보해 결제 링크 생성/조회/취소/webhook/정산 필드를 확인한다.
4. `PaymentLinkProvider` 인터페이스와 `payment_links` / `payment_events` 테이블 초안을 작성하되, 결제 성공 webhook이 `order_timeline`과 같은 트랜잭션에 남도록 설계한다.
5. `rg "customer_token|customer_name|customer_phone|customer_address|source_channel|customer_visible_payment" backend/app frontend/src backend/tests`로 legacy `Order` 컬럼 의존도를 다시 확인한다.
6. 아직 `Order`에서 customer 정보를 읽는 dashboard/calendar/message/partner DTO 경로를 group join 또는 explicit group 인자로 전환한다.
7. cleanup migration은 결제 provider 설계와 충돌하지 않도록 별도 R15 PR로 분리한다.
8. backend 테스트와 E2E를 전체 실행한다.

후속 후보:

- soft-delete 복구 운영 절차/UI
- 체크리스트/정기관리/계약서 흐름
- 고객 사진 열람 이벤트 정책
- 고객전달완료/서비스완료 수동 또는 자동 전환 정책
- 실제 SMS/알림톡 provider 연동

---

## 4. 명령어

백엔드:

```powershell
cd backend
python -m pytest -q
python -m alembic upgrade head --sql
python -m alembic upgrade head
```

프론트:

```powershell
cd frontend
npm run typecheck
npm run lint
npm run build
npm run e2e
```

E2E는 Playwright webServer가 백엔드/프론트 서버를 자동으로 띄운다.

---

## 5. 현재 남은 리스크

- R7 동안 legacy `orders.customer_*` 컬럼은 호환 미러링 용도로 남아 있다. R8.5/R9에서 제거해야 한다.
- soft-delete 복구 UI는 아직 없다. 복구는 DB 운영 절차로만 처리한다.
- `OrderGroupRepository.list_lines()`는 별도 sort_order 없이 생성 시각/id 기반으로 정렬한다. 명시적인 line 순서가 필요하면 R8에서 sort 컬럼을 추가한다.
- Vite build chunk size warning이 남아 있다.
- 대용량 운영 데이터에서는 admin order list의 group 조회가 N+1 구조다. 운영 데이터가 커지면 join 기반 조회로 개선한다.

---

## 6. 다음 세션 첫 메시지 추천

```text
AGENTS.md, CLAUDE.md, .master/next_session_plan.md를 읽고,
R14.1 Verification Cleanup + Payment Provider Contract Prep을 진행해줘.

먼저 backend dev dependency/ruff 실행 경로와 Alembic offline SQL 이슈를 정리하고,
셀프페이/결제선생 계약 스펙 수령을 전제로 PaymentLinkProvider 설계안을 잡아줘.
그 다음 legacy orders.customer_* 컬럼 의존도를 rg로 확인해 OrderGroup source of truth cleanup 계획을 이어가줘. 권한/DTO/timeline 규칙은 AGENTS.md 기준으로 유지해줘.
```

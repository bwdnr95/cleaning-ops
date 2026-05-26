# Cleaning Ops Control Center 다음 세션 인수인계

작성일: 2026-05-20  
목적: R8 Ops UX Hardening 이후 상태를 빠르게 파악하고, 다음 cleanup/운영 기능을 안전하게 이어가기 위한 handoff.

최신 업데이트:

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

**R8.5 Post-R8 Stabilization + Deprecated Order Customer Columns Cleanup**

목표:

R8 배포 후 운영 UX 회귀를 점검하고, R7에서 호환을 위해 남겨둔 `orders.customer_token`, `orders.customer_name`, `orders.customer_phone`, `orders.customer_address`, `orders.source_channel`, `orders.customer_visible_payment`를 제거할 준비를 한다.

권장 순서:

1. 배포 환경에서 주소 검색 모달이 CSP 오류 없이 열리는지 확인한다.
2. soft-delete된 주문이 관리자 목록/상세, 협력사 작업, 고객 링크에서 모두 숨겨지는지 운영 데이터 기준으로 점검한다.
3. `rg "customer_token|customer_name|customer_phone|customer_address|source_channel|customer_visible_payment" backend/app frontend/src backend/tests`로 legacy `Order` 컬럼 의존도를 다시 확인한다.
4. 아직 `Order`에서 customer 정보를 읽는 dashboard/calendar/message/partner DTO 경로를 group join 또는 explicit group 인자로 전환한다.
5. import/외부 연동 스크립트가 있다면 group 생성 API를 사용하도록 바꾼다.
6. Alembic cleanup migration을 별도 PR로 만든다.
7. backend 테스트와 E2E를 전체 실행한다.

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
R8.5 Post-R8 Stabilization + Deprecated Order Customer Columns Cleanup을 진행해줘.

먼저 legacy orders.customer_* 컬럼 의존도를 rg로 확인하고,
R8의 soft-delete/주소 입력/세션 안전망 회귀가 없는지 확인한 뒤
서비스/DTO/화면이 OrderGroup을 source of truth로 읽도록 cleanup migration 계획을 세워줘. 권한/DTO/timeline 규칙은 AGENTS.md 기준으로 유지해줘.
```

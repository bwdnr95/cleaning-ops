# Cleaning Ops Control Center 다음 세션 인수인계

작성일: 2026-05-18  
목적: 다음 Codex/Claude Code 세션이 R6 이후 상태를 빠르게 파악하고, 운영 흐름/권한/테스트 기준을 유지한 채 이어서 작업할 수 있게 정리한다.

최신 업데이트:

- `R6 Photo Auto Publish + Revoke` 완료.
- 협력사 업로드 사진은 정책상 즉시 고객 공개(`is_customer_visible=true`)된다.
- 잘못 올라온 사진은 관리자가 사진 모니터링 화면에서 비공개로 되돌린다.
- 협력사 사진 업로드는 주문 상태를 바꾸지 않는다. 협력사 `작업 완료` 액션이 `작업진행 -> 고객전달필요` 전환을 담당한다.
- `customer_photo_ready` 메시지 발송은 더 이상 주문 상태를 자동으로 `고객전달완료`로 이동시키지 않는다.
- 신규 주문 폼은 `카테고리 -> 상세상품` 2단계 선택 구조로 변경됐다.
- 주문관리에는 `partner_id` 기준 협력사 탭과 접수일 필터가 추가됐다.
- 검증 완료: backend `96 passed`, frontend `typecheck/lint/build/e2e 20 passed`.

---

## 1. 프로젝트 기준 문서

반드시 먼저 참고할 파일:

- `AGENTS.md`
- `CLAUDE.md`
- `.master/cleaning_ops_control_center_project_brief.md`
- `.master/codex_claude_code_dev_brief.md`
- `README.md`

핵심 규칙:

- 관리자/협력사/고객 권한은 서버 단에서 분리한다.
- 협력사는 자기 `partner_id`에 배정된 주문만 본다.
- 고객은 `customer_token` + 전화번호 뒷자리 인증 후에만 본인 주문을 본다.
- 고객/협력사 DTO는 whitelist 방식으로 만든다. 객체 spread 후 delete 방식 금지.
- 고객/협력사 응답에는 내부 메모, 결제 메모, 증빙 메모, 협력사 정산 금액을 노출하지 않는다.
- 협력사 업로드 사진은 즉시 고객 공개된다.
- 고객 페이지는 `is_customer_visible=true` 사진만 노출한다.
- 관리자가 revoke한 사진은 고객에게 보이지 않아야 하며 `photo_revoked` timeline에 기록한다.
- 주문 상태 변경, 협력사 배정, 사진 업로드/자동 공개/revoke, 메시지 발송은 timeline에 기록한다.
- 메시지 발송은 `MessageProvider` 교체 가능 구조를 유지한다.

---

## 2. 현재 구현 상태

### 2.1 프론트엔드

위치: `frontend/`

주요 구현:

- Vite + React + TSX 앱 구조.
- 관리자/협력사 로그인과 mode 기반 auth gate.
- 관리자 Dashboard/Orders/Calendar/Photo Review/Products/Partners/Messages 주요 read/write path API 연결.
- 주문 등록 폼 카테고리/상세상품 2단계 드롭다운.
- 주문관리 협력사 탭은 `partner_id` 기준으로 필터링.
- 접수일/방문일 필터.
- 협력사 작업 상세 모바일 화면:
  - 작업 시작/완료 액션.
  - before/after/etc 실제 파일 업로드.
  - 업로드 실패 메시지.
  - 자동 공개 안내 문구.
- 고객 화면:
  - `customer_token` 링크 + 전화번호 뒤 4자리 인증.
  - 공개 사진 grid.
  - 내부 운영 용어와 민감정보 비노출.
- 사진 모니터링 화면:
  - 자동 공개된 사진 확인.
  - 고객 사진 링크 발송/재전송.
  - 선택 사진 비공개 되돌리기.
  - 마지막 고객 링크 발송 시각 기반 버튼 라벨.

중요 파일:

- `frontend/src/features/admin/photo-review/PhotoReviewPage.tsx`
- `frontend/src/features/admin/orders/OrderFormPage.tsx`
- `frontend/src/features/admin/orders/OrdersPage.tsx`
- `frontend/src/features/admin/orders/OrderDetailPage.tsx`
- `frontend/src/features/partner/PartnerJobDetail.tsx`
- `frontend/src/features/customer/CustomerReservation.tsx`
- `frontend/src/api/photos.ts`
- `frontend/e2e/admin-photo-review-e2e.spec.ts`
- `frontend/e2e/partner-customer-e2e.spec.ts`
- `frontend/e2e/helpers.ts`

### 2.2 백엔드

위치: `backend/`

주요 구현:

- FastAPI + SQLAlchemy + Alembic + Pydantic.
- Auth:
  - admin/partner login.
  - access/refresh token 분리.
  - refresh rotation/revoke.
  - password change 시 기존 refresh token revoke.
  - login failure lockout.
  - audit/security headers.
- Domain constants 중앙화.
- 역할별 DTO:
  - `AdminOrderDto`
  - `PartnerJobDto`
  - `CustomerOrderDto`
- 사진 정책 R6:
  - `PhotoService.upload_for_partner()`는 사진 저장 + `photo_uploaded` + `photo_approved(auto)` timeline만 기록한다.
  - 업로드 직후 `is_customer_visible=true`.
  - 업로드는 주문 상태를 변경하지 않는다.
  - `OrderService.complete_partner_job()`은 공개 사진 1장 이상일 때만 `고객전달필요`로 전환한다.
  - 공개 사진이 없으면 422 `photo_required_for_completion`.
  - `PhotoService.revoke_visibility()`는 row lock 기반으로 사진을 비공개 처리하고 `photo_revoked` timeline을 남긴다.
  - 마지막 공개 사진 revoke 시 상태가 `고객전달필요`이면 `작업진행`으로 되돌린다.
  - `고객전달완료` 상태에서는 revoke해도 상태를 유지한다.
- 메시지 R6:
  - `customer_photo_ready` 발송 성공/실패는 `message_logs`, `message_sent`, `customer_link_sent`를 기록한다.
  - 발송 성공 후 주문 상태 자동 이동은 제거됐다.
  - `last_customer_link_sent_at`은 admin photo review DTO에만 노출한다.
- Legacy 사진 마이그레이션:
  - `backend/alembic/versions/0007_auto_publish_legacy_photos.py`
  - `docs/runbooks/r6-photo-policy-migration.md`

중요 파일:

- `backend/app/services/photos.py`
- `backend/app/services/orders.py`
- `backend/app/services/messages.py`
- `backend/app/repositories/photos.py`
- `backend/app/repositories/messages.py`
- `backend/app/api/routes/admin/photos.py`
- `backend/app/api/routes/partner/jobs.py`
- `backend/app/domain/constants.py`
- `backend/tests/test_photo_auto_visibility.py`
- `backend/tests/test_photo_revoke.py`
- `backend/tests/test_auth_integration.py`

---

## 3. R6 완료 요약

완료 커밋 흐름:

- 정책 문서 자동 공개 룰 갱신.
- `photo_revoked` timeline 이벤트 추가.
- legacy 비공개 사진 일괄 공개 마이그레이션과 운영 runbook 추가.
- 사진 업로드 자동 공개 및 revoke 서비스 구현.
- 협력사 작업 완료 시 사진 필수 검증과 `고객전달필요` 전환 적용.
- 메시지 발송 후 상태 자동 advance 제거.
- 사진 모니터링 UI에서 승인 단계 제거, 링크 재전송 및 revoke 액션 적용.
- 관리자 주문 상세 timeline 라벨 갱신.
- 대시보드/주문관리/신규 주문 폼/E2E 정책 가정 갱신.

검증:

```powershell
cd backend
python -m pytest -q
# 96 passed

cd ../frontend
npm run typecheck
npm run lint
npm run build
npm run e2e
# 20 passed
```

빌드는 Vite chunk size warning이 남지만 실패는 아니다.

---

## 4. 다음 세션 추천 작업

다음 세션 이름:

**R7 Customer Delivery Completion Policy**

목표:

R6에서 `customer_photo_ready` 발송 후 자동 `고객전달완료` 전환을 제거했다. 다음 세션에서는 어떤 트리거로 `고객전달완료`와 `서비스완료`를 확정할지 운영 정책을 정하고 구현한다.

R7 후보:

1. 고객 전달 완료 트리거 결정
   - 고객 링크 발송 즉시 완료로 볼지.
   - 고객이 링크를 열람/사진 확인했을 때 완료로 볼지.
   - 관리자가 수동 완료 처리할지.
   - 일정 시간 후 자동 완료할지.

2. feature flag 도입
   - 자동 공개 정책을 환경별/고객사별로 켜고 끌 수 있게 할지 검토.
   - `auto_publish_partner_photos` 같은 서버 설정을 둘 경우 DTO와 UI 문구도 함께 분기해야 한다.

3. 고객 사진 링크 열람 이벤트
   - 고객 인증 성공 또는 사진 섹션 조회 시 `customer_link_opened`/`customer_photos_viewed` timeline 이벤트를 남길지 결정.
   - 개인정보/감사 로그 범위를 먼저 정해야 한다.

4. 고객 전달/서비스 완료 관리자 액션
   - 사진 모니터링 또는 주문 상세에서 `고객전달완료`, `서비스완료` 수동 전환 버튼을 둘지 검토.
   - 상태 전이 helper와 timeline 테스트를 먼저 추가한다.

5. 실제 메시지 provider 연동 준비
   - Mock provider 유지.
   - Solapi/SMS/알림톡 provider는 교체 가능한 구조로 추가.
   - 실패 재시도, provider error code, 운영자 재발송 UX를 함께 설계.

권장 시작 순서:

1. `AGENTS.md`, `CLAUDE.md`, 이 파일을 먼저 읽는다.
2. `backend/app/domain/constants.py`의 상태/메시지/timeline 이벤트를 확인한다.
3. `backend/app/services/messages.py`, `backend/app/services/orders.py`에서 현재 상태 전이 책임을 확인한다.
4. R7 정책을 작은 ADR 또는 plan 문서로 고정한다.
5. backend domain/service 테스트를 먼저 작성하고 UI 액션은 그 다음 연결한다.

---

## 5. 명령어

백엔드:

```powershell
cd backend
python -m pytest -q
python -m alembic upgrade head --sql
```

프론트:

```powershell
cd frontend
npm run typecheck
npm run lint
npm run build
npm run e2e
```

E2E는 Playwright webServer가 백엔드/프론트 서버를 자동으로 띄운다. 일반 개발 서버는 사용자가 요청하지 않는 한 임의로 띄우지 않는다.

---

## 6. 현재 남은 리스크

- `사진검수대기` 상태는 legacy 호환으로 남아 있지만 신규 흐름에서는 사용하지 않는다.
- 고객 링크 발송 후 `고객전달완료`로 언제 이동할지 정책이 아직 비어 있다.
- 자동 공개 정책을 고객사/환경별로 끌 수 있는 feature flag는 아직 없다.
- 실제 SMS/알림톡 provider 미연동. Mock provider 기준으로 테스트한다.
- 대용량 운영 데이터에서 사진 review queue 쿼리 성능은 별도 점검이 필요하다.
- 일부 운영 화면은 아직 완전한 React Router 기반 URL 라우팅이 아니다.

---

## 7. 다음 세션 첫 메시지 추천

```text
.master/next_session_plan.md와 AGENTS.md를 읽고,
R7 Customer Delivery Completion Policy를 Plan -> Implement -> Test -> Review 순서로 진행해줘.

R6에서 customer_photo_ready 발송 후 상태 자동 이동을 제거했으니,
고객전달완료/서비스완료를 어떤 트리거로 전환할지 정책부터 짧게 고정하고
domain/service 테스트를 먼저 추가한 뒤 UI 액션을 연결해줘.
권한/DTO/timeline 규칙은 AGENTS.md 기준을 반드시 지켜줘.
```

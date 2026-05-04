# Cleaning Ops Control Center 다음 세션 인수인계

작성일: 2026-05-02  
목적: 다음 Codex/Claude Code 세션이 컨텍스트를 다시 많이 읽지 않고도 바로 이어서 작업할 수 있게 현재 상태, 고정 규칙, 다음 계획을 정리한다.

최신 업데이트:

- `Frontend Auth + API Client R1` 완료.
- `Seed + Integration Auth R1` 완료.
- `Frontend Data Wiring R1` 완료.
- `Customer Link Verify R1` 완료.
- `Customer Visible Photos R1` 완료.
- `Photo Workflow Wiring R1` 완료.
- `Message Dispatch + Customer Link Sent R1` 완료.
- 다음 추천 작업은 `Storage + Real Upload R1`이다.

---

## 1. 프로젝트 기준 문서

반드시 먼저 참고할 파일:

- `AGENTS.md`
- `.master/cleaning_ops_control_center_project_brief.md`
- `.master/codex_claude_code_dev_brief.md`
- `README.md`

`AGENTS.md`에는 프로젝트 전체 개발 규칙이 정리되어 있다.

핵심 규칙:

- 관리자/협력사/고객 권한은 서버 단에서 분리한다.
- 협력사는 자기 `partner_id`에 배정된 주문만 본다.
- 고객은 `customer_token` + 전화번호 뒷자리 인증 후에만 본인 주문을 본다.
- 고객/협력사 DTO는 whitelist 방식으로 만든다. 객체 spread 후 delete 방식 금지.
- 협력사 업로드 사진은 기본 `is_customer_visible=false`.
- 고객 페이지는 승인된 사진만 노출한다.
- 주문 상태 변경, 협력사 배정, 사진 업로드/승인, 메시지 발송은 타임라인에 기록한다.
- 메시지 발송은 `MessageProvider` 교체 가능 구조를 유지한다.
- 큰 작업은 Plan -> Implement -> Test -> Review 순서로 진행한다.

---

## 2. 현재 구현 상태

### 2.1 프론트엔드

위치: `frontend/`

기술:

- Vite
- React
- TypeScript / TSX
- CSS token 기반 스타일

현재 상태:

- 기존 디자인 핸드오프 JSX/CSS를 React TS 앱 구조로 이관함.
- `.jsx` 파일은 모두 `.tsx`로 전환됨.
- mock/domain 파일은 `.ts`로 전환됨.
- `npm run typecheck`, `npm run lint`, `npm run build` 통과 확인.

주요 파일:

- `frontend/src/app/App.tsx`
- `frontend/src/main.tsx`
- `frontend/src/components/common/ui.tsx`
- `frontend/src/components/layout/AdminShell.tsx`
- `frontend/src/components/frames/DeviceFrames.tsx`
- `frontend/src/features/admin/dashboard/Dashboard.tsx`
- `frontend/src/features/admin/orders/OrdersPage.tsx`
- `frontend/src/features/admin/orders/OrderDetailPage.tsx`
- `frontend/src/features/admin/calendar/CalendarPage.tsx`
- `frontend/src/features/admin/photo-review/PhotoReviewPage.tsx`
- `frontend/src/features/partner/PartnerJobDetail.tsx`
- `frontend/src/features/customer/CustomerReservation.tsx`
- `frontend/src/styles/global.css`
- `frontend/src/styles/app.css`

현재 남은 것:

- 일부 보조 영역은 여전히 mock 데이터 기반임. 최근 사진/발송 이력과 주문 상세는 아직 mock이다.
- React Router 기반 실제 라우팅은 아직 도입하지 않음.
- 고객 token 인증 화면은 실제 verify API 기반임.

최근 구현됨:

- `frontend/src/api/client.ts`
  - `VITE_API_BASE_URL`
  - `Authorization` 자동 첨부
  - `X-Request-ID`
  - 401 refresh/retry
  - FastAPI validation error 정규화
- `frontend/src/api/auth.ts`
- `frontend/src/store/authStore.tsx`
- 관리자/협력사 로그인 화면과 mode 기반 auth gate
- `frontend/src/api/admin.ts`
- `frontend/src/api/partner.ts`
- `frontend/src/api/useApiResource.tsx`
- 관리자 Dashboard/Orders read path 일부 API 연결
- 협력사 jobs read path API 연결
- `frontend/src/api/customer.ts`
- 고객 화면 `customer_token` + 전화번호 뒷자리 인증 gate 연결
- 고객 공개 사진 grid 연결
- `frontend/src/api/photos.ts`
- `frontend/src/api/messages.ts`
- 협력사 사진 업로드 액션 연결
- 관리자 사진 검수 큐/승인 화면 API 연결
- 사진 검수 화면 고객 링크 발송 버튼 연결

### 2.2 백엔드

위치: `backend/`

기술:

- FastAPI
- SQLAlchemy
- Alembic
- Pydantic
- bcrypt
- python-jose JWT

구조:

- `backend/app/models`
- `backend/app/schemas`
- `backend/app/repositories`
- `backend/app/services`
- `backend/app/api/routes`
- `backend/app/domain`
- `backend/alembic`
- `backend/tests`

현재 구현됨:

- 주문/협력사/상품/사진/메시지/타임라인 모델 초안
- Alembic 초기 마이그레이션 `0001_initial_schema.py`
- Auth 기반:
  - bcrypt 비밀번호 해싱
  - access token / refresh token 분리
  - JWT token type 검증: `access`, `refresh`
  - refresh token jti 해시 저장
  - refresh token rotation
  - logout revoke
  - password change 시 기존 refresh token revoke
  - 로그인 실패 lockout 기반
  - audit log 모델/서비스
  - security headers middleware
  - production에서 약한/default secret 차단
- `/api/auth/admin/login`
- `/api/auth/partner/login`
- `/api/auth/refresh`
- `/api/auth/logout`
- `/api/auth/admin/change-password`
- `/api/auth/partner/change-password`
- 개발 seed:
  - `backend/app/db/seed.py`
  - `backend/scripts/seed_dev.py`
  - 초기 관리자/협력사 계정
  - 샘플 협력사/주문/created timeline
- Auth 통합 테스트:
  - admin login -> admin route 접근
  - partner login -> admin route 403
  - partner login -> 자기 jobs 조회
  - refresh token rotation/reuse 차단
  - logout 후 refresh 차단
- Dashboard summary 실제 집계
- 고객 링크 verify 통합 테스트:
  - 올바른 customer token + phone suffix 성공
  - 잘못된 suffix 실패
  - Customer DTO 민감정보 비노출
- 고객 공개 사진 DTO/API 테스트:
  - `is_customer_visible=true` 사진만 노출
  - `uploaded_by_user_id`, `is_customer_visible` 비노출
- 사진 워크플로우 통합 테스트:
  - 협력사 업로드 직후 `is_customer_visible=false`
  - 고객 verify 응답 비노출
  - 관리자 review queue 조회
  - 관리자 승인 후 고객 verify 응답 노출
- 고객 링크 발송 테스트:
  - `customer_photo_ready` 메시지 content에 고객 링크 포함
  - `message_logs` 기록
  - `customer_link_sent` timeline 기록
  - 발송 성공 후 주문 상태 `고객전달완료` 이동

검증됨:

- `python -m compileall backend\app backend\tests`
- `python -m pytest backend\tests`
- `python -m alembic upgrade head --sql`
- `npm run typecheck`
- `npm run lint`
- `npm run build`

마지막 확인 기준:

- 백엔드 테스트 27개 통과.
- 프론트 typecheck/lint/build 통과.

---

## 3. 중요한 운영/보안 판단

이 프로젝트는 수주 프로젝트이며, 고객 개인정보와 사진, 주소, 결제 메모가 들어간다.  
따라서 보안은 “나중에 보강”이 아니라 초기부터 상용 기준으로 잡는다.

현재 보안 방향은 `tono-operation` 프로젝트를 참고하되, Cleaning Ops에 맞게 단순화해서 적용한다.

가져온/가져올 패턴:

- bcrypt password hashing
- JWT access/refresh 분리
- refresh token 원문 저장 금지
- refresh token rotation
- logout revoke
- change password 시 모든 세션 revoke
- login failure lockout
- audit logs
- security headers
- 환경별 CORS 제한
- 프론트 API client의 401 refresh/retry
- `X-Request-ID`

Cleaning Ops에는 과한 패턴:

- multi-org TONO admin 구조
- housekeeper/partner 복합 middleware
- 대규모 feature flag 권한 체계

Cleaning Ops에 맞는 권한 모델:

- `admin`: 전체 운영 관리
- `partner`: 자기 배정 주문만 조회/사진 업로드/작업 완료
- `customer`: 회원 없음. 고객 링크 인증 후 본인 주문만 조회

---

## 4. 다음 세션 추천 작업

다음 세션 이름:

**Storage + Real Upload R1**

목표:

협력사 사진 업로드의 R1 mock URL adapter를 실제 파일 업로드 흐름으로 교체할 준비를 한다. 운영 방향은 `PostgreSQL + Object Storage`다. PostgreSQL에는 사진 바이너리를 저장하지 않고 사진 메타데이터만 저장하며, 실제 파일은 Object Storage에 저장한다. R1은 `LocalStorageProvider`로 구현하되, 이후 S3/Supabase Storage로 교체 가능하게 adapter 인터페이스를 분리한다.

저장소 결정:

- 운영 DB: PostgreSQL
- 파일 저장소: Object Storage
- R1 파일 provider: LocalStorageProvider
- 향후 provider: S3StorageProvider 또는 SupabaseStorageProvider
- 금지: 사진 파일을 PostgreSQL `bytea`/blob로 저장하지 않는다.
- DB 저장 대상: `storage_key`, `file_url`/`public_url`, `file_name`, `file_size`, `content_type`, `photo_type`, `is_customer_visible`, `uploaded_by_user_id`

### 4.1 계획

1. storage adapter 인터페이스 추가
   - `StorageProvider.save(...) -> StoredFile`
   - local provider 구현
   - S3/Supabase provider가 들어와도 `PhotoService` 호출부가 바뀌지 않게 설계

2. backend upload endpoint 확장
   - multipart file 수신
   - 파일 형식/용량 검증
   - jpeg/png/webp 우선 허용
   - `content_type`, `storage_key`, `file_url`, `file_size` 메타데이터 저장
   - PostgreSQL 호환 SQLAlchemy/Alembic 타입 사용
   - `PhotoService.upload_for_partner` 호출부 유지

3. frontend partner upload UX
   - 실제 file input/camera capture
   - 업로드 진행/실패 표시
   - before/after/etc 선택

4. 테스트 보강
   - 허용 파일 성공
   - 잘못된 확장자/용량 실패
   - 업로드 직후 고객 비노출 유지
   - 사진 바이너리를 DB에 저장하지 않는 구조 확인

5. 테스트/검증
   - `npm run typecheck`
   - `npm run lint`
   - `npm run build`
   - API 계약 변경 시 `python -m pytest backend\tests`

### 4.2 주의점

- 서버를 임의로 띄우지 말 것. 사용자가 요청하거나 포트 확인 후 진행.
- 현재 사용자 환경에서 `5173`, `8000`, `8001`은 다른 프로젝트가 사용할 수 있음.
- dev server를 띄워야 한다면 먼저 사용자에게 포트 확인을 받고, 충돌 없는 포트를 사용한다.
- `tono-operation`은 참고만 하고 코드를 수정하지 말 것.
- `tono-operation`의 코드를 그대로 복붙하지 말고 이 프로젝트 구조에 맞게 재작성할 것.

---

## 5. 완료된 백엔드 작업

완료됨:

**Seed + Integration Auth R1**

목표:

실제 DB에 초기 관리자/협력사 계정을 넣고, login -> protected API 접근까지 통합 테스트한다.

구현됨:

- `backend/app/db/seed.py`
- `backend/scripts/seed_dev.py`
- admin 계정 seed
- partner 계정 seed
- sample partner seed
- sample order seed
- auth 통합 테스트

테스트됨:

- admin login 성공
- partner login 성공
- admin token으로 admin route 접근 성공
- partner token으로 admin route 403
- partner token으로 자기 jobs 조회 성공
- refresh token rotation
- logout 후 refresh 실패

추가로 발견/수정한 점:

- SQLite 통합 테스트에서 refresh token `expires_at`이 naive datetime으로 반환될 수 있어, auth service에서 UTC aware datetime으로 보정 후 비교하도록 수정했다.
- Dashboard summary placeholder를 실제 주문 집계로 교체했다.

## 5.1 완료된 프론트 작업

완료됨:

**Frontend Data Wiring R1**

구현됨:

- `frontend/src/api/admin.ts`
- `frontend/src/api/partner.ts`
- `frontend/src/api/useApiResource.tsx`
- Dashboard KPI/업무 큐/오늘·내일 작업 read path API 연결
- OrdersPage 목록 read path API 연결
- PartnerJobDetail 첫 배정 작업 read path API 연결
- loading/error/empty 상태 추가

**Customer Link Verify R1**

구현됨:

- TONO reference 문서 `.master/CLEANING_PHOTOS_GUEST_LINK_REFERENCE.md` 검토
- 현 R1에서는 새 photo view 모델 대신 기존 `orders.customer_token`을 capability token으로 사용
- `frontend/src/api/customer.ts`
- `CustomerReservation` 인증 gate
  - URL `?t=`, `?token=`, `?customer_token=` 지원
  - sessionStorage token 보존
  - 전화번호 뒷 4자리 인증
  - 인증 성공 후 Customer DTO 기반 예약 정보 렌더링
- 고객 인증 API 통합 테스트와 민감정보 비노출 테스트 추가

**Customer Visible Photos R1**

구현됨:

- `CustomerPhotoRead` whitelist DTO 추가
- `CustomerOrderRead.photos` 추가
- 고객 verify route에서 `PhotoRepository.list_for_order(customer_visible_only=True)` 사용
- 고객 DTO 변환 시 공개 승인된 사진만 포함
- 고객 화면 사진 영역을 공개 사진 grid로 연결
- 공개 사진이 없을 때는 기존 대기 안내 유지
- 공개/비공개 사진 누출 방지 통합 테스트 추가

**Photo Workflow Wiring R1**

구현됨:

- `frontend/src/api/photos.ts`
- `/api/admin/photos/review-queue`
- `AdminPhotoReviewItem` DTO
- 관리자 사진 검수 화면이 실제 review queue 조회
- 선택/전체 사진 승인 버튼 연결
- 협력사 작업 화면 R1 mock upload adapter 연결
- 협력사 업로드 시 주문 상태 `사진검수대기` 이동
- 관리자 승인 시 기존 규칙대로 주문 상태 `고객전달필요` 이동
- 업로드 직후 비공개, 승인 후 고객 공개 통합 테스트 추가

**Message Dispatch + Customer Link Sent R1**

구현됨:

- `settings.frontend_url`
- `customer_photo_ready` 메시지에 고객 링크 포함
- 고객 링크 형식: `{frontend_url}/customer?t={customer_token}`
- 발송 성공 시 `message_logs` 기록
- 발송 성공 시 `message_sent`와 `customer_link_sent` timeline 기록
- 발송 성공 시 주문 상태 `고객전달완료` 이동
- `frontend/src/api/messages.ts`
- 사진 검수 화면 고객 링크 발송 버튼/성공/실패 상태 연결
- 서비스/API 통합 테스트 추가

---

## 6. 명령어

백엔드:

```powershell
python -m compileall backend\app backend\tests
python -m pytest backend\tests
cd backend
python -m alembic upgrade head --sql
```

프론트:

```powershell
cd frontend
npm run typecheck
npm run lint
npm run build
```

서버 실행은 사용자의 명시 요청 없이는 하지 않는다.

---

## 7. 현재 남은 리스크

- 주문 상세, 최근 사진/발송 이력은 mock 데이터 기반.
- 실제 파일 스토리지/S3/Supabase Storage 전이라 협력사 업로드는 R1 mock URL adapter 기반.
- 파일 업로드 저장소/S3/Supabase Storage 결정 전.
- 실제 SMS/알림톡 provider 미정.
- Alembic 초기 마이그레이션은 fresh DB 기준. 이미 생성된 DB가 있다면 별도 migration 전략 필요.

---

## 8. 다음 세션 첫 메시지 추천

다음 세션에서 바로 이렇게 시작하면 된다.

```text
.master/next_session_plan.md와 AGENTS.md를 읽고,
Storage + Real Upload R1을 Plan -> Implement -> Test -> Review 순서로 진행해줘.

인프라 방향은 PostgreSQL + Object Storage야.
PostgreSQL에는 주문/사진 메타데이터만 저장하고, 실제 사진 파일은 Object Storage에 저장하는 구조로 설계해줘.
R1에서는 운영 storage를 바로 붙이지 말고 LocalStorageProvider로 구현하되, 나중에 S3/Supabase Storage로 교체할 수 있게 StorageProvider 인터페이스를 분리해줘.
사진 파일을 DB에 bytea/blob로 저장하지 말고, order_photos에는 storage_key, file_url/public_url, file_name, file_size, content_type, is_customer_visible 같은 메타데이터만 저장해줘.
서버는 띄우지 말고 typecheck/lint/build와 필요한 backend 테스트까지만 검증해줘.
```

# Cleaning Ops Control Center Agent Guide

이 문서는 이 저장소에서 Codex/Claude Code/기타 AI 에이전트가 작업할 때 따라야 하는 프로젝트 규칙이다.  
목표는 기능을 빠르게 붙이는 것이 아니라, 운영 업무 흐름이 끊기지 않고 권한/데이터/테스트가 일관된 코드베이스를 만드는 것이다.

## Source Of Truth

- 제품/업무 기획: `.master/cleaning_ops_control_center_project_brief.md`
- 개발/QA 브리프: `.master/codex_claude_code_dev_brief.md`
- 디자인 핸드오프: `README.md`, `.master/design_handoff_prototype/styles.css`, `.master/design_handoff_prototype/page-*.jsx`, `.master/design_handoff_prototype/components.jsx`, `.master/design_handoff_prototype/admin-shell.jsx`
- `.master/design_handoff_prototype/`의 HTML/JSX 파일은 high-fidelity prototype이다. Production 코드로 그대로 복사하지 말고, 대상 앱 구조에 맞게 재구현한다.

## Product Invariants

- 제품명은 `Cleaning Ops Control Center`다.
- 이 서비스는 단순 CRUD가 아니라 청소업체 운영 컨트롤타워다.
- 핵심 흐름은 `주문 접수 -> 협력사 배정 -> 일정 확정/안내 -> 작업 진행 -> 사진 업로드 -> 관리자 검수 -> 고객 전달 -> 완료`다.
- 관리자는 전체 운영을 관리한다.
- 협력사는 본인에게 배정된 작업만 본다.
- 고객은 회원가입 없이 `customer_token` 링크와 전화번호 뒷자리 인증으로 본인 주문만 본다.

## Security And Privacy Rules

- 관리자, 협력사, 고객 권한은 서버 단에서 분리한다.
- 협력사 API는 반드시 현재 사용자 `partner_id` 기준으로 주문을 제한한다.
- 고객 API는 `customer_token`과 전화번호 뒷자리 인증을 통과한 경우에만 주문 상세를 반환한다.
- 고객/협력사 응답 DTO에는 내부 전용 필드를 포함하지 않는다.
- 고객에게 절대 노출하지 않는 필드:
  - `source_channel`
  - `payment_memo`
  - `evidence_memo`
  - `partner_payment_amount`
  - `partner_payment_status`
  - 내부 메모
  - 다른 협력사 정보
- 협력사에게 절대 노출하지 않는 필드:
  - `total_amount`
  - `deposit_amount`
  - `balance_amount`
  - `onsite_extra_amount`
  - `vat_type`
  - `payment_memo`
  - `evidence_memo`
  - `source_channel`
  - 다른 협력사 주문/정산 정보
- 협력사가 업로드한 사진은 자동 공개 정책(자세한 내용은 Photo Rules 참조)에 따라 처리한다. 관리자는 언제든 revoke로 가릴 수 있다.
- 고객 페이지는 `is_customer_visible=true`인 사진만 보여준다.

## Domain Constants

상태값, 메시지 타입, 사진 타입, 결제 상태는 코드 곳곳에 문자열로 흩뿌리지 않는다. Production 앱에서는 중앙 파일에 정의한다.

권장 위치:

- `src/domain/order-status.ts`
- `src/domain/photo-type.ts`
- `src/domain/message-type.ts`
- `src/domain/payment-status.ts`

주문 상태는 브리프의 13개 값을 기준으로 한다.

- `신규접수`
- `상담중`
- `협력사확인중`
- `일정확정`
- `전날안내필요`
- `전날안내완료`
- `작업예정`
- `작업진행`
- `사진검수대기`
- `고객전달필요`
- `고객전달완료`
- `서비스완료`
- `취소`

상태 전이는 업무 의미를 보존해야 한다. 상태 변경 시 반드시 `order_timeline`에 기록한다.

## Architecture Rules

Production 앱을 만들 때는 다음 레이어를 분리한다.

- `app/` 또는 `pages/`: 라우팅과 화면 조립
- `components/`: 재사용 UI 컴포넌트
- `features/`: 주문, 협력사, 사진, 메시지 등 업무 단위 UI와 액션
- `domain/`: 상태값, 타입, 업무 규칙, 순수 함수
- `server/` 또는 `lib/server/`: DB 접근, 인증, 권한 검사, 외부 API 어댑터
- `schemas/`: Zod 입력 검증
- `tests/`: 단위/통합/E2E 테스트

UI 컴포넌트는 DB를 직접 호출하지 않는다.  
DB write는 service/action 계층을 통해 수행하고, 그 안에서 권한 검사와 타임라인 기록을 함께 처리한다.

## Data Access Rules

- 주문 생성 시 `customer_token`을 생성한다.
- 주문 생성 시 `order_timeline`에 `created` 이벤트를 기록한다.
- 주문 상태 변경 시 `status_changed` 이벤트를 기록한다.
- 협력사 배정 시 `partner_assigned` 이벤트를 기록한다.
- 메시지 발송 시 `message_sent` 이벤트와 `message_logs`를 함께 기록한다.
- 사진 업로드 시 `photo_uploaded` 이벤트를 기록한다.
- 사진 고객 공개 승인 시 `photo_approved` 이벤트를 기록한다.
- 고객 링크 발송 시 `customer_link_sent` 이벤트를 기록한다.
- 메모 추가 시 `memo_added` 이벤트를 기록한다.

트랜잭션이 가능한 환경에서는 주문 변경과 타임라인 기록을 같은 트랜잭션으로 묶는다.

## Delete Policy

- 주문/그룹 삭제는 **soft-delete**다. 모델의 `deleted_at` 컬럼을 채우고 hard-delete는 사용하지 않는다.
- 모든 list/detail/dashboard/calendar/customer 조회 경로는 `deleted_at IS NULL` 필터를 포함한다.
- 삭제 시 `order_timeline`에 `order_deleted` 이벤트를 기록한다 (actor=관리자 user_id). photos, message_logs, timeline은 그대로 보존되어 audit trail을 유지한다.
- 그룹 내 모든 line이 삭제되면 service 단에서 `OrderGroup.deleted_at`도 함께 채운다. 일부만 삭제되면 그룹은 살아있다.
- 협력사/고객 API는 삭제된 주문에 접근할 수 없다 (`deleted_at IS NULL` 가드 + 404 응답).
- 복구 기능은 본 정책 범위 밖이다. DB에 직접 접근하여 `deleted_at`을 NULL로 되돌리는 운영 절차로만 처리한다.

## Reporting / Export Rules

- 모든 보고서 endpoint는 `require_admin` 가드와 `Order.deleted_at IS NULL` 필터를 강제한다.
- **매출 정의는 `status IN (CUSTOMER_DELIVERY_DONE, COMPLETED)` 합계**다. `DashboardService.monthly_revenue`와 정확히 동일하게 유지한다. 화면마다 매출이 달라지면 운영자는 회사 매출을 믿을 수 없다.
- 정산 대기는 `OrderStatus.COMPLETED` + `partner_payment_status`가 `PARTNER_SETTLEMENT_PENDING_STATUSES` 또는 NULL인 주문이다.
- 집계는 SQLAlchemy의 `case`/`date_trunc` 같은 DB 방언 함수 대신 Python aggregation (`itertools.groupby` + `Decimal`)으로 구현한다. 운영 데이터량(수십~수백 건) 수준에서 성능 영향 없음 + dialect 무관.
- Export는 화면의 현재 필터/기간을 query string으로 묶어 호출하고 backend가 content-disposition으로 다운로드시킨다. 파일명은 ASCII (`revenue.csv`).
- 주문 import는 행별 validate + `group_key` 컬럼으로 묶어 OrderGroup 단위 commit. 한 group 안의 line 하나라도 실패하면 그 group 전체를 rollback한다.

## DTO Rules

API 응답은 역할별 DTO를 분리한다.

- `AdminOrderDto`: 관리자용 전체 운영 정보
- `PartnerJobDto`: 협력사용 현장 작업 정보
- `CustomerOrderDto`: 고객용 예약/사진 확인 정보

DTO 변환 함수는 명시적으로 작성한다. 민감정보를 제거하기 위해 객체 spread 후 일부 필드를 삭제하는 방식은 피한다.

권장 이름:

- `toAdminOrderDto`
- `toPartnerJobDto`
- `toCustomerOrderDto`

## Validation Rules

- 모든 외부 입력은 Zod schema로 검증한다.
- 폼 검증과 서버 검증은 가능하면 같은 schema를 공유한다.
- 전화번호는 저장 전 정규화한다.
- 고객 인증은 저장된 전화번호의 마지막 4자리와 입력값을 비교한다.
- 금액 필드는 숫자 변환 실패, 음수, 빈 문자열을 명확히 처리한다.

## Message Sending Rules

메시지 발송은 교체 가능한 provider 구조로 둔다.

권장 인터페이스:

```ts
export interface MessageProvider {
  send(input: MessageSendInput): Promise<MessageSendResult>;
}
```

초기 구현은 `MockMessageProvider`를 사용한다.  
실제 SMS/알림톡 연동을 추가해도 호출부는 `sendMessage({ orderId, type, recipientType })` 형태를 유지한다.

필수 메시지 타입:

- `customer_schedule_confirmed`
- `customer_day_before`
- `partner_assignment`
- `customer_photo_ready`

발송 성공/실패 모두 `message_logs`에 남긴다.

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

## UI Rules

- 관리자 화면은 데스크톱 우선, 테이블과 업무 큐 중심이다.
- 협력사 화면은 모바일 우선, 큰 버튼과 작업 카드 중심이다.
- 고객 화면은 모바일 우선, 신뢰감 있는 브랜드 페이지처럼 만든다.
- 디자인 토큰은 `README.md`와 `.master/design_handoff_prototype/styles.css`를 기준으로 한다.
- 기존 프로토타입의 색상, 간격, 상태 배지 의미를 보존한다.
- 상태별 색상과 배지 의미를 임의로 바꾸지 않는다.
- 고객/협력사 화면에는 내부 운영 용어를 노출하지 않는다.

## Code Style

- TypeScript를 기본으로 한다.
- `any`는 피하고, 불가피하면 이유를 주석으로 남긴다.
- 하드코딩 문자열 대신 domain constants를 사용한다.
- 중복된 업무 로직은 domain/service 함수로 올린다.
- 함수는 하나의 업무 의도를 갖게 한다.
- boolean 플래그 이름은 `is`, `has`, `can`, `should`로 시작한다.
- 날짜 계산은 helper로 분리하고 테스트한다.
- 컴포넌트 파일은 UI 중심, service 파일은 업무 로직 중심으로 유지한다.
- 불필요한 추상화는 만들지 않는다. 단, 권한/DTO/상태/메시지는 반드시 중앙화한다.

## Test Strategy

작업 완료 전 가능한 범위에서 테스트를 추가하고 실행한다.

필수 테스트 대상:

- 상태 전이와 타임라인 기록
- 대시보드 계산 항목
- 협력사 권한 필터
- 고객 토큰/전화번호 뒷자리 인증
- 고객 DTO 민감정보 비노출
- 사진 기본 비공개 및 승인 후 공개
- 메시지 발송 성공/실패 로그

권장 테스트 구조:

- Unit: 순수 domain 함수, DTO 변환, 날짜/상태 계산
- Integration: service/action과 DB 접근 흐름
- E2E: 관리자 -> 협력사 -> 고객으로 이어지는 실제 업무 플로우

대표 E2E 시나리오:

```text
관리자 주문 생성
-> 협력사 생성/배정
-> 협력사 로그인
-> 본인 작업만 조회
-> 비포/애프터 사진 업로드
-> 작업 완료
-> 관리자 사진 검수/승인
-> 고객 링크 접근
-> 전화번호 뒷자리 인증
-> 승인된 사진만 확인
-> 내부 정보 비노출 확인
```

## Review Checklist

코드 리뷰 시 다음을 먼저 본다.

- 권한 분리가 서버 단에서 보장되는가?
- 고객/협력사 DTO에 민감정보가 섞이지 않았는가?
- 상태 변경, 메시지 발송, 사진 업로드/승인이 타임라인에 남는가?
- 상태값/메시지 타입/사진 타입이 중앙화되어 있는가?
- 실패 케이스가 기록되고 사용자에게 설명되는가?
- 운영자가 오늘 처리해야 할 업무 큐가 깨지지 않는가?
- 테스트가 핵심 업무 흐름을 덮고 있는가?
- 디자인 토큰과 화면 밀도가 핸드오프 기준을 따르는가?

## Agent Workflow

에이전트는 작업 시 다음 순서를 따른다.

1. 관련 브리프와 현재 코드를 읽는다.
2. 변경 범위를 작게 잡고 기존 패턴을 따른다.
3. 파일을 수정하기 전 어떤 수정을 할지 짧게 알린다.
4. 구현한다.
5. 관련 테스트를 추가하거나 갱신한다.
6. 가능한 검증 명령을 실행한다.
7. 자체 리뷰로 권한, DTO, 타임라인, 테스트 누락을 확인한다.
8. 최종 답변에는 변경 사항과 실행한 검증을 간단히 남긴다.

새 기능 요청을 받을 때 에이전트는 “돌아가는 화면”만 보지 말고, 실제 운영 흐름이 끊기지 않는지 기준으로 판단한다.

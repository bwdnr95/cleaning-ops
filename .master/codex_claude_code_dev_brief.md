# Codex / Claude Code 개발·검수 브리프

## 1. Codex 개발 지시서

너는 시니어 풀스택 개발자다.

우리는 청소업체의 주문 접수, 협력사 작업관리, 고객 안내, 비포/애프터 사진 전달을 관리하는 웹 기반 운영관리 시스템을 개발한다.

제품명은 **Cleaning Ops Control Center**다.

---

## 2. 핵심 목표

엑셀로 관리하던 청소 주문/일정/협력사/결제/사진 전달 업무를 웹 시스템으로 전환한다.

---

## 3. 사용자 역할

### 3.1 admin

- 전체 주문 관리
- 상품 관리
- 협력사 관리
- 고객 안내 발송
- 사진 검수
- 결제 상태 확인
- 발송 이력 확인

### 3.2 partner

- 본인에게 배정된 작업만 조회
- 작업 상세 확인
- 비포/애프터 사진 업로드
- 작업 완료 처리

### 3.3 customer

- 회원가입 없음
- 고유 링크 + 전화번호 뒷자리 인증으로 주문 페이지 접근
- 예약 정보 및 완료 사진 확인

---

## 4. 우선 구현해야 할 기능

1. 관리자 로그인
2. 관리자 대시보드
3. 주문 CRUD
4. 상품/카테고리 CRUD
5. 협력사 CRUD
6. 협력사 로그인
7. 협력사 내 작업 조회
8. 협력사 사진 업로드
9. 관리자 사진 검수
10. 고객 링크 페이지
11. 연락처 뒷자리 인증
12. 메시지 발송 이력 구조
13. 문자/알림톡 발송 API 연동을 위한 추상화 레이어
14. 주문 타임라인 로그

---

## 5. 추천 기술 스택

- Next.js App Router
- TypeScript
- Tailwind CSS
- shadcn/ui
- Supabase 또는 PostgreSQL
- Supabase Storage 또는 S3-compatible storage
- Server Actions 또는 API Routes
- Zod validation
- React Hook Form
- TanStack Table if needed

---

## 6. 중요 개발 원칙

- 관리자/협력사/고객 권한을 명확히 분리한다.
- 협력사는 본인에게 배정된 주문만 볼 수 있다.
- 고객은 customer_token과 전화번호 뒷자리 인증을 통과해야 주문을 볼 수 있다.
- 협력사가 업로드한 사진은 기본적으로 고객에게 비공개다.
- 관리자가 승인한 사진만 고객 페이지에 노출된다.
- 모든 상태 변경, 발송, 사진 업로드는 order_timeline에 기록한다.
- 메시지 발송은 실제 API가 없어도 교체 가능한 adapter 구조로 만든다.
- 초기에는 mock sender를 두고, 이후 SMS/알림톡 API로 교체 가능하게 만든다.

---

## 7. 필수 DB 테이블

- users
- partners
- service_categories
- service_items
- orders
- order_photos
- message_logs
- order_timeline

---

## 8. 데이터 모델

### 8.1 users

```ts
users {
  id: string
  role: 'admin' | 'partner'
  name: string
  email?: string
  phone?: string
  password_hash: string
  partner_id?: string
  is_active: boolean
  created_at: datetime
  updated_at: datetime
}
```

---

### 8.2 partners

```ts
partners {
  id: string
  name: string
  manager_name?: string
  phone: string
  service_areas?: string
  available_services?: string
  memo?: string
  is_active: boolean
  created_at: datetime
  updated_at: datetime
}
```

---

### 8.3 service_categories

```ts
service_categories {
  id: string
  name: string
  description?: string
  is_active: boolean
  sort_order: number
  created_at: datetime
  updated_at: datetime
}
```

---

### 8.4 service_items

```ts
service_items {
  id: string
  category_id: string
  name: string
  unit: '평' | '대' | '건' | '세트' | '기타'
  base_price: number
  description?: string
  is_active: boolean
  sort_order: number
  created_at: datetime
  updated_at: datetime
}
```

---

### 8.5 orders

```ts
orders {
  id: string

  status:
    '신규접수' |
    '상담중' |
    '협력사확인중' |
    '일정확정' |
    '전날안내필요' |
    '전날안내완료' |
    '작업예정' |
    '작업진행' |
    '사진검수대기' |
    '고객전달필요' |
    '고객전달완료' |
    '서비스완료' |
    '취소'

  received_date: date
  scheduled_date?: date
  requested_time?: string

  partner_id?: string
  team_name?: string

  service_category_id?: string
  service_item_id?: string
  service_name: string
  size_or_quantity?: string
  service_detail?: string
  special_request?: string

  source_channel?: string

  customer_name: string
  customer_phone: string
  customer_address: string

  total_amount?: number
  deposit_amount?: number
  balance_amount?: number
  onsite_extra_amount?: number
  vat_type?: '포함' | '미포함' | '해당없음'
  payment_status?: string
  payment_memo?: string
  evidence_memo?: string

  partner_payment_amount?: number
  partner_payment_status?: string

  customer_token: string
  customer_visible_payment: boolean

  created_at: datetime
  updated_at: datetime
}
```

---

### 8.6 order_photos

```ts
order_photos {
  id: string
  order_id: string
  uploaded_by_user_id: string
  photo_type: 'before' | 'after' | 'etc'
  file_url: string
  file_name?: string
  file_size?: number
  is_customer_visible: boolean
  created_at: datetime
}
```

---

### 8.7 message_logs

```ts
message_logs {
  id: string
  order_id: string
  recipient_type: 'customer' | 'partner'
  recipient_name: string
  recipient_phone: string
  message_type:
    'customer_schedule_confirmed' |
    'customer_day_before' |
    'partner_assignment' |
    'customer_photo_ready'
  channel: 'sms' | 'lms' | 'alimtalk'
  content: string
  status: 'pending' | 'sent' | 'failed'
  error_message?: string
  sent_at?: datetime
  created_at: datetime
}
```

---

### 8.8 order_timeline

```ts
order_timeline {
  id: string
  order_id: string
  actor_user_id?: string
  event_type:
    'created' |
    'status_changed' |
    'partner_assigned' |
    'message_sent' |
    'photo_uploaded' |
    'photo_approved' |
    'customer_link_sent' |
    'memo_added'
  title: string
  description?: string
  metadata?: json
  created_at: datetime
}
```

---

## 9. 상태값

- 신규접수
- 상담중
- 협력사확인중
- 일정확정
- 전날안내필요
- 전날안내완료
- 작업예정
- 작업진행
- 사진검수대기
- 고객전달필요
- 고객전달완료
- 서비스완료
- 취소

---

## 10. 라우트 예시

### 관리자

- `/admin/login`
- `/admin/dashboard`
- `/admin/orders`
- `/admin/orders/new`
- `/admin/orders/[id]`
- `/admin/photo-review`
- `/admin/services`
- `/admin/partners`
- `/admin/messages`
- `/admin/settings`

### 협력사

- `/partner/login`
- `/partner/jobs`
- `/partner/jobs/[id]`

### 고객

- `/c/[customerToken]`
- `/c/[customerToken]/verify`
- `/c/[customerToken]/order`

---

## 11. 대시보드 계산 항목

- `todayJobs`: scheduled_date가 오늘이고 취소가 아닌 주문
- `tomorrowNoticeTargets`: scheduled_date가 내일이고 전날안내완료가 아닌 주문
- `partnerPending`: status가 협력사확인중인 주문
- `photoReviewPending`: status가 사진검수대기인 주문
- `customerDeliveryNeeded`: status가 고객전달필요인 주문
- `paymentCheckNeeded`: payment_status가 미확인 또는 잔금미확인인 주문
- `monthlyCompleted`: 이번 달 서비스완료 주문 수
- `monthlyRevenue`: 이번 달 서비스완료 주문 total_amount 합계

---

## 12. 메시지 발송

### 메시지 발송 유형

1. `customer_schedule_confirmed`
2. `customer_day_before`
3. `partner_assignment`
4. `customer_photo_ready`

### 메시지 발송 구현 방식

- `sendMessage({ orderId, type, recipientType })` 함수로 추상화한다.
- 실제 발송 전 message preview를 생성한다.
- 실제 발송 API가 없는 경우 mock 발송으로 `message_logs`에 `sent` 상태 저장한다.
- 이후 SMS/알림톡 API provider로 교체할 수 있도록 `MessageProvider` 인터페이스를 둔다.

---

## 13. 사진 업로드 원칙

- 협력사는 before, after, etc 타입으로 업로드한다.
- 업로드된 사진은 `is_customer_visible=false`로 저장한다.
- 관리자가 승인하면 `is_customer_visible=true`로 변경한다.
- 고객 페이지는 `is_customer_visible=true`인 사진만 보여준다.

---

## 14. 고객 인증

- 고객 링크는 `customer_token`으로 접근한다.
- 첫 접근 시 전화번호 뒷자리 4자리를 입력받는다.
- `orders.customer_phone`의 마지막 4자리와 일치하면 세션 또는 임시 토큰으로 접근 허용한다.
- 인증 실패 시 주문 상세를 노출하지 않는다.

---

## 15. 주문 타임라인

다음 이벤트는 반드시 기록한다.

- 주문 생성
- 상태 변경
- 협력사 배정
- 메시지 발송
- 사진 업로드
- 사진 고객 공개 승인
- 고객 링크 발송
- 메모 추가

---

## 16. UI 구현 방향

- 관리자: 데스크톱 우선, 테이블과 대시보드 중심
- 협력사: 모바일 우선, 작업 카드 중심
- 고객: 모바일 우선, 브랜드 페이지처럼 깔끔하게

---

## 17. 최우선 구현 순서

1. DB schema
2. Auth and roles
3. Admin order CRUD
4. Admin dashboard
5. Partner job view
6. Photo upload/review flow
7. Customer token page
8. Message log and mock sending
9. Timeline logs
10. Polish and validation

---

## 18. 완성 기준

- 관리자가 주문을 등록할 수 있다.
- 관리자가 협력사를 배정할 수 있다.
- 협력사가 로그인 후 본인 작업만 볼 수 있다.
- 협력사가 사진을 업로드할 수 있다.
- 관리자가 사진을 검수하고 고객 공개 승인할 수 있다.
- 고객이 링크와 전화번호 뒷자리 인증으로 주문 정보를 볼 수 있다.
- 고객은 승인된 사진만 볼 수 있다.
- 메시지 발송 이력이 남는다.
- 주문 상태 변경 이력이 타임라인에 남는다.
- 대시보드에서 오늘 처리할 일이 표시된다.

---

# Claude Code 테스트/검수 지시서

너는 QA 엔지니어이자 코드 리뷰어다.

Cleaning Ops Control Center 프로젝트의 전체 동작을 점검해줘.

---

## 1. 관리자 주문 생성

- 신규 주문을 생성한다.
- 고객명, 연락처, 주소, 상품명, 방문예정일, 요청시간, 금액 정보를 입력한다.
- 주문 상태가 신규접수로 저장되는지 확인한다.
- 주문 생성 로그가 타임라인에 남는지 확인한다.

---

## 2. 협력사 배정

- 관리자에서 협력사를 생성한다.
- 주문에 협력사를 배정한다.
- 협력사 배정 로그가 타임라인에 남는지 확인한다.
- 협력사 계정으로 로그인했을 때 본인에게 배정된 작업만 보이는지 확인한다.

---

## 3. 협력사 작업 처리

- 협력사로 로그인한다.
- 작업 상세를 확인한다.
- 금액 정보가 보이지 않는지 확인한다.
- 비포 사진을 업로드한다.
- 애프터 사진을 업로드한다.
- 작업 완료 버튼을 누른다.
- 주문 상태가 사진검수대기로 변경되는지 확인한다.
- 사진 업로드 로그가 남는지 확인한다.

---

## 4. 관리자 사진 검수

- 관리자에서 사진검수 메뉴를 확인한다.
- 협력사가 올린 사진이 보이는지 확인한다.
- 사진을 고객 공개 승인한다.
- 승인된 사진만 고객 페이지에 보이는지 확인한다.

---

## 5. 고객 페이지

- `customer_token` 링크로 접근한다.
- 전화번호 뒷자리 인증 전에는 주문 정보가 노출되지 않는지 확인한다.
- 올바른 뒷자리 입력 시 주문 정보가 보이는지 확인한다.
- 잘못된 뒷자리 입력 시 접근이 제한되는지 확인한다.
- 고객 페이지에는 내부 메모, 협력사 지급금액, 유입경로, 내부 결제메모가 노출되지 않는지 확인한다.

---

## 6. 메시지 발송

- 고객 일정 확정 안내 발송을 테스트한다.
- 고객 전날 안내 발송을 테스트한다.
- 협력사 작업 배정 안내 발송을 테스트한다.
- 고객 완료 사진 안내 발송을 테스트한다.
- 각 발송 건이 `message_logs`에 기록되는지 확인한다.
- 실패 케이스도 기록 가능한지 확인한다.

---

## 7. 대시보드

- 오늘 작업 수가 올바르게 계산되는지 확인한다.
- 내일 안내 대상이 올바르게 계산되는지 확인한다.
- 사진 검수 대기가 올바르게 표시되는지 확인한다.
- 고객 전달 필요 건수가 올바르게 표시되는지 확인한다.
- 결제 확인 필요 건수가 올바르게 표시되는지 확인한다.

---

## 8. 권한 검수

- 협력사가 다른 협력사의 주문을 볼 수 없는지 확인한다.
- 고객이 다른 고객 주문에 접근할 수 없는지 확인한다.
- 비로그인 사용자가 관리자/협력사 페이지에 접근할 수 없는지 확인한다.
- 고객 페이지에 민감한 내부 정보가 노출되지 않는지 확인한다.

---

## 9. 코드 품질

- 타입 안정성 확인
- 중복 로직 확인
- 상태값 하드코딩 과다 여부 확인
- 메시지 발송 provider가 교체 가능한 구조인지 확인
- 사진 업로드 에러 처리가 있는지 확인
- DB 접근 권한이 안전한지 확인

이 프로젝트는 단순 CRUD가 아니라 실제 운영 시스템이므로, 기능이 돌아가는지만 보지 말고 업무 흐름이 끊기지 않는지 기준으로 점검해줘.

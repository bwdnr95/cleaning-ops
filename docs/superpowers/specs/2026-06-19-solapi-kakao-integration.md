# SOLAPI(문자) + 카카오 알림톡 연동 — 설정 런북

- 작성일: 2026-06-19
- 결론: **연동 코드는 이미 구현 완료.** 남은 일은 콘솔 설정 + `backend/.env` 주입 + 검증.
- 순서: **Phase 1 = SMS/LMS 먼저 가동**, Phase 2 = 알림톡(템플릿 승인 후).
- 관련 코드: `backend/app/services/messages.py`(`SolapiMessageProvider`, `build_solapi_auth_header`), `backend/app/domain/message_templates.py`(알림톡 템플릿 변수), `backend/app/api/routes/webhooks.py`(전송 리포트 웹훅), `backend/app/core/config.py`(설정 키).

---

## 현재 구현 상태 (확인 완료)
- SMS 발송: `SolapiMessageProvider.send` — SOLAPI v4 send-many/detail 호출, 인증 서명(`HMAC-SHA256 apiKey/date/salt`) **규격 일치**.
- 알림톡: `_send_kakao_alimtalk` — `kakaoOptions(pfId/templateId/variables)` + **실패 시 SMS 자동 폴백**.
- 웹훅: `/api/webhooks/solapi` — 서명 검증 후 `message_logs` 전송상태 갱신.
- 준비상태 점검: 관리자 "메시지 설정"에서 `can_send_alimtalk`, 누락 경고 표시.
- 설정 키: `config.py`에 api key/secret/발신번호/pfId/템플릿/웹훅시크릿/폴백 모두 정의. `.env`는 `backend/.env`.

---

## 자동 발송 기준 (2026-07-11 확인)
- 현재 운영 설정 기준 자동 ON: `partner_assignment`, `customer_schedule_confirmed`, `customer_day_before`, `customer_balance_due`.
- 현재 운영 설정 기준 자동 OFF: 고객 사진확인 안내(수동 발송 유지).
- `customer_balance_due`: 협력사가 작업 완료 처리했고 고객 미수금이 남아 있을 때 자동 발송.
- `partner_assignment`: 자동 설정을 켠 경우, 주문 생성 시 협력사가 이미 배정되어 있거나 기존 주문의 `partner_id`가 변경될 때 발송.
- `customer_schedule_confirmed`: 주문이 `일정확정`으로 생성/수정되거나 협력사가 작업확인을 눌러 `작업예정`으로 전환될 때 고객에게 자동 발송한다. 같은 주문의 pending/sent/delivered 시도는 중복하지 않는다.
- `customer_day_before`: 매일 오전 10시(KST), 기준일 다음날 방문 예정인 일정확정/전날안내필요/작업예정 건에 발송. pending/sent/delivered 시도는 중복하지 않는다. 수동 실행 엔드포인트도 존재한다.
- `customer_photo_ready`: 수동 발송 기준으로 구현되어 있으며, 자동 설정값은 존재하지만 현재 사진 업로드/작업완료에 연결된 자동 트리거는 없음.
- `partner_as_request`, `customer_as_notice`: 고객 AS 접수 후 운영자가 AS 요청 처리를 실행할 때 협력사와 고객에게 각각 자동 발송한다.

## SOLAPI 실계정 template_id 대조 (2026-07-11)

`GET /kakao/v2/templates` 실조회 결과 아래 9개 모두 채널 `KA01PF260625095328232y4DcSniavuQ`에서 `APPROVED` 상태다.

| 메시지 타입 | SOLAPI 템플릿명 | template_id |
|---|---|---|
| `customer_schedule_confirmed` | 일정 확정 안내 | `KA01TP260625095558697f6OQqqhxjqb` |
| `customer_day_before` | 전날 안내 | `KA01TP260625095745441foLkYjPPfnS` |
| `partner_assignment` | 협력사 배정 안내(사본) | `KA01TP260703114932918wBetIEHC8dg` |
| `customer_photo_ready` | 사진 링크 발송 | `KA01TP260625095950577Dxz0dLAs9aH` |
| `customer_balance_due` | 잔금 안내 | `KA01TP260625100057110pUAJaMeQ99G` |
| `customer_quote` | 견적 안내 | `KA01TP260625100150149r4XMoHWve1R` |
| `partner_customer_info` | 협력사 고객정보(미입금) | `KA01TP260625100259815c7MUvtoPo72` |
| `partner_as_request` | AS 협력사용 | `KA01TP2607090709454037h9FwYAHMbW` |
| `customer_as_notice` | AS 고객용 | `KA01TP260709071111937Ctnx5OzcNNq` |

---

## Phase 1 — SMS/LMS 가동

### 1. SOLAPI 콘솔 (직접)
1. **API Key / Secret** 확인 (이미 보유).
2. **발신번호 등록**: `메시지 > 발신번호 관리`에서 ARS 또는 서류 인증. ⏳ 등록 완료 전에는 실제 발송 불가(핵심 블로커).
3. **잔액 충전** 확인.

### 2. `backend/.env` 주입
이미 빈 키 블록을 추가해 둠. 아래 3개만 채우면 SMS 가능:
```
SOLAPI_API_KEY=<발급키>
SOLAPI_API_SECRET=<발급시크릿>
SOLAPI_SENDER_NUMBER=<등록한 발신번호, 하이픈 없이>
```
> 값 뒤에 인라인 주석(`# ...`) 금지(dotenv 파싱 오류). 설명은 윗줄 주석으로.

### 3. 검증 (단계적)
1. **단건 테스트 스크립트** (앱 전환 전, 안전):
   ```powershell
   cd backend
   python scripts/test_solapi_sms.py 010XXXXYYYY
   ```
   - `status: sent` + 단말기 수신 확인 → 발송 정상.
   - 실패 시 출력된 `error_message` / `provider_response`로 원인(발신번호 미등록, 잔액부족, 인증오류 등) 파악.
2. **앱 전체 전환**: 위 성공 후 `backend/.env`에서 `MESSAGE_PROVIDER=solapi`로 변경 → 백엔드 재기동.
3. **운영 플로우 확인**: 관리자 주문 상세에서 안내 발송(예: 일정확정) → `message_logs`에 SENT 기록 + 고객 단말 수신.

### 4. 웹훅(전송 리포트) — 배포 환경에서만
- 로컬(8002)은 공개 URL이 없어 웹훅 수신 불가 → Phase 1 검증은 발송 즉시 응답으로 충분.
- 배포 도메인(`cleanjob.tono-operation.com`) 사용 시 SOLAPI 콘솔 웹훅 URL = `https://<도메인>/api/webhooks/solapi`.
- **확인 필요(미확정)**: 현재 코드는 웹훅 서명을 "우리 `SOLAPI_WEBHOOK_SECRET`으로 body HMAC-SHA256 → `X-Solapi-Signature`" 라고 가정한다. SOLAPI 실제 리포트 웹훅의 서명 방식이 이와 다르면 웹훅이 401로 전부 거부될 수 있음. 웹훅을 켜기 전, SOLAPI 콘솔의 웹훅 설정(서명/시크릿 지원 여부)과 대조해 코드의 `verify_solapi_webhook_signature`를 맞춰야 함. (공식 웹훅 레퍼런스 문서가 이전되어 온라인으로 즉시 확정 못 함.)

---

## Phase 2 — 카카오 알림톡 (템플릿 승인 후)

### 1. 카카오 채널 + 연동
1. 카카오 비즈니스 채널 보유(로그인 완료).
2. SOLAPI에 카카오 채널 연동 → **pfId(카카오 알림톡 발신프로필 ID)** 발급.

### 2. 알림톡 템플릿 등록 + 검수 승인
9종 메시지 타입을 등록하고, **변수명을 코드의 `#{...}` 형식과 정확히 일치**시킨다(`message_templates.py` 기준):
- `customer_schedule_confirmed`: `#{고객명} #{방문일정} #{서비스명} #{평수} #{대수} #{주소} #{연락처} #{금액} #{계약금} #{잔금} #{총금액} #{고객링크}`
- `customer_day_before`: `#{고객명} #{서비스명} #{방문일정} #{평수} #{대수} #{주소} #{연락처} #{고객링크}`
- `partner_assignment`: `#{고객명} #{서비스명} #{협력사명} #{방문일정} #{평수} #{대수} #{주소} #{연락처} #{요청사항} #{협력사링크}`
- `customer_photo_ready`: `#{고객명} #{서비스명} #{고객링크}`
- `customer_balance_due`: `#{고객명} #{서비스명} #{잔금} #{고객링크}`
- `customer_quote`: `#{고객명} #{서비스명} #{방문일정} #{평수} #{대수} #{주소} #{성함} #{금액} #{할인가} #{계약금} #{잔금} #{총금액}`
- `partner_customer_info`: `#{담당자} #{고객명} #{연락처} #{주소} #{요청사항}`
- `partner_as_request`: `#{협력사명} #{고객명} #{서비스명} #{협력사링크}`
- `customer_as_notice`: `#{고객명} #{서비스명} #{고객링크}`

### 3. `.env` 채우기 + 테스트
```
SOLAPI_KAKAO_PF_ID=<pfId>
# 기존 배포 호환용으로 SOLAPI_KAKAO_CHANNEL_ID도 읽지만, 신규 설정은 PF_ID를 사용한다.
SOLAPI_KAKAO_CHANNEL_ID=
SOLAPI_KAKAO_TEMPLATE_CUSTOMER_SCHEDULE_CONFIRMED=<템플릿ID>
... (9종)
```
- 채널을 `ALIMTALK`로 발송 테스트 → 알림톡 수신 확인, 실패 시 SMS 폴백 동작 확인.

---

## 미해결/확인 포인트
1. 웹훅 서명 방식(위 Phase 1-4) — 배포 시 SOLAPI 실제 스펙과 대조 후 확정.
2. 발신번호/수신번호 포맷 — 코드가 `normalize_phone`으로 숫자만 추출(하이픈 제거)하므로 국내번호 OK.
3. 알림톡 템플릿 변수명 — 승인된 템플릿과 `message_templates.py`가 1:1로 맞아야 치환됨.

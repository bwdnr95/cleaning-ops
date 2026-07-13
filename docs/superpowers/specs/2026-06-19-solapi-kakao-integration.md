# SOLAPI(문자) + 카카오 알림톡 연동 — 설정 런북

- 작성일: 2026-06-19 / 최종 대조: 2026-07-11
- 결론: **SOLAPI 발신프로필과 알림톡 9종 승인 상태를 실조회해 코드·운영 예시와 대조 완료.**
- 순서: **Phase 1 = SMS/LMS 먼저 가동**, Phase 2 = 알림톡(템플릿 승인 후).
- 관련 코드: `backend/app/services/messages.py`(`SolapiMessageProvider`, `build_solapi_auth_header`), `backend/app/domain/message_templates.py`(알림톡 템플릿 변수), `backend/app/api/routes/webhooks.py`(전송 리포트 웹훅), `backend/app/core/config.py`(설정 키).

---

## 현재 구현 상태 (확인 완료)
- SMS 발송: `SolapiMessageProvider.send` — SOLAPI v4 send-many/detail 호출, 인증 서명(`HMAC-SHA256 apiKey/date/salt`) **규격 일치**.
- 알림톡: `SolapiMessageProvider.send_with_context` — `kakaoOptions(pfId/templateId/variables)` + **실패 시 SMS 자동 폴백**.
- 웹훅: `/api/webhooks/solapi` — `X-Solapi-Secret`의 `SHA1(SOLAPI_WEBHOOK_SECRET)`을 검증한 후 `message_logs` 전송상태 갱신.
- 준비상태 점검: 관리자 "메시지 설정"에서 `can_send_alimtalk`, 누락 경고 표시.
- 설정 키: `config.py`에 api key/secret/발신번호/pfId/템플릿 9종/웹훅시크릿/폴백을 정의한다. `.env`는 `backend/.env`.

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
- SOLAPI 콘솔에는 `SOLAPI_WEBHOOK_SECRET` 원문을 등록한다. SOLAPI는 `SHA1(secret)`을 `X-Solapi-Secret` 헤더로 보내며 서버는 상수 시간 비교로 검증한다. 본문이나 secret 값은 로그에 남기지 않는다.

---

## Phase 2 — 카카오 알림톡 (템플릿 승인 후)

### 1. 카카오 채널 + 연동
1. 카카오 비즈니스 채널 보유(로그인 완료).
2. SOLAPI에 카카오 채널 연동 → **pfId(알림톡 발신프로필 ID)** 발급.

### 2. 알림톡 템플릿 등록 + 검수 승인
실조회한 승인 템플릿은 아래 9종이다. 치환문자 집합은
`backend/tests/test_message_templates.py`가 승인본과 1:1로 잠근다.

| 메시지 타입 | 승인 templateId |
|---|---|
| `customer_schedule_confirmed` | `KA01TP260625095558697f6OQqqhxjqb` |
| `customer_day_before` | `KA01TP260625095745441foLkYjPPfnS` |
| `partner_assignment` | `KA01TP260703114932918wBetIEHC8dg` |
| `customer_photo_ready` | `KA01TP260625095950577Dxz0dLAs9aH` |
| `customer_balance_due` | `KA01TP260625100057110pUAJaMeQ99G` |
| `customer_quote` | `KA01TP260625100150149r4XMoHWve1R` |
| `partner_customer_info` | `KA01TP260625100259815c7MUvtoPo72` |
| `partner_as_request` | `KA01TP2607090709454037h9FwYAHMbW` |
| `customer_as_notice` | `KA01TP260709071111937Ctnx5OzcNNq` |

### 3. `.env` 채우기 + 테스트
```
SOLAPI_KAKAO_PF_ID=KA01PF260625095328232y4DcSniavuQ
SOLAPI_KAKAO_TEMPLATE_CUSTOMER_SCHEDULE_CONFIRMED=<템플릿ID>
... (9종, `.env.production.example` 참조)
```
- 채널을 `ALIMTALK`로 발송 테스트 → 알림톡 수신 확인, 실패 시 SMS 폴백 동작 확인.
- 운영 자격증명을 출력하지 않는 승인본 대조: `cd backend && python -m scripts.verify_solapi_alimtalk_templates`
- 이 검증기는 `GET /kakao/v2/templates/sendable` 결과, 승인 상태, `pfId`, 변수 집합, 실행 환경의 9개 template ID를 함께 대조하며 인증 헤더를 다른 호스트로 전달할 수 있는 redirect는 거부한다.

---

## 운영 확인 포인트
1. 발신번호/수신번호 포맷 — 코드가 `normalize_phone`으로 숫자만 추출(하이픈 제거)하므로 국내번호 OK.
2. 알림톡 템플릿 변수명 — 승인된 템플릿과 `message_templates.py`가 1:1로 맞아야 치환됨.
3. AS 승인 템플릿에는 AS 메모와 고객 연락처 치환문자가 없다. 상세 내용은 인증된 협력사/고객 링크에서 확인한다. 애플리케이션의 명확한 초기 실패 후 직접 SMS 폴백에는 메모 요약이 포함되지만, SOLAPI 자체 비동기 폴백에서는 메모 포함을 보장하지 않는다.

# Payself / 셀프페이 연동 가능성 조사

조사일: 2026-05-26  
범위: R14 가격/견적/정산 마일스톤 후속 결제 링크 연동 가능성

## 결론

공개 웹 기준으로는 “Payself”라는 영문명보다는 `셀프페이 | SELFPAY` 공식 사이트가 확인된다. 공식 페이지는 ERP/CRM/POS 또는 자사몰과 연결하는 API 제공을 안내하지만, 엔드포인트/인증/웹훅 시그니처/샌드박스 같은 상세 개발 문서는 공개되어 있지 않다. 따라서 R14에서 바로 provider 구현까지 넣기보다는, 결제 provider 인터페이스와 주문/메시지 타임라인을 유지한 채 계약 후 스펙을 받아 `PaymentLinkProvider`로 붙이는 방식이 안전하다.

## 확인한 공개 정보

- 셀프페이 공식 “자사몰 API 제공” 페이지는 가맹사가 쓰는 ERP, CRM, POS 등 결제가 필요한 영역과 셀프페이를 연동하기 위한 API를 제공한다고 설명한다.  
  Source: https://www.selfpay.kr/home/index_subpage.html?mainwhat=1&subwhat=12
- 셀프페이 “비대면 결제” 페이지는 판매자가 문자 또는 카카오 알림톡으로 결제 요청을 보내는 비대면 결제 모델을 설명한다. Cleaning Ops의 고객 견적/잔금 안내 메시지와 제품 방향은 맞는다.  
  Source: https://www.selfpay.kr/home/index_subpage.html?mainwhat=1&subwhat=2
- 공식 소개서 PDF는 가맹사 연결 API, 이용료, 결제 수수료, 결제 주기(D+3~15일), API 개발운영비가 별도 협의될 수 있음을 안내한다.  
  Source: https://www.selfpay.kr/home/brochure/%EC%85%80%ED%94%84%ED%8E%98%EC%9D%B4_%EC%A2%85%ED%95%A9%EC%86%8C%EA%B0%9C%EC%84%9C%28%EC%86%94%EB%A3%A8%EC%85%98%ED%8C%90%EB%A7%A4%EC%9A%A9%29.pdf
- 정산 프로세스 공개 페이지는 결제요청, 고객결제, 승인요청, PG 대금지급의 큰 흐름을 설명한다.  
  Source: https://www.selfpay.kr/home/index_subpage.html?mainwhat=2&subwhat=6

## 후속 확인 질문

- 결제 링크 생성 API의 인증 방식, IP allowlist 필요 여부, sandbox 제공 여부
- 주문번호/가맹점 주문키 중복 정책과 취소/부분취소 API
- 결제 성공/실패/취소 웹훅 payload, 서명 검증 방식, 재시도 정책
- 결제 링크 만료 시간, 금액 변경/재발송 정책
- 정산 조회 API 제공 여부와 수수료/VAT/입금일 필드 정의
- 개인정보 위탁/보관 범위, 고객 전화번호/주소 전송 필요 여부

## 권장 설계

1. `PaymentProvider` 또는 `PaymentLinkProvider` 인터페이스를 메시지 provider처럼 교체 가능하게 둔다.
2. 주문에는 외부 결제 provider raw payload를 직접 섞지 않고 `payment_links`/`payment_events` 같은 별도 테이블을 둔다.
3. 고객 메시지는 기존 `MessageService`에서 결제 링크만 변수로 주입한다. 견적/도급가 분리 규칙은 그대로 유지한다.
4. 결제 성공 웹훅은 `payment_status`, `deposit_amount`/`balance_amount` 변경과 `order_timeline` 기록을 같은 트랜잭션으로 묶는다.

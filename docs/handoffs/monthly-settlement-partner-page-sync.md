<!--
핸드오프 스펙 = Claude↔Codex 바통. 루프 계약: `.claude/rules/codex-loop.md`
-->

# 월 청구 정기 도급비를 협력사관리 정산 화면에 표시/실행 동기화   | Tier: A

## 배경 (대표 보고 2026-08-28)

김해푸르지오하이엔드1차(월 청구 정기계약, 도급 월 660,000원, 협력사 치움):
- 월 트래커에서 8월 지급 체크 → DB `recurring_monthly_status.partner_payment_paid=true` 정상 반영.
- 그러나 협력사관리(치움) 정산 목록에는 월정산 행이 아예 없음 — 미지급 탭 제외,
  전체 탭 0원+체크박스 비활성, 정산완료 탭에도 미표시.
- 반면 협력사 목록/상세의 "미정산 합계" 배지에는 월 정기 미지급(7월분 660,000)이 합산됨.
  → **배지와 목록이 모순** ("미정산으로 보이는데 정산 체크가 불가"). AGENTS.md 1-1 원칙 위반 상태.

## 완료정의 (성공기준 — 실표면 증거로 증명)

- [x] 협력사관리 정산 목록에 월정산 행(계약×월)이 표시된다 — 미지급 탭: 미지급 월(날짜필터 무관, 배지와 동일 기준), 정산완료 탭: 지급 월. → HTTP `GET /api/admin/partners/{id}/settlements` 응답 `monthly_items` + 화면
- [x] 협력사관리에서 월정산 행 지급 처리/되돌리기 가능, 월 트래커와 같은 DB 행이므로 양방향 동기화. → HTTP POST + DB diff
- [x] **월정산 축에서** 배지 == 목록 — 같은 헬퍼(list_monthly_settlement_rows)에서 파생 + 리포트 백로그(다른 계산 경로)와의 교차 대조 테스트. ⚠️ 주문 축은 의도된 정책 차이가 남는다: 배지는 `PARTNER_ADMIN_UNPAID_STATUSES`(작업진행 이후) + 방문일≤오늘만 합산하고, 목록 미정산 탭은 더 넓게 보여준다(완료 전 정산 정책, order_metrics.py 문서화). 운영 데이터 감사 결과 그 차이는 전부 협력사확인중/일정확정/작업예정 상태의 예정 작업이었다.
- [x] 회당(per_visit) 계약·미래 월·타 협력사 월은 목록/실행 모두 제외.

## 스코프 (건드릴 파일)

- backend: `services/recurring_partner_billing.py`(공용 행 빌더), `services/partners.py`(배지 재구성),
  `services/partner_settlements.py`(목록+실행), `schemas/partner.py`, `api/routes/admin/partner_settlements.py`
- frontend: `features/admin/partners/PartnersPage.tsx`, `api/admin.ts`
- tests: `tests/test_partner_settlement_recurring_monthly.py`(신규)

## 불변유지 (절대 건드리지 말 것)

- 주문 단위 정산 흐름(settle/revert, unpaid_partner_condition, 1-1 정책) 불변.
- 월 트래커(정기청소 탭) 동작·가드(`RecurringMonthlyService.set_status`) 불변 — 재사용만.
- reports.py 정산 백로그(월정산대기 행) 불변.
- 마이그레이션 없음 (스키마 변경 없음).

## 게이트

- [x] 멱등 (지급 토글 재실행 안전 — 같은 값 재설정은 no-op)
- [x] 격리/회귀 (기존 주문 정산 테스트 green, 기존 DTO 필드 불변·추가만)
- [ ] 마이그 — 해당 없음
- [x] soft-delete — 신규 조회는 계약/상태 기반, 주문 조회 경로 불변
- [ ] 타임라인 — 월정산 토글은 주문 무소속이라 timeline 미기록(월 트래커와 동일 정책). 한계로 보고.

## ⚠️ 위험지대

- [x] **숫자 산출**(정산) → 실DB dry-run + 배지↔목록 cross-check 테스트로 결착
- [x] 서로소 리뷰 필수 (Tier A)
- 배포: 백엔드 8002가 --reload로 기동 중 → main 반영 시 자동 적용됨을 보고에 명시

## 검증 커맨드

```
cd backend && python -m pytest tests/test_partner_settlement_recurring_monthly.py tests/test_partner_settlement_unpaid.py tests/test_recurring_monthly.py
cd backend && python -m pytest
cd frontend && npm run typecheck && npm run build
```

## 상태표 (진행하며 갱신)

| 증분 | 상태 | 증거/커밋 |
|---|---|---|
| 공용 행 빌더 + 배지 재구성 | 완료 | recurring_partner_billing.list_monthly_settlement_rows |
| 정산 목록 monthly_items + 실행 API | 완료 | partner_settlements.py + routes |
| 프론트 월정산 행 표시/버튼 | 완료 | PartnersPage.tsx |
| 테스트 + 전체 스위트 | 완료 | backend 전체 green |
| 서로소 리뷰(Opus) | CHANGES → 반영 | H1: set_status expected_partner_id 락 내 재검증 · H3: 리포트 교차 대조 테스트 · H2: 본 문서 정정 · M4: today 주입 통일 · M5: revert no-op 가드 · M3 일부: 실행 응답을 set_status 반환값으로 구성(재스캔 제거) · L1: 정렬 수정 |
| 운영 DB 전수 감사(모순 시나리오 6종) | 완료 | S1~S6 이상 0건 · S4 이중계상 0건(M1 실데이터 해당 없음) · S5 매출 갭 별건 보고 |

## 이월 / 교훈

- **M2(리뷰)**: 월정산 지급/되돌리기에 액터 감사 기록 없음(월 트래커도 동일). order_timeline은 주문
  무소속이라 불가하지만 `AuditService.record(user_id=...)`는 가능 — 신규 AuditEventType 필요해
  constants.py 수정이 필요한데, 현재 main 워킹트리에 사람의 constants.py 미커밋 수정이 있어 충돌
  위험으로 이번 배치에서 제외. 다음 배치에서 추가할 것.
- **M3(리뷰)**: list_monthly_settlement_rows가 (계약×월)마다 resolve() 쿼리 — 운영 규모(계약 수십)
  에선 문제 없으나 billing_period 일괄 로드로 개선 여지. M6: 월정산 버튼 in-flight 가드 없음
  (기존 주문 버튼과 동일 패턴, 멱등이라 이중지급은 없음).
- per_visit↔monthly 전환 월은 주문 정산 + 월정산이 공존할 수 있다(전환 전 확정분 보존 정책,
  기존 배지도 동일 합산). 현 운영 데이터엔 해당 월 0건(감사 S4). 전환 운영 시 이중 지급하지
  않도록 화면 안내/상호 배제 후속 검토.
- 월 청구 정기 **매출**은 어떤 매출 화면에도 안 잡힌다(회차 주문 total_amount=None, 매출은 주문
  기반 합계). 운영 누적 갭 약 2,306만원 — 매출 정의 변경은 §3 대표 결정 사항으로 별건 보고.
- 운영 8002 uvicorn이 --reload라 백엔드 파일 편집=즉시 배포. 작업은 워크트리에서 하고 완성본만 main에 반영할 것.
- 2026-07월분(김해) 지급 체크는 미처리 상태로 남아 있음(계약 시작 7/13 — 일할 여부는 대표 판단 필요).

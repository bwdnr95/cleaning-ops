<!--
핸드오프 스펙 = Claude↔Codex 바통. Claude가 이 1장을 채워 넘기고, Codex가 읽어 구현하고,
리뷰 때 같은 문서로 대조한다. 맥락 재설명 0. 새 세션 재개도 이 문서부터.
사용법: 이 파일을 복사해 `docs/handoffs/<goal-slug>.md`로 저장 후 채운다. 진행 중 상태표 갱신.
루프 계약: `.claude/rules/codex-loop.md`
-->

# <goal 한 줄>   | Tier: A / B / C

## 완료정의 (성공기준 — 실표면 증거로 증명)
- [ ] <성공기준 1 — 어떤 증거로 증명하나: HTTP/E2E/DB diff/스크린샷>
- [ ] <성공기준 2>

## 스코프 (건드릴 파일)
- backend: `...`
- frontend: `...`

## 불변유지 (절대 건드리지 말 것)
- <기존 흐름/계약 — 회귀 금지 항목>

## 게이트 (해당 항목만 체크)
- [ ] 멱등 (재실행/재시도 안전, 이중처리·이중발송 0)
- [ ] 격리/회귀 (기존 조회/상태전이/DTO 불변, 신규참조 grep 0)
- [ ] 마이그 additive-only · 단일 head · up/down
- [ ] default-off/kill-switch + 롤백 1줄
- [ ] soft-delete `deleted_at IS NULL` 가드 (조회 추가 시)
- [ ] 타임라인 기록 (상태/발송/사진/삭제 이벤트)

## ⚠️ 위험지대 (해당 시 자율 정지 → 사람 판단)
- [ ] **숫자 산출**(매출/정산/지표) → 실주문 dry-run + 독립신호 cross-check 필수 (§4)
- [ ] **개인정보 DTO**(고객/협력사 민감필드) → 서로소 리뷰 필수
- [ ] **권한 경로**(partner_id 스코프·customer_token 인증) 변경
- [ ] **실제 외부 발송**(SMS/알림톡) · 배포 · prod DB → §3 승인

## 검증 커맨드
```
cd backend && python -m pytest <타깃>        # + mypy app (설정 시)
cd frontend && npm run build                 # + npm run typecheck / npm run e2e
```

## 리뷰
- 1차(같은모델): review-work / gate-reviewer
- 서로소(Tier A): diff를 다른 도구로 크로스 (Codex 구현 → Claude 리뷰 등)

## 상태표 (진행하며 갱신)
| 증분 | 상태 | 증거/커밋 |
|---|---|---|
| <증분1> | 대기/진행/리뷰/완료 | |

## 이월 / 교훈
-

# Cleaning Ops 운영 Runbook

## 시스템 구성

| 영역 | 호스트 | URL |
|---|---|---|
| 프론트 | Vercel | `https://app.<도메인>.kr` |
| API | Railway (FastAPI + uvicorn, 단일 서비스) | `https://api.<도메인>.kr` |
| DB | Railway PostgreSQL 16 | `DATABASE_URL` 환경변수에 자동 주입 |
| 사진 스토리지 | Cloudflare R2 (S3 호환) | `https://photos.<도메인>.kr` |
| 메시지 | SOL-API (카카오 알림톡 + SMS/LMS 폴백) | webhook: `https://api.<도메인>.kr/api/webhooks/solapi` |
| 모니터링 | Sentry | https://sentry.io |
| 코드/CI | GitHub + GitHub Actions | `.github/workflows/ci.yml` |

---

## 1. 배포 (정상)

평상시: `main` 에 push → Railway/Vercel 가 자동 배포.

1. 작업 PR 만들고 리뷰
2. CI green 확인 (`backend` + `frontend` job)
3. main 으로 머지 (squash 권장)
4. Railway: 자동으로 새 deploy 트리거. logs 에서 `alembic upgrade head` 성공 확인 후 트래픽 전환.
5. Vercel: 자동으로 새 build → preview → production 승격
6. 배포 후 5분간 Sentry 대시보드에서 새 에러 spike 없는지 모니터

소요: 약 5-8분.

---

## 2. 롤백

### 2.1 코드 롤백 (코드 결함)

**Railway (백엔드)**
- Railway 대시보드 → 프로젝트 → Deployments → 직전 정상 deploy 의 `Redeploy` 버튼

**Vercel (프론트)**
- Vercel 대시보드 → Project → Deployments → 직전 정상 deploy 의 `Promote to Production`

소요: 1-2분.

### 2.2 DB 마이그레이션 롤백

**원칙**: alembic downgrade 는 위험. 컬럼 추가/제거 회수에 따라 데이터 손실 가능.

**옵션 A (권장)**: 새 hotfix 마이그레이션을 forward-only 로 작성해서 schema를 원하는 상태로 되돌림.

**옵션 B (비상)**: 직전 정상 시점 PostgreSQL 스냅샷으로 복구 — 4번 절차 참고.

---

## 3. Secret / 키 로테이션

| 키 | 영향 | 절차 |
|---|---|---|
| `SECRET_KEY` | 모든 admin/partner JWT 무효 → 즉시 재로그인 | Railway 환경변수 수정 → restart |
| `SOLAPI_API_KEY/SECRET` | 메시지 발송 즉시 실패 (회복: 새 키 입력) | SOL-API 콘솔 신규 키 발급 → Railway 변수 교체 → 기존 키 폐기 |
| `SOLAPI_WEBHOOK_SECRET` | webhook 거부 → 발송 결과 갱신 안 됨 | Railway 변경 → SOL-API 콘솔에서도 동일 원문 secret 등록. 요청 헤더는 SOLAPI가 `SHA1(secret)`을 `X-Solapi-Secret`으로 전송 |
| `S3_ACCESS_KEY_ID/SECRET` | 사진 업로드/조회 즉시 실패 | R2/S3 콘솔에서 새 토큰 발급 → Railway 교체 → 이전 토큰 revoke |
| `SENTRY_DSN` | 에러 추적만 멈춤 (서비스 정상) | Sentry 콘솔 → 신규 DSN → Railway 교체 |

**일반 규칙**: 변경 후 반드시 health 엔드포인트 `/api/health/ready` 확인.

---

## 4. DB 복구

Railway PostgreSQL 자동 백업 사용 가정.

1. Railway 대시보드 → PostgreSQL 서비스 → Backups
2. 복구 시점 선택 (PITR 가능 plan 인 경우 분 단위)
3. 새 DB 인스턴스로 복구 → connection string 복사
4. App 서비스의 `DATABASE_URL` 을 새 인스턴스로 변경 → restart
5. 데이터 검증 (시드 admin 으로 로그인, 최근 주문 수 확인)
6. 스키마가 코드보다 옛날이면 `alembic upgrade head` 수동 실행

**소요**: 10-30분 (백업 크기에 따라).

---

## 5. Sentry 알림 처리

**P0 (즉시 대응, 5분 내 응답)**
- 5xx 에러율 > 1% 5분 지속
- DB 연결 실패
- 로그인 100% 실패

**P1 (당일 처리)**
- 사진 업로드 실패 spike
- 메시지 발송 실패 spike (provider 에러)
- 특정 화면 client-side 에러 반복

**P2 (주간 처리)**
- 단발성 에러
- 사용자 1명만 발생한 에지 케이스

**대응 절차**:
1. Sentry 이벤트의 `request_id` 확인
2. Railway 로그에서 동일 `request_id` grep 으로 컨텍스트 확보
3. 재현 → 원인 분석 → 핫픽스 PR
4. 머지 후 Sentry 에서 이슈 resolve, 회귀 발생 시 재오픈

---

## 6. 주요 모니터링 체크리스트 (주 1회)

- [ ] Sentry P0/P1 이슈 0건 또는 모두 resolved
- [ ] Railway PostgreSQL 디스크 사용률 < 70%
- [ ] R2 버킷 사용량/요청 수 (월 free tier 한도 추적)
- [ ] SOL-API 잔액 + 발송 성공률 > 95%
- [ ] 카카오 알림톡 템플릿 9종 승인·활성 상태와 발신프로필 `pfId` 일치
- [ ] `notification_recovery_scheduler_completed` 로그가 60초 주기로 기록되고 `failed=0`
- [ ] DB 백업 정상 생성 (Railway → Backups 확인)
- [ ] 도메인/SSL 만료일 (90일 전 자동 갱신 가정)

---

## 7. 비상 연락 / 권한

- **GitHub repo admin**: TBD
- **Railway 결제/admin**: TBD
- **Vercel 결제/admin**: TBD
- **Cloudflare account**: TBD
- **SOL-API 결제/admin**: TBD
- **Sentry 워크스페이스 admin**: TBD
- **도메인 등록기관 (KISA/가비아 등)**: TBD

---

## 8. 환경 변수 일괄 점검

`.env.production.example` 의 모든 키가 Railway 에 등록되어 있어야 함. 누락 시 `docker-compose.production.yml` 의 `?set` 검증 또는 `app.core.config.Settings.model_post_init` 가 부팅을 막음.

빠른 점검:
```bash
# Railway CLI 로
railway variables --service api
```

---

## 9. 자주 발생하는 문제

| 증상 | 가장 흔한 원인 | 1차 조치 |
|---|---|---|
| 어드민 로그인 후 즉시 로그아웃 | `SECRET_KEY` 변경됨 | 사용자에게 재로그인 안내 |
| 협력사 사진 업로드 500 | R2 키 만료/CORS 설정 | R2 콘솔에서 토큰/CORS 확인 |
| 알림톡 발송 실패 spike | 카카오 템플릿 비활성 또는 SOL 잔액 부족 | SOL-API 콘솔 첫 페이지 확인 |
| 상태는 변경됐지만 자동 알림 로그가 없음 | 복구 스케줄러 비활성/중단 | `AUTOMATION_NOTIFICATION_RECOVERY_ENABLED=true` 및 scheduler 완료 로그 확인 |
| webhook 401 | `SOLAPI_WEBHOOK_SECRET` 불일치 또는 `X-Solapi-Secret` 헤더 누락 | 콘솔에는 원문 secret, 요청 헤더에는 그 SHA1 해시가 들어오는지 확인 |
| `/api/health/ready` 503 | DB 연결 또는 S3 설정 누락 | Railway 환경변수 점검 |

자동 발송 복구 설정:

- `AUTOMATION_NOTIFICATION_RECOVERY_ENABLED=true`
- `AUTOMATION_NOTIFICATION_RECOVERY_INTERVAL_SECONDS=60` (최소 10초)
- `MESSAGE_PENDING_RETRY_AFTER_MINUTES=15`

복구 대상은 협력사 배정, 협력사 작업확인 후 예약확정, 관리자 승인 후 AS 양측 안내, 작업완료 후 잔금 안내다. 각 업무 이벤트와 현재 수신 협력사 epoch 이후의 성공 로그를 기준으로 멱등 처리하므로 정상 발송분은 중복 전송하지 않는다. SOLAPI PENDING은 API 결과 저장 전 프로세스 중단까지 포함해 이미 수락됐을 가능성이 있으므로, 유예시간 뒤 `solapi_outcome_unknown`으로 표시하고 같은 epoch에서 자동·수동 재발송하지 않는다. 운영자는 SOLAPI 콘솔에서 수신번호·요청시각을 대조한 뒤 관리자 **발송 이력**에서 실제 발송이면 **[발송 확인]**, 실제 미발송이면 **[미발송 확인]**을 누른다. 미발송 확인으로 실패 확정된 건만 재발송할 수 있다. 일정 재확인·새 AS·새 작업완료처럼 새 업무 epoch가 시작되면 이전 불명 결과는 새 발송을 차단하지 않는다.

운영 Docker 이미지는 고객 인증 토큰이 URL access log에 남지 않도록 uvicorn access log를 비활성화한다. 애플리케이션 오류 로그와 Sentry에도 고객 URL·토큰을 별도 필드로 기록하지 않는다.

`0029_orders_as_intake_pending`는 운영 PostgreSQL의 `0028_orders_active_as_request_id` 다음에서 구형 path/query 링크에 사용된 기존 고객 토큰을 전부 회전한다. 이 배포는 일반 rolling deploy로 실행하지 않는다. 기존 앱 인스턴스를 모두 내려 주문 쓰기를 중단하고, PostgreSQL에 온라인 마이그레이션을 적용한 뒤 새 버전만 기동한다. 마이그레이션은 `order_groups`와 `orders`를 잠그고 토큰을 함께 교체하며, `ct2_` 형식 제약으로 구 버전 인스턴스의 재유입을 차단한다.

현재 고객사 운영 DB가 로컬 SQLite이면 운영 파일을 테스트 명령의 `DATABASE_URL`로 사용하지 않는다. 앱을 완전히 중지하고 별도 백업을 만든 뒤, 백업 복제본에서 현재 버전부터 `head`까지 먼저 검증한다. 현재 확인된 운영 스키마 `0009_address_detail_and_soft_delete`부터의 경로는 데이터 없는 동일 스키마로 검증했고, 신규 SQLite 전체 경로는 CI에서도 매번 검증한다. 실제 운영 파일 마이그레이션과 고객 링크 재발송은 별도 점검 시간에만 실행한다.

기존 `작업예정` 계열 주문에 현재 협력사의 `partner_confirmed` 이벤트가 없으면 새 버전은 전날안내와 작업시작을 차단한다. 상태를 일괄 변경하거나 확인 이벤트를 위조하지 않고, 협력사 화면에 **작업 일정 확인**을 다시 노출한다. 협력사가 직접 확인한 뒤에만 이후 안내와 작업이 진행된다.

기동 전 아래 검증 결과가 모두 `0`인지 확인한다.

```sql
SELECT count(*) FROM order_groups WHERE substr(customer_token, 1, 4) <> 'ct2_';
SELECT count(*)
FROM orders o
LEFT JOIN order_groups g ON g.id = o.group_id
WHERE o.customer_token IS NULL
   OR substr(o.customer_token, 1, 4) <> 'ct2_'
   OR o.customer_token IS DISTINCT FROM g.customer_token;
```

회전 전 링크는 복구하지 않는다. 진행 중 주문뿐 아니라 사진 열람·AS 접수가 가능한 서비스완료 주문도 신규 `/c#token=...` 링크 재발송 대상에 포함한다.

토큰 회전 배포 체크리스트:

1. DB 백업을 생성하고 비삭제 주문 그룹 수와 고객 전화번호 누락 건수를 기록한다.
2. 기존 앱 인스턴스를 0대로 내려 주문 쓰기를 중단한다.
3. `python -m alembic upgrade head`를 별도 작업으로 1회 실행하고 위 두 검증 SQL이 모두 `0`인지 확인한다.
4. 새 앱 버전만 기동한다. 관리자 주문 목록에서 비삭제 주문을 그룹별 한 줄만 선택한다. 같은 그룹의 여러 서비스 라인을 함께 선택하면 같은 고객에게 중복 발송되므로 한 줄만 선택한다.
5. 일괄 작업의 **안내 발송 → 고객 접속 링크 LMS**를 실행한다. 취소 주문은 제외하고, 진행 중 주문과 고객 사진·AS 지원 기간이 남은 서비스완료 주문을 포함한다.
6. 발송 이력에서 `고객 접속 링크`의 성공·실패·결과 확인 중 건수를 대조한다. `solapi_outcome_unknown`은 SOLAPI 콘솔 확인 전 재발송하지 않고 **발송 확인/미발송 확인** 절차로 확정한다.

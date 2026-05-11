# Cleaning Ops 운영 Runbook

## 시스템 구성

| 영역 | 호스트 | URL |
|---|---|---|
| 프론트 | Vercel | `https://app.<도메인>.kr` |
| API | Railway (FastAPI + uvicorn, 단일 서비스) | `https://api.<도메인>.kr` |
| DB | Railway PostgreSQL 16 | `DATABASE_URL` 환경변수에 자동 주입 |
| 사진 스토리지 | Cloudflare R2 (S3 호환) | `https://photos.<도메인>.kr` |
| 메시지 | SOL-API (카카오 알림톡 + SMS 폴백) | webhook: `https://api.<도메인>.kr/api/webhooks/solapi/delivery` |
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
| `SOLAPI_WEBHOOK_SECRET` | webhook 거부 → 발송 결과 갱신 안 됨 | Railway 변경 → SOL-API 콘솔에서도 동일 값 등록 |
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
- [ ] 카카오 알림톡 템플릿 4종 활성 상태
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
| webhook 401 | `SOLAPI_WEBHOOK_SECRET` 불일치 | 양쪽 동일한 값 확인 |
| `/api/health/ready` 503 | DB 연결 또는 S3 설정 누락 | Railway 환경변수 점검 |

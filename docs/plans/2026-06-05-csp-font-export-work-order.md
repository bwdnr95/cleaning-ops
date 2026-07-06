# 작업 지시서 — 폰트 CSP 핫픽스 / Pretendard self-host / 주문 내보내기

- **작성**: CTO
- **수신**: 코드 작업자(Codex)
- **작성일**: 2026-06-05
- **배경**: 운영에서 주문관리 진입 시 콘솔에 CSP 위반 에러
  `Loading the stylesheet 'https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/.../pretendard.min.css' violates ... "style-src 'self' 'unsafe-inline'"` 발생.
  - 원인: Pretendard 웹폰트를 `frontend/src/styles/global.css:2`에서 외부 CDN(jsdelivr) `@import`로 로드하는데, 운영 CSP(`backend/app/core/middleware.py` `_build_csp_value()`)의 `style-src`·`font-src`에 해당 도메인이 없어 차단됨 → 폰트가 시스템 폰트로 폴백 + 콘솔 에러.
  - "내보내기" 버튼과는 **무관**(그 버튼은 현재 `onClick` 없음 = 미구현). Task 3에서 별도 구현.

## 공통 규칙 (위반 시 반려)
- AGENTS.md / CLAUDE.md / `.claude/rules/*` 준수. 역할별 DTO 화이트리스트, soft-delete, timeline 규칙 유지.
- 프론트 Tailwind/shadcn 금지, `global.css` 토큰 + plain CSS, 로딩/에러/빈 상태 3종.
- 검증: 백엔드 `python -m pytest`, 프론트 `npm run typecheck && npm run lint`, 영향 E2E `npm run e2e`(안전 포트 5176/8003).
- **Task별 독립 커밋**(한국어 메시지). 순서: Task 1 → Task 2 → Task 3.
- 모호하면 멈추고 질문.

> ⚠️ **Task 1 ↔ Task 2 관계**: Task 2(self-host)는 CDN 의존을 없애므로 **Task 1에서 추가한 CSP의 jsdelivr 허용을 다시 제거**한다. 즉 Task 1은 "즉시 배포용 핫픽스", Task 2는 "정식 해결(핫픽스 되돌림 포함)". 둘 다 진행한다.

---

## Task 1 — 🟢 CSP 핫픽스: Pretendard CDN 허용 (즉시 배포용)

운영 백엔드 재배포만으로 폰트/콘솔 에러를 즉시 해소한다. (이미 CTO가 검증한 변경 — 그대로 적용)

**수정 1) `backend/app/core/middleware.py` `_build_csp_value()`**
- 상단 소스 집합에 추가:
```python
    # Pretendard 웹폰트(global.css @import)는 jsDelivr CDN에서 stylesheet + woff2 폰트를 로드한다.
    style_sources = {"'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net"}
    font_sources = {"'self'", "data:", "https://cdn.jsdelivr.net"}
```
- `parts` 리스트의 하드코딩된 두 줄을 치환:
```python
        # 변경 전
        "style-src 'self' 'unsafe-inline'",
        "font-src 'self' data:",
        # 변경 후
        f"style-src {' '.join(sorted(style_sources))}",
        f"font-src {' '.join(sorted(font_sources))}",
```
  - `style-src`(stylesheet 로드)·`font-src`(woff2 폰트 파일) **둘 다** 필요(폰트 파일도 jsdelivr에서 받음).

**수정 2) `backend/tests/test_middleware.py`** — 검증 테스트 추가:
```python
def test_csp_allows_pretendard_cdn_for_style_and_font(client):
    response = client.get("/api/health")
    csp = response.headers.get("content-security-policy", "")
    style_directive = next(part for part in csp.split(";") if part.strip().startswith("style-src"))
    font_directive = next(part for part in csp.split(";") if part.strip().startswith("font-src"))
    assert "https://cdn.jsdelivr.net" in style_directive
    assert "https://cdn.jsdelivr.net" in font_directive
```

**수용 기준**: `/api/health` 응답 CSP의 `style-src`·`font-src`에 `https://cdn.jsdelivr.net` 포함. 기존 카카오 도메인 테스트(`test_csp_includes_kakao_postcode_domains`) 통과 유지. `python -m pytest tests/test_middleware.py` 통과.
**커밋**: `폰트 CDN 로드 허용하도록 CSP 보정`
**배포 주의**: CSP는 백엔드가 내려주므로 **백엔드 재배포** 해야 반영됨(프론트 빌드만으론 안 됨).

---

## Task 2 — 🟡 Pretendard self-host (정식 해결, Task 1의 CDN 허용 제거)

외부 CDN 의존(가용성·프라이버시·CSP allowlist)을 없앤다. 폰트를 번들에 포함해 `'self'`로 서빙.

**구현**
1. 의존성 추가: `cd frontend && npm i pretendard` (woff2 + CSS 포함 패키지).
2. `frontend/src/styles/global.css:2`의 외부 `@import`
   `@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css');`
   를 **로컬 import로 교체**.
   - 권장: `global.css`의 `@import`를 제거하고 `frontend/src/main.tsx`(엔트리)에서 `import 'pretendard/dist/web/static/pretendard.css';` 추가 → Vite가 woff2를 `dist/assets`로 emit하여 `'self'`에서 서빙.
   - (CSS `@import`로 로컬 패키지 경로를 쓰는 방식도 가능하나, Vite 자산 처리상 엔트리 import가 안전.)
   - `--font: 'Pretendard', ...`(global.css:81) 변수는 그대로 둔다.
3. **Task 1에서 추가한 CSP의 jsdelivr 허용 되돌리기**: `_build_csp_value()`의 `style_sources`/`font_sources`에서 `https://cdn.jsdelivr.net` 제거(원래 `style-src 'self' 'unsafe-inline'`, `font-src 'self' data:`로 복귀). Task 1에서 추가한 `test_csp_allows_pretendard_cdn_for_style_and_font` 테스트도 제거 또는 "jsdelivr 미포함" 검증으로 반전.
4. 빌드 후 네트워크 확인: 운영 빌드 실행 시 **jsdelivr로 나가는 요청이 없어야** 함(전부 `'self'` 자산).

**수용 기준**: 외부 폰트 요청 0건, 콘솔 CSP 에러 없음, Pretendard 정상 적용. `npm run build` 성공, typecheck/lint 통과, 백엔드 미들웨어 테스트(jsdelivr 미포함 상태) 통과.
**커밋**: `Pretendard 폰트 self-host 전환 및 CSP CDN 허용 제거`

> 참고: Task 1·2를 **연속으로** 진행해 즉시 배포가 필요 없다면, Task 1을 건너뛰고 Task 2만 해도 폰트 문제는 해결된다. 단 본 지시서는 "즉시 핫픽스 + 정식 해결" 2단계를 기본으로 한다.

---

## Task 3 — 🟡 주문관리 "내보내기"(엑셀 다운로드) 구현 (확정 지시서 #7)

현재 `frontend/src/features/admin/orders/OrdersPage.tsx:528` 내보내기 버튼은 `onClick`이 없어 무동작. **관리자 전용 / 전 항목 포함 / 화면 필터 그대로 반영**으로 구현(도급사 회신: "관리자만 사용 → 최대한 많은 정보 포함").

### 설계 (필터 동기화 문제 회피)
주문관리의 필터·정렬(탭/방문일/접수일/협력사/검색/정렬)은 **전부 프론트의 `filtered` 배열에서 클라이언트 사이드로 계산**됨(`OrdersPage.tsx`). 서버에서 동일 필터를 재구현하면 이중 관리 위험 → **화면에 보이는 `filtered`의 주문 ID 목록을 서버로 보내고, 서버는 그 주문들의 전체 정보를 xlsx로 생성**하는 방식 권장.

1. **백엔드 신규 엔드포인트** — `POST /api/admin/orders/export` (`require_admin`)
   - 요청 바디: `{ "order_ids": [...] }` (현재 화면 `filtered` 순서 유지).
   - 응답: `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` (xlsx 바이트), `Content-Disposition: attachment; filename=...`.
   - 생성: 기존 `backend/app/services/exporters.py`의 `to_xlsx_bytes` 재사용(보고서 export 패턴 `api/routes/admin/reports.py` 참고).
   - **포함 컬럼(관리자 전용, 가능한 전부)**: 접수일·방문예정일·요청시간·고객명·연락처·주소·상품·수량·소비자가·할인·계약금·잔금·현장추가·결제상태·도급가·**이윤(소비자가−도급가)**·협력사·협력사 정산상태·메모/특이사항·표시상태·취소여부. (실제 가용 필드는 `Order` 모델 / `to_admin_order_dto` 기준으로 Codex가 확정. 없는 필드는 빈칸.)
   - soft-deleted 제외. 빈 `order_ids`면 헤더만 있는 빈 시트 또는 400 — 안전 처리.
   - 수량은 #12 `formatQuantity` 규칙과 동일하게 `.0` 제거된 형태로(서버 포맷터 또는 동일 규칙) 출력.

2. **프론트** — `OrdersPage.tsx`
   - `api/admin.ts`에 `exportAdminOrders(orderIds: string[]): Promise<Blob>` 추가(`apiRequest` 사용, blob 응답 처리).
   - 내보내기 버튼 `onClick` → 현재 `filtered`의 `id` 배열로 호출 → 받은 blob을 `URL.createObjectURL` + 임시 `<a download>`로 저장. 파일명 예: `주문내보내기_YYYYMMDD.xlsx`(KST `getAppTodayValue()` 기반).
   - 다운로드 중 버튼 비활성/로딩 표시, 실패 시 에러 토스트(목 데이터 폴백 같은 silent 처리 금지).
   - `data-testid="admin-orders-export"` 부여(E2E).

**수용 기준**: 버튼 클릭 시 **현재 화면 필터/정렬 그대로** 반영된 xlsx 다운로드(보이는 행 = 파일 행), 관리자 권한 가드, 도급가·이윤·메모·연락처 포함(관리자 전용이라 허용), 빈 결과·실패 안전 처리. 백엔드 export 테스트 + 프론트 typecheck/lint 통과, 관련 E2E 통과.
**커밋**: `주문관리 엑셀 내보내기 구현`

---

## 작업 순서 / 검증 요약
1. Task 1(CSP 핫픽스) → 백엔드 테스트 → 커밋.
2. Task 2(self-host) → build + 네트워크 확인 → CSP 되돌림 → 커밋.
3. Task 3(내보내기) → 백엔드+프론트 → pytest/typecheck/lint/e2e → 커밋.
- 미추적 `backend/test_storage/photos/*` 및 `docs/plans/*.md`는 커밋에 포함하지 말 것.
- 본 지시서 범위 외(상태 enum/가격정책/마이그레이션 등 M2~M4)는 손대지 말 것.

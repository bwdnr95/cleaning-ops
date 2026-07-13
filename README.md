# Handoff: Cleaning Ops Control Center

> Archive note: the standalone design prototype files now live in
> `.master/design_handoff_prototype/`. Production implementation lives in
> `backend/` and `frontend/`.

청소업체용 통합 운영 관리 시스템 — 주문 접수, 협력사 배정, 일정관리, 사진 검수, 고객 안내, 결제 확인을 통합한 B2B SaaS.

---

## About the Design Files

이 폴더의 HTML/JSX 파일들은 **디자인 레퍼런스**입니다. 의도한 룩앤필과 인터랙션을 보여주기 위해 HTML 프로토타입으로 만든 것이며, **그대로 production에 복사하기 위한 코드가 아닙니다**.

작업할 일은 이 디자인을 **타깃 코드베이스의 환경(React + 라이브러리, Vue, Next.js 등)에 맞게 재구현**하는 것입니다. 코드베이스에 이미 디자인 시스템이 있다면 그 패턴/컴포넌트를 사용해서 같은 비주얼·동작을 만드세요. 환경이 아직 없다면 React + Tailwind 또는 React + CSS Modules 조합을 권장합니다.

프로토타입은 React 18 (Babel standalone)으로 작성되어 있어 — 빌드 시스템 없이 바로 브라우저에서 열어 확인 가능합니다. `.master/design_handoff_prototype/Cleaning Ops Control Center.html` 을 브라우저로 여세요.

## Fidelity

**High-fidelity (hifi).** 컬러, 타이포그래피, 스페이싱, 인터랙션이 모두 확정되어 있습니다. 구현 시 디자인 토큰(아래 명시)을 그대로 사용하고, 컴포넌트 위계와 spacing scale을 픽셀 단위로 맞춰주세요.

---

## 사용자 역할 (3종)

| 역할     | 디바이스 | 설명 |
|---------|---------|---|
| **관리자** | 데스크톱 (1440×900) | 청소업체 내부 직원. 주문/일정/협력사/사진/결제 통합 관리 |
| **협력사** | 모바일 (360×720) | 외부 청소 파트너. 배정된 작업 확인·사진 업로드·완료 처리 |
| **고객** | 모바일 (360×720) | 회원가입 없이 SMS 링크로 접속. 예약 확인 + 작업 사진 확인 |

---

## Screens / Views

### 1. 관리자 — 대시보드 (`page-dashboard.jsx`)

- **목적**: 운영 컨트롤타워. 오늘 처리할 업무를 놓치지 않게 한다.
- **레이아웃**: Top KPI 카드(7개) → 업무 큐(6개 카드) → 오늘/내일 작업 리스트(2열) → 최근 사진 + 발송 이력(2열)
- **KPI 카드**: 오늘 작업 예정 / 내일 안내 대상 / 협력사 확인 중 / 사진 검수 대기 / 고객 전달 필요 / 결제 확인 필요 / 이번 달 완료 / 이번 달 매출
- **업무 큐**: 클릭 시 해당 필터가 적용된 주문 리스트로 이동
- **간격**: KPI 12px gap, 큐 카드 10px gap, 섹션 간 16px

### 2. 관리자 — 주문관리 리스트 (`page-orders.jsx`)

- **목적**: 엑셀을 대체하는 운영 핵심 화면. 모든 주문 상태와 작업 흐름이 한눈에.
- **레이아웃** (위→아래):
  1. **인사이트 라인** (24px padding) — 오늘 작업/미배정/검수 대기/고객 전달/미수금/이번 달 매출. 카드 X, 타이포로만. 사이에 1px×14px divider
  2. **검색 + 필터 바** — 검색(⌘K) + 기간/협력사/결제 칩 + 필터 추가 + 정렬 토글
  3. **상태 탭** (8개) — `전체 / 오늘 작업 / 확인 대기 / 작업·검수 / 고객 전달 / 완료 / 취소`. 액티브: 텍스트 컬러 + bottom underline 2px
  4. **선택 바** (조건부) — 행 선택 시 등장. "N건 선택 · 상태 변경 · 메시지 · 협력사 배정 · 해제"
  5. **테이블** — 14컬럼, 행 높이 44px, 호버 시 surface 배경 + 1px shadow로 떠보이는 인터랙션 (`.table-modern`)
  6. **푸터** — 페이지네이션 (50건/페이지)
- **테이블 컬럼**: 체크박스 / 상태(도트) / 주문번호 / 방문일+시간 / 상품 / 주소 / 고객 / 연락처 / 담당팀 / 금액 / 결제 / 사진 / 고객전달 / 액션
- **상태 표시**: 텍스트 + 7px 도트 + 도트 주변 12% opacity halo (`StatusDot` 컴포넌트)
- **결제/사진/고객전달**: 5px 도트 + 텍스트 (`PaidPill`, `SimplePill`)
- **취소 행**: opacity 0.5, 호버 시 0.8
- **호버 시**: 우측 액션 버튼(메시지/사진/더보기) 노출 — 평소엔 더보기만 40% opacity로

### 3. 관리자 — 일정 캘린더 (`page-calendar.jsx`)

- **목적**: 월간 작업 일정을 현장(지점)별로 시각적으로 확인.
- **레이아웃**: 좌측 사이트 패널(200px, 11개 지점) + 메인 캘린더
- **툴바**: 오늘 / ‹ › / "2026년 5월" / 범례(대기·진행·완료·작업중) / 월·주·일 토글 / 일정 추가
- **캘린더 셀** (110px min): 날짜 (오늘은 인디고 동그라미) + 이벤트 리스트. 이벤트는 좌측 컬러바 + 시간대 + 작업명. 4건 이상이면 "+ N건 더보기"
- **요일 헤더**: 일=red, 토=blue, 평일=tertiary

### 4. 관리자 — 주문 상세 (`page-order-detail.jsx`)

- **목적**: 한 주문의 전체 정보 + 모든 액션을 한 화면에.
- **레이아웃**: 메인 본문 (섹션형 카드) + 우측 사이드 패널 (320px)
- **본문 섹션**: 기본 상태 → 고객 정보 → 상품 정보 → 금액 정보 → 협력사 정보 → 사진 영역
- **사이드 패널**: 현재 상태 / 주요 액션 버튼 (상태 변경, 협력사 배정, 일정 안내 발송, 사진 승인, 완료 링크 발송) / 고객 링크 / 타임라인

### 5. 관리자 — 사진검수 (`page-photo-review.jsx`)

- **목적**: 협력사 업로드 사진을 관리자가 승인 후 고객에게 노출.
- **레이아웃**: 좌(검수 큐 리스트) + 중앙(비포·애프터 좌우 비교) + 우(승인 플로우)
- **원칙**: 협력사가 올린 사진은 즉시 고객에게 보이지 않는다. 관리자 승인 후에만 노출.
- **액션**: 사진별 승인/보류/반려, 협력사 메모 확인, 고객 공개 승인, 완료 링크 발송

### 6. 협력사 — 작업 상세 (`page-partner.jsx`)

- **목적**: 모바일 현장에서 10초 안에 정보 확인 + 사진 업로드 가능.
- **레이아웃**: iPhone 360×720 프레임. 카드형 정보 → 비포 사진 그리드 → 애프터 사진 그리드 → 작업 메모 → CTA
- **표시**: 서비스명, 방문일+시간, 주소, 평수, 특별요청, 고객명, 연락처, 관리자 메모 (협력사 공개분만)
- **비노출**: 총계약금액, 계약금/잔금, 부가세, 입금정보, 유입경로, 다른 협력사 정보
- **사진 업로드**: 비포/애프터/기타 구분, 다중 업로드, 진행률 표시, 미리보기, 삭제 가능
- **하단 CTA**: "지도 열기 / 전화하기 / 사진 업로드 / 작업 완료"

### 7. 고객 — 예약 확인 (`page-customer.jsx`)

- **목적**: SMS 링크 접속 → 인증 → 예약 정보 + 완료 사진 확인. "체계적으로 운영되는 업체"라는 신뢰감.
- **인증**: 연락처 뒷자리 4자리 입력
- **예약 페이지**: 업체 로고 → 예약 상태 배지 → 고객명 → 문의 전화 → 서비스/방문일/시간/주소/요청사항/결제 안내/방문 전 안내사항
- **사진 페이지**:
  - 작업 완료 전: "작업 완료 후 비포/애프터 사진이 이곳에 표시됩니다" 플레이스홀더
  - 작업 완료 후: 비포 / 애프터 / 기타 갤러리 (관리자 승인분만)

---

## Interactions & Behavior

### 글로벌
- **다크 모드** 지원 — `<html data-theme="dark">` 토글. 모든 화면 자동 대응.
- **사이드바 토글** — 관리자 좌측 nav 접고 펴기.
- **검색 단축키** — `⌘K` (UI에 표시만, 로직은 미구현 상태)

### 주문 리스트
- **체크박스**: 헤더 체크 시 전체 선택. 행 체크 시 선택 바 등장.
- **행 클릭**: 주문 상세로 이동 (체크박스 영역 클릭은 stopPropagation).
- **호버 인터랙션**: 행 배경 = `var(--surface)`, `box-shadow: 0 1px 0 var(--border), 0 -1px 0 var(--border)`, `transition: 100ms`. 호버 시 우측 액션 버튼이 나타남.
- **취소 상태**: opacity 0.5 → 0.8 (호버).
- **탭 전환**: 클라이언트 사이드 필터링.

### 상태 변경
- 13개 상태 (아래 [상태값 일람] 참조). 상태 변경은 사이드 패널의 드롭다운에서.
- 상태에 따라 노출 액션이 달라짐 (예: `사진검수대기` → 사진 승인 버튼 활성화).

### 사진 업로드 (협력사)
- 다중 선택, 업로드 진행률 표시, 업로드 후 미리보기, 삭제 가능.

### 트랜지션
- 모든 호버/액티브 상태 80~100ms ease.
- 라우팅 전환은 instant (스피너 X).

---

## State Management

각 페이지에 필요한 state:

### `OrdersPage`
- `tab: string` — 활성 탭 (`'all' | 'today' | ...`)
- `selected: Set<string>` — 선택된 주문 ID
- `hoverRow: string | null` — 호버 중인 행
- `sortBy: 'visit' | 'received'` — 정렬 키

### `OrderDetailPage`
- `activeAction: string | null` — 열린 액션 모달 (메시지 발송 등)
- `timeline: Event[]` — 변경 이력

### `PhotoReviewPage`
- `currentJobId: string` — 검수 중인 주문
- `approvedPhotos: Set<string>` — 승인된 사진 ID

### `CalendarPage`
- `view: 'month' | 'week' | 'day'`
- `selectedSite: string` — 선택된 지점 ID
- `currentMonth: Date`

### `PartnerJobDetail`
- `photosBefore / photosAfter / photosEtc: File[]`
- `uploadProgress: Map<id, percent>`
- `memo: string`

### `CustomerReservation`
- `authenticated: boolean`
- `phoneSuffix: string` — 입력값

### 데이터 fetching
- 현재 프로토타입은 `data.jsx`의 mock 사용. 실제 구현 시 `/api/orders`, `/api/orders/:id`, `/api/orders/:id/photos`, `/api/calendar?month=YYYY-MM` 등 REST 또는 GraphQL로 교체.
- 주문 리스트는 서버 사이드 페이지네이션 권장 (50건/페이지).

---

## Design Tokens

전체는 `.master/design_handoff_prototype/styles.css` 의 `:root` 와 `[data-theme="dark"]` 참고.

### Colors (Light)

| Token | Hex | 용도 |
|---|---|---|
| `--bg` | `#fafbfc` | 페이지 배경 |
| `--bg-subtle` | `#f4f6f8` | 카드 사이 배경 |
| `--bg-muted` | `#eef1f4` | hover, 카운트 칩 |
| `--surface` | `#ffffff` | 카드, 테이블 |
| `--border` | `#e4e8ee` | 일반 보더 |
| `--border-strong` | `#d4d9e1` | 강조 보더 |
| `--divider` | `#eef1f4` | 인라인 디바이더 |
| `--text` | `#0f172a` | 본문 |
| `--text-secondary` | `#475569` | 보조 |
| `--text-tertiary` | `#64748b` | 메타 |
| `--text-quaternary` | `#94a3b8` | placeholder |
| `--brand` | `#4f46e5` (indigo-600) | 메인 브랜드 |
| `--brand-bg` | `#eef2ff` | 브랜드 배경 |
| `--info-fg` / `--info-bg` | `#1d4ed8` / `#eff6ff` | 진행 |
| `--warn-fg` / `--warn-bg` | `#b45309` / `#fffbeb` | 대기 |
| `--success-fg` / `--success-bg` | `#047857` / `#ecfdf5` | 완료 |
| `--danger-fg` / `--danger-bg` | `#b91c1c` / `#fef2f2` | 문제 |
| `--purple-fg` / `--purple-bg` | `#6d28d9` / `#f5f3ff` | 상담 |

### Spacing (8pt grid 기반)
- `4 / 6 / 8 / 10 / 12 / 14 / 16 / 20 / 24 / 32 / 48` (px)

### Border radius
- `--radius-sm: 4px` — 칩, 작은 요소
- `--radius: 6px` — 인풋, 버튼
- `--radius-md: 8px` — 카드, 모던 테이블 행
- `--radius-lg: 12px` — 큰 카드, 모달

### Typography
- **Font**: Pretendard (한글), system fallback
- **Mono**: ui-monospace, SF Mono — 주문번호, 연락처
- **Scale**:
  - `10.5px / 11px / 11.5px` — 메타, 라벨
  - `12px / 12.5px` — 본문, 테이블
  - `13px` — 카드 헤더
  - `14px / 15px` — 섹션 타이틀
  - `18px` — 인사이트 숫자
  - `20px / 22px` — KPI 큰 숫자
  - `24px+` — 페이지 타이틀
- **Weight**: 400 (regular), 500 (medium), 600 (semibold), 700 (bold)
- **Letter-spacing**: 큰 숫자에 `-0.02em` 적용

### Shadow
- `--shadow-xs: 0 1px 2px rgba(15,23,42,0.04)` — 인풋
- `--shadow-sm: 0 1px 2px rgba(15,23,42,0.06), 0 1px 3px rgba(15,23,42,0.04)` — 카드
- `--shadow-md: 0 4px 12px rgba(15,23,42,0.06), 0 1px 3px rgba(15,23,42,0.04)` — popover
- `--shadow-lg: 0 12px 32px rgba(15,23,42,0.08), 0 2px 6px rgba(15,23,42,0.04)` — 모달

### Density (Compact 어드민)
- `--row-h: 38px` (기본 테이블), 44px (모던 테이블)
- `--header-h: 36px`

---

## 상태값 일람 (13종)

순서는 운영 흐름 순:

| 상태 | 톤 | 도트 컬러 | 의미 |
|---|---|---|---|
| 신규접수 | neutral | `#94a3b8` | 주문이 막 들어옴 |
| 상담중 | purple | `#8b5cf6` | 견적 협의 중 |
| 협력사확인중 | warn | `#f59e0b` | 협력사 가용성 확인 |
| 일정확정 | info | `#3b82f6` | 방문일 확정 |
| 전날안내필요 | warn | `#f59e0b` | 전날 안내 발송 대기 |
| 전날안내완료 | info | `#3b82f6` | 전날 안내 완료 |
| 작업예정 | info | `#3b82f6` | 당일 작업 예정 |
| 작업진행 | brand | `#4f46e5` | 현장 작업 중 |
| 사진검수대기 | warn | `#f59e0b` | 협력사 사진 업로드 완료, 관리자 검수 대기 |
| 고객전달필요 | warn | `#f59e0b` | 검수 완료, 고객 전달 대기 |
| 고객전달완료 | success | `#10b981` | 고객에게 사진 전달됨 |
| 서비스완료 | success | `#10b981` | 결제까지 완료 |
| 취소 | neutral muted | `#cbd5e1` | 주문 취소 |

매핑은 `components.jsx` 의 `STATUS_MAP` 과 `page-orders.jsx` 의 `STATUS_DOT` 참조.

### 결제 상태 (4종)
- `paid` 완납 (success)
- `partial` 계약금 (info)
- `pending` 대기 / 미수 (작업 진행됐는데 미결제면 미수=danger, 그 외 대기=neutral)
- `refund` 환불 (danger)

### 사진 상태 (4종)
- `none` (없음 — `—` 표시)
- `partial` 진행 (info)
- `wait` 검수 (warn)
- `approved` 승인 (success)

### 고객전달 상태 (3종)
- `pending` 대기
- `done` 전달 (success)
- `cancelled` (`—`)

---

## Components 인벤토리

`components.jsx` — 공통:
- `StatusBadge` — 13종 상태 배지 (배경+테두리 형태)
- `Badge` — 범용 배지 (tone: brand/info/success/warn/danger/purple/neutral)
- `Icon` — 30개 stroke 아이콘 (24×24 viewBox, stroke-width 1.6)
- `Avatar` — 이니셜 아바타 (tone 컬러)
- `Sparkline` — 인라인 미니 차트

`page-orders.jsx` — 주문 리스트 전용:
- `StatusDot` — 모던 스타일 7px 도트 + 텍스트
- `PaidPill / SimplePill` — 결제·사진·전달 상태 5px 도트 칩
- `Insight / InsightDivider` — 상단 타이포 인사이트
- `SoftChip` — 호버 시에만 배경 나오는 필터 칩

`admin-shell.jsx`:
- `AdminShell` — 좌측 nav + topbar + main 구조
- `Topbar` — 페이지 타이틀 + 브레드크럼 + 액션
- `NAV` 정의 (대시보드 / 주문관리 / 일정 캘린더 / 사진검수 / 상품관리 / 협력사관리 / 발송이력)

---

## Files

| 파일 | 역할 |
|---|---|
| `.master/design_handoff_prototype/Cleaning Ops Control Center.html` | 엔트리 — design canvas로 모든 화면 진열 |
| `.master/design_handoff_prototype/styles.css` | 디자인 토큰 + 공통 CSS (버튼, 테이블, 인풋, 카드) |
| `.master/design_handoff_prototype/components.jsx` | 공통 컴포넌트 (Icon, Badge, StatusBadge, Avatar, Sparkline) |
| `.master/design_handoff_prototype/data.jsx` | Mock 데이터 (ORDERS, KPI, QUEUES, TODAY_JOBS 등) |
| `.master/design_handoff_prototype/admin-shell.jsx` | 관리자 사이드바 + topbar |
| `.master/design_handoff_prototype/page-dashboard.jsx` | 관리자 대시보드 |
| `.master/design_handoff_prototype/page-orders.jsx` | 관리자 주문 리스트 (모던 톤) |
| `.master/design_handoff_prototype/page-calendar.jsx` | 관리자 일정 캘린더 |
| `.master/design_handoff_prototype/page-order-detail.jsx` | 관리자 주문 상세 |
| `.master/design_handoff_prototype/page-photo-review.jsx` | 관리자 사진 검수 |
| `.master/design_handoff_prototype/page-partner.jsx` | 협력사 모바일 작업 상세 |
| `.master/design_handoff_prototype/page-customer.jsx` | 고객 모바일 예약 확인 |
| `.master/design_handoff_prototype/design-canvas.jsx` | 디자인 캔버스 (개발 환경에서는 사용 안 함) |
| `.master/design_handoff_prototype/tweaks-panel.jsx` | 라이트/다크 토글 (개발 환경에서는 사용 안 함) |

---

## 구현 권장사항

1. **프레임워크**: React 18 + TypeScript 권장. Next.js (App Router) 또는 Vite + React Router.
2. **스타일링**:
   - **선호**: CSS Modules 또는 vanilla-extract — `.master/design_handoff_prototype/styles.css` 의 토큰을 그대로 옮기기 쉬움
   - **대안**: Tailwind — `tailwind.config` 의 `theme.extend.colors` 에 디자인 토큰 매핑
   - 인라인 스타일은 프로토타입 편의용. production 에서는 className 기반으로 분리.
3. **컴포넌트 라이브러리**: Headless UI (Radix UI) 권장 — 드롭다운, 체크박스, 탭 등의 접근성 처리.
4. **아이콘**: 현재 30개 inline SVG. 그대로 유지하거나 Lucide / Heroicons 로 1:1 매핑 가능.
5. **데이터**:
   - REST: `/api/orders?status=xxx&page=1` / `/api/orders/:id` / `/api/orders/:id/photos`
   - 캐싱: TanStack Query 권장
   - 사진 업로드: presigned URL 패턴 (S3 등)
6. **인증**:
   - 관리자/협력사: 세션 기반
   - 고객: SMS 링크 토큰 + 연락처 4자리 검증 (OTP 형식)
7. **라우팅**:
   - `/admin/dashboard` `/admin/orders` `/admin/orders/:id` `/admin/calendar` `/admin/photos` ...
   - `/partner/jobs` `/partner/jobs/:id`
   - `/c#token=<고객토큰>` (고객 — fragment는 서버 access log에 전달되지 않음, 인증 API는 `X-Customer-Token` 헤더 사용)
8. **반응형**: 관리자 화면은 1280px 이상 데스크톱 우선. 모바일(협력사·고객)은 360~414px 우선.
9. **다크 모드**: `<html data-theme>` 패턴 그대로 사용 가능. 시스템 prefers-color-scheme 추종 + 사용자 토글.

---

## 빠르게 보려면

```bash
# 로컬 서버 띄우기 (Python 예)
cd design_handoff_cleaning_ops
python3 -m http.server 8000
# → http://localhost:8000/Cleaning%20Ops%20Control%20Center.html
```

브라우저에서 6개 화면이 design canvas에 진열됩니다. 카드 더블클릭 시 풀스크린 포커스 모드. 우상단 툴바에서 라이트/다크 토글.

---

## Open Questions

작업 시작 전 PM/디자이너에게 확인 필요한 사항:

1. **알림톡/SMS 연동** — 어떤 채널 사용? (네이버 알림톡, 카카오 비즈메시지, NHN Toast 등)
2. **사진 저장소** — S3? CloudFront 캐싱 필요?
3. **결제 연동** — 자동 확인이 가능한 PG가 있는지, 아니면 수동 확인만?
4. **협력사 앱** — 현재 모바일 웹으로 설계되어 있음. PWA 또는 네이티브 앱 필요한지?
5. **권한 체계** — 관리자 내부에서도 역할 분리 필요한지 (담당자/관리자/대표)?
6. **다국어** — 한국어 only 인지 영어 지원 필요한지?

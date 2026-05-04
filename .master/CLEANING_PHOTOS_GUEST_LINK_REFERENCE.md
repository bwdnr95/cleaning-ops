# 청소관리 시스템 — 게스트 사진 페이지 링크/인증 패턴 참조

> 목적: 청소가 완료된 후 고객에게 "현장 사진 확인 페이지" 링크를 발송하는 기능을 만들기 위한 **TONO 본 저장소의 기존 패턴 정리**.
> 청소관리 시스템(별도 저장소)에서 codex가 구현할 때 그대로 참고/이식할 수 있도록 파일·함수 단위로 위치를 명시.
>
> 본 저장소에서 가장 가까운 참고 도메인:
> - **TONO Chat** (`tono_chat.*`): 게스트 라우트 + 세션-수명 토큰(`room_token`) + 단계적 권한(access_level) — 사진 페이지에 가장 가깝다.
> - **TTLock 게스트 페이지** (`/guest/*`): JWT 기반 일회용 세션 + 화이트리스트 DTO — 짧은 수명/만료/revoke 패턴 참고.
> - **CheckinAnnouncementService**: 메시지 빌드 + SMS/카톡 발송 + 링크 변수 + 멱등 발송 로그.
>
> ⚠️ **CLAUDE.md TOP 5 적용**: 모든 쿼리에 `organization_id` 필터, group_code도 같이 체크, 한국어 제네릭 에러 메시지, .env는 루트에만, 마이그레이션은 `alembic upgrade head` 즉시 실행.

---

## 0. 도메인 매핑 (TONO Chat ↔ 청소 사진)

| 개념 | TONO Chat | 청소 사진 페이지 권장 |
|---|---|---|
| 식별자 | `room_token` (URL-safe 22자, 128bit) | `view_token` (동일 패턴) |
| 컨테이너 모델 | `Conversation` (channel=tono_chat) | `CleaningPhotoView` (또는 기존 `CleaningJob`에 토큰 컬럼 추가) |
| 컨테이너 1차 키 | `Conversation.id` (UUID) | `CleaningJob.id` (또는 신규 view 모델) |
| 게스트 식별 | `guest_name` | `reservation.guest_name` (FK) |
| 만료 | `valid_until` | `valid_until` (체크아웃 + N일 권장) |
| 권한 단계 | `access_level: inquiry / qr_scan / verified` | `access_level: pending / verified` (단순 2단계로 충분) |
| 진입 채널 | `access_channel: ota_link / qr_code / kiosk` | `access_channel: sms / kakao / email` |
| 인증 1단계 | 게스트 이름 매칭 | **전화번호 뒷 4자리 매칭** (권장) |
| 인증 fallback | 예약 코드 | 예약 코드 |
| URL | `app.tonify.co.kr/chat?r=...&p=...` | `app.tonify.co.kr/cleaning-photos?t=<view_token>` |

> 💡 **결정 포인트**: 청소 사진 페이지는 `room_token` 패턴(server-side state) 권장.
> JWT 패턴(GuestSession)은 토큰 자체에 정보가 들어 있어 짧은 수명에 강점이지만, 사진은 체크아웃 후 며칠간 다시 보고 싶어할 가능성이 높아 **DB-backed long-lived token**이 UX에 적합.

---

## 1. 토큰/모델 패턴

### 1-A. Long-lived 토큰 (TONO Chat 패턴, **사진 페이지 권장**)

**모델**: `backend/app/domain/models/conversation.py:62-195` (`Conversation`)

핵심 컬럼만 발췌:

```python
# 식별: 22자 token_urlsafe(16) — 128bit 엔트로피
room_token: Mapped[str | None] = mapped_column(
    String(64), nullable=True, unique=True, index=True
)

# 만료
valid_until: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True), nullable=True
)

# 진입 채널 추적
access_channel: Mapped[str | None] = mapped_column(String(20), nullable=True)
# 'ota_link' | 'qr_code' | 'kiosk'

# 권한 단계 (3-tier; 사진 페이지는 2-tier로 단순화 가능)
access_level: Mapped[str] = mapped_column(
    String(20), nullable=False, default="inquiry", server_default="inquiry"
)
# 'inquiry' | 'qr_scan' | 'verified'

# Multi-tenant 필수
organization_id: Mapped[int] = mapped_column(
    Integer, ForeignKey("organizations.id", ondelete="CASCADE"),
    nullable=False, index=True,
)

# 예약 연결 (선택; 사진은 청소 작업 단위로 연결)
reservation_id: Mapped[int | None] = mapped_column(
    Integer, ForeignKey("reservation_info.id", ondelete="SET NULL"),
    nullable=True, index=True,
)
```

**토큰 생성**: `backend/app/api/v1/tono_chat.py:195-197`

```python
def _generate_room_token() -> str:
    """128비트 엔트로피 안전한 랜덤 토큰 생성"""
    return secrets.token_urlsafe(16)  # 22자, 128비트
```

**유효기간 산정**: `tono_chat.py:411-418`

```python
# 기본 30일 또는 체크아웃+3일
valid_until = utc_now() + timedelta(days=30)
if reservation and reservation.checkout_date:
    valid_until = datetime.combine(
        reservation.checkout_date + timedelta(days=3),
        datetime.min.time(),
        tzinfo=timezone.utc,
    )
```

> 사진 페이지: **체크아웃 + 30일** 권장 (앨범 다시 보기 패턴). DB 컬럼만 늘리면 점진적 변경 가능.

**중복 방지 인덱스 (마이그레이션)**: `backend/alembic/versions/3658e97cb12f_add_tono_chat_room_dedup_indexes.py` 참조 — `(property_code, organization_id, status, valid_until)` 부분 인덱스로 active room 빠른 조회.

---

### 1-B. Short-lived JWT 토큰 (TTLock 패턴, **참고용**)

**모델**: `backend/app/domain/models/guest_session.py:1-71`

```python
class GuestSessionStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"

class GuestSession(Base):
    __tablename__ = "guest_sessions"
    __table_args__ = (
        Index("idx_guest_sessions_token", "token"),
        # partial index: active 세션만
        Index("idx_guest_sessions_active", "status",
              postgresql_where="status = 'active'"),
    )

    organization_id: Mapped[int]
    reservation_id: Mapped[str]
    property_code: Mapped[str]
    token: Mapped[str]  # JWT의 jti (서버 revocation 가능)
    status: Mapped[str]
    expires_at: Mapped[datetime]
    revoked_at: Mapped[Optional[datetime]]
```

**JWT 발급/검증**: `backend/app/core/security.py:177-220`

```python
def create_guest_token(*, session_id, reservation_id, organization_id,
                       expires_at, jti) -> str:
    payload = {
        "type": "guest",  # access 토큰과 분리
        "sub": str(session_id),
        "reservation_id": reservation_id,
        "organization_id": organization_id,
        "jti": jti,  # DB의 token 컬럼과 매칭
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY,
                     algorithm=settings.JWT_ALGORITHM)
```

**서비스**: `backend/app/services/guest_session_service.py:27-68`
- `create_session()`: 같은 reservation에 active 세션 있으면 **REVOKED** 후 새 세션 발급 (재발급 정책).
- `revoke_session()`: 즉시 무효화 (admin 강제).

**의존성 주입**: `backend/app/core/deps.py:565-591`

```python
def get_current_guest_session(
    guest_token: str = Query(..., alias="t"),  # ?t=<JWT>
    db: Session = Depends(get_db),
) -> GuestSession:
    try:
        payload = decode_guest_token(guest_token)
    except Exception:
        raise HTTPException(401, "유효하지 않은 게스트 토큰입니다.")

    jti = payload.get("jti")  # KeyError 방어
    if not jti:
        raise HTTPException(401, "유효하지 않은 게스트 토큰입니다.")

    session = GuestSessionRepository(db).get_by_token(jti)
    if session is None or session.status != GuestSessionStatus.ACTIVE.value:
        raise HTTPException(401, "세션이 활성 상태가 아닙니다.")
    return session
```

> JWT 패턴의 장점: server stateless 확인 가능, payload에 org_id 포함되어 multi-tenant 강제.
> 단점: revoke 위해 결국 DB hit 필요. 만료/재발급 흐름이 복잡.
> **사진 페이지에는 1-A를 권장**.

---

## 2. 백엔드 — 게스트 API 엔드포인트

**원본**: `backend/app/api/v1/tono_chat.py` (전체 ~1467줄, 핵심만 발췌)

### 2-1. 라우터 + 인증 정책

```python
router = APIRouter(prefix="/tono-chat", tags=["tono-chat"])

# 게스트 API: 인증 없음 (room_token 자체가 capability token)
# Host API: get_current_active_user 필요
```

**핵심 원칙**: room_token이 곧 capability — 따로 사용자 인증 안 함. 토큰을 가진 사람이 곧 권한자. 그래서 토큰 길이/엔트로피 + valid_until + access_level이 보안의 핵심.

### 2-2. 방 생성 (또는 재사용) — `tono_chat.py:277-455`

청소 사진은 일반적으로 **청소 작업당 1개 view**가 자연스러우므로 더 단순:

```python
@router.post("/photo-views", response_model=PhotoViewResponse)
@limiter.limit("30/minute")  # IP 기반
def create_or_get_photo_view(
    request: Request,
    body: CreatePhotoViewRequest,  # cleaning_job_id 또는 reservation_code
    db: Session = Depends(get_db),
):
    # 1. cleaning_job 조회 + organization_id 추출 (하드코딩 금지!)
    job = db.execute(
        select(CleaningJob)
        .where(CleaningJob.id == body.cleaning_job_id)
    ).scalar_one_or_none()
    if not job:
        raise HTTPException(404, "요청을 처리할 수 없습니다.")  # 한국어 제네릭

    # 2. 기존 active view 재사용 (멱등)
    existing = db.execute(
        select(CleaningPhotoView)
        .where(CleaningPhotoView.cleaning_job_id == job.id)
        .where(CleaningPhotoView.organization_id == job.organization_id)
        .where(CleaningPhotoView.valid_until > utc_now())
    ).scalar_one_or_none()
    if existing:
        return _to_photo_view_response(existing)

    # 3. 새 토큰 발급
    view = CleaningPhotoView(
        organization_id=job.organization_id,  # ← 직접 가져오기, current_user.organization_id 금지
        cleaning_job_id=job.id,
        view_token=secrets.token_urlsafe(16),
        valid_until=utc_now() + timedelta(days=30),
        access_level="pending",
        access_channel=body.access_channel,
    )
    db.add(view)
    db.commit()
    return _to_photo_view_response(view)
```

> ⚠️ **TONO Admin이 발송 시 주의** — `organization_id`는 청소 작업/예약의 실제 org를 사용. `current_user.organization_id` (보통 3) 사용 금지. CLAUDE.md TOP 5 #6 위반.

### 2-3. 방 조회 + 만료 처리 — `tono_chat.py:200-219, 458-488`

```python
def _get_view_or_410(db: Session, view_token: str) -> CleaningPhotoView:
    view = db.execute(
        select(CleaningPhotoView)
        .where(CleaningPhotoView.view_token == view_token)
    ).scalar_one_or_none()

    if not view:
        raise HTTPException(404, "사진을 찾을 수 없습니다.")

    if view.status == "archived":
        raise HTTPException(410, "종료된 페이지입니다.")  # Gone

    if view.valid_until and view.valid_until < utc_now():
        raise HTTPException(410, "링크가 만료되었습니다.")

    return view
```

**상태 코드 표준화 매우 중요** (프론트가 분기):
- `404`: 토큰 자체가 없음 (오타/위변조)
- `410`: 토큰은 있으나 만료/종료 (Gone) — 프론트는 별도 만료 화면
- `401`: 토큰 유효하지만 인증 단계 미통과
- `403`: 인증은 됐는데 다른 org 리소스
- `429`: rate limit 초과

### 2-4. 게스트 인증 API — `tono_chat.py:819-1013`

TONO Chat은 3단계 인증을 사용 (`이름 자동매칭 → 예약자명 입력 → 예약코드 fallback`).

청소 사진은 **전화번호 뒷 4자리** 권장 (입력 부담 ↓, 정확도 ↑):

```python
class VerifyPhotoViewRequest(BaseModel):
    phone_last4: Optional[str] = Field(None, pattern=r"^\d{4}$")
    reservation_code: Optional[str] = Field(None, max_length=100)

class VerifyPhotoViewResponse(BaseModel):
    success: bool
    access_level: str  # "pending" | "verified"
    step: Optional[str]  # "verified" | "fallback_code"

@router.post("/photo-views/{view_token}/verify",
             response_model=VerifyPhotoViewResponse)
@limiter.limit("10/minute")  # brute-force 방지
def verify_photo_view(
    view_token: str,
    body: VerifyPhotoViewRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    view = _get_view_or_410(db, view_token)
    reservation = db.get(ReservationInfo, view.reservation_id)
    if not reservation or reservation.status == "canceled":
        raise HTTPException(400, "유효하지 않은 예약입니다.")

    if body.phone_last4 and reservation.guest_phone:
        # ⚠️ 정규화 필수 (-, 공백 제거)
        normalized = re.sub(r"\D", "", reservation.guest_phone)
        if normalized.endswith(body.phone_last4):
            view.access_level = "verified"
            db.commit()
            return VerifyPhotoViewResponse(
                success=True, access_level="verified", step="verified"
            )
        # 실패 → fallback 권유
        return VerifyPhotoViewResponse(
            success=False, access_level="pending", step="fallback_code"
        )

    if body.reservation_code:
        if reservation.reservation_code == body.reservation_code:
            view.access_level = "verified"
            db.commit()
            return VerifyPhotoViewResponse(
                success=True, access_level="verified", step="verified"
            )
        raise HTTPException(400, "예약 코드가 일치하지 않습니다.")

    raise HTTPException(400, "전화번호 또는 예약 코드가 필요합니다.")
```

**TONO Chat의 ILIKE 매칭 시 SQL injection 방어 패턴 참고** — `tono_chat.py:858-868`:

```python
# 와일드카드 메타문자 이스케이프 (%, _ 방지)
escaped_name = guest_name.replace("%", "\\%").replace("_", "\\_")
stmt = ...where(ReservationInfo.guest_name.ilike(f"%{escaped_name}%"))
```

### 2-5. 인증 시도 제한 (brute-force 방어)

`tono_chat.py:820`의 `@limiter.limit("10/minute")`는 IP 단위. 청소 사진은 추가로:

- 인증 실패 카운터를 view 모델에 컬럼으로: `failed_verify_count: int = 0`
- 5회 이상 실패 시 view를 일시 잠금 (1시간) → `verification_locked_until`
- 잠금 중에는 401 + "잠시 후 다시 시도해주세요" 반환

이는 TONO Chat에는 없는 패턴이라 신규 구현 필요. 사진은 민감도 더 높음.

---

## 3. 백엔드 — 게스트용 DTO (민감정보 화이트리스트)

### 3-1. 단계별 노출 — `tono_chat.py:635-812` `get_property_info`

핵심 패턴: **access_level에 따라 응답 필드를 동적으로 비움**.

```python
# Level 0 (pending): 기본 스펙만
basic_info = PropertyInfoBasic(...)

# Level 1 (qr_scan): + 가이드
guides = None
if access_level in ("qr_scan", "verified"):
    guides = PropertyInfoGuides(...)

# Level 2 (verified): + 민감정보
if access_level == "verified":
    sensitive = PropertyInfoSensitive(
        locked=False,
        wifi_ssid=...,
        wifi_password=...,
    )
else:
    sensitive = PropertyInfoSensitive(
        locked=True,
        unlock_message="이름 확인 후 Wi-Fi, 상세 주소 등을 확인할 수 있습니다.",
    )
```

청소 사진 적용:

```python
class PhotoViewResponse(BaseModel):
    access_level: str
    property_name: str
    cleaning_completed_at: datetime
    photos: List[PhotoDTO]  # access_level == "verified"일 때만 채움
    locked_message: Optional[str]  # pending일 때 안내문

@router.get("/photo-views/{view_token}", response_model=PhotoViewResponse,
            response_model_exclude_none=True)  # ← null 필드 자동 제거
def get_photo_view(view_token: str, db: Session = Depends(get_db)):
    view = _get_view_or_410(db, view_token)

    photos = []
    locked_msg = None
    if view.access_level == "verified":
        photos = _list_photos(db, view)
    else:
        locked_msg = "예약자 본인 확인 후 사진을 볼 수 있습니다."

    return PhotoViewResponse(
        access_level=view.access_level,
        property_name=view.property_name,
        cleaning_completed_at=view.cleaning_completed_at,
        photos=photos,
        locked_message=locked_msg,
    )
```

### 3-2. allowlist 패턴 — `backend/app/api/v1/guest.py:36-43`

`extra_metadata` 같은 자유 JSON 컬럼은 반드시 **denylist 아닌 allowlist**:

```python
GUEST_VISIBLE_EXTRA_KEYS: frozenset[str] = frozenset({
    "checkin_guide", "amenities", "wifi_note",
    "parking", "luggage_storage", "house_rules",
})

# ...
extra_info={k: extra[k] for k in GUEST_VISIBLE_EXTRA_KEYS if k in extra}
```

운영자가 임의 키(`internal_note`, `host_phone`)를 추가해도 자동 누설되지 않음.

**테스트로 회귀 방지** — `test_guest_api.py:98-138`: 명시적으로 `assert "host_phone" not in body["extra_info"]` 까지 검증.

---

## 4. 메시지 발송 — 링크 + 템플릿 + 채널

### 4-1. URL 빌더 — `checkin_announcement_service.py:1398-1424`

```python
def _build_tono_chat_url(self, reservation: ReservationInfo) -> str:
    """
    ⚠️ 카카오 알림톡 버튼 URL에는 https:// prefix가 자동으로 붙으므로
    여기서는 scheme을 제외한 URL만 반환한다.
    예: app.tono-operation.com/chat?r=7833004&g=SALT-K
    """
    base = settings.FRONTEND_URL.rstrip("/")
    base = base.replace("https://", "").replace("http://", "")  # 카카오용

    params: list[str] = []
    if reservation.reservation_code:
        params.append(f"r={reservation.reservation_code}")
    if reservation.property_code:
        params.append(f"p={reservation.property_code}")
    if reservation.guest_name:
        from urllib.parse import quote
        params.append(f"guest_name={quote(reservation.guest_name)}")

    if params:
        return f"{base}/chat?{'&'.join(params)}"
    return f"{base}/chat"
```

청소 사진 적용:

```python
def _build_photo_view_url(self, view: CleaningPhotoView) -> str:
    base = settings.FRONTEND_URL.rstrip("/").replace("https://", "").replace("http://", "")
    # SMS는 https:// 자동 prefix 안 됨 → 채널별로 분기
    return f"{base}/cleaning-photos?t={view.view_token}"

def _build_photo_view_url_sms(self, view: CleaningPhotoView) -> str:
    # SMS는 full URL
    return f"{settings.FRONTEND_URL.rstrip('/')}/cleaning-photos?t={view.view_token}"
```

> 💡 **중요**: 카톡 알림톡 버튼은 https 자동 prefix, SMS는 안 됨. 채널별로 다른 빌더 권장.

### 4-2. 템플릿 변수 시스템 — `checkin_announcement_service.py:81-157`

`KAKAO_DATA_SOURCES` 레지스트리 패턴이 매우 깔끔. 청소 사진용 변수 예시:

```python
PHOTO_VIEW_DATA_SOURCES: dict[str, dict] = {
    "guest_name": {"label": "게스트 이름", "example": "홍길동"},
    "property_name": {"label": "숙소명", "example": "솔트하우스 K동"},
    "checkout_date_formatted": {"label": "체크아웃 날짜", "example": "3월 22일(일)"},
    "photo_view_link": {
        "label": "사진 확인 링크",
        "example": "app.tonify.co.kr/cleaning-photos?t=abc123...",
    },
}

DEFAULT_PHOTO_TEMPLATE = (
    "{{guest_name}}님, 체크아웃 후 청소 점검이 완료되었습니다.\n"
    "객실 사진을 아래 링크에서 확인하실 수 있습니다.\n"
    "{{photo_view_link}}\n"
    "(링크는 {{expire_date}}까지 유효)"
)
```

### 4-3. 채널 어댑터 — `checkin_announcement_service.py:193-227`

```python
class BaseChannelAdapter:
    def send(self, reservation, message: str, **kwargs) -> dict:
        raise NotImplementedError

class SmsChannelAdapter(BaseChannelAdapter):
    def send(self, reservation, message: str, **kwargs) -> dict:
        if not reservation.guest_phone:
            raise ValueError("게스트 연락처(guest_phone)가 없습니다.")
        return send_sms(to=reservation.guest_phone, text=message)

class KakaoChannelAdapter(BaseChannelAdapter):
    def send(self, reservation, message: str, **kwargs) -> dict:
        return send_kakao_alimtalk(
            to=reservation.guest_phone,
            template_id=kwargs["template_id"],
            variables=kwargs.get("variables", {}),
            pf_id=kwargs.get("pf_id"),
        )
```

**Solapi 발송 함수**: `backend/app/adapters/sms_adapter.py:48-115`
- 90바이트 이하 SMS, 초과 LMS 자동 판별
- HMAC-SHA256 인증
- 발송 실패 검출 + 로깅 (전화번호 마스킹: `010****1234`)

### 4-4. 발송 멱등성 (중복 방지)

`checkin_announcement_service.py:298` `_announcement_repo.is_already_sent(reservation.id, primary_channel)` 패턴.

청소 사진:

```python
class CleaningPhotoSendLog(Base):
    __tablename__ = "cleaning_photo_send_logs"
    id: Mapped[int]
    organization_id: Mapped[int]  # multi-tenant 필수
    cleaning_job_id: Mapped[int]
    photo_view_id: Mapped[int]
    channel: Mapped[str]  # 'sms' | 'kakao' | 'email'
    status: Mapped[str]  # 'sent' | 'failed' | 'pending'
    sent_at: Mapped[datetime]
    provider_response: Mapped[dict | None]  # JSONB
    failure_reason: Mapped[str | None]

    __table_args__ = (
        # 같은 작업 + 같은 채널 1회만 발송 (재발송은 admin override)
        UniqueConstraint("cleaning_job_id", "channel",
                        name="uq_photo_send_per_channel"),
    )
```

---

## 5. 프론트엔드 — 라우팅 + 페이지

### 5-1. 라우트 등록 — `frontend/src/AppRoutes.tsx:79-81, 244-247`

```tsx
// AppShell 외부 (인증 안 함)
const TonoChatEntryPage = lazy(() => import("./pages/tono-chat/TonoChatEntryPage"));
const TonoChatRoomPage = lazy(() => import("./pages/tono-chat/TonoChatRoomPage"));

<Route path="/chat"
       element={<Suspense fallback={<FullScreenLoader />}><TonoChatEntryPage /></Suspense>} />
<Route path="/chat/:roomToken"
       element={<Suspense fallback={<FullScreenLoader />}><TonoChatRoomPage /></Suspense>} />
```

청소 사진:

```tsx
const CleaningPhotosEntryPage = lazy(() => import("./pages/cleaning-photos/EntryPage"));
const CleaningPhotosViewPage = lazy(() => import("./pages/cleaning-photos/ViewPage"));

<Route path="/cleaning-photos"
       element={<Suspense fallback={<FullScreenLoader />}><CleaningPhotosEntryPage /></Suspense>} />
<Route path="/cleaning-photos/:viewToken"
       element={<Suspense fallback={<FullScreenLoader />}><CleaningPhotosViewPage /></Suspense>} />
```

> **AppShell 외부에 둬야** 로그인/네비 없이 깔끔. `NonHousekeeperPage`/`TonoAdminPage` 같은 보호 래퍼 사용 금지.

### 5-2. 엔트리 페이지 (URL 파싱 + sessionStorage) — `TonoChatEntryPage.tsx:33-159`

핵심 패턴 정리:

1. **URL 파라미터 양식 지원** (`r`, `rc` 같은 단축/완전형):
   ```tsx
   const t = searchParams.get("t");  // view_token
   const rc = searchParams.get("r") || searchParams.get("rc");  // reservation_code
   ```

2. **sessionStorage로 토큰 보존** (새로고침/탭 이동 시 재진입):
   ```tsx
   sessionStorage.setItem("cleaning_photo_view_token", view.view_token);
   navigate(`/cleaning-photos/${view.view_token}`, { replace: true });
   ```

3. **StrictMode 이중 호출 방어** (`useRef` guard):
   ```tsx
   const createCalled = useRef(false);
   useEffect(() => {
     if (createCalled.current) return;
     createCalled.current = true;
     createPhotoView({...});
   }, [...]);
   ```

4. **에러/로딩/빈 상태 3종 처리** (CLAUDE.md `frontend.md`):
   ```tsx
   type PageState = "loading" | "ready" | "error";
   ```

### 5-3. 메인 뷰 페이지 — `TonoChatRoomPage.tsx`

청소 사진은 채팅과 달라서 폴링 불필요. 단순화 가능:

```tsx
export default function CleaningPhotosViewPage() {
  const { viewToken } = useParams<{ viewToken: string }>();
  const { view, photos, isExpired, error,
          isVerified, verify } = useCleaningPhotoView(viewToken!);

  if (error && !view) return <ErrorScreen message={error} />;
  if (isExpired) return <ExpiredScreen />;

  if (!isVerified) {
    return <VerificationPrompt onVerified={verify}
                               viewToken={viewToken!} />;
  }

  return <PhotoGrid photos={photos} property={view.property_name} />;
}
```

### 5-4. API 클라이언트 (raw fetch, no auth) — `frontend/src/api/tonoChat.ts`

**`apiGet/apiPost` 사용 금지** — 자동 Authorization 헤더 + 401 시 /login 리다이렉트. 게스트는 raw fetch.

```ts
// frontend/src/api/cleaningPhotos.ts
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";
const BASE = `${API_BASE_URL.replace(/\/+$/, "")}/cleaning-photos`;

export class CleaningPhotoApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

async function handleResponse<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    let detail: string;
    try {
      const json = await resp.json();
      detail = json.detail || JSON.stringify(json);
    } catch {
      detail = await resp.text().catch(() => "Unknown error");
    }
    throw new CleaningPhotoApiError(resp.status, detail);
  }
  return resp.json() as Promise<T>;
}

export async function getPhotoView(token: string): Promise<PhotoViewResponse> {
  const resp = await fetch(`${BASE}/${encodeURIComponent(token)}`);
  return handleResponse<PhotoViewResponse>(resp);
}

export async function verifyPhotoView(
  token: string,
  payload: { phone_last4?: string; reservation_code?: string }
): Promise<VerifyResponse> {
  const resp = await fetch(`${BASE}/${encodeURIComponent(token)}/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse<VerifyResponse>(resp);
}
```

### 5-5. 인증 컴포넌트 (다단계) — `VerificationPrompt.tsx:18-203`

서버 응답의 `step` 필드로 다음 단계 결정. 청소 사진 단순화:

```tsx
type VerifyStep = "phone_last4" | "reservation_code" | "success";

const [step, setStep] = useState<VerifyStep>("phone_last4");

// 폰번호 4자리 → 실패 시 → 예약코드 fallback
const result = await verifyPhotoView(token, { phone_last4: input });
if (result.success) {
  setStep("success");
  onVerified(result);
} else if (result.step === "fallback_code") {
  setStep("reservation_code");
}
```

iOS 줌 방지 (CLAUDE.md frontend.md): `<input>` font-size ≥ 16px, `inputMode="numeric"` for 숫자.

---

## 6. 실패 케이스 처리 (백엔드 ↔ 프론트 매핑)

| 시나리오 | 백엔드 응답 | 프론트 처리 |
|---|---|---|
| 잘못된 토큰 | `404 "사진을 찾을 수 없습니다."` | "유효하지 않은 링크" 화면 |
| 만료된 토큰 | `410 "링크가 만료되었습니다."` | 만료 전용 화면 + 호스트 연락 안내 |
| 인증 실패 (1차) | `200 success=false, step="fallback_code"` | 다음 단계 입력 폼으로 전환 |
| 인증 실패 (코드) | `400 "예약 코드가 일치하지 않습니다."` | 인라인 에러 + 재시도 |
| 인증 시도 초과 | `429 "잠시 후 다시 시도해주세요."` | "잠시 후 다시" 안내 + 자동 disable |
| 취소된 예약 | `400 "유효하지 않은 예약입니다."` | "체크아웃 정보를 확인할 수 없습니다" |
| 다른 org 접근 | 일어나면 안 됨 (토큰이 capability) | — |
| 서버 에러 | `500 "처리 중 오류가 발생했습니다."` | 일반 에러 + Slack 알림 |

**한국어 제네릭 메시지 원칙** (CLAUDE.md): 내부 에러는 노출하지 않음. `"DB connection failed"` 같은 메시지 직접 노출 금지.

---

## 7. 테스트 패턴

### 7-1. 게스트 API 테스트 — `backend/tests/test_guest_api.py`

핵심 패턴:
1. **fresh app + dependency_overrides[get_db]** — 누수 방지 (`_make_client`, `test_guest_api.py:14-30`)
2. **유효 토큰 정상 응답** — `test_guest_session_endpoint`
3. **잘못된 토큰 → 401** — `test_guest_invalid_token`
4. **민감정보 비노출 화이트리스트 검증** — `test_guest_room_info_extra_info_allowlist`
   - `assert body["extra_info"] == {허용된 키만}`
   - `assert "host_phone" not in body["extra_info"]` (회귀 명시 검증)

### 7-2. TONO Chat 테스트 — `backend/tests/test_tono_chat_auto_reply.py`

```python
@pytest.fixture
def expired_conversation(db, org_a, property_a):
    """만료된 채팅방 — valid_until 지난 케이스"""
    conv = Conversation(
        id=uuid.uuid4(),
        organization_id=org_a.id,
        channel=ConversationChannel.tono_chat,
        room_token=secrets.token_urlsafe(16),
        valid_until=utc_now() - timedelta(hours=1),  # 이미 만료
    )
    db.add(conv); db.flush()
    return conv
```

### 7-3. 청소 사진용 필수 테스트 체크리스트

- [ ] `test_create_view_success` — 청소 작업으로 view 생성
- [ ] `test_create_view_idempotent` — 같은 작업 2번 호출 시 같은 토큰 반환
- [ ] `test_create_view_org_isolation` — `current_user.organization_id` 무시, job의 org 사용 검증
- [ ] `test_get_view_pending_no_photos` — `access_level=pending`이면 photos 빈 배열
- [ ] `test_get_view_verified_with_photos` — verified면 사진 노출
- [ ] `test_get_view_404_invalid_token`
- [ ] `test_get_view_410_expired`
- [ ] `test_verify_phone_last4_success`
- [ ] `test_verify_phone_last4_fail_fallback` — step="fallback_code" 반환
- [ ] `test_verify_phone_normalization` — `010-1234-5678` ↔ `01012345678` 모두 매칭
- [ ] `test_verify_reservation_code_success`
- [ ] `test_verify_reservation_code_mismatch_400`
- [ ] `test_verify_canceled_reservation_400`
- [ ] `test_verify_rate_limit_429` — 10회/분 초과
- [ ] `test_verify_brute_force_lockout` — 5회 연속 실패 → 잠금
- [ ] `test_send_log_recorded` — SMS/카톡 발송 후 로그 기록 확인
- [ ] `test_send_idempotent` — 같은 channel 2번 발송 시 unique 제약 발동
- [ ] `test_view_response_no_internal_fields` — extra_metadata에 internal_note 넣어도 응답 누설 X
- [ ] `test_url_no_https_prefix_for_kakao` — 카톡용 URL은 scheme 없음

---

## 8. 청소 사진 시나리오 — 권장 설계 요약

### 8-1. DB 스키마 (Alembic 마이그레이션 1개)

```python
# cleaning_photo_views: 게스트가 사진을 보는 view 단위
class CleaningPhotoView(Base):
    __tablename__ = "cleaning_photo_views"
    id: Mapped[int]
    organization_id: Mapped[int]  # CASCADE
    cleaning_job_id: Mapped[int]  # CASCADE
    reservation_id: Mapped[int | None]  # SET NULL (예약 취소돼도 사진은 남음)
    view_token: Mapped[str]  # 22자, unique
    access_level: Mapped[str]  # "pending" | "verified"
    access_channel: Mapped[str | None]  # "sms" | "kakao" | "email"
    valid_until: Mapped[datetime]
    failed_verify_count: Mapped[int]  # default 0
    verification_locked_until: Mapped[datetime | None]
    status: Mapped[str]  # "active" | "archived"
    created_at, updated_at

    __table_args__ = (
        Index("idx_cpv_token", "view_token"),
        UniqueConstraint("cleaning_job_id", "organization_id",
                         name="uq_cpv_job_per_org"),  # 작업당 1 view
    )

# cleaning_photos: 실제 사진 메타 (S3 등 별도 스토리지 URL)
class CleaningPhoto(Base):
    __tablename__ = "cleaning_photos"
    id, organization_id, cleaning_job_id
    s3_key: Mapped[str]
    thumbnail_s3_key: Mapped[str | None]
    category: Mapped[str | None]  # "before" | "after" | "issue"
    room_label: Mapped[str | None]  # "거실" | "침실 1"
    captured_at: Mapped[datetime]
    sort_order: Mapped[int]

# cleaning_photo_send_logs: 발송 멱등 + 감사
class CleaningPhotoSendLog(Base):
    # §4-4 참고
```

마이그레이션 작성 후 **즉시** `alembic upgrade head` 실행 (CLAUDE.md feedback_run_migration).

### 8-2. 백엔드 모듈 분리

```
backend/app/
├── api/v1/
│   └── cleaning_photos.py      # 게스트 API (인증 X) + 호스트 admin API
├── domain/models/
│   ├── cleaning_photo_view.py
│   ├── cleaning_photo.py
│   └── cleaning_photo_send_log.py
├── repositories/
│   ├── cleaning_photo_view_repository.py
│   └── cleaning_photo_send_log_repository.py
├── services/
│   ├── cleaning_photo_view_service.py   # view 생성/만료/잠금 로직
│   └── cleaning_photo_dispatch_service.py  # 메시지 발송 + 멱등
└── adapters/
    └── (sms_adapter.py 재사용)
```

### 8-3. 프론트 모듈 분리

```
frontend/src/
├── pages/cleaning-photos/
│   ├── EntryPage.tsx        # /cleaning-photos?t=...
│   ├── ViewPage.tsx         # /cleaning-photos/:viewToken
│   ├── ExpiredScreen.tsx
│   └── components/
│       ├── PhotoGrid.tsx
│       ├── PhotoLightbox.tsx
│       └── VerificationPrompt.tsx
├── api/cleaningPhotos.ts
├── hooks/useCleaningPhotoView.ts
├── styles/cleaning-photos.css
└── types/cleaningPhotos.ts
```

### 8-4. AppRoutes 등록 위치

`AppRoutes.tsx` — `TonoChat`과 같은 위치(파일 끝, AppShell 외부, 라우트 패턴 동일).

### 8-5. 발송 트리거

청소 작업이 `completed` 상태로 전환되는 곳에서:

```python
# services/cleaning_job_service.py 안에서
def complete_job(self, job_id: int):
    job = self.repo.get(job_id)
    job.status = "completed"
    job.completed_at = utc_now()
    self.db.flush()

    # 사진이 1장 이상이면 view 생성 + 발송
    if self._photo_repo.count_by_job(job_id) > 0:
        view = self.view_service.create_or_get(job)
        # BackgroundTask로 발송 (요청 응답을 막지 않음)
        background_tasks.add_task(
            self.dispatch_service.send_to_guest,
            view_id=view.id,
        )

    self.db.commit()
```

`tono_chat.py:560-566`처럼 `BackgroundTasks` 활용. **재시도 가능하도록 멱등** 설계.

---

## 9. 보안 체크리스트 (배포 전 확인)

- [ ] 토큰은 `secrets.token_urlsafe(16)` 이상 (≥128bit 엔트로피)
- [ ] 모든 게스트 쿼리에 `organization_id` 필터 (multi-tenant 격리)
- [ ] DTO는 allowlist (denylist 금지)
- [ ] `response_model_exclude_none=True`로 null 필드 자동 제거
- [ ] 인증 실패 시 IP rate limit + view 단위 lockout (이중 보호)
- [ ] 한국어 제네릭 에러 메시지 (`"처리 중 오류가 발생했습니다."`)
- [ ] HTTPS 강제 (사진 URL signed URL 권장 — S3 presigned)
- [ ] 사진 자체에는 게스트 토큰 없이도 short-lived signed URL로만 접근
- [ ] valid_until 만료된 view는 401/410 (절대 200 + 빈 목록 금지)
- [ ] SMS/카톡 발송 로그에 전화번호 마스킹 (`010****1234`)
- [ ] 카카오 알림톡: 템플릿 사전 승인 + variable에 빈 문자열 금지 (Solapi 제약 — `"-"` fallback)
- [ ] view 토큰 노출 경로 (URL, sessionStorage)에 PII 포함 금지
- [ ] 인증 시도 카운터/lockout 컬럼은 `failed_verify_count`, `verification_locked_until`로 명명
- [ ] 마이그레이션 후 즉시 `alembic upgrade head` 실행

---

## 10. 핵심 파일 인덱스 (codex 빠른 참조)

| 영역 | 파일 | 핵심 라인 |
|---|---|---|
| 토큰 모델 | `backend/app/domain/models/conversation.py` | 62-195 |
| 토큰 생성 | `backend/app/api/v1/tono_chat.py` | 195-197 |
| 만료 가드 | `backend/app/api/v1/tono_chat.py` | 200-219 |
| 방 생성 (idempotent) | `backend/app/api/v1/tono_chat.py` | 277-455 |
| 인증 다단계 | `backend/app/api/v1/tono_chat.py` | 819-1013 |
| 단계별 DTO | `backend/app/api/v1/tono_chat.py` | 635-812 |
| URL 빌더 | `backend/app/services/checkin_announcement_service.py` | 1398-1424 |
| 템플릿 변수 | `backend/app/services/checkin_announcement_service.py` | 81-181 |
| 채널 어댑터 | `backend/app/services/checkin_announcement_service.py` | 193-227 |
| Solapi SMS/카톡 | `backend/app/adapters/sms_adapter.py` | 48-200 |
| JWT 발급/검증 | `backend/app/core/security.py` | 177-220 |
| Guest 의존성 | `backend/app/core/deps.py` | 565-591 |
| Allowlist DTO | `backend/app/api/v1/guest.py` | 36-100 |
| Rate limiter | `backend/app/core/rate_limiter.py` | 47-50 |
| 라우트 등록 | `frontend/src/AppRoutes.tsx` | 79-81, 244-247 |
| Entry 페이지 | `frontend/src/pages/tono-chat/TonoChatEntryPage.tsx` | 33-241 |
| View 페이지 | `frontend/src/pages/tono-chat/TonoChatRoomPage.tsx` | 27-272 |
| API client | `frontend/src/api/tonoChat.ts` | 1-269 |
| 데이터 hook | `frontend/src/hooks/useTonoChat.ts` | 59-548 |
| 인증 컴포넌트 | `frontend/src/components/tono-chat/VerificationPrompt.tsx` | 18-203 |
| 게스트 API 테스트 | `backend/tests/test_guest_api.py` | 14-138 |
| TONO Chat 테스트 | `backend/tests/test_tono_chat_auto_reply.py` | 50-200 |

---

> 본 문서는 본 저장소의 현 시점(2026-05-03 기준) 코드 스냅샷에서 추출.
> 청소관리 시스템 저장소에 그대로 이식 가능하지만, **CLAUDE.md / .claude/rules/ 규칙은 해당 저장소 기준으로 다시 확인** 필요.

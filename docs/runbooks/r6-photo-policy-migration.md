# R6 사진 자동 공개 정책 전환 운영 runbook

## 배경

2026-05-18부터 협력사가 업로드한 사진은 관리자 검수 없이 즉시 고객에게 공개된다. 잘못 올라온 사진은 관리자가 사진검수 화면에서 비공개로 되돌린다.

## 배포 전 확인

- DB 백업 또는 복구 가능한 스냅샷이 있는지 확인한다.
- 운영자가 정책 변경을 알고 있는지 확인한다.
- `alembic current`가 `0006_default_partner_categories` 또는 그 이후인지 확인한다.

## 실행

```powershell
cd backend
python -m alembic upgrade head
```

## 검증

```powershell
python -c "from app.db.session import SessionLocal; from sqlalchemy import text; s = SessionLocal(); print(s.execute(text(\"SELECT COUNT(*) FROM order_photos WHERE is_customer_visible = FALSE\")).scalar()); print(s.execute(text(\"SELECT COUNT(*) FROM orders WHERE status = '사진검수대기'\")).scalar())"
```

두 값이 모두 `0`이면 마이그레이션이 의도대로 적용된 것이다.

## 영향

- 기존 비공개 사진은 모두 고객 공개 상태가 된다.
- 사진이 있는 `사진검수대기` 주문은 `고객전달필요`로 이동한다.
- 사진이 없는 `사진검수대기` 주문은 `작업진행`으로 되돌린다.
- timeline 이벤트는 대량 생성하지 않는다.

## 롤백

이 마이그레이션의 downgrade는 의도적으로 no-op이다. 정책을 되돌려야 하면 운영 판단 후 새 forward-only 마이그레이션을 작성한다.

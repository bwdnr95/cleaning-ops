# R7 Multi-line Orders Migration Runbook

작성일: 2026-05-18

## 목적

R7은 기존 `Order = 작업 라인` 의미를 유지하면서 상위 묶음인 `OrderGroup`을 추가한다. 고객 정보, 주소, `customer_token`, `source_channel`, `customer_visible_payment`는 그룹으로 이동하고, 상태/결제/사진/메시지/협력사 배정은 계속 line(`orders`) 단위로 처리한다.

## 배포 전 체크

- DB 백업을 먼저 만든다.
- 현재 Alembic head가 `0007_auto_publish_legacy_photos`인지 확인한다.
- 배포 전 주문 수를 기록한다.

```sql
SELECT COUNT(*) AS orders_before FROM orders;
SELECT COUNT(*) AS orders_without_token FROM orders WHERE customer_token IS NULL;
```

`orders_without_token`은 기존 스키마 기준 0이어야 한다.

## 마이그레이션 실행

```powershell
cd backend
python -m alembic upgrade head
```

마이그레이션 `0008_order_groups`가 수행하는 일:

- `order_groups` 테이블 생성
- `orders.group_id` 추가
- 기존 주문마다 1개의 1-line 그룹 생성
- 기존 customer/token/source/payment-visible 데이터를 그룹으로 복사
- `orders.customer_token` legacy unique 제약 제거
- legacy customer 컬럼 nullable 전환

## 배포 후 검증 SQL

```sql
SELECT COUNT(*) AS groups_after FROM order_groups;
SELECT COUNT(*) AS orders_after FROM orders;
SELECT COUNT(*) AS orders_without_group FROM orders WHERE group_id IS NULL;
SELECT COUNT(*) AS broken_group_refs
FROM orders o
LEFT JOIN order_groups g ON g.id = o.group_id
WHERE g.id IS NULL;
```

기대값:

- `groups_after = orders_after`는 R7 배포 직후 기존 데이터 기준으로 성립한다. 배포 후 신규 multi-line 주문이 생성되면 groups 수는 orders 수보다 작을 수 있다.
- `orders_without_group = 0`
- `broken_group_refs = 0`

## 운영 확인

- 관리자 신규 주문 폼에서 라인 2개를 생성한다.
- 주문 목록에서 같은 그룹의 라인이 시각적으로 묶여 보이는지 확인한다.
- 주문 상세에서 "이 그룹의 다른 라인"으로 이동되는지 확인한다.
- 협력사 계정에서는 본인에게 배정된 line만 보이는지 확인한다.
- 고객 링크 하나로 접속해 전화번호 뒤 4자리 인증 후 line 카드 N개가 보이는지 확인한다.
- line 하나만 `취소`로 바꿔도 같은 그룹의 다른 line 상태가 유지되는지 확인한다.

## 롤백

`downgrade()`는 의도적으로 no-op이다. 구조 변경과 데이터 백필이 포함되어 있어 DB 롤백은 백업 복구로만 처리한다.

롤백 절차:

1. 앱 배포를 R7 이전 커밋으로 되돌린다.
2. DB는 R7 적용 전 백업에서 복구한다.
3. 복구 후 `orders` 조회, 고객 링크 인증, 협력사 작업 조회를 smoke test 한다.

## FAQ

**라인을 추가하려면?**  
관리자 API `POST /api/admin/orders/groups/{group_id}/lines` 또는 신규 주문 폼의 라인 추가 UI를 사용한다.

**그룹 전체 취소 상태가 따로 있나?**  
없다. line별 `orders.status`만 유지한다. 모든 line이 `취소`이면 목록 UI에서 묶음에 "취소됨" 배지를 표시한다.

**고객 결제 정보는 어디 기준인가?**  
R7에서는 `order_groups.customer_visible_payment`가 고객 결제 표시 여부를 결정한다. false이면 각 line의 결제 금액/상태는 고객 DTO에서 `null`로 내려간다.

**협력사 DTO에 그룹 정보가 보이나?**  
보이면 안 된다. 협력사는 본인 `partner_id`에 배정된 `Order` line만 보고, `group_id`, `customer_token`, `source_channel`, 정산/고객 결제 정보는 노출하지 않는다.

# R13 보고서 / 일괄 등록

## 보고서 4 화면

- **매출 추세**: 기간/단위(일, 주, 월)와 협력사/서비스 필터로 매출을 확인한다. 매출은 `고객전달완료 + 서비스완료` 상태의 `total_amount` 합계이며, 대시보드 매출 정의와 같다.
- **협력사 성과**: 협력사별 작업 수, 평균 단가, 정산 대기 수, 정산 예정액을 본다. 취소 주문은 작업 수에서 제외한다.
- **서비스 인기**: 서비스별 작업 수, 매출, 매출 비중을 본다. `service_item_id`가 없는 import 주문도 `service_name` 기준으로 포함한다.
- **정산 대기**: `서비스완료` 상태이면서 `partner_payment_status`가 `unpaid`, `ready`, 또는 NULL인 주문만 표시한다. `고객전달완료`는 정산 대기가 아니다. 정산 대기는 운영자가 명시적으로 `서비스완료`로 전환한 시점부터 본다.

각 화면 오른쪽의 `CSV` / `Excel` 버튼은 현재 필터와 기간 조건을 그대로 적용해 다운로드한다.

## 일괄 등록

- 주문관리 상단의 `일괄 등록`에서 xlsx 파일을 업로드한다.
- 필수 컬럼은 `group_key`, `customer_name`, `customer_phone`, `customer_address`, `scheduled_date`, `service_name`, `total_amount`다.
- 같은 `group_key` 행은 하나의 주문 그룹 안에 여러 작업 라인으로 묶인다.
- 행 단위로 검증하지만, 한 그룹 안에서 잘못된 행이 하나라도 있으면 그 `group_key` 전체가 등록되지 않는다. 다른 그룹은 계속 처리된다.
- 응답은 `succeeded_groups`, `succeeded_lines`, `failed: [{row_index, reason}]` 형태다.

## 데이터 일관성

- 모든 보고서는 `Order.deleted_at IS NULL` 조건을 강제한다.
- 매출과 작업 수가 다른 화면과 다르면 먼저 `DashboardService`와 `ReportService`의 정의를 확인한다.
- import로 들어온 주문도 고객 토큰 생성, 그룹/라인 생성, 타임라인 기록 정책을 따른다.

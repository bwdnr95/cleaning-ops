import type { RecurringContract, RecurringContractStatus } from '../api/recurring';

export const CONTRACT_STATUS_LABEL: Record<RecurringContractStatus, string> = {
  active: '진행중',
  paused: '일시정지',
  ended: '종료',
};

// 상태 배지 배경색. 토큰이 없는 환경을 대비해 fallback 값을 함께 둔다.
export const CONTRACT_STATUS_TONE: Record<RecurringContractStatus, string> = {
  active: 'var(--success-bg, #e6f7ed)',
  paused: 'var(--warn-bg, #fff4e5)',
  ended: 'var(--neutral-bg, #eef0f3)',
};

// weekday는 월=0 ... 일=6 (Python date.weekday() 규약).
export const WEEKDAY_LABEL = ['월', '화', '수', '목', '금', '토', '일'];

export function formatAmount(value: number | null | undefined): string {
  if (value == null) return '-';
  return `${value.toLocaleString('ko-KR')}원`;
}

// 계약 상세는 schedule_text를 내려받지 않으므로(요약 DTO 전용) 원시 스케줄 필드로 표기를 만든다.
export function formatScheduleText(
  contract: Pick<RecurringContract, 'recurrence_mode' | 'day_of_month' | 'interval_weeks' | 'weekday'>,
): string {
  if (contract.recurrence_mode === 'monthly') {
    return contract.day_of_month != null ? `매월 ${contract.day_of_month}일` : '매월';
  }
  const interval = contract.interval_weeks ?? 1;
  const base = interval === 1 ? '매주' : interval === 2 ? '격주' : `${interval}주마다`;
  const weekday =
    contract.weekday != null && WEEKDAY_LABEL[contract.weekday]
      ? ` (${WEEKDAY_LABEL[contract.weekday]})`
      : '';
  return `${base}${weekday}`;
}

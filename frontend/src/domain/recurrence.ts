import type {
  RecurringContract,
  RecurringContractStatus,
  RecurringOccurrenceStatus,
} from '../api/recurring';

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

// 회차 원장 상태 라벨/배지색.
export const OCCURRENCE_STATUS_LABEL: Record<RecurringOccurrenceStatus, string> = {
  pending: '대기',
  generated: '생성',
  skipped: '건너뜀',
};

export const OCCURRENCE_STATUS_TONE: Record<RecurringOccurrenceStatus, string> = {
  pending: 'var(--warn-bg, #fff4e5)',
  generated: 'var(--success-bg, #e6f7ed)',
  skipped: 'var(--neutral-bg, #eef0f3)',
};

// weekday는 월=0 ... 일=6 (Python date.weekday() 규약).
export const WEEKDAY_LABEL = ['월', '화', '수', '목', '금', '토', '일'];

export function formatAmount(value: number | null | undefined): string {
  if (value == null) return '-';
  return `${value.toLocaleString('ko-KR')}원`;
}

// 계약 상세는 schedule_text를 내려받지 않으므로(요약 DTO 전용) 원시 스케줄 필드로 표기를 만든다.
export function formatScheduleText(
  contract: Pick<
    RecurringContract,
    'recurrence_mode' | 'day_of_month' | 'interval_weeks' | 'weekday' | 'weekdays'
  >,
): string {
  if (contract.recurrence_mode === 'monthly') {
    return contract.day_of_month != null ? `매월 ${contract.day_of_month}일` : '매월';
  }
  const interval = contract.interval_weeks ?? 1;
  const base = interval === 1 ? '매주' : interval === 2 ? '격주' : `${interval}주마다`;
  // 다중요일(weekdays)을 우선 사용하고, 없으면 레거시 단일 weekday로 폴백한다.
  const source =
    contract.weekdays && contract.weekdays.length > 0
      ? contract.weekdays
      : contract.weekday != null
        ? [contract.weekday]
        : [];
  const labels = [...source]
    .sort((a, b) => a - b)
    .map((w) => WEEKDAY_LABEL[w])
    .filter(Boolean);
  const suffix = labels.length > 0 ? ` (${labels.join('·')})` : '';
  return `${base}${suffix}`;
}

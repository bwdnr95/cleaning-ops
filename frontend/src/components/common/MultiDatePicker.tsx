import React from 'react';
import { createPortal } from 'react-dom';

import { formatDateValue, getAppTodayDate, parseDateValue } from '../../domain/time';
import { Icon } from './ui';

const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토'];

interface MultiDatePickerProps {
  readonly value: readonly string[];
  readonly onChange: (value: string[]) => void;
  readonly placeholder?: string;
  readonly testId?: string;
  readonly ariaLabel?: string;
}

interface CalendarCell {
  readonly date: Date;
  readonly value: string;
  readonly isOutsideMonth: boolean;
}

export function MultiDatePicker({
  value,
  onChange,
  placeholder = '방문일 선택',
  testId,
  ariaLabel = '방문 예정일 여러 개 선택',
}: MultiDatePickerProps) {
  const rootRef = React.useRef<HTMLDivElement | null>(null);
  const triggerRef = React.useRef<HTMLButtonElement | null>(null);
  const popupRef = React.useRef<HTMLDivElement | null>(null);
  const popupId = React.useId();
  const normalized = React.useMemo(() => [...new Set(value)].sort(), [value]);
  const selected = React.useMemo(() => new Set(normalized), [normalized]);
  const [isOpen, setIsOpen] = React.useState(false);
  const [viewDate, setViewDate] = React.useState(
    () => parseDateValue(normalized[0]) || getAppTodayDate(),
  );
  const [focusDateValue, setFocusDateValue] = React.useState(
    () => normalized[0] || formatDateValue(getAppTodayDate()),
  );
  const [position, setPosition] = React.useState<{ top: number; left: number; width: number } | null>(null);
  const cells = React.useMemo(() => buildMonthCells(viewDate), [viewDate]);
  const calendarFocusValue = cells.some((cell) => cell.value === focusDateValue)
    ? focusDateValue
    : cells.find((cell) => !cell.isOutsideMonth)?.value || cells[0]?.value;

  const close = React.useCallback(() => {
    setIsOpen(false);
    window.requestAnimationFrame(() => triggerRef.current?.focus());
  }, []);

  const updatePosition = React.useCallback(() => {
    const root = rootRef.current;
    if (!root) return;
    const rect = root.getBoundingClientRect();
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    const width = Math.min(320, viewportWidth - 24);
    const left = Math.max(12, Math.min(rect.left, viewportWidth - width - 12));
    const estimatedHeight = 400;
    const below = rect.bottom + 6;
    const top = below + estimatedHeight <= viewportHeight - 12
      ? below
      : Math.max(12, rect.top - estimatedHeight - 6);
    setPosition({ top, left, width });
  }, []);

  React.useLayoutEffect(() => {
    if (!isOpen) {
      setPosition(null);
      return undefined;
    }
    updatePosition();
    window.addEventListener('resize', updatePosition);
    window.addEventListener('scroll', updatePosition, true);
    return () => {
      window.removeEventListener('resize', updatePosition);
      window.removeEventListener('scroll', updatePosition, true);
    };
  }, [isOpen, updatePosition]);

  React.useEffect(() => {
    if (!isOpen || !position) return;
    window.requestAnimationFrame(() => {
      popupRef.current
        ?.querySelector<HTMLButtonElement>(`[data-date-value="${calendarFocusValue}"]`)
        ?.focus();
    });
  }, [calendarFocusValue, isOpen, position]);

  React.useEffect(() => {
    if (!isOpen) return undefined;
    const handlePointer = (event: MouseEvent) => {
      const target = event.target;
      if (!(target instanceof Node)) return;
      if (!rootRef.current?.contains(target) && !popupRef.current?.contains(target)) close();
    };
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        close();
        return;
      }
      if (event.key !== 'Tab') return;
      const popup = popupRef.current;
      if (!popup) return;
      const focusable = [...popup.querySelectorAll<HTMLButtonElement>('button:not([disabled])')];
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (!first || !last) return;
      const active = document.activeElement;
      if (event.shiftKey && (active === first || !popup.contains(active))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (active === last || !popup.contains(active))) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('mousedown', handlePointer);
    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('mousedown', handlePointer);
      document.removeEventListener('keydown', handleKey);
    };
  }, [close, isOpen]);

  const toggleDate = (dateValue: string) => {
    const next = new Set(normalized);
    if (next.has(dateValue)) next.delete(dateValue);
    else next.add(dateValue);
    onChange([...next].sort());
  };

  const moveFocus = (event: React.KeyboardEvent<HTMLButtonElement>, date: Date) => {
    const delta = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 }[event.key];
    if (delta === undefined) return;
    event.preventDefault();
    const next = new Date(date.getFullYear(), date.getMonth(), date.getDate() + delta);
    const nextValue = formatDateValue(next);
    setFocusDateValue(nextValue);
    setViewDate(new Date(next.getFullYear(), next.getMonth(), 1));
    window.requestAnimationFrame(() => {
      popupRef.current?.querySelector<HTMLButtonElement>(`[data-date-value="${nextValue}"]`)?.focus();
    });
  };

  const changeMonth = (delta: number) => {
    const next = new Date(viewDate.getFullYear(), viewDate.getMonth() + delta, 1);
    setFocusDateValue(formatDateValue(next));
    setViewDate(next);
  };

  const summary = normalized.length === 0
    ? placeholder
    : normalized.length === 1
      ? formatDisplayDate(normalized[0])
      : `${formatDisplayDate(normalized[0])} 외 ${normalized.length - 1}일`;

  const popup = isOpen && position ? createPortal(
    <div
      ref={popupRef}
      id={popupId}
      role="dialog"
      aria-modal="true"
      aria-label="방문 예정일 선택 달력"
      className="multi-date-picker__popover"
      style={{ top: position.top, left: position.left, width: position.width }}
    >
      <div className="multi-date-picker__header">
        <button type="button" className="multi-date-picker__nav" aria-label="이전 달" onClick={() => changeMonth(-1)}>
          <Icon name="chevronLeft" size={15}/>
        </button>
        <strong data-testid={testId ? `${testId}-month-label` : undefined}>
          {viewDate.getFullYear()}년 {viewDate.getMonth() + 1}월
        </strong>
        <button type="button" className="multi-date-picker__nav" aria-label="다음 달" onClick={() => changeMonth(1)}>
          <Icon name="chevronRight" size={15}/>
        </button>
      </div>
      <div className="multi-date-picker__weekdays" aria-hidden="true">
        {WEEKDAYS.map((weekday) => <span key={weekday}>{weekday}</span>)}
      </div>
      <div className="multi-date-picker__grid">
        {cells.map((cell) => (
          <button
            key={cell.value}
            type="button"
            data-date-value={cell.value}
            data-testid={testId ? `${testId}-day-${cell.value}` : undefined}
            className="multi-date-picker__day"
            data-selected={selected.has(cell.value)}
            data-outside={cell.isOutsideMonth}
            tabIndex={cell.value === calendarFocusValue ? 0 : -1}
            aria-pressed={selected.has(cell.value)}
            aria-label={`${formatDisplayDate(cell.value)}${selected.has(cell.value) ? ', 선택됨' : ''}`}
            onClick={() => toggleDate(cell.value)}
            onFocus={() => setFocusDateValue(cell.value)}
            onKeyDown={(event) => moveFocus(event, cell.date)}
          >
            {cell.date.getDate()}
          </button>
        ))}
      </div>
      <div className="multi-date-picker__selection" aria-live="polite">
        {normalized.length > 0 ? `${normalized.length}일 선택됨` : '날짜를 여러 개 선택할 수 있습니다.'}
      </div>
      <div className="multi-date-picker__footer">
        <button type="button" className="btn btn--ghost btn--sm" onClick={() => onChange([])}>전체 해제</button>
        <button type="button" className="btn btn--ghost btn--sm" onClick={() => toggleDate(formatDateValue(getAppTodayDate()))}>오늘 추가</button>
        <button type="button" className="btn btn--primary btn--sm" onClick={close}>선택 완료</button>
      </div>
    </div>,
    document.body,
  ) : null;

  return (
    <div ref={rootRef} className="multi-date-picker">
      <button
        ref={triggerRef}
        type="button"
        className="date-picker-trigger multi-date-picker__trigger"
        data-testid={testId}
        aria-label={ariaLabel}
        aria-expanded={isOpen}
        aria-haspopup="dialog"
        aria-controls={isOpen ? popupId : undefined}
        onClick={() => {
          if (!isOpen) {
            const nextFocusDate = normalized[0] || formatDateValue(getAppTodayDate());
            setFocusDateValue(nextFocusDate);
            setViewDate(parseDateValue(nextFocusDate) || getAppTodayDate());
          }
          setIsOpen((current) => !current);
        }}
      >
        <Icon name="calendar" size={13}/>
        <span>{summary}</span>
        <Icon name={isOpen ? 'chevronUp' : 'chevronDown'} size={11}/>
      </button>
      {normalized.length > 0 && (
        <div className="multi-date-picker__chips" aria-label="선택한 방문일">
          {normalized.map((dateValue) => (
            <span key={dateValue} className="multi-date-picker__chip">
              {formatDisplayDate(dateValue)}
              <button type="button" aria-label={`${formatDisplayDate(dateValue)} 삭제`} onClick={() => toggleDate(dateValue)}>
                <Icon name="x" size={10}/>
              </button>
            </span>
          ))}
        </div>
      )}
      {popup}
    </div>
  );
}

function buildMonthCells(viewDate: Date): CalendarCell[] {
  const first = new Date(viewDate.getFullYear(), viewDate.getMonth(), 1);
  const gridStart = new Date(first.getFullYear(), first.getMonth(), 1 - first.getDay());
  return Array.from({ length: 42 }, (_, index) => {
    const date = new Date(gridStart.getFullYear(), gridStart.getMonth(), gridStart.getDate() + index);
    return {
      date,
      value: formatDateValue(date),
      isOutsideMonth: date.getMonth() !== viewDate.getMonth(),
    };
  });
}

function formatDisplayDate(value: string): string {
  const date = parseDateValue(value);
  if (!date) return value;
  return `${date.getMonth() + 1}월 ${date.getDate()}일`;
}

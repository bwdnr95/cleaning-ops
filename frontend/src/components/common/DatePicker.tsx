import React from 'react';
import { createPortal } from 'react-dom';

import { formatDateValue, getAppTodayDate, parseDateValue } from '../../domain/time';
import { Icon } from './ui';

const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토'];
const PICKER_WIDTH = 286;
const PICKER_HEIGHT = 318;
const PICKER_OFFSET = 6;
const VIEWPORT_GAP = 8;

export function DatePicker({ value, onChange, placeholder = '날짜 선택', testId, ariaLabel = '날짜 선택', compact = false, style = undefined }) {
  const rootRef = React.useRef(null);
  const popupRef = React.useRef(null);
  const [isOpen, setIsOpen] = React.useState(false);
  const [popupPosition, setPopupPosition] = React.useState(null);
  const [viewDate, setViewDate] = React.useState(() => parseDateValue(value) || getAppTodayDate());

  const updatePopupPosition = React.useCallback(() => {
    const root = rootRef.current;
    if (!root) {
      return;
    }

    const rect = root.getBoundingClientRect();
    const viewportWidth = window.innerWidth || document.documentElement.clientWidth;
    const viewportHeight = window.innerHeight || document.documentElement.clientHeight;
    const spaceBelow = viewportHeight - rect.bottom - PICKER_OFFSET - VIEWPORT_GAP;
    const spaceAbove = rect.top - PICKER_OFFSET - VIEWPORT_GAP;
    const shouldOpenAbove = spaceBelow < PICKER_HEIGHT && spaceAbove > spaceBelow;
    const rawTop = shouldOpenAbove
      ? rect.top - PICKER_HEIGHT - PICKER_OFFSET
      : rect.bottom + PICKER_OFFSET;
    const top = Math.max(VIEWPORT_GAP, Math.min(rawTop, viewportHeight - PICKER_HEIGHT - VIEWPORT_GAP));
    const left = Math.max(
      VIEWPORT_GAP,
      Math.min(rect.left, viewportWidth - PICKER_WIDTH - VIEWPORT_GAP),
    );

    setPopupPosition({ top, left });
  }, []);

  React.useEffect(() => {
    if (isOpen) {
      setViewDate(parseDateValue(value) || getAppTodayDate());
      updatePopupPosition();
    }
  }, [isOpen, updatePopupPosition, value]);

  React.useLayoutEffect(() => {
    if (!isOpen) {
      setPopupPosition(null);
      return undefined;
    }

    updatePopupPosition();
    window.addEventListener('resize', updatePopupPosition);
    window.addEventListener('scroll', updatePopupPosition, true);
    return () => {
      window.removeEventListener('resize', updatePopupPosition);
      window.removeEventListener('scroll', updatePopupPosition, true);
    };
  }, [isOpen, updatePopupPosition]);

  React.useEffect(() => {
    if (!isOpen) {
      return undefined;
    }

    const handleDocumentMouseDown = (event) => {
      const target = event.target;
      const isInsideRoot = rootRef.current && rootRef.current.contains(target);
      const isInsidePopup = popupRef.current && popupRef.current.contains(target);
      if (!isInsideRoot && !isInsidePopup) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleDocumentMouseDown);
    return () => document.removeEventListener('mousedown', handleDocumentMouseDown);
  }, [isOpen]);

  const selectedDate = parseDateValue(value);
  const todayValue = formatDateValue(getAppTodayDate());
  const cells = buildMonthCells(viewDate);
  const monthLabel = `${viewDate.getFullYear()}년 ${viewDate.getMonth() + 1}월`;

  const moveMonth = (delta) => {
    setViewDate((current) => new Date(current.getFullYear(), current.getMonth() + delta, 1));
  };

  const selectDate = (date) => {
    onChange(formatDateValue(date));
    setIsOpen(false);
  };

  const clearDate = () => {
    onChange('');
    setIsOpen(false);
  };

  const selectToday = () => {
    const today = getAppTodayDate();
    onChange(formatDateValue(today));
    setViewDate(today);
    setIsOpen(false);
  };

  return (
    <div ref={rootRef} style={{ position: 'relative', minWidth: compact ? 132 : 0, ...style }}>
      <button
        type="button"
        data-testid={testId}
        aria-label={ariaLabel}
        aria-expanded={isOpen}
        onClick={() => setIsOpen((current) => !current)}
        style={{
          width: '100%',
          height: compact ? 30 : 34,
          padding: compact ? '0 9px' : '0 10px',
          display: 'flex',
          alignItems: 'center',
          gap: 7,
          border: `1px solid ${isOpen ? 'var(--brand)' : 'var(--border)'}`,
          borderRadius: 8,
          background: 'var(--surface)',
          boxShadow: isOpen ? '0 0 0 3px var(--brand-bg)' : 'var(--shadow-xs)',
          color: value ? 'var(--text)' : 'var(--text-tertiary)',
          fontSize: compact ? 12 : 12.5,
          fontWeight: 500,
          cursor: 'pointer',
          textAlign: 'left',
        }}
      >
        <Icon name="calendar" size={compact ? 12 : 13}/>
        <span style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {value ? formatDisplayDate(value) : placeholder}
        </span>
        <Icon name={isOpen ? 'chevronUp' : 'chevronDown'} size={11}/>
      </button>

      {isOpen && popupPosition && createPortal((
        <div
          ref={popupRef}
          style={{
            position: 'fixed',
            top: popupPosition.top,
            left: popupPosition.left,
            zIndex: 1000,
            width: PICKER_WIDTH,
            padding: 10,
            border: '1px solid var(--border)',
            borderRadius: 8,
            background: 'var(--surface)',
            boxShadow: 'var(--shadow-md)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}>
            <button type="button" aria-label="이전 달" onClick={() => moveMonth(-1)} style={pickerIconButton}>
              <Icon name="chevronLeft" size={13}/>
            </button>
            <div style={{ flex: 1, textAlign: 'center', fontSize: 13, fontWeight: 700, color: 'var(--text)' }}>{monthLabel}</div>
            <button type="button" aria-label="다음 달" onClick={() => moveMonth(1)} style={pickerIconButton}>
              <Icon name="chevronRight" size={13}/>
            </button>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 2, marginBottom: 4 }}>
            {WEEKDAYS.map((day, index) => (
              <div
                key={day}
                style={{
                  height: 24,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 10.5,
                  fontWeight: 700,
                  color: index === 0 ? 'var(--danger-fg)' : index === 6 ? 'var(--info-fg)' : 'var(--text-tertiary)',
                }}
              >
                {day}
              </div>
            ))}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 2 }}>
            {cells.map((cell) => {
              const dateValue = formatDateValue(cell.date);
              const isSelected = selectedDate && dateValue === formatDateValue(selectedDate);
              const isToday = dateValue === todayValue;
              return (
                <button
                  key={dateValue}
                  type="button"
                  data-testid={`date-picker-day-${dateValue}`}
                  onClick={() => selectDate(cell.date)}
                  style={{
                    height: 31,
                    border: isSelected ? '1px solid var(--brand)' : '1px solid transparent',
                    borderRadius: 7,
                    background: isSelected ? 'var(--brand)' : isToday ? 'var(--brand-bg)' : 'transparent',
                    color: isSelected ? '#fff' : cell.isCurrentMonth ? 'var(--text)' : 'var(--text-quaternary)',
                    fontSize: 12,
                    fontWeight: isSelected || isToday ? 700 : 500,
                    cursor: 'pointer',
                    fontVariantNumeric: 'tabular-nums',
                  }}
                >
                  {cell.date.getDate()}
                </button>
              );
            })}
          </div>

          <div style={{ marginTop: 10, paddingTop: 8, borderTop: '1px solid var(--divider)', display: 'flex', gap: 6 }}>
            <button type="button" onClick={selectToday} className="btn btn--secondary btn--sm" style={{ flex: 1 }}>
              오늘
            </button>
            <button type="button" onClick={clearDate} className="btn btn--ghost btn--sm" style={{ flex: 1 }}>
              지우기
            </button>
          </div>
        </div>
      ), document.body)}
    </div>
  );
}

function buildMonthCells(viewDate) {
  const year = viewDate.getFullYear();
  const month = viewDate.getMonth();
  const firstDay = new Date(year, month, 1);
  const start = new Date(year, month, 1 - firstDay.getDay());

  return Array.from({ length: 42 }).map((_, index) => {
    const date = new Date(start.getFullYear(), start.getMonth(), start.getDate() + index);
    return {
      date,
      isCurrentMonth: date.getMonth() === month,
    };
  });
}

function formatDisplayDate(value) {
  const date = parseDateValue(value);
  if (!date) {
    return value;
  }

  return `${date.getFullYear()}.${String(date.getMonth() + 1).padStart(2, '0')}.${String(date.getDate()).padStart(2, '0')} ${WEEKDAYS[date.getDay()]}`;
}

const pickerIconButton = {
  width: 28,
  height: 28,
  padding: 0,
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  border: 'none',
  borderRadius: 7,
  background: 'transparent',
  color: 'var(--text-tertiary)',
  cursor: 'pointer',
};

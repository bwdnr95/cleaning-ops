import React from 'react';

import { Icon } from './ui';

export const PAGE_SIZE_OPTIONS = [10, 20, 50, 100];

export function getPageCount(totalItems, pageSize) {
  return Math.max(1, Math.ceil(totalItems / pageSize));
}

export function clampPage(page, totalItems, pageSize) {
  return Math.min(Math.max(1, page), getPageCount(totalItems, pageSize));
}

export function paginateItems(items, page, pageSize) {
  const safePage = clampPage(page, items.length, pageSize);
  const startIndex = (safePage - 1) * pageSize;
  return items.slice(startIndex, startIndex + pageSize);
}

export function PaginationBar({
  totalItems,
  page,
  pageSize,
  onPageChange,
  onPageSizeChange,
  itemLabel = '건',
  testId = 'pagination',
  pageSizeOptions = PAGE_SIZE_OPTIONS,
}) {
  const safePage = clampPage(page, totalItems, pageSize);
  const pageCount = getPageCount(totalItems, pageSize);
  const start = totalItems === 0 ? 0 : (safePage - 1) * pageSize + 1;
  const end = Math.min(totalItems, safePage * pageSize);
  const canGoPrevious = safePage > 1;
  const canGoNext = safePage < pageCount;

  React.useEffect(() => {
    if (page !== safePage) {
      onPageChange(safePage);
    }
  }, [onPageChange, page, safePage]);

  return (
    <div
      data-testid={testId}
      style={{
        minHeight: 44,
        padding: '9px 14px',
        borderTop: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        fontSize: 11.5,
        color: 'var(--text-tertiary)',
        background: 'var(--bg)',
      }}
    >
      <span data-testid={`${testId}-summary`} style={{ fontVariantNumeric: 'tabular-nums' }}>
        {start}-{end} / {totalItems}{itemLabel}
      </span>
      <div style={{ flex: 1 }} />
      <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, whiteSpace: 'nowrap' }}>
        <span>페이지당</span>
        <select
          data-testid={`${testId}-page-size`}
          className="input"
          value={pageSize}
          onChange={(event) => {
            onPageSizeChange(Number(event.target.value));
            onPageChange(1);
          }}
          style={{ width: 76, height: 28, fontSize: 11.5, padding: '0 6px' }}
        >
          {pageSizeOptions.map((option) => (
            <option key={option} value={option}>{option}</option>
          ))}
        </select>
      </label>
      <button
        type="button"
        data-testid={`${testId}-prev`}
        disabled={!canGoPrevious}
        onClick={() => onPageChange(safePage - 1)}
        style={paginationButtonStyle}
        aria-label="이전 페이지"
      >
        <Icon name="chevronLeft" size={11} />
      </button>
      <span data-testid={`${testId}-page`} style={{ minWidth: 48, textAlign: 'center', fontVariantNumeric: 'tabular-nums' }}>
        {safePage} / {pageCount}
      </span>
      <button
        type="button"
        data-testid={`${testId}-next`}
        disabled={!canGoNext}
        onClick={() => onPageChange(safePage + 1)}
        style={paginationButtonStyle}
        aria-label="다음 페이지"
      >
        <Icon name="chevronRight" size={11} />
      </button>
    </div>
  );
}

const paginationButtonStyle = {
  width: 28,
  height: 28,
  border: '1px solid var(--border)',
  borderRadius: 6,
  background: 'var(--surface)',
  color: 'var(--text-secondary)',
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  cursor: 'pointer',
};

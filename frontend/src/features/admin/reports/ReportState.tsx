import React from 'react';

interface Props<T> {
  data: T | null;
  error: string | null;
  empty: boolean;
  children: React.ReactNode;
}

export function ReportState<T>({ data, error, empty, children }: Props<T>) {
  if (error) {
    return (
      <div data-testid="reports-error" style={{ color: 'var(--danger-fg)', padding: 20 }}>
        불러오기 실패: {error}
      </div>
    );
  }
  if (data === null) {
    return <div data-testid="reports-loading" style={{ padding: 20 }}>불러오는 중...</div>;
  }
  if (empty) {
    return (
      <div data-testid="reports-empty" style={{ padding: 20, color: 'var(--text-tertiary)' }}>
        표시할 데이터가 없습니다.
      </div>
    );
  }
  return <>{children}</>;
}

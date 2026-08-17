import React from 'react';

import { importOrders, type ImportResult } from '../../../api/admin';
import { Icon } from '../../../components/common/ui';

interface Props {
  onClose: () => void;
  onImported: () => void;
}

export function OrderImportDialog({ onClose, onImported }: Props) {
  const [file, setFile] = React.useState<File | null>(null);
  const [result, setResult] = React.useState<ImportResult | null>(null);
  const [isUploading, setIsUploading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const handleSubmit = async () => {
    if (!file) {
      return;
    }

    setIsUploading(true);
    setError(null);
    try {
      const response = await importOrders(file);
      setResult(response);
      if (response.succeeded_groups > 0) {
        onImported();
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : String(requestError));
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div
      data-testid="order-import-dialog"
      role="dialog"
      aria-modal="true"
      aria-labelledby="order-import-title"
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 1000,
        background: 'rgba(15, 23, 42, 0.38)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 20,
      }}
    >
      <div
        className="card"
        onClick={(event) => event.stopPropagation()}
        style={{
          width: 'min(560px, 100%)',
          maxHeight: 'min(720px, calc(100vh - 40px))',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--divider)', display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div id="order-import-title" style={{ fontSize: 14, fontWeight: 700 }}>주문 일괄 등록</div>
            <div style={{ marginTop: 3, fontSize: 11.5, color: 'var(--text-tertiary)' }}>
              xlsx 파일의 같은 group_key 행은 하나의 주문 그룹으로 등록됩니다.
            </div>
          </div>
          <button type="button" className="btn btn--ghost btn--sm" onClick={onClose} aria-label="닫기" style={{ padding: '0 6px' }}>
            <Icon name="x" size={14}/>
          </button>
        </div>

        <div className="scroll" style={{ padding: 16, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{ padding: 12, border: '1px solid var(--border)', borderRadius: 8, background: 'var(--bg-subtle)', color: 'var(--text-secondary)', fontSize: 12, lineHeight: 1.55 }}>
            <div style={{ fontWeight: 700, color: 'var(--text)', marginBottom: 4 }}>필수 컬럼</div>
            <div className="mono" style={{ wordBreak: 'break-word' }}>
              group_key, customer_name, customer_phone, customer_address, scheduled_date, service_name, total_amount
            </div>
            <div style={{ marginTop: 8, fontWeight: 700, color: 'var(--text)' }}>여러 방문일(선택)</div>
            <div className="mono" style={{ wordBreak: 'break-word' }}>visit_dates</div>
            <div style={{ marginTop: 3, color: 'var(--text-tertiary)' }}>
              여러 날짜는 쉼표, 세미콜론 또는 줄바꿈으로 구분하세요. 생략하면 scheduled_date가 방문일로 등록됩니다.
            </div>
            <div style={{ marginTop: 8, color: 'var(--text-tertiary)' }}>
              한 그룹 안에서 일부 행이 실패하면 그 group_key 전체가 등록되지 않고 실패 목록에 표시됩니다.
            </div>
          </div>

          <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span style={{ fontSize: 11.5, color: 'var(--text-tertiary)', fontWeight: 700 }}>업로드 파일</span>
            <input
              data-testid="order-import-file"
              type="file"
              accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              onChange={(event) => {
                setFile(event.target.files?.[0] ?? null);
                setResult(null);
                setError(null);
              }}
            />
          </label>

          {error && (
            <div style={{ padding: 10, borderRadius: 6, background: 'var(--danger-bg)', color: 'var(--danger-fg)', fontSize: 12 }}>
              {error}
            </div>
          )}

          {result && (
            <div style={{ padding: 12, border: '1px solid var(--border)', borderRadius: 8, fontSize: 12.5 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--success-fg)', fontWeight: 700 }}>
                <Icon name="check" size={14}/>
                등록 완료: 그룹 {result.succeeded_groups.toLocaleString()}개 / 라인 {result.succeeded_lines.toLocaleString()}개
              </div>
              {result.failed.length > 0 && (
                <details style={{ marginTop: 10 }}>
                  <summary style={{ cursor: 'pointer', color: 'var(--warn-fg)', fontWeight: 700 }}>
                    실패 {result.failed.length.toLocaleString()}건
                  </summary>
                  <ul style={{ margin: '8px 0 0', paddingLeft: 18, color: 'var(--text-secondary)', lineHeight: 1.55 }}>
                    {result.failed.map((failure, index) => (
                      <li key={`${failure.row_index}-${index}`}>
                        {formatFailureRow(failure.row_index)}: {failure.reason}
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </div>
          )}
        </div>

        <div style={{ padding: '12px 16px', borderTop: '1px solid var(--divider)', display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
          <button type="button" className="btn btn--secondary btn--sm" onClick={onClose}>
            닫기
          </button>
          <button
            type="button"
            data-testid="order-import-submit"
            className="btn btn--primary btn--sm"
            disabled={!file || isUploading}
            onClick={() => void handleSubmit()}
          >
            {isUploading ? '업로드 중' : '업로드'}
          </button>
        </div>
      </div>
    </div>
  );
}

function formatFailureRow(rowIndex: number) {
  if (rowIndex === 0) {
    return '헤더';
  }
  return `${rowIndex}행`;
}

import React from 'react';

import { exportReport } from '../../../api/reports';

interface Props {
  name: 'revenue' | 'partners' | 'services' | 'source-channels' | 'settlements';
  params: Record<string, string>;
}

export function ExportButtons({ name, params }: Props) {
  const [isExporting, setIsExporting] = React.useState<'csv' | 'xlsx' | null>(null);

  const handleExport = async (format: 'csv' | 'xlsx') => {
    setIsExporting(format);
    try {
      await exportReport(name, params, format);
    } catch (error) {
      window.alert(`다운로드 실패: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setIsExporting(null);
    }
  };

  return (
    <div style={{ display: 'flex', gap: 6 }}>
      <button
        data-testid={`reports-${name}-export-csv`}
        className="btn btn--secondary btn--sm"
        disabled={isExporting !== null}
        onClick={() => void handleExport('csv')}
      >
        {isExporting === 'csv' ? '...' : 'CSV'}
      </button>
      <button
        data-testid={`reports-${name}-export-xlsx`}
        className="btn btn--secondary btn--sm"
        disabled={isExporting !== null}
        onClick={() => void handleExport('xlsx')}
      >
        {isExporting === 'xlsx' ? '...' : 'Excel'}
      </button>
    </div>
  );
}

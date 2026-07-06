import React from 'react';

import { fetchSourceChannels, type SourceChannelReport } from '../../../api/reports';
import { ExportButtons } from './ExportButtons';
import { ReportState } from './ReportState';
import { SourceChannelTable } from './SourceChannelTable';

interface Props {
  range: { start_date: string; end_date: string };
}

export function SourceChannelsView({ range }: Props) {
  const [report, setReport] = React.useState<SourceChannelReport | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let isCurrent = true;
    setReport(null);
    setError(null);
    fetchSourceChannels(range)
      .then((nextReport) => {
        if (isCurrent) {
          setReport(nextReport);
        }
      })
      .catch((requestError) => {
        if (isCurrent) {
          setReport(null);
          setError(requestError instanceof Error ? requestError.message : String(requestError));
        }
      });
    return () => {
      isCurrent = false;
    };
  }, [range]);

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
        <div style={{ fontSize: 12, marginRight: 12 }}>
          {report && (
            <>
              <strong>총 매출: {formatWon(report.total_revenue)}</strong>
              <span style={{ marginLeft: 14, color: 'var(--text-tertiary)' }}>
                주문 {report.total_orders}건 · 완료 {report.total_completed}건
              </span>
            </>
          )}
        </div>
        <ExportButtons name="source-channels" params={range} />
      </div>
      <ReportState data={report} error={error} empty={!!report && report.rows.length === 0}>
        <SourceChannelTable rows={report?.rows ?? []} />
      </ReportState>
    </>
  );
}

function formatWon(value: string | number) {
  return `${Number(value || 0).toLocaleString()}원`;
}

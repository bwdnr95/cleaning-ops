import React from 'react';

import { fetchSettlements, type SettlementBacklogReport } from '../../../api/reports';
import { ExportButtons } from './ExportButtons';
import { ReportState } from './ReportState';
import { ReportToolbarEnd } from './ReportToolbarEnd';
import { SettlementBacklogTable } from './SettlementBacklogTable';

export function SettlementsView() {
  const [report, setReport] = React.useState<SettlementBacklogReport | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let isCurrent = true;
    setReport(null);
    setError(null);
    fetchSettlements()
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
  }, []);

  return (
    <>
      <ReportToolbarEnd>
        <ExportButtons name="settlements" params={{}} />
      </ReportToolbarEnd>
      <ReportState data={report} error={error} empty={!!report && report.rows.length === 0}>
        <SettlementBacklogTable rows={report?.rows ?? []} />
      </ReportState>
    </>
  );
}

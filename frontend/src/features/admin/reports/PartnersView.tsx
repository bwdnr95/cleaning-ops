import React from 'react';

import { fetchPartners, type PartnerPerformanceReport } from '../../../api/reports';
import { ExportButtons } from './ExportButtons';
import { PartnerPerformanceTable } from './PartnerPerformanceTable';
import { ReportState } from './ReportState';
import { ReportToolbarEnd } from './ReportToolbarEnd';

interface Props {
  range: { start_date: string; end_date: string };
}

export function PartnersView({ range }: Props) {
  const [report, setReport] = React.useState<PartnerPerformanceReport | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let isCurrent = true;
    setReport(null);
    setError(null);
    fetchPartners(range)
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
      <ReportToolbarEnd>
        <ExportButtons name="partners" params={range} />
      </ReportToolbarEnd>
      <ReportState data={report} error={error} empty={!!report && report.rows.length === 0}>
        <PartnerPerformanceTable rows={report?.rows ?? []} />
      </ReportState>
    </>
  );
}

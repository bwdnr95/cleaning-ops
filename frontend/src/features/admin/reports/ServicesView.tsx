import React from 'react';

import { fetchServices, type ServicePopularityReport } from '../../../api/reports';
import { ExportButtons } from './ExportButtons';
import { ReportState } from './ReportState';
import { ReportToolbarEnd } from './ReportToolbarEnd';
import { ServicePopularityTable } from './ServicePopularityTable';

interface Props {
  range: { start_date: string; end_date: string };
}

export function ServicesView({ range }: Props) {
  const [report, setReport] = React.useState<ServicePopularityReport | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let isCurrent = true;
    setReport(null);
    setError(null);
    fetchServices(range)
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
        <ExportButtons name="services" params={range} />
      </ReportToolbarEnd>
      <ReportState data={report} error={error} empty={!!report && report.rows.length === 0}>
        <ServicePopularityTable rows={report?.rows ?? []} />
      </ReportState>
    </>
  );
}

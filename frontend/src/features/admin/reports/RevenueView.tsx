import React from 'react';

import { listPartners, listServiceItems } from '../../../api/admin';
import { fetchRevenue, type RevenueReport } from '../../../api/reports';
import { ExportButtons } from './ExportButtons';
import { ReportState } from './ReportState';
import { RevenueChart } from './RevenueChart';

interface Props {
  range: { start_date: string; end_date: string };
  granularity: 'day' | 'week' | 'month';
}

interface SelectOption {
  id: string;
  name: string;
}

export function RevenueView({ range, granularity }: Props) {
  const [report, setReport] = React.useState<RevenueReport | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [partners, setPartners] = React.useState<SelectOption[]>([]);
  const [services, setServices] = React.useState<SelectOption[]>([]);
  const [partnerId, setPartnerId] = React.useState('');
  const [serviceItemId, setServiceItemId] = React.useState('');

  React.useEffect(() => {
    listPartners()
      .then((rows: SelectOption[]) => setPartners((rows ?? []).map((row) => ({ id: row.id, name: row.name }))))
      .catch(() => setPartners([]));
    listServiceItems()
      .then((rows) => setServices(rows ?? []))
      .catch(() => setServices([]));
  }, []);

  const params = React.useMemo(() => {
    const next: Record<string, string> = { ...range, granularity };
    if (partnerId) {
      next.partner_id = partnerId;
    }
    if (serviceItemId) {
      next.service_item_id = serviceItemId;
    }
    return next;
  }, [granularity, partnerId, range, serviceItemId]);

  React.useEffect(() => {
    let isCurrent = true;
    setReport(null);
    setError(null);
    fetchRevenue(params)
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
  }, [params]);

  return (
    <>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <select
          data-testid="reports-revenue-partner-filter"
          className="input"
          value={partnerId}
          onChange={(event) => setPartnerId(event.target.value)}
          style={{ height: 30, minWidth: 150 }}
        >
          <option value="">전체 협력사</option>
          {partners.map((partner) => (
            <option key={partner.id} value={partner.id}>
              {partner.name}
            </option>
          ))}
        </select>
        <select
          data-testid="reports-revenue-service-filter"
          className="input"
          value={serviceItemId}
          onChange={(event) => setServiceItemId(event.target.value)}
          style={{ height: 30, minWidth: 150 }}
        >
          <option value="">전체 서비스</option>
          {services.map((service) => (
            <option key={service.id} value={service.id}>
              {service.name}
            </option>
          ))}
        </select>
        <div style={{ flex: 1 }} />
        {report && (
          <div style={{ fontSize: 12 }}>
            <strong>총 매출: {formatWon(report.total_revenue)}</strong>
            <span style={{ marginLeft: 14, color: 'var(--text-tertiary)' }}>
              완료 {report.total_completed}건
            </span>
          </div>
        )}
        <ExportButtons name="revenue" params={params} />
      </div>
      <ReportState data={report} error={error} empty={!!report && report.buckets.length === 0}>
        <RevenueChart
          data={(report?.buckets ?? []).map((bucket) => ({
            period: bucket.period,
            revenue: Number(bucket.revenue),
            completed_count: bucket.completed_count,
          }))}
        />
      </ReportState>
    </>
  );
}

function formatWon(value: string | number) {
  return `${Number(value || 0).toLocaleString()}원`;
}

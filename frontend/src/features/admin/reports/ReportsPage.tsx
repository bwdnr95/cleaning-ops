import React from 'react';

import { listPartners, listServiceItems } from '../../../api/admin';
import {
  fetchPartners,
  fetchRevenue,
  fetchServices,
  fetchSettlements,
  type PartnerPerformanceReport,
  type RevenueReport,
  type ServicePopularityReport,
  type SettlementBacklogReport,
} from '../../../api/reports';
import { ExportButtons } from './ExportButtons';
import { PartnerPerformanceTable } from './PartnerPerformanceTable';
import { RevenueChart } from './RevenueChart';
import { ServicePopularityTable } from './ServicePopularityTable';
import { SettlementBacklogTable } from './SettlementBacklogTable';

const TABS = [
  { key: 'revenue', label: '매출 추세' },
  { key: 'partners', label: '협력사 성과' },
  { key: 'services', label: '서비스 인기' },
  { key: 'settlements', label: '정산 대기' },
] as const;

type TabKey = (typeof TABS)[number]['key'];

interface SelectOption {
  id: string;
  name: string;
}

function defaultRange() {
  const today = new Date();
  const start = new Date(today.getFullYear(), today.getMonth() - 5, 1);
  const end = new Date(today.getFullYear(), today.getMonth() + 1, 0);
  return { start_date: formatDate(start), end_date: formatDate(end) };
}

export function ReportsPage() {
  const [tab, setTab] = React.useState<TabKey>('revenue');
  const [range, setRange] = React.useState(defaultRange);
  const [granularity, setGranularity] = React.useState<'day' | 'week' | 'month'>('month');

  return (
    <div
      data-testid="admin-reports-page"
      style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, background: 'var(--bg)' }}
    >
      <div
        style={{
          padding: '12px 20px',
          display: 'flex',
          gap: 8,
          alignItems: 'center',
          flexWrap: 'wrap',
          borderBottom: '1px solid var(--border)',
          background: 'var(--surface)',
        }}
      >
        {TABS.map((item) => (
          <button
            key={item.key}
            data-testid={`reports-tab-${item.key}`}
            className={tab === item.key ? 'btn btn--primary btn--sm' : 'btn btn--ghost btn--sm'}
            onClick={() => setTab(item.key)}
          >
            {item.label}
          </button>
        ))}
        <div style={{ flex: 1 }} />
        {tab !== 'settlements' && (
          <>
            <input
              data-testid="reports-start-date"
              className="input"
              type="date"
              value={range.start_date}
              onChange={(event) => setRange({ ...range, start_date: event.target.value })}
              style={{ height: 28, width: 136 }}
            />
            <span style={{ color: 'var(--text-tertiary)', fontSize: 12 }}>~</span>
            <input
              data-testid="reports-end-date"
              className="input"
              type="date"
              value={range.end_date}
              onChange={(event) => setRange({ ...range, end_date: event.target.value })}
              style={{ height: 28, width: 136 }}
            />
          </>
        )}
        {tab === 'revenue' && (
          <select
            data-testid="reports-granularity"
            className="input"
            value={granularity}
            onChange={(event) => setGranularity(event.target.value as 'day' | 'week' | 'month')}
            style={{ height: 28, width: 96 }}
          >
            <option value="day">일</option>
            <option value="week">주</option>
            <option value="month">월</option>
          </select>
        )}
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: 20 }}>
        {tab === 'revenue' && <RevenueView range={range} granularity={granularity} />}
        {tab === 'partners' && <PartnersView range={range} />}
        {tab === 'services' && <ServicesView range={range} />}
        {tab === 'settlements' && <SettlementsView />}
      </div>
    </div>
  );
}

function RevenueView({
  range,
  granularity,
}: {
  range: { start_date: string; end_date: string };
  granularity: 'day' | 'week' | 'month';
}) {
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

function PartnersView({ range }: { range: { start_date: string; end_date: string } }) {
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
      <ToolbarEnd>
        <ExportButtons name="partners" params={range} />
      </ToolbarEnd>
      <ReportState data={report} error={error} empty={!!report && report.rows.length === 0}>
        <PartnerPerformanceTable rows={report?.rows ?? []} />
      </ReportState>
    </>
  );
}

function ServicesView({ range }: { range: { start_date: string; end_date: string } }) {
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
      <ToolbarEnd>
        <ExportButtons name="services" params={range} />
      </ToolbarEnd>
      <ReportState data={report} error={error} empty={!!report && report.rows.length === 0}>
        <ServicePopularityTable rows={report?.rows ?? []} />
      </ReportState>
    </>
  );
}

function SettlementsView() {
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
      <ToolbarEnd>
        <ExportButtons name="settlements" params={{}} />
      </ToolbarEnd>
      <ReportState data={report} error={error} empty={!!report && report.rows.length === 0}>
        <SettlementBacklogTable rows={report?.rows ?? []} />
      </ReportState>
    </>
  );
}

function ReportState<T>({
  data,
  error,
  empty,
  children,
}: {
  data: T | null;
  error: string | null;
  empty: boolean;
  children: React.ReactNode;
}) {
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

function ToolbarEnd({ children }: { children: React.ReactNode }) {
  return <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>{children}</div>;
}

function formatWon(value: string | number) {
  return `${Number(value || 0).toLocaleString()}원`;
}

function formatDate(value: Date) {
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`;
}

import React from 'react';

import { PartnersView } from './PartnersView';
import { RevenueView } from './RevenueView';
import { ServicesView } from './ServicesView';
import { SettlementsView } from './SettlementsView';
import { SourceChannelsView } from './SourceChannelsView';

const TABS = [
  { key: 'revenue', label: '매출 추세' },
  { key: 'partners', label: '협력사 성과' },
  { key: 'services', label: '서비스 인기' },
  { key: 'source_channels', label: '유입경로' },
  { key: 'settlements', label: '정산 대기' },
] as const;

type TabKey = (typeof TABS)[number]['key'];

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
        className="page-shell"
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
        <div className="page-shell">
          {tab === 'revenue' && <RevenueView range={range} granularity={granularity} />}
          {tab === 'partners' && <PartnersView range={range} />}
          {tab === 'services' && <ServicesView range={range} />}
          {tab === 'source_channels' && <SourceChannelsView range={range} />}
          {tab === 'settlements' && <SettlementsView />}
        </div>
      </div>
    </div>
  );
}

function formatDate(value: Date) {
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`;
}

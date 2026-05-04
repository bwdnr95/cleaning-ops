import React from 'react';
import { Avatar, Icon } from '../../../components/common/ui';
import { ORDERS } from '../../../mocks/cleaningOpsData';
import { listAdminOrders } from '../../../api/admin';
import { useApiResource } from '../../../api/useApiResource';

// Orders list v3 — modern Linear/Attio style: airy, typographic, low-chrome

// status → soft dot color (used in dot-style badge)
const STATUS_DOT = {
  '신규접수':     '#94a3b8',
  '상담중':       '#8b5cf6',
  '협력사확인중': '#f59e0b',
  '일정확정':     '#3b82f6',
  '전날안내필요': '#f59e0b',
  '전날안내완료': '#3b82f6',
  '작업예정':     '#3b82f6',
  '작업진행':     '#4f46e5',
  '사진검수대기': '#f59e0b',
  '고객전달필요': '#f59e0b',
  '고객전달완료': '#10b981',
  '서비스완료':   '#10b981',
  '취소':         '#cbd5e1',
};

function StatusDot({ status }) {
  const color = STATUS_DOT[status] || '#94a3b8';
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)',
      whiteSpace: 'nowrap',
    }}>
      <span style={{
        width: 7, height: 7, borderRadius: '50%',
        background: color, flexShrink: 0,
        boxShadow: `0 0 0 3px ${color}1a`,
      }}/>
      {status}
    </span>
  );
}

function PaidPill({ paid, isUnpaid }) {
  const map = {
    paid:    { label: '완납',   color: '#059669' },
    partial: { label: '계약금', color: '#0891b2' },
    pending: { label: isUnpaid ? '미수' : '대기', color: isUnpaid ? '#dc2626' : '#94a3b8' },
    refund:  { label: '환불',   color: '#dc2626' },
  };
  const c = map[paid];
  if (!c) return <span style={{ color: 'var(--text-quaternary)' }}>—</span>;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      fontSize: 11.5, fontWeight: 500, color: c.color,
    }}>
      <span style={{ width: 5, height: 5, borderRadius: '50%', background: c.color }}/>
      {c.label}
    </span>
  );
}

function SimplePill({ kind, value }) {
  const photo = {
    none:     null,
    partial:  { label: '진행', color: '#3b82f6' },
    wait:     { label: '검수', color: '#f59e0b' },
    approved: { label: '승인', color: '#10b981' },
  };
  const deliver = {
    pending:   { label: '대기', color: '#94a3b8' },
    done:      { label: '전달', color: '#10b981' },
    cancelled: null,
  };
  const map = kind === 'photo' ? photo : deliver;
  const c = map[value];
  if (!c) return <span style={{ color: 'var(--text-quaternary)' }}>—</span>;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      fontSize: 11.5, fontWeight: 500, color: c.color,
    }}>
      <span style={{ width: 5, height: 5, borderRadius: '50%', background: c.color }}/>
      {c.label}
    </span>
  );
}

export function OrdersPage({ onOpenOrder, onCreateOrder }) {
  const ordersResource = useApiResource(listAdminOrders);
  const orders = ordersResource.data ? ordersResource.data.map(toOrderRow) : ORDERS;
  const [tab, setTab] = React.useState('all');
  const [selected, setSelected] = React.useState(new Set());
  const [hoverRow, setHoverRow] = React.useState(null);
  const [sortBy, setSortBy] = React.useState('visit');
  const statusTabs = getStatusTabs(orders);

  const toggleRow = (id) => {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id); else next.add(id);
    setSelected(next);
  };

  const filtered = orders.filter((o) => {
    if (tab === 'today') return ['작업진행', '작업예정', '사진검수대기'].includes(o.status);
    if (tab === 'pending') return ['신규접수', '상담중', '협력사확인중'].includes(o.status);
    if (tab === 'work') return ['일정확정', '전날안내필요', '전날안내완료', '작업예정', '작업진행', '사진검수대기'].includes(o.status);
    if (tab === 'deliver') return ['고객전달필요'].includes(o.status);
    if (tab === 'done') return ['고객전달완료', '서비스완료'].includes(o.status);
    if (tab === 'cancel') return o.status === '취소';
    return true;
  });

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, background: 'var(--bg)' }}>
      {/* Insight line — typographic, no card chrome */}
      <div style={{
        padding: '18px 24px 14px',
        background: 'var(--bg)',
        display: 'flex', alignItems: 'center', gap: 24,
      }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 18, flex: 1, flexWrap: 'wrap' }}>
          <Insight num={statusTabs.find((item) => item.key === 'today')?.count ?? 0} label="오늘 작업" />
          <InsightDivider/>
          <Insight num={orders.filter((order) => order.team === '미배정').length} label="미배정" warn />
          <InsightDivider/>
          <Insight num={orders.filter((order) => order.status === '사진검수대기').length} label="검수 대기" />
          <InsightDivider/>
          <Insight num={orders.filter((order) => order.status === '고객전달필요').length} label="고객 전달" />
          <InsightDivider/>
          <Insight num={formatCompactWon(orders.filter((order) => order.paid === 'pending').reduce((sum, order) => sum + order.amount, 0))} label="미수금" danger/>
          <InsightDivider/>
          <Insight num={formatCompactWon(orders.reduce((sum, order) => sum + order.amount, 0))} label="이번 달" muted/>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <button className="btn btn--secondary btn--sm">
            <Icon name="fileText" size={12}/> 내보내기
          </button>
          <button className="btn btn--primary btn--sm" onClick={onCreateOrder}>
            <Icon name="plus" size={12}/> 신규 주문
          </button>
        </div>
      </div>

      {/* Toolbar — search, filters, tabs in one airy row */}
      <div style={{
        padding: '0 24px 12px',
        background: 'var(--bg)',
        display: 'flex', alignItems: 'center', gap: 8,
      }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '0 10px', height: 30,
          background: 'var(--surface)',
          border: '1px solid var(--border)', borderRadius: 8,
          minWidth: 240, color: 'var(--text-tertiary)', fontSize: 12,
          boxShadow: 'var(--shadow-xs)',
        }}>
          <Icon name="search" size={13}/>
          <span>검색</span>
          <span style={{
            marginLeft: 'auto',
            fontSize: 10.5, color: 'var(--text-quaternary)',
            padding: '1px 5px', border: '1px solid var(--border)', borderRadius: 4,
          }}>⌘K</span>
        </div>
        <SoftChip label="이번 달"   />
        <SoftChip label="협력사 전체" />
        <SoftChip label="결제 전체"   />
        <button style={softGhostBtn}>
          <Icon name="plus" size={11}/> 필터
        </button>
        <div style={{ flex: 1 }}/>
        <button style={softGhostBtn} onClick={() => setSortBy(sortBy === 'visit' ? 'received' : 'visit')}>
          <Icon name="list" size={11}/> {sortBy === 'visit' ? '방문일순' : '접수일순'}
        </button>
      </div>

      {/* Tabs — minimal underline */}
      <div style={{
        padding: '0 24px',
        borderBottom: '1px solid var(--border)',
        display: 'flex', gap: 2,
      }}>
        {statusTabs.map((t) => {
          const active = tab === t.key;
          return (
            <button key={t.key} onClick={() => setTab(t.key)}
              style={{
                position: 'relative',
                padding: '10px 12px',
                border: 'none', background: 'transparent',
                fontSize: 12.5, fontWeight: 500,
                color: active ? 'var(--text)' : 'var(--text-tertiary)',
                cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: 6,
              }}>
              {t.label}
              <span style={{
                fontSize: 10.5, fontWeight: 500,
                color: active ? 'var(--text-secondary)' : 'var(--text-quaternary)',
              }}>{t.count}</span>
              {active && <span style={{
                position: 'absolute', left: 8, right: 8, bottom: -1,
                height: 2, background: 'var(--text)', borderRadius: 1,
              }}/>}
            </button>
          );
        })}
      </div>

      {/* Selection bar */}
      {selected.size > 0 && (
        <div style={{
          padding: '8px 24px',
          background: 'var(--bg)',
          borderBottom: '1px solid var(--border)',
          display: 'flex', alignItems: 'center', gap: 10, fontSize: 12,
        }}>
          <span style={{ fontWeight: 500, color: 'var(--text)' }}>{selected.size}건 선택</span>
          <span style={{ color: 'var(--text-quaternary)' }}>·</span>
          <button style={softGhostBtn}>상태 변경</button>
          <button style={softGhostBtn}>메시지</button>
          <button style={softGhostBtn}>협력사 배정</button>
          <div style={{ flex: 1 }}/>
          <button style={softGhostBtn} onClick={() => setSelected(new Set())}>해제</button>
        </div>
      )}

      {/* Table — airy, no inner borders, hover float */}
      <div className="scroll" style={{ flex: 1, overflow: 'auto', padding: '4px 12px 20px' }}>
        {ordersResource.isLoading && <ListNotice text="주문 목록을 불러오는 중입니다." />}
        {!ordersResource.isLoading && ordersResource.error && <ListNotice text="주문 목록을 불러오지 못했습니다." tone="danger" />}
        {!ordersResource.isLoading && !ordersResource.error && filtered.length === 0 && <ListNotice text="표시할 주문이 없습니다." />}
        <table className="table-modern" style={{ minWidth: 1500 }}>
          <colgroup>
            <col style={{ width: 36 }}/>
            <col style={{ width: 130 }}/>
            <col style={{ width: 100 }}/>
            <col style={{ width: 150 }}/>
            <col/>
            <col/>
            <col style={{ width: 80 }}/>
            <col style={{ width: 110 }}/>
            <col style={{ width: 120 }}/>
            <col style={{ width: 110, textAlign: 'right' }}/>
            <col style={{ width: 70 }}/>
            <col style={{ width: 70 }}/>
            <col style={{ width: 80 }}/>
            <col style={{ width: 50 }}/>
          </colgroup>
          <thead>
            <tr>
              <th style={{ paddingRight: 0 }}>
                <input type="checkbox" style={{ margin: 0 }} onChange={(e) => {
                  setSelected(e.target.checked ? new Set(filtered.map((o) => o.id)) : new Set());
                }}/>
              </th>
              <th>상태</th>
              <th>주문번호</th>
              <th>방문일</th>
              <th>상품</th>
              <th>주소</th>
              <th>고객</th>
              <th>연락처</th>
              <th>담당팀</th>
              <th style={{ textAlign: 'right' }}>금액</th>
              <th>결제</th>
              <th>사진</th>
              <th>고객전달</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {!ordersResource.isLoading && !ordersResource.error && filtered.map((o) => {
              const isUnassigned = o.team === '미배정';
              const isUnpaid = o.paid === 'pending' && o.amount > 0 && !['취소', '신규접수', '상담중'].includes(o.status);
              const isCancelled = o.status === '취소';
              return (
                <tr key={o.id}
                  className={[
                    selected.has(o.id) ? 'is-selected' : '',
                    isCancelled ? 'is-muted' : '',
                  ].join(' ')}
                  onMouseEnter={() => setHoverRow(o.id)}
                  onMouseLeave={() => setHoverRow(null)}
                  onClick={() => onOpenOrder && onOpenOrder(o.id)}
                  style={{ cursor: 'pointer' }}>
                  <td onClick={(e) => e.stopPropagation()} style={{ paddingRight: 0 }}>
                    <input type="checkbox" checked={selected.has(o.id)}
                      onChange={() => toggleRow(o.id)} style={{ margin: 0 }}/>
                  </td>
                  <td><StatusDot status={o.status}/></td>
                  <td className="mono" style={{ fontSize: 11.5, color: 'var(--text-tertiary)' }}>{o.id}</td>
                  <td style={{ fontWeight: 500 }}>
                    {o.visit === '미정'
                      ? <span style={{ color: 'var(--text-quaternary)', fontWeight: 400 }}>미정</span>
                      : <span style={{ display: 'inline-flex', alignItems: 'baseline', gap: 6, whiteSpace: 'nowrap' }}>
                          <span>{o.visit}</span>
                          <span style={{ color: 'var(--text-quaternary)', fontWeight: 400, fontSize: 11 }}>{o.timeWindow}</span>
                        </span>}
                  </td>
                  <td>
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', display: 'block' }}>{o.product}</span>
                  </td>
                  <td style={{ color: 'var(--text-tertiary)', maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 12 }} title={o.address}>{o.address}</td>
                  <td>{o.customer}</td>
                  <td className="mono" style={{ fontSize: 11.5, color: 'var(--text-tertiary)' }}>{o.phone}</td>
                  <td>
                    {isUnassigned
                      ? <span style={{
                          fontSize: 12, fontWeight: 500, color: '#b45309',
                          display: 'inline-flex', alignItems: 'center', gap: 5,
                        }}>
                          <span style={{ width: 5, height: 5, borderRadius: '50%', background: '#f59e0b' }}/>
                          미배정
                        </span>
                      : <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                          <Avatar name={o.team[0]} size={18} tone="info"/>
                          <span style={{ fontSize: 12 }}>{o.team}</span>
                        </span>}
                  </td>
                  <td style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums', fontWeight: 600 }}>
                    {o.amount === 0
                      ? <span style={{ color: 'var(--text-quaternary)', fontWeight: 400 }}>—</span>
                      : `₩${o.amount.toLocaleString()}`}
                  </td>
                  <td><PaidPill paid={o.paid} isUnpaid={isUnpaid}/></td>
                  <td><SimplePill kind="photo" value={o.photo}/></td>
                  <td><SimplePill kind="deliver" value={o.delivered}/></td>
                  <td onClick={(e) => e.stopPropagation()} style={{ textAlign: 'right' }}>
                    {hoverRow === o.id ? (
                      <div style={{ display: 'inline-flex', gap: 1 }}>
                        <button style={iconBtn} title="메시지"><Icon name="send" size={12}/></button>
                        <button style={iconBtn} title="사진"><Icon name="image" size={12}/></button>
                        <button style={iconBtn} title="더보기"><Icon name="moreHorizontal" size={13}/></button>
                      </div>
                    ) : (
                      <button style={{ ...iconBtn, opacity: 0.4 }}>
                        <Icon name="moreHorizontal" size={13}/>
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Footer */}
      <div style={{
        padding: '10px 24px',
        borderTop: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: 10,
        fontSize: 11.5, color: 'var(--text-tertiary)',
        background: 'var(--bg)',
      }}>
        <span>{filtered.length}건 표시 · 50건/페이지</span>
        <div style={{ flex: 1 }}/>
        <button style={iconBtn}><Icon name="chevronLeft" size={11}/></button>
        <span style={{ fontVariantNumeric: 'tabular-nums' }}>1 / 4</span>
        <button style={iconBtn}><Icon name="chevronRight" size={11}/></button>
      </div>
    </div>
  );
}

function Insight({ num, label, warn = false, danger = false, muted = false }) {
  const numColor = danger ? '#dc2626' : warn ? '#b45309' : muted ? 'var(--text-secondary)' : 'var(--text)';
  return (
    <span style={{ display: 'inline-flex', alignItems: 'baseline', gap: 6 }}>
      <span style={{
        fontSize: 18, fontWeight: 600,
        color: numColor,
        letterSpacing: '-0.02em',
        fontVariantNumeric: 'tabular-nums',
      }}>{num}</span>
      <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>{label}</span>
    </span>
  );
}

function InsightDivider() {
  return <span style={{ width: 1, height: 14, background: 'var(--border)', alignSelf: 'center' }}/>;
}

function ListNotice({ text, tone = 'muted' }) {
  return (
    <div style={{
      padding: '18px 12px',
      color: tone === 'danger' ? 'var(--danger-fg)' : 'var(--text-tertiary)',
      fontSize: 12.5,
    }}>
      {text}
    </div>
  );
}

function getStatusTabs(orders) {
  return [
    { key: 'all', label: '전체', count: orders.length },
    { key: 'today', label: '오늘 작업', count: orders.filter((o) => ['작업진행', '작업예정', '사진검수대기'].includes(o.status)).length },
    { key: 'pending', label: '확인 대기', count: orders.filter((o) => ['신규접수', '상담중', '협력사확인중'].includes(o.status)).length },
    { key: 'work', label: '작업/검수', count: orders.filter((o) => ['일정확정', '전날안내필요', '전날안내완료', '작업예정', '작업진행', '사진검수대기'].includes(o.status)).length },
    { key: 'deliver', label: '고객 전달', count: orders.filter((o) => ['고객전달필요'].includes(o.status)).length },
    { key: 'done', label: '완료', count: orders.filter((o) => ['고객전달완료', '서비스완료'].includes(o.status)).length },
    { key: 'cancel', label: '취소', count: orders.filter((o) => o.status === '취소').length },
  ];
}

function toOrderRow(order) {
  return {
    id: order.id,
    status: order.status,
    received: formatDate(order.received_date),
    visit: formatDate(order.scheduled_date) || '미정',
    timeWindow: order.requested_time || '-',
    team: order.team_name || '미배정',
    product: order.size_or_quantity ? `${order.service_name} (${order.size_or_quantity})` : order.service_name,
    address: order.customer_address,
    customer: order.customer_name,
    phone: maskPhone(order.customer_phone),
    amount: Number(order.total_amount || 0),
    paid: toPaidState(order.payment_status),
    photo: toPhotoState(order.status),
    delivered: toDeliveredState(order.status),
  };
}

function formatDate(value) {
  if (!value) {
    return '';
  }

  const date = new Date(`${value}T00:00:00`);
  return `${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

function maskPhone(phone) {
  if (!phone) {
    return '';
  }
  const digits = phone.replace(/\D/g, '');
  if (digits.length < 8) {
    return phone;
  }
  return `${digits.slice(0, 3)}-${digits.slice(3, 4)}***-${digits.slice(-4)}`;
}

function toPaidState(status) {
  if (['paid', 'complete', 'completed', 'deposit_paid'].includes(status)) {
    return status === 'deposit_paid' ? 'partial' : 'paid';
  }
  if (['refund', 'refunded'].includes(status)) {
    return 'refund';
  }
  return 'pending';
}

function toPhotoState(status) {
  if (status === '사진검수대기') {
    return 'wait';
  }
  if (['고객전달필요', '고객전달완료', '서비스완료'].includes(status)) {
    return 'approved';
  }
  if (status === '작업진행') {
    return 'partial';
  }
  return 'none';
}

function toDeliveredState(status) {
  if (status === '취소') {
    return 'cancelled';
  }
  if (['고객전달완료', '서비스완료'].includes(status)) {
    return 'done';
  }
  return 'pending';
}

function formatCompactWon(value) {
  const amount = Number(value || 0);
  if (amount >= 100000000) {
    return `₩${(amount / 100000000).toFixed(1)}억`;
  }
  if (amount >= 10000) {
    return `₩${Math.round(amount / 10000).toLocaleString()}만`;
  }
  return `₩${amount.toLocaleString()}`;
}

function SoftChip({ label }) {
  return (
    <button style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      height: 30, padding: '0 10px',
      background: 'transparent',
      border: 'none', borderRadius: 8,
      fontSize: 12, fontWeight: 500,
      color: 'var(--text-secondary)',
      cursor: 'pointer',
    }}
    onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-subtle)'}
    onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}>
      {label}
      <Icon name="chevronDown" size={11} color="var(--text-quaternary)"/>
    </button>
  );
}

const softGhostBtn = {
  display: 'inline-flex', alignItems: 'center', gap: 5,
  height: 30, padding: '0 10px',
  background: 'transparent',
  border: 'none', borderRadius: 8,
  fontSize: 12, fontWeight: 500,
  color: 'var(--text-tertiary)',
  cursor: 'pointer',
};

const iconBtn = {
  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
  width: 24, height: 24, padding: 0,
  background: 'transparent',
  border: 'none', borderRadius: 6,
  color: 'var(--text-tertiary)',
  cursor: 'pointer',
};

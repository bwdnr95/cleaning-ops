import React from 'react';
import { DatePicker } from '../../../components/common/DatePicker';
import { Avatar, Icon } from '../../../components/common/ui';
import { ORDERS } from '../../../mocks/cleaningOpsData';
import { listAdminOrders, listPartners, updateAdminOrder } from '../../../api/admin';
import { sendAdminMessage } from '../../../api/messages';
import { useApiResource } from '../../../api/useApiResource';
import { ORDER_STATUSES } from '../../../domain/orderStatus';
import { isPaymentCheckNeeded } from '../../../domain/paymentStatus';

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

const TODAY_JOB_STATUSES = ['작업예정', '작업진행', '사진검수대기'];
const TOMORROW_NOTICE_STATUSES = ['일정확정', '전날안내필요'];
const BULK_MESSAGE_OPTIONS = [
  { value: 'customer_schedule_confirmed', label: '고객 일정확정 안내', recipient: 'customer' },
  { value: 'customer_day_before', label: '고객 전날 안내', recipient: 'customer' },
  { value: 'partner_assignment', label: '협력사 배정 안내', recipient: 'partner' },
  { value: 'customer_photo_ready', label: '고객 사진 확인 안내', recipient: 'customer' },
];

export function OrdersPage({ onOpenOrder, onCreateOrder, onEditOrder, initialTab = 'all' }) {
  const ordersResource = useApiResource(listAdminOrders);
  const partnersResource = useApiResource(listPartners);
  const orders = ordersResource.data ? ordersResource.data.map(toOrderRow) : ORDERS;
  const [tab, setTab] = React.useState(initialTab);
  const [selected, setSelected] = React.useState(new Set());
  const [hoverRow, setHoverRow] = React.useState(null);
  const [sortBy, setSortBy] = React.useState('visit');
  const [query, setQuery] = React.useState('');
  const [dateFilter, setDateFilter] = React.useState(() => createInitialDateFilter(initialTab));
  const [actionError, setActionError] = React.useState('');
  const [actionNotice, setActionNotice] = React.useState(null);
  const [isSavingAction, setIsSavingAction] = React.useState(false);
  const [bulkAction, setBulkAction] = React.useState(null);
  const [bulkStatus, setBulkStatus] = React.useState('일정확정');
  const [bulkPartnerId, setBulkPartnerId] = React.useState('');
  const [bulkMessageType, setBulkMessageType] = React.useState('customer_schedule_confirmed');
  const statusTabs = getStatusTabs(orders);
  const isDateFilterActive = dateFilter.start !== '' || dateFilter.end !== '';
  const partners = partnersResource.data || [];

  React.useEffect(() => {
    setTab(initialTab);
    setDateFilter(createInitialDateFilter(initialTab));
  }, [initialTab]);

  const toggleRow = (id) => {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id); else next.add(id);
    setSelected(next);
  };

  const handleCancelOrder = async (order) => {
    if (!window.confirm(`${order.id} 주문을 취소 처리할까요?`)) {
      return;
    }

    setActionError('');
    setIsSavingAction(true);
    try {
      await updateAdminOrder(order.id, { status: '취소' });
      ordersResource.reload();
    } catch {
      setActionError('주문 취소 처리에 실패했습니다.');
    } finally {
      setIsSavingAction(false);
    }
  };

  const runSelectedOrdersAction = async ({ execute, successLabel }) => {
    const selectedIds = [...selected];
    if (selectedIds.length === 0) {
      return;
    }

    setActionError('');
    setActionNotice(null);
    setIsSavingAction(true);
    const failures = [];

    for (const orderId of selectedIds) {
      try {
        await execute(orderId);
      } catch (error) {
        failures.push({ orderId, message: normalizeActionError(error) });
      }
    }

    ordersResource.reload();
    const successCount = selectedIds.length - failures.length;
    setSelected(new Set(failures.map((failure) => failure.orderId)));
    setActionNotice({
      tone: failures.length > 0 ? 'warn' : 'success',
      text: failures.length > 0
        ? `${successCount}건 처리, ${failures.length}건 실패 · ${failures.slice(0, 2).map((failure) => `${shortOrderId(failure.orderId)} ${failure.message}`).join(', ')}`
        : `${successCount}건 ${successLabel}`,
    });
    setIsSavingAction(false);
  };

  const handleBulkStatusChange = async () => {
    await runSelectedOrdersAction({
      successLabel: `${bulkStatus} 상태로 변경했습니다.`,
      execute: (orderId) => updateAdminOrder(orderId, { status: bulkStatus }),
    });
  };

  const handleBulkPartnerAssign = async () => {
    const partner = partners.find((item) => item.id === bulkPartnerId);
    if (!partner) {
      setActionNotice({ tone: 'danger', text: '배정할 협력사를 선택해주세요.' });
      return;
    }

    await runSelectedOrdersAction({
      successLabel: `${partner.name}에 배정했습니다.`,
      execute: (orderId) => updateAdminOrder(orderId, { partner_id: partner.id, team_name: partner.name }),
    });
  };

  const handleBulkMessageSend = async () => {
    const option = BULK_MESSAGE_OPTIONS.find((item) => item.value === bulkMessageType);
    if (!option) {
      setActionNotice({ tone: 'danger', text: '발송할 메시지 타입을 선택해주세요.' });
      return;
    }

    await runSelectedOrdersAction({
      successLabel: `${option.label}를 발송했습니다.`,
      execute: (orderId) => sendAdminMessage(orderId, option.value, option.recipient),
    });
  };

  const filtered = sortOrders(
    orders
      .filter((o) => {
        if (tab === 'today') return isTodayDate(o.scheduledDate) && TODAY_JOB_STATUSES.includes(o.status);
        if (tab === 'tomorrow_notice') return isTomorrowDate(o.scheduledDate) && TOMORROW_NOTICE_STATUSES.includes(o.status);
        if (tab === 'partner_pending') return o.status === '협력사확인중';
        if (tab === 'pending') return ['신규접수', '상담중', '협력사확인중'].includes(o.status);
        if (tab === 'work') return ['일정확정', '전날안내필요', '전날안내완료', '작업예정', '작업진행', '사진검수대기'].includes(o.status);
        if (tab === 'deliver') return ['고객전달필요'].includes(o.status);
        if (tab === 'payment_check') return isPaymentCheckNeeded(o.paymentStatus);
        if (tab === 'done') return ['고객전달완료', '서비스완료'].includes(o.status);
        if (tab === 'cancel') return o.status === '취소';
        return true;
      })
      .filter((o) => matchesDateFilter(o.scheduledDate, dateFilter))
      .filter((o) => matchesOrderQuery(o, query)),
    sortBy,
  );

  const setDatePreset = (preset) => {
    setDateFilter(createDateFilter(preset));
  };

  const setDateBoundary = (key, value) => {
    setDateFilter((current) => ({
      ...current,
      preset: 'range',
      [key]: value,
    }));
  };

  return (
    <div data-testid="admin-orders-page" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, background: 'var(--bg)' }}>
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
          <Insight num={formatCompactWon(orders.filter((order) => isPaymentCheckNeeded(order.paymentStatus)).reduce((sum, order) => sum + order.amount, 0))} label="미수금" danger/>
          <InsightDivider/>
          <Insight num={formatCompactWon(orders.reduce((sum, order) => sum + order.amount, 0))} label="이번 달" muted/>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <button className="btn btn--secondary btn--sm">
            <Icon name="fileText" size={12}/> 내보내기
          </button>
          <button data-testid="admin-orders-create" className="btn btn--primary btn--sm" onClick={onCreateOrder}>
            <Icon name="plus" size={12}/> 신규 주문
          </button>
        </div>
      </div>

      {/* Toolbar — real search, visit-date filtering, and sort */}
      <div style={{
        padding: '0 24px 12px',
        background: 'var(--bg)',
        display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap',
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
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="주문번호, 고객, 주소 검색"
            aria-label="주문 검색"
            style={{
              flex: 1,
              minWidth: 0,
              border: 'none',
              outline: 'none',
              background: 'transparent',
              color: 'var(--text)',
              fontSize: 12,
            }}
          />
        </div>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          minHeight: 32,
          paddingLeft: 4,
        }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, color: 'var(--text-tertiary)', fontSize: 12, fontWeight: 600, whiteSpace: 'nowrap' }}>
            <Icon name="calendar" size={12}/> 방문일
          </span>
          {[
            ['all', '전체'],
            ['today', '오늘'],
            ['tomorrow', '내일'],
            ['week', '이번주'],
          ].map(([key, label]) => (
            <button
              key={key}
              type="button"
              data-testid={`orders-date-preset-${key}`}
              aria-pressed={dateFilter.preset === key}
              onClick={() => setDatePreset(key)}
              style={datePresetButton(dateFilter.preset === key)}
            >
              {label}
            </button>
          ))}
          <DatePicker
            compact
            testId="orders-date-start"
            ariaLabel="방문일 시작"
            placeholder="시작일"
            value={dateFilter.start}
            onChange={(value) => setDateBoundary('start', value)}
          />
          <span style={{ color: 'var(--text-quaternary)', fontSize: 12 }}>~</span>
          <DatePicker
            compact
            testId="orders-date-end"
            ariaLabel="방문일 종료"
            placeholder="종료일"
            value={dateFilter.end}
            onChange={(value) => setDateBoundary('end', value)}
          />
          {isDateFilterActive && (
            <button type="button" data-testid="orders-date-clear" style={softGhostBtn} onClick={() => setDatePreset('all')}>
              해제
            </button>
          )}
        </div>
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
            <button
              key={t.key}
              data-testid={`orders-tab-${t.key}`}
              aria-pressed={active}
              onClick={() => setTab(t.key)}
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
          <button data-testid="orders-bulk-status-open" style={bulkActionButton(bulkAction === 'status')} onClick={() => setBulkAction(bulkAction === 'status' ? null : 'status')}>상태 변경</button>
          <button data-testid="orders-bulk-message-open" style={bulkActionButton(bulkAction === 'message')} onClick={() => setBulkAction(bulkAction === 'message' ? null : 'message')}>메시지</button>
          <button data-testid="orders-bulk-partner-open" style={bulkActionButton(bulkAction === 'partner')} onClick={() => setBulkAction(bulkAction === 'partner' ? null : 'partner')}>협력사 배정</button>
          <div style={{ flex: 1 }}/>
          <button style={softGhostBtn} onClick={() => { setSelected(new Set()); setBulkAction(null); }}>해제</button>
        </div>
      )}

      {selected.size > 0 && bulkAction && (
        <BulkActionPanel
          action={bulkAction}
          bulkStatus={bulkStatus}
          onStatusChange={setBulkStatus}
          bulkPartnerId={bulkPartnerId}
          onPartnerChange={setBulkPartnerId}
          partners={partners}
          bulkMessageType={bulkMessageType}
          onMessageTypeChange={setBulkMessageType}
          isSaving={isSavingAction}
          onApplyStatus={() => void handleBulkStatusChange()}
          onApplyPartner={() => void handleBulkPartnerAssign()}
          onApplyMessage={() => void handleBulkMessageSend()}
        />
      )}

      {/* Table — airy, no inner borders, hover float */}
      <div className="scroll" style={{ flex: 1, overflow: 'auto', padding: '4px 12px 20px' }}>
        {actionError && <ListNotice text={actionError} tone="danger" />}
        {actionNotice && <ListNotice testId="orders-bulk-notice" text={actionNotice.text} tone={actionNotice.tone} />}
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
            <col style={{ width: 132 }}/>
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
              <th>관리</th>
            </tr>
          </thead>
          <tbody>
            {!ordersResource.isLoading && !ordersResource.error && filtered.map((o) => {
              const isUnassigned = o.team === '미배정';
              const isUnpaid = o.paid === 'pending' && o.amount > 0 && !['취소', '신규접수', '상담중'].includes(o.status);
              const isCancelled = o.status === '취소';
              return (
                <tr key={o.id}
                  data-testid={`admin-order-row-${o.id}`}
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
                    <div style={{ display: 'inline-flex', gap: 4, opacity: hoverRow === o.id ? 1 : 0.78 }}>
                      <button
                        type="button"
                        className="btn btn--secondary btn--sm"
                        aria-label={`${o.id} 수정`}
                        onClick={() => onEditOrder ? onEditOrder(o.id) : onOpenOrder && onOpenOrder(o.id)}
                      >
                        수정
                      </button>
                      {!isCancelled && (
                        <button
                          type="button"
                          className="btn btn--danger btn--sm"
                          aria-label={`${o.id} 취소`}
                          disabled={isSavingAction}
                          onClick={() => void handleCancelOrder(o)}
                          style={{ padding: '0 7px' }}
                        >
                          취소
                        </button>
                      )}
                    </div>
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
        <span>{filtered.length}건 표시 · {formatDateFilterSummary(dateFilter)}</span>
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

function BulkActionPanel({
  action,
  bulkStatus,
  onStatusChange,
  bulkPartnerId,
  onPartnerChange,
  partners,
  bulkMessageType,
  onMessageTypeChange,
  isSaving,
  onApplyStatus,
  onApplyPartner,
  onApplyMessage,
}) {
  return (
    <div
      data-testid="orders-bulk-panel"
      style={{
        padding: '10px 24px',
        background: 'var(--surface)',
        borderBottom: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        minHeight: 48,
      }}
    >
      {action === 'status' && (
        <>
          <span style={panelLabelStyle}>선택 주문 상태</span>
          <select data-testid="orders-bulk-status-select" className="input" value={bulkStatus} onChange={(event) => onStatusChange(event.target.value)} style={{ width: 180, height: 32 }}>
            {ORDER_STATUSES.map((status) => <option key={status} value={status}>{status}</option>)}
          </select>
          <button data-testid="orders-bulk-status-apply" className="btn btn--primary btn--sm" disabled={isSaving} onClick={onApplyStatus}>
            {isSaving ? '처리 중' : '적용'}
          </button>
        </>
      )}

      {action === 'partner' && (
        <>
          <span style={panelLabelStyle}>선택 주문 배정</span>
          <select data-testid="orders-bulk-partner-select" className="input" value={bulkPartnerId} onChange={(event) => onPartnerChange(event.target.value)} style={{ width: 220, height: 32 }}>
            <option value="">협력사 선택</option>
            {partners.map((partner) => <option key={partner.id} value={partner.id}>{partner.name}</option>)}
          </select>
          <button data-testid="orders-bulk-partner-apply" className="btn btn--primary btn--sm" disabled={isSaving} onClick={onApplyPartner}>
            {isSaving ? '처리 중' : '배정'}
          </button>
        </>
      )}

      {action === 'message' && (
        <>
          <span style={panelLabelStyle}>선택 주문 발송</span>
          <select data-testid="orders-bulk-message-type" className="input" value={bulkMessageType} onChange={(event) => onMessageTypeChange(event.target.value)} style={{ width: 220, height: 32 }}>
            {BULK_MESSAGE_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
          <button data-testid="orders-bulk-message-apply" className="btn btn--primary btn--sm" disabled={isSaving} onClick={onApplyMessage}>
            {isSaving ? '발송 중' : '발송'}
          </button>
        </>
      )}
      <span style={{ color: 'var(--text-tertiary)', fontSize: 11.5 }}>
        각 주문의 타임라인과 발송 이력에 처리 결과가 기록됩니다.
      </span>
    </div>
  );
}

function ListNotice({ text, tone = 'muted', testId = undefined }) {
  const color = tone === 'danger'
    ? 'var(--danger-fg)'
    : tone === 'success'
      ? 'var(--success-fg)'
      : tone === 'warn'
        ? 'var(--warn-fg)'
        : 'var(--text-tertiary)';
  return (
    <div data-testid={testId} style={{
      padding: '18px 12px',
      color,
      fontSize: 12.5,
    }}>
      {text}
    </div>
  );
}

function getStatusTabs(orders) {
  return [
    { key: 'all', label: '전체', count: orders.length },
    { key: 'today', label: '오늘 작업', count: orders.filter((o) => isTodayDate(o.scheduledDate) && TODAY_JOB_STATUSES.includes(o.status)).length },
    { key: 'tomorrow_notice', label: '내일 안내', count: orders.filter((o) => isTomorrowDate(o.scheduledDate) && TOMORROW_NOTICE_STATUSES.includes(o.status)).length },
    { key: 'partner_pending', label: '협력사 확인', count: orders.filter((o) => o.status === '협력사확인중').length },
    { key: 'pending', label: '확인 대기', count: orders.filter((o) => ['신규접수', '상담중', '협력사확인중'].includes(o.status)).length },
    { key: 'work', label: '작업/검수', count: orders.filter((o) => ['일정확정', '전날안내필요', '전날안내완료', '작업예정', '작업진행', '사진검수대기'].includes(o.status)).length },
    { key: 'deliver', label: '고객 전달', count: orders.filter((o) => ['고객전달필요'].includes(o.status)).length },
    { key: 'payment_check', label: '결제 확인', count: orders.filter((o) => isPaymentCheckNeeded(o.paymentStatus)).length },
    { key: 'done', label: '완료', count: orders.filter((o) => ['고객전달완료', '서비스완료'].includes(o.status)).length },
    { key: 'cancel', label: '취소', count: orders.filter((o) => o.status === '취소').length },
  ];
}

function matchesOrderQuery(order, query) {
  const keyword = query.trim().toLowerCase();
  if (!keyword) {
    return true;
  }

  return [
    order.id,
    order.status,
    order.product,
    order.address,
    order.customer,
    order.phone,
    order.team,
  ].some((value) => String(value || '').toLowerCase().includes(keyword));
}

function normalizeActionError(error) {
  const detail = error?.detail || error?.message || '';
  const map = {
    order_not_found: '주문 없음',
    partner_not_assigned: '협력사 미배정',
    partner_not_found: '협력사 없음',
    no_customer_visible_photos: '공개 사진 없음',
    invalid_recipient_type: '수신자 오류',
  };
  return map[detail] || '처리 실패';
}

function shortOrderId(orderId) {
  return String(orderId || '').slice(0, 8);
}

function matchesDateFilter(value, dateFilter) {
  if (!dateFilter.start && !dateFilter.end) {
    return true;
  }

  if (!value) {
    return false;
  }

  const { start, end } = normalizeDateRange(dateFilter.start, dateFilter.end);

  if (start && value < start) {
    return false;
  }
  if (end && value > end) {
    return false;
  }
  return true;
}

function sortOrders(orders, sortBy) {
  return [...orders].sort((a, b) => {
    const aValue = sortBy === 'received' ? a.received : (a.scheduledDate || '9999-99-99');
    const bValue = sortBy === 'received' ? b.received : (b.scheduledDate || '9999-99-99');
    return String(aValue).localeCompare(String(bValue));
  });
}

function toOrderRow(order) {
  return {
    id: order.id,
    status: order.status,
    received: formatDate(order.received_date),
    visit: formatDate(order.scheduled_date) || '미정',
    scheduledDate: order.scheduled_date,
    timeWindow: order.requested_time || '-',
    team: order.team_name || '미배정',
    product: order.size_or_quantity ? `${order.service_name} (${order.size_or_quantity})` : order.service_name,
    address: order.customer_address,
    customer: order.customer_name,
    phone: maskPhone(order.customer_phone),
    amount: Number(order.total_amount || 0),
    paymentStatus: order.payment_status,
    paid: toPaidState(order.payment_status),
    photo: toPhotoState(order.status),
    delivered: toDeliveredState(order.status),
  };
}

function createDateFilter(preset) {
  const today = new Date();
  if (preset === 'today') {
    const value = toDateString(today);
    return { preset, start: value, end: value };
  }
  if (preset === 'tomorrow') {
    const value = toDateString(addDays(today, 1));
    return { preset, start: value, end: value };
  }
  if (preset === 'week') {
    return {
      preset,
      start: toDateString(startOfWeek(today)),
      end: toDateString(addDays(startOfWeek(today), 6)),
    };
  }
  return { preset: 'all', start: '', end: '' };
}

function createInitialDateFilter(initialTab) {
  if (initialTab === 'tomorrow_notice') {
    return createDateFilter('tomorrow');
  }
  if (initialTab === 'payment_check') {
    return createDateFilter('all');
  }
  return createDateFilter('today');
}

function normalizeDateRange(start, end) {
  if (start && end && start > end) {
    return { start: end, end: start };
  }
  return { start, end };
}

function formatDateFilterSummary(dateFilter) {
  if (!dateFilter.start && !dateFilter.end) {
    return '전체 방문일';
  }

  const { start, end } = normalizeDateRange(dateFilter.start, dateFilter.end);
  if (start && end && start === end) {
    return `${formatFullDate(start)} 방문`;
  }
  if (start && end) {
    return `${formatFullDate(start)} ~ ${formatFullDate(end)}`;
  }
  if (start) {
    return `${formatFullDate(start)} 이후`;
  }
  return `${formatFullDate(end)} 이전`;
}

function toDateString(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

function addDays(date, days) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate() + days);
}

function startOfWeek(date) {
  const day = date.getDay();
  const mondayOffset = day === 0 ? -6 : 1 - day;
  return addDays(date, mondayOffset);
}

function isTodayDate(value) {
  return isRelativeDate(value, 0);
}

function isTomorrowDate(value) {
  return isRelativeDate(value, 1);
}

function isRelativeDate(value, offsetDays) {
  if (!value) {
    return false;
  }
  const target = new Date();
  target.setHours(0, 0, 0, 0);
  target.setDate(target.getDate() + offsetDays);
  const date = new Date(`${value}T00:00:00`);
  return date.getFullYear() === target.getFullYear()
    && date.getMonth() === target.getMonth()
    && date.getDate() === target.getDate();
}

function formatDate(value) {
  if (!value) {
    return '';
  }

  const date = new Date(`${value}T00:00:00`);
  return `${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

function formatFullDate(value) {
  if (!value) {
    return '';
  }

  const [year, month, day] = value.split('-');
  return `${year}.${month}.${day}`;
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
  if (!status) {
    return null;
  }
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

const softGhostBtn = {
  display: 'inline-flex', alignItems: 'center', gap: 5,
  height: 30, padding: '0 10px',
  background: 'transparent',
  border: 'none', borderRadius: 8,
  fontSize: 12, fontWeight: 500,
  color: 'var(--text-tertiary)',
  cursor: 'pointer',
};

const panelLabelStyle = {
  color: 'var(--text-tertiary)',
  fontSize: 12,
  fontWeight: 700,
  whiteSpace: 'nowrap',
};

function bulkActionButton(active) {
  return {
    ...softGhostBtn,
    background: active ? 'var(--brand-bg)' : 'transparent',
    color: active ? 'var(--brand)' : 'var(--text-tertiary)',
  };
}

function datePresetButton(active) {
  return {
    height: 30,
    padding: '0 9px',
    border: 'none',
    borderRadius: 8,
    background: active ? 'var(--brand-bg)' : 'transparent',
    color: active ? 'var(--brand)' : 'var(--text-tertiary)',
    fontSize: 12,
    fontWeight: 600,
    cursor: 'pointer',
    whiteSpace: 'nowrap',
  };
}

const iconBtn = {
  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
  width: 24, height: 24, padding: 0,
  background: 'transparent',
  border: 'none', borderRadius: 6,
  color: 'var(--text-tertiary)',
  cursor: 'pointer',
};

import React from 'react';
import { DatePicker } from '../../../components/common/DatePicker';
import { PaginationBar } from '../../../components/common/Pagination';
import { Avatar, Icon } from '../../../components/common/ui';
import { bulkDeleteAdminOrders, exportAdminOrders, listAdminOrdersPage, listPartners, updateAdminOrder, type AdminOrderPageParams, type AdminOrderSort } from '../../../api/admin';
import { sendAdminMessage } from '../../../api/messages';
import { useApiResource } from '../../../api/useApiResource';
import { ORDER_STATUS_OPTIONS, orderStatusLabel, orderWorkflowStatusValue } from '../../../domain/orderStatus';
import { formatQuantity } from '../../../domain/format';
import { receiptBadge } from '../../../domain/receiptType';
import { PAYMENT_STATUSES, paymentStatusLabel } from '../../../domain/paymentStatus';
import { formatPhone } from '../../../domain/phone';
import { OrderImportDialog } from './OrderImportDialog';
import { PartnerFilterSelect } from './PartnerFilterSelect';
import {
  addDays,
  formatDateValue,
  getAppTodayDate,
  getAppTodayValue,
  parseDateValue,
  startOfWeek,
} from '../../../domain/time';

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
  '고객확인필요': '#ef4444',
  '서비스완료':   '#10b981',
  '취소':         '#cbd5e1',
};

function StatusDot({ status }) {
  const color = STATUS_DOT[status] || '#94a3b8';
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)',
      maxWidth: '100%',
      minWidth: 0,
      whiteSpace: 'nowrap',
    }}>
      <span style={{
        width: 7, height: 7, borderRadius: '50%',
        background: color, flexShrink: 0,
        boxShadow: `0 0 0 3px ${color}1a`,
      }}/>
      <span style={{ minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis' }}>{orderStatusLabel(status)}</span>
    </span>
  );
}

function PaidPill({ paid, isUnpaid }) {
  const map = {
    paid:    { label: '완납',   color: 'var(--paid-fg)' },
    partial: { label: '계약금', color: 'var(--deposit-fg)' },
    pending: { label: isUnpaid ? '미수' : '대기', color: isUnpaid ? 'var(--unpaid-fg)' : 'var(--text-quaternary)' },
    refund:  { label: '환불',   color: 'var(--danger-fg)' },
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

function EvidencePill({ type, status }) {
  const badge = receiptBadge(type, status);
  if (badge.text === '-') return <span style={{ color: 'var(--text-quaternary)' }}>—</span>;
  const color = badge.tone === 'ok' ? '#10b981' : badge.tone === 'warn' ? '#f59e0b' : 'var(--text-quaternary)';
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11, fontWeight: 500, color }}>
      <span style={{ width: 5, height: 5, borderRadius: '50%', background: color }}/>
      {badge.text}
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

function DateSortHeader({ sortBy, onSortChange }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0 }}>
      <DateSortLine label="방문" asc="visit_asc" desc="visit_desc" sortBy={sortBy} onSortChange={onSortChange} />
      <DateSortLine label="접수" asc="received_asc" desc="received_desc" sortBy={sortBy} onSortChange={onSortChange} />
    </div>
  );
}

function DateSortLine({ label, asc, desc, sortBy, onSortChange }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, whiteSpace: 'nowrap' }}>
      <span style={{ minWidth: 24 }}>{label}</span>
      <SortArrowButton
        active={sortBy === asc}
        icon="chevronUp"
        label={`${label} 오름차순`}
        onClick={() => onSortChange(asc)}
      />
      <SortArrowButton
        active={sortBy === desc}
        icon="chevronDown"
        label={`${label} 내림차순`}
        onClick={() => onSortChange(desc)}
      />
    </span>
  );
}

function SortArrowButton({ active, icon, label, onClick }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={(event) => {
        event.stopPropagation();
        onClick();
      }}
      style={{
        width: 18,
        height: 18,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 0,
        border: 'none',
        borderRadius: 4,
        background: active ? 'var(--brand-bg)' : 'transparent',
        color: active ? 'var(--brand)' : 'var(--text-quaternary)',
        cursor: 'pointer',
      }}
    >
      <Icon name={icon} size={10} />
    </button>
  );
}

function ResizableTh({ columnKey, children, onResizeStart, isResizing = false, style = {} }) {
  return (
    <th data-testid={`orders-column-${columnKey}`} style={style}>
      <div className="orders-table-th-content">
        {children}
      </div>
      <button
        type="button"
        data-testid={`orders-column-resizer-${columnKey}`}
        className={`orders-table-resizer${isResizing ? ' is-active' : ''}`}
        aria-label={`${columnKey} 열 너비 조정`}
        title="열 너비 조정"
        onMouseDown={(event) => onResizeStart(event, columnKey)}
      />
    </th>
  );
}

const ORDER_STATUS_TAB_OPTIONS = [
  { key: 'consulting_unassigned', status: '상담중', label: '상담중/미배정' },
  { key: 'schedule_partner_checking', status: '협력사확인중', label: '일정 및 협력사 확인중' },
  { key: 'schedule_work_confirmed', status: '작업예정', label: '일정 및 작업 확정' },
  { key: 'work_done', status: '고객전달필요', label: '작업완료' },
  { key: 'customer_check_needed', status: '고객확인필요', label: '고객확인필요' },
  { key: 'final_payment_complete', status: '서비스완료', label: '최종결제완료' },
  { key: 'cancel', status: '취소', label: '취소' },
];
const ORDER_STATUS_TAB_BY_KEY = new Map(ORDER_STATUS_TAB_OPTIONS.map((item) => [item.key, item]));
const BULK_MESSAGE_OPTIONS = [
  { value: 'customer_schedule_confirmed', label: '고객 일정확정 안내', recipient: 'customer' },
  { value: 'customer_day_before', label: '고객 전날 안내', recipient: 'customer' },
  { value: 'partner_assignment', label: '협력사 배정 안내', recipient: 'partner' },
  { value: 'customer_photo_ready', label: '고객 사진 확인 안내', recipient: 'customer' },
  { value: 'customer_balance_due', label: '고객 잔금 안내', recipient: 'customer' },
];
// v3: 상태 칸(한글 라벨 '일정 및 협력사 확인중' 등)이 좁아 옆 칸으로 글자가 겹치던 문제 해결.
// 상태 폭을 키우고 주소를 약간 줄여 재배분. 키를 올려 저장된(또는 드래그로 깨진) 폭을 새 기본값으로 리셋한다.
// (어떤 폭에서도 겹침이 없도록 셀은 .orders-table tbody td { overflow:hidden } 으로 클립)
const ORDER_TABLE_COLUMN_STORAGE_KEY = 'cleaning.ops.orders.columnWidths.v3';
const ORDER_TABLE_COLUMNS = [
  { key: 'select', width: 2.2, min: 2 },
  { key: 'status', width: 11, min: 8 },
  { key: 'date', width: 9, min: 7 },
  { key: 'team', width: 8.5, min: 6 },
  { key: 'service', width: 9.5, min: 6.5 },
  { key: 'address', width: 18.5, min: 11 },
  { key: 'customer', width: 8.5, min: 6.5 },
  { key: 'amount', width: 11, min: 8 },
  { key: 'payment', width: 5.5, min: 4 },
  { key: 'evidence', width: 8.5, min: 5.5 },
  { key: 'progress', width: 5.5, min: 4 },
  { key: 'actions', width: 8.5, min: 6 },
];
const ORDER_TABLE_DEFAULT_WIDTHS = ORDER_TABLE_COLUMNS.reduce((widths, column) => {
  widths[column.key] = column.width;
  return widths;
}, {});

export function OrdersPage({ onOpenOrder, onCreateOrder, onEditOrder, initialTab = 'all', initialDatePreset = undefined }) {
  const tableScrollRef = React.useRef(null);
  const [tab, setTab] = React.useState(initialTab);
  const [selected, setSelected] = React.useState(new Set());
  const [hoverRow, setHoverRow] = React.useState(null);
  const [sortBy, setSortBy] = React.useState<AdminOrderSort>('visit_asc');
  const [query, setQuery] = React.useState('');
  const [dateFilter, setDateFilter] = React.useState(() => createInitialDateFilter(initialTab, initialDatePreset));
  const [partnerFilter, setPartnerFilter] = React.useState('all');
  const [receivedDateFilter, setReceivedDateFilter] = React.useState(() => createDateFilter('all'));
  const [page, setPage] = React.useState(1);
  const [pageSize, setPageSize] = React.useState(50);
  const [actionError, setActionError] = React.useState('');
  const [actionNotice, setActionNotice] = React.useState(null);
  const [isSavingAction, setIsSavingAction] = React.useState(false);
  const [isDeleting, setIsDeleting] = React.useState(false);
  const [isExporting, setIsExporting] = React.useState(false);
  const [bulkAction, setBulkAction] = React.useState(null);
  const [bulkStatus, setBulkStatus] = React.useState('작업예정');
  const [bulkPartnerId, setBulkPartnerId] = React.useState('');
  const [bulkMessageType, setBulkMessageType] = React.useState('customer_schedule_confirmed');
  const [bulkPaymentStatus, setBulkPaymentStatus] = React.useState('paid');
  const [bulkScheduledDate, setBulkScheduledDate] = React.useState('');
  const [isImportOpen, setImportOpen] = React.useState(false);
  const [columnWidths, setColumnWidths] = React.useState(getInitialOrderTableColumnWidths);
  const [resizingColumn, setResizingColumn] = React.useState(null);
  const [debouncedQuery, setDebouncedQuery] = React.useState('');

  // 검색어는 디바운스하여 키 입력마다 요청이 나가지 않도록 한다(입력 자체는 query로 즉시 반영).
  React.useEffect(() => {
    const handle = window.setTimeout(() => setDebouncedQuery(query.trim()), 300);
    return () => window.clearTimeout(handle);
  }, [query]);

  // 서버가 필터·정렬·페이지네이션·집계를 모두 처리한다. items는 그대로 화면에 표시하고
  // 클라이언트에서 재필터/재정렬/재페이지하지 않는다.
  const orderPageParams = React.useMemo<AdminOrderPageParams>(() => ({
    page,
    page_size: pageSize,
    sort: sortBy,
    status: tab,
    visit_preset: dateFilter.preset,
    visit_from: dateFilter.start || undefined,
    visit_to: dateFilter.end || undefined,
    received_preset: receivedDateFilter.preset,
    received_from: receivedDateFilter.start || undefined,
    received_to: receivedDateFilter.end || undefined,
    partner_id: partnerFilter === 'all' ? undefined : partnerFilter,
    q: debouncedQuery || undefined,
  }), [
    page,
    pageSize,
    sortBy,
    tab,
    dateFilter.preset,
    dateFilter.start,
    dateFilter.end,
    receivedDateFilter.preset,
    receivedDateFilter.start,
    receivedDateFilter.end,
    partnerFilter,
    debouncedQuery,
  ]);
  const ordersResourceKey = [
    tab,
    sortBy,
    page,
    pageSize,
    dateFilter.preset,
    dateFilter.start,
    dateFilter.end,
    receivedDateFilter.preset,
    receivedDateFilter.start,
    receivedDateFilter.end,
    partnerFilter,
    debouncedQuery,
  ].join('|');
  const loadOrders = React.useCallback(() => listAdminOrdersPage(orderPageParams), [orderPageParams]);
  const ordersResource = useApiResource(loadOrders, ordersResourceKey);
  const partnersResource = useApiResource(listPartners);
  const orderPage = ordersResource.data;
  const items = React.useMemo(
    () => (orderPage?.items ? orderPage.items.map(toOrderRow) : []),
    [orderPage],
  );
  const statusTabs = React.useMemo(
    () => getStatusTabs(orderPage?.status_counts),
    [orderPage],
  );
  const insight = orderPage?.insight;
  const summary = orderPage?.summary;
  const totalItems = orderPage?.total ?? 0;
  const isDateFilterActive = dateFilter.start !== '' || dateFilter.end !== '';
  const isReceivedDateFilterActive = receivedDateFilter.start !== '' || receivedDateFilter.end !== '';
  const partners = React.useMemo(() => partnersResource.data || [], [partnersResource.data]);
  const sortedActivePartners = React.useMemo(() => {
    return partners
      .filter((partner) => partner.is_active !== false)
      .slice()
      .sort((a, b) => String(a.name || '').localeCompare(String(b.name || ''), 'ko'));
  }, [partners]);

  React.useEffect(() => {
    setTab(initialTab);
    setDateFilter(createInitialDateFilter(initialTab, initialDatePreset));
    setPage(1);
  }, [initialDatePreset, initialTab]);

  React.useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    window.localStorage.setItem(ORDER_TABLE_COLUMN_STORAGE_KEY, JSON.stringify(columnWidths));
  }, [columnWidths]);

  React.useEffect(() => {
    setPage(1);
  }, [
    tab,
    sortBy,
    query,
    dateFilter.start,
    dateFilter.end,
    partnerFilter,
    receivedDateFilter.start,
    receivedDateFilter.end,
  ]);

  const handleColumnResizeStart = React.useCallback((event, columnKey) => {
    event.preventDefault();
    event.stopPropagation();

    const columnIndex = ORDER_TABLE_COLUMNS.findIndex((column) => column.key === columnKey);
    const currentColumn = ORDER_TABLE_COLUMNS[columnIndex];
    const nextColumn = ORDER_TABLE_COLUMNS[columnIndex + 1];
    if (!currentColumn || !nextColumn) {
      return;
    }

    const tableWidth = tableScrollRef.current?.clientWidth || 1;
    const startX = event.clientX;
    const startWidths = columnWidths;
    setResizingColumn(columnKey);
    document.body.classList.add('orders-column-resizing');

    const handleMouseMove = (moveEvent) => {
      const delta = ((moveEvent.clientX - startX) / tableWidth) * 100;
      setColumnWidths(resizeOrderTableColumnPair(startWidths, currentColumn, nextColumn, delta));
    };
    const handleMouseUp = () => {
      setResizingColumn(null);
      document.body.classList.remove('orders-column-resizing');
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
  }, [columnWidths]);

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
    return { successCount, failures };
  };

  const handleBulkStatusChange = async () => {
    const result = await runSelectedOrdersAction({
      successLabel: `${orderStatusLabel(bulkStatus)} 상태로 변경했습니다.`,
      execute: (orderId) => updateAdminOrder(orderId, { status: bulkStatus }),
    });
    // 일괄 '작업완료(고객전달필요)' 처리는 상세화면과 달리 잔금 미리보기가 자동으로 뜨지 않는다.
    // 잔금 안내 발송 누락을 막기 위해, 전건 성공 시 후속 안내를 띄운다.
    if (result && result.failures.length === 0 && bulkStatus === '고객전달필요') {
      setActionNotice({
        tone: 'warn',
        text: `${result.successCount}건을 '작업완료'로 변경했습니다. 일괄 변경은 잔금 안내 미리보기가 자동으로 뜨지 않으니, 각 주문 상세에서 잔금 안내를 확인 후 발송하세요.`,
      });
    }
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

  const handleBulkPaymentStatusChange = async () => {
    await runSelectedOrdersAction({
      successLabel: `${paymentStatusLabel(bulkPaymentStatus)} 결제상태로 변경했습니다.`,
      execute: (orderId) => updateAdminOrder(orderId, { payment_status: bulkPaymentStatus }),
    });
  };

  const handleBulkScheduleChange = async () => {
    // 날짜를 비우면(지우기) 방문일을 미배정으로 변경한다.
    const toUnassigned = !bulkScheduledDate;
    if (toUnassigned && !window.confirm(`선택한 ${selected.size}건의 방문일을 미배정으로 비울까요?`)) {
      return;
    }
    await runSelectedOrdersAction({
      successLabel: toUnassigned ? '방문일을 미배정으로 변경했습니다.' : `방문일을 ${bulkScheduledDate}(으)로 변경했습니다.`,
      execute: (orderId) => updateAdminOrder(orderId, { scheduled_date: bulkScheduledDate || null }),
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

  const handleBulkDelete = async () => {
    if (selected.size === 0) return;
    if (!window.confirm(`선택한 ${selected.size}건의 주문을 삭제하시겠습니까? 삭제된 주문은 목록에서 사라지지만 운영 기록(타임라인)은 보존됩니다.`)) {
      return;
    }

    setActionError('');
    setActionNotice(null);
    setIsDeleting(true);
    try {
      const result = await bulkDeleteAdminOrders(Array.from(selected));
      setSelected(new Set());
      setBulkAction(null);
      setActionNotice({
        tone: result.failed.length > 0 ? 'warn' : 'success',
        text: result.failed.length > 0
          ? `${result.succeeded.length}건 삭제 완료, ${result.failed.length}건 실패: ${result.failed.map((failure) => shortOrderId(failure.order_id)).join(', ')}`
          : `${result.succeeded.length}건 삭제 완료`,
      });
      ordersResource.reload();
    } catch (error) {
      setActionError(`삭제 실패: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setIsDeleting(false);
    }
  };

  // 서버가 정렬·페이지네이션한 현재 페이지 항목에 대해서만 그룹 시각화 메타를 계산한다.
  const pagedRows = React.useMemo(() => {
    const sorted = [...items];
    const groupStatusMap = new Map();
    for (const row of sorted) {
      const key = row.groupId || row.id;
      const group = groupStatusMap.get(key) || { count: 0, cancelled: 0 };
      group.count += 1;
      if (row.status === '취소') {
        group.cancelled += 1;
      }
      groupStatusMap.set(key, group);
    }
    return sorted.map((row, idx) => {
      const prev = sorted[idx - 1];
      const next = sorted[idx + 1];
      const key = row.groupId || row.id;
      const group = groupStatusMap.get(key);
      return {
        ...row,
        isGroupFirst: !prev || (prev.groupId || prev.id) !== key,
        isGroupLast: !next || (next.groupId || next.id) !== key,
        groupSize: group?.count || 1,
        isGroupCancelled: Boolean(group && group.count > 1 && group.count === group.cancelled),
      };
    });
  }, [items]);
  const filterSummary = React.useMemo(() => ({
    count: summary?.count ?? 0,
    consumerTotal: summary?.consumer_total ?? 0,
    partnerTotal: summary?.partner_total ?? 0,
    profitTotal: summary?.profit ?? 0,
  }), [summary]);
  const visibleActiveTabKey = getVisibleStatusTabKey(tab);
  const selectedPartnerName = partnerFilter === 'all'
    ? '전체 협력사'
    : sortedActivePartners.find((partner) => partner.id === partnerFilter)?.name || '선택 협력사';
  const shouldShowFilterSummary = partnerFilter !== 'all' || isDateFilterActive;
  const filterSummaryLabel = `${selectedPartnerName} · ${formatDateFilterSummary(dateFilter)}`;

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

  const setReceivedDateBoundary = (key, value) => {
    setReceivedDateFilter((current) => ({
      ...current,
      preset: 'range',
      [key]: value,
    }));
  };

  const handleExportOrders = async () => {
    setActionError('');
    setActionNotice(null);

    if (!ordersResource.data) {
      setActionError('주문 목록을 불러온 뒤 내보내기를 다시 시도해주세요.');
      return;
    }
    if (totalItems === 0) {
      setActionNotice({ tone: 'warn', text: '내보낼 주문이 없습니다.' });
      return;
    }

    setIsExporting(true);
    try {
      // 현재 필터 조건 그대로, 한 번에 전체 결과를 받아 id 목록을 만든다(서버 page_size 최대 2000).
      const fullPage = await listAdminOrdersPage({
        ...orderPageParams,
        page: 1,
        page_size: totalItems,
      });
      const orderIds = fullPage.items.map((order) => order.id);
      if (orderIds.length === 0) {
        setActionNotice({ tone: 'warn', text: '내보낼 주문이 없습니다.' });
        return;
      }
      const blob = await exportAdminOrders(orderIds);
      downloadExportBlob(blob, createOrdersExportFilename());
      setActionNotice({ tone: 'success', text: `${orderIds.length}건을 내보냈습니다.` });
    } catch (error) {
      setActionError(`내보내기 실패: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div data-testid="admin-orders-page" className="page-shell" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, background: 'var(--bg)', maxWidth: 'none' }}>
      {/* Insight line — typographic, no card chrome */}
      <div style={{
        padding: '12px 10px 10px',
        background: 'var(--bg)',
        display: 'flex', alignItems: 'center', gap: 24,
      }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 18, flex: 1, flexWrap: 'wrap' }}>
          <Insight num={insight?.today_jobs ?? 0} label="오늘 작업" />
          <InsightDivider/>
          <Insight num={insight?.unassigned ?? 0} label="미배정" warn />
          <InsightDivider/>
          <Insight num={insight?.schedule_confirmed ?? 0} label="일정/작업 확정" />
          <InsightDivider/>
          <Insight num={insight?.work_done ?? 0} label="작업완료" />
          <InsightDivider/>
          <Insight num={formatCompactWon(insight?.unpaid_total ?? 0)} label="미수금" danger/>
          <InsightDivider/>
          <Insight num={formatCompactWon(insight?.month_total ?? 0)} label="이번 달" muted/>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <button
            type="button"
            data-testid="admin-orders-export"
            className="btn btn--secondary btn--sm"
            disabled={isExporting || ordersResource.isLoading || Boolean(ordersResource.error)}
            onClick={() => void handleExportOrders()}
          >
            <Icon name="fileText" size={12}/> {isExporting ? '내보내는 중' : '내보내기'}
          </button>
          <button
            data-testid="admin-orders-import"
            className="btn btn--secondary btn--sm"
            onClick={() => setImportOpen(true)}
          >
            <Icon name="upload" size={12}/> 일괄 등록
          </button>
        </div>
      </div>

      {/* Toolbar — real search, visit-date filtering, and sort */}
      <div style={{
        padding: '0 10px 8px',
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
            placeholder="고객/주소/연락처 검색"
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
        <div style={{ flex: 1 }}/>
        <button
          data-testid="admin-orders-create"
          className="btn btn--primary btn--lg"
          onClick={onCreateOrder}
        >
          <Icon name="plus" size={14}/> 신규 주문 등록
        </button>
      </div>

      {/* 협력사 필터 — 수십 개 협력사를 인라인 칩 대신 검색형 드롭다운으로 제공 */}
      <div style={{ padding: '0 10px 8px', background: 'var(--bg)', display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, color: 'var(--text-tertiary)', fontSize: 12, fontWeight: 600, whiteSpace: 'nowrap' }}>
          <Icon name="user" size={12}/> 협력사
        </span>
        <PartnerFilterSelect
          partners={sortedActivePartners}
          value={partnerFilter}
          onChange={setPartnerFilter}
        />
        {partnerFilter !== 'all' && (
          <button type="button" data-testid="orders-partner-clear" style={softGhostBtn} onClick={() => setPartnerFilter('all')}>
            해제
          </button>
        )}
      </div>

      {shouldShowFilterSummary && (
        <FilterSummaryLine
          label={filterSummaryLabel}
          summary={filterSummary}
        />
      )}

      {/* 접수일 필터 */}
      <div style={{ padding: '0 10px 8px', background: 'var(--bg)', display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, color: 'var(--text-tertiary)', fontSize: 12, fontWeight: 600, whiteSpace: 'nowrap' }}>
          <Icon name="calendar" size={12}/> 접수일
        </span>
        {[
          ['all', '전체'],
          ['today', '오늘'],
          ['yesterday', '어제'],
          ['tomorrow', '내일'],
          ['week', '이번주'],
          ['lastweek', '지난주'],
          ['month', '이번달'],
          ['last14', '지난 14일'],
        ].map(([key, label]) => (
          <button
            key={key}
            type="button"
            data-testid={`orders-received-preset-${key}`}
            aria-pressed={receivedDateFilter.preset === key}
            onClick={() => setReceivedDateFilter(createDateFilter(key))}
            style={datePresetButton(receivedDateFilter.preset === key)}
          >
            {label}
          </button>
        ))}
        <DatePicker
          compact
          testId="orders-received-start"
          ariaLabel="접수일 시작"
          placeholder="시작일"
          value={receivedDateFilter.start}
          onChange={(value) => setReceivedDateBoundary('start', value)}
        />
        <span style={{ color: 'var(--text-quaternary)', fontSize: 12 }}>~</span>
        <DatePicker
          compact
          testId="orders-received-end"
          ariaLabel="접수일 종료"
          placeholder="종료일"
          value={receivedDateFilter.end}
          onChange={(value) => setReceivedDateBoundary('end', value)}
        />
        {isReceivedDateFilterActive && (
          <button type="button" data-testid="orders-received-clear" style={softGhostBtn} onClick={() => setReceivedDateFilter(createDateFilter('all'))}>
            해제
          </button>
        )}
      </div>

      {/* 방문일 필터 — 접수일 아래에 배치 */}
      <div style={{ padding: '0 10px 8px', background: 'var(--bg)', display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, color: 'var(--text-tertiary)', fontSize: 12, fontWeight: 600, whiteSpace: 'nowrap' }}>
          <Icon name="calendar" size={12}/> 방문일
        </span>
        {[
          ['upcoming', '오늘부터'],
          ['all', '전체'],
          ['today', '오늘'],
          ['yesterday', '어제'],
          ['tomorrow', '내일'],
          ['week', '이번주'],
          ['lastweek', '지난주'],
          ['month', '이번달'],
          ['last14', '지난 14일'],
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

      {/* Tabs — minimal underline */}
      <div style={{
        padding: '0 10px',
        borderBottom: '1px solid var(--border)',
        display: 'flex', gap: 2,
      }}>
        {statusTabs.map((t) => {
          const active = visibleActiveTabKey === t.key;
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
          padding: '8px 10px',
          background: 'var(--bg)',
          borderBottom: '1px solid var(--border)',
          display: 'flex', alignItems: 'center', gap: 10, fontSize: 12,
        }}>
          <span style={{ fontWeight: 500, color: 'var(--text)' }}>{selected.size}건 선택</span>
          <span style={{ color: 'var(--text-quaternary)' }}>·</span>
          <button data-testid="orders-bulk-status-open" style={bulkActionButton(bulkAction === 'status')} onClick={() => setBulkAction(bulkAction === 'status' ? null : 'status')}>상태 변경</button>
          <button data-testid="orders-bulk-message-open" style={bulkActionButton(bulkAction === 'message')} onClick={() => setBulkAction(bulkAction === 'message' ? null : 'message')}>메시지</button>
          <button data-testid="orders-bulk-partner-open" style={bulkActionButton(bulkAction === 'partner')} onClick={() => setBulkAction(bulkAction === 'partner' ? null : 'partner')}>협력사 배정</button>
          <button data-testid="orders-bulk-payment-open" style={bulkActionButton(bulkAction === 'payment')} onClick={() => setBulkAction(bulkAction === 'payment' ? null : 'payment')}>결제상태</button>
          <button data-testid="orders-bulk-schedule-open" style={bulkActionButton(bulkAction === 'schedule')} onClick={() => setBulkAction(bulkAction === 'schedule' ? null : 'schedule')}>일정 변경</button>
          <button
            data-testid="orders-bulk-delete"
            style={{ ...bulkActionButton(false), color: 'var(--danger-fg)' }}
            disabled={isDeleting}
            onClick={() => void handleBulkDelete()}
          >
            {isDeleting ? '삭제 중' : '삭제'}
          </button>
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
          bulkPaymentStatus={bulkPaymentStatus}
          onPaymentStatusChange={setBulkPaymentStatus}
          bulkScheduledDate={bulkScheduledDate}
          onScheduledDateChange={setBulkScheduledDate}
          isSaving={isSavingAction}
          onApplyStatus={() => void handleBulkStatusChange()}
          onApplyPartner={() => void handleBulkPartnerAssign()}
          onApplyMessage={() => void handleBulkMessageSend()}
          onApplyPaymentStatus={() => void handleBulkPaymentStatusChange()}
          onApplySchedule={() => void handleBulkScheduleChange()}
        />
      )}

      {/* Table — airy, no inner borders, hover float.
          넓은 화면에선 칸이 화면폭에 맞춰 늘어나고(유동), 화면이 좁아지면 칸을 뭉개지 않고
          최소너비(min-width)를 유지한 채 가로 스크롤이 생긴다 → 글자 겹침/뭉개짐 없이 항상 가독. */}
      <div ref={tableScrollRef} data-testid="orders-table-scroll" className="scroll" style={{ flex: 1, overflowY: 'auto', overflowX: 'auto', padding: '4px 4px 20px' }}>
        {actionError && <ListNotice text={actionError} tone="danger" />}
        {actionNotice && <ListNotice testId="orders-bulk-notice" text={actionNotice.text} tone={actionNotice.tone} />}
        {ordersResource.isLoading && <ListNotice text="주문 목록을 불러오는 중입니다." />}
        {!ordersResource.isLoading && ordersResource.error && <ListNotice text="주문 목록을 불러오지 못했습니다." tone="danger" />}
        {!ordersResource.isLoading && !ordersResource.error && items.length === 0 && <ListNotice text="표시할 주문이 없습니다." />}
        <table className="table-modern orders-table" style={{ width: 'calc(100% - 12px)', minWidth: 1120, tableLayout: 'fixed' }}>
          <colgroup>
            {ORDER_TABLE_COLUMNS.map((column) => (
              <col key={column.key} style={{ width: `${columnWidths[column.key]}%` }} />
            ))}
          </colgroup>
          <thead>
            <tr>
              <ResizableTh
                columnKey="select"
                onResizeStart={handleColumnResizeStart}
                isResizing={resizingColumn === 'select'}
                style={{ paddingRight: 0 }}
              >
                <input
                  data-testid="orders-select-all"
                  type="checkbox"
                  checked={pagedRows.length > 0 && pagedRows.every((order) => selected.has(order.id))}
                  style={{ margin: 0 }}
                  onChange={(event) => {
                    setSelected(event.target.checked ? new Set(pagedRows.map((order) => order.id)) : new Set());
                  }}
                />
              </ResizableTh>
              <ResizableTh columnKey="status" onResizeStart={handleColumnResizeStart} isResizing={resizingColumn === 'status'}>상태</ResizableTh>
              <ResizableTh columnKey="date" onResizeStart={handleColumnResizeStart} isResizing={resizingColumn === 'date'}><DateSortHeader sortBy={sortBy} onSortChange={setSortBy} /></ResizableTh>
              <ResizableTh columnKey="team" onResizeStart={handleColumnResizeStart} isResizing={resizingColumn === 'team'}>담당</ResizableTh>
              <ResizableTh columnKey="service" onResizeStart={handleColumnResizeStart} isResizing={resizingColumn === 'service'}>상품</ResizableTh>
              <ResizableTh columnKey="address" onResizeStart={handleColumnResizeStart} isResizing={resizingColumn === 'address'}>주소</ResizableTh>
              <ResizableTh columnKey="customer" onResizeStart={handleColumnResizeStart} isResizing={resizingColumn === 'customer'}>고객</ResizableTh>
              <ResizableTh columnKey="amount" onResizeStart={handleColumnResizeStart} isResizing={resizingColumn === 'amount'} style={{ textAlign: 'right' }}>금액</ResizableTh>
              <ResizableTh columnKey="payment" onResizeStart={handleColumnResizeStart} isResizing={resizingColumn === 'payment'}>결제</ResizableTh>
              <ResizableTh columnKey="evidence" onResizeStart={handleColumnResizeStart} isResizing={resizingColumn === 'evidence'}>증빙</ResizableTh>
              <ResizableTh columnKey="progress" onResizeStart={handleColumnResizeStart} isResizing={resizingColumn === 'progress'}>진행</ResizableTh>
              <th data-testid="orders-column-actions">관리</th>
            </tr>
          </thead>
          <tbody>
            {!ordersResource.isLoading && !ordersResource.error && pagedRows.map((o) => {
              const isUnassigned = o.team === '미배정';
              const isUnpaid = o.paid === 'pending' && o.amount > 0 && !['취소', '상담중'].includes(o.status);
              const isCancelled = o.status === '취소';
              return (
                <tr key={o.id}
                  data-testid={`admin-order-row-${o.id}`}
                  className={[
                    selected.has(o.id) ? 'is-selected' : '',
                    isUnpaid ? 'is-flagged' : '',
                    isCancelled ? 'is-muted' : '',
                  ].join(' ')}
                  onMouseEnter={() => setHoverRow(o.id)}
                  onMouseLeave={() => setHoverRow(null)}
                  onClick={() => onOpenOrder && onOpenOrder(o.id)}
                  style={{ cursor: 'pointer' }}>
                  <td
                    onClick={(e) => e.stopPropagation()}
                    style={{
                      paddingRight: 0,
                      borderLeft: o.groupId && o.groupSize > 1 ? '3px solid var(--brand)' : '3px solid transparent',
                      paddingLeft: o.groupId && o.groupSize > 1 && !o.isGroupFirst ? 12 : 6,
                    }}
                  >
                    {o.groupId && o.groupSize > 1 && !o.isGroupFirst && (
                      <span aria-hidden="true" style={{ color: 'var(--text-quaternary)', marginRight: 5, fontSize: 12 }}>└</span>
                    )}
                    <input type="checkbox" checked={selected.has(o.id)}
                      onChange={() => toggleRow(o.id)} style={{ margin: 0 }}/>
                  </td>
                  <td>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                      <StatusDot status={o.status}/>
                      {o.isGroupFirst && o.isGroupCancelled && (
                        <span style={{ fontSize: 10.5, color: 'var(--danger-fg)', background: 'var(--danger-bg)', borderRadius: 4, padding: '1px 5px' }}>
                          취소됨
                        </span>
                      )}
                    </span>
                  </td>
                  <td style={{ fontWeight: 500 }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
                      {o.visit === '미정'
                        ? <span style={{ color: 'var(--text-quaternary)', fontWeight: 400 }}>미정</span>
                        : <span style={{ display: 'inline-flex', alignItems: 'baseline', gap: 5, whiteSpace: 'nowrap' }}>
                            <span>{o.visit}</span>
                            <span style={{ color: 'var(--text-quaternary)', fontWeight: 400, fontSize: 10.5 }}>{o.timeWindow}</span>
                          </span>}
                      <span style={{ color: 'var(--text-quaternary)', fontSize: 10.5, fontWeight: 400, whiteSpace: 'nowrap' }}>
                        접수 {o.received || '-'}
                      </span>
                    </div>
                  </td>
                  <td>
                    {isUnassigned
                      ? <span style={{
                          fontSize: 11.5, fontWeight: 500, color: '#b45309',
                          display: 'inline-flex', alignItems: 'center', gap: 5,
                        }}>
                          <span style={{ width: 5, height: 5, borderRadius: '50%', background: '#f59e0b' }}/>
                          미배정
                        </span>
                      : <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                          <Avatar name={o.team[0]} size={16} tone="info"/>
                          <span style={{ fontSize: 11.5, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{o.team}</span>
                        </span>}
                  </td>
                  <td>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
                      <span style={{ display: 'flex', alignItems: 'center', gap: 4, minWidth: 0 }}>
                        {o.recurringContractId && (
                          <span
                            data-testid="order-row-recurring-badge"
                            title="정기청소 계약에서 생성된 주문"
                            style={{
                              flexShrink: 0,
                              fontSize: 9.5, fontWeight: 700, lineHeight: 1.5,
                              padding: '0 5px', borderRadius: 8,
                              background: 'var(--brand-bg)', color: 'var(--brand)',
                            }}
                          >
                            정기
                          </span>
                        )}
                        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{o.serviceName}</span>
                      </span>
                      {o.sizeOrQuantity && (
                        <span style={{ color: 'var(--text-quaternary)', fontSize: 10.5, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {o.sizeOrQuantity}
                        </span>
                      )}
                    </div>
                  </td>
                  <td
                    style={{
                      color: 'var(--text-tertiary)',
                      overflow: 'hidden',
                      display: '-webkit-box',
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: 'vertical',
                      whiteSpace: 'normal',
                      lineHeight: 1.35,
                      fontSize: 12,
                    }}
                    title={o.fullAddress || o.address}
                  >
                    {o.fullAddress || o.address}
                  </td>
                  <td>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{o.customer}</span>
                      <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-quaternary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {o.phone}
                      </span>
                    </div>
                  </td>
                  <td style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 2 }}>
                      <span style={{ fontWeight: 600 }}>
                        {o.amount === 0
                          ? <span style={{ color: 'var(--text-quaternary)', fontWeight: 400 }}>—</span>
                          : `₩${o.amount.toLocaleString()}`}
                      </span>
                      <span style={{ color: 'var(--text-quaternary)', fontSize: 10.5, fontWeight: 500 }}>
                        도급 {o.partnerPrice === 0 ? '—' : `₩${o.partnerPrice.toLocaleString()}`}
                      </span>
                      {o.vatType === 'excluded' && <span style={{ color: 'var(--warn-fg)', fontSize: 10.5, fontWeight: 500 }}>VAT 별도</span>}
                    </div>
                  </td>
                  <td><PaidPill paid={o.paid} isUnpaid={isUnpaid}/></td>
                  <td><EvidencePill type={o.receiptType} status={o.receiptStatus}/></td>
                  <td>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                      <SimplePill kind="photo" value={o.photo}/>
                      <SimplePill kind="deliver" value={o.delivered}/>
                    </div>
                  </td>
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

      <PaginationBar
        testId="orders-pagination"
        totalItems={totalItems}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        onPageSizeChange={setPageSize}
        itemLabel={`건 표시 · ${formatDateFilterSummary(dateFilter)}`}
      />
      {isImportOpen && (
        <OrderImportDialog
          onClose={() => setImportOpen(false)}
          onImported={() => {
            ordersResource.reload();
          }}
        />
      )}
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

function FilterSummaryLine({ label, summary }) {
  const items = [
    ['건수', `${summary.count.toLocaleString()}건`],
    ['총금액(VAT포함)', formatWon(summary.consumerTotal)],
    ['도급가(VAT 포함)', formatWon(summary.partnerTotal)],
    ['이윤', formatWon(summary.profitTotal)],
  ];

  return (
    <div
      data-testid="orders-filter-summary"
      style={{
        padding: '0 10px 8px',
        background: 'var(--bg)',
        display: 'flex',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          flexWrap: 'wrap',
          minHeight: 30,
          padding: '5px 10px',
          border: '1px solid var(--border)',
          borderRadius: 8,
          background: 'var(--surface)',
          color: 'var(--text-secondary)',
          fontSize: 12,
          boxShadow: 'var(--shadow-xs)',
        }}
      >
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontWeight: 700, color: 'var(--text)' }}>
          <Icon name="trending" size={12}/>
          {label}
        </span>
        {items.map(([itemLabel, value]) => (
          <span key={itemLabel} style={{ display: 'inline-flex', alignItems: 'baseline', gap: 4, whiteSpace: 'nowrap' }}>
            <span style={{ color: 'var(--text-quaternary)' }}>·</span>
            <span style={{ color: 'var(--text-tertiary)', fontWeight: 600 }}>{itemLabel}</span>
            <span style={{ color: 'var(--text)', fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>{value}</span>
          </span>
        ))}
      </div>
    </div>
  );
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
  bulkPaymentStatus,
  onPaymentStatusChange,
  bulkScheduledDate,
  onScheduledDateChange,
  isSaving,
  onApplyStatus,
  onApplyPartner,
  onApplyMessage,
  onApplyPaymentStatus,
  onApplySchedule,
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
            {ORDER_STATUS_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
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

      {action === 'payment' && (
        <>
          <span style={panelLabelStyle}>선택 주문 결제상태</span>
          <select data-testid="orders-bulk-payment-select" className="input" value={bulkPaymentStatus} onChange={(event) => onPaymentStatusChange(event.target.value)} style={{ width: 180, height: 32 }}>
            {PAYMENT_STATUSES.map((status) => <option key={status.value} value={status.value}>{status.label}</option>)}
          </select>
          <button data-testid="orders-bulk-payment-apply" className="btn btn--primary btn--sm" disabled={isSaving} onClick={onApplyPaymentStatus}>
            {isSaving ? '처리 중' : '적용'}
          </button>
        </>
      )}

      {action === 'schedule' && (
        <>
          <span style={panelLabelStyle}>선택 주문 방문일</span>
          <DatePicker
            compact
            testId="orders-bulk-schedule-date"
            ariaLabel="일괄 방문일"
            placeholder="방문일 선택"
            value={bulkScheduledDate}
            onChange={(value) => onScheduledDateChange(value)}
          />
          <button data-testid="orders-bulk-schedule-apply" className="btn btn--primary btn--sm" disabled={isSaving} onClick={onApplySchedule}>
            {isSaving ? '처리 중' : '적용'}
          </button>
          <span style={{ color: 'var(--text-tertiary)', fontSize: 11.5 }}>날짜를 비우면(지우기) 미배정으로 변경</span>
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

function getStatusTabs(statusCounts) {
  const counts = statusCounts || {};
  return [
    { key: 'all', label: '전체', count: counts.all ?? 0 },
    ...ORDER_STATUS_TAB_OPTIONS.map((option) => ({
      key: option.key,
      label: option.label,
      count: counts[option.key] ?? 0,
    })),
  ];
}

function getVisibleStatusTabKey(tab) {
  if (tab === 'all' || ORDER_STATUS_TAB_BY_KEY.has(tab)) {
    return tab;
  }
  const legacyMap = {
    today: 'schedule_work_confirmed',
    tomorrow_notice: 'schedule_work_confirmed',
    partner_pending: 'schedule_partner_checking',
    photo_review: 'work_done',
    pending: 'consulting_unassigned',
    work: 'schedule_work_confirmed',
    deliver: 'work_done',
    monthly_done: 'final_payment_complete',
  };
  return legacyMap[tab] || null;
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

function createOrdersExportFilename() {
  return `주문내보내기_${getAppTodayValue().replace(/-/g, '')}.xlsx`;
}

function downloadExportBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  try {
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
  } finally {
    URL.revokeObjectURL(url);
  }
}

function getInitialOrderTableColumnWidths() {
  if (typeof window === 'undefined') {
    return ORDER_TABLE_DEFAULT_WIDTHS;
  }
  try {
    const saved = window.localStorage.getItem(ORDER_TABLE_COLUMN_STORAGE_KEY);
    if (!saved) {
      return ORDER_TABLE_DEFAULT_WIDTHS;
    }
    return normalizeOrderTableColumnWidths(JSON.parse(saved));
  } catch {
    return ORDER_TABLE_DEFAULT_WIDTHS;
  }
}

function normalizeOrderTableColumnWidths(input) {
  const next = {};
  let total = 0;
  for (const column of ORDER_TABLE_COLUMNS) {
    const value = Number(input?.[column.key]);
    const width = Number.isFinite(value) ? Math.max(value, column.min) : column.width;
    next[column.key] = width;
    total += width;
  }

  if (!total) {
    return ORDER_TABLE_DEFAULT_WIDTHS;
  }

  for (const column of ORDER_TABLE_COLUMNS) {
    next[column.key] = Number(((next[column.key] / total) * 100).toFixed(3));
  }
  return next;
}

function resizeOrderTableColumnPair(widths, currentColumn, nextColumn, delta) {
  const currentWidth = widths[currentColumn.key];
  const nextWidth = widths[nextColumn.key];
  const minDelta = currentColumn.min - currentWidth;
  const maxDelta = nextWidth - nextColumn.min;
  const boundedDelta = Math.max(minDelta, Math.min(delta, maxDelta));

  return {
    ...widths,
    [currentColumn.key]: Number((currentWidth + boundedDelta).toFixed(3)),
    [nextColumn.key]: Number((nextWidth - boundedDelta).toFixed(3)),
  };
}

function toOrderRow(order) {
  const sizeOrQuantity = formatQuantity(order.size_or_quantity);
  const rawStatus = order.status;
  const status = orderWorkflowStatusValue(rawStatus, order.payment_status);
  return {
    id: order.id,
    groupId: order.group_id || null,
    partnerId: order.partner_id || null,
    recurringContractId: order.recurring_contract_id || null,
    status,
    rawStatus,
    receivedRaw: order.received_date,
    received: formatDate(order.received_date),
    visit: formatDate(order.scheduled_date) || '미정',
    scheduledDate: order.scheduled_date,
    timeWindow: order.requested_time || '-',
    team: order.team_name || '미배정',
    product: sizeOrQuantity ? `${order.service_name} (${sizeOrQuantity})` : order.service_name,
    serviceName: order.service_name,
    sizeOrQuantity,
    address: order.customer_address,
    addressDetail: order.customer_address_detail || '',
    fullAddress: [order.customer_address, order.customer_address_detail].filter(Boolean).join(' '),
    customer: order.customer_name,
    phone: formatPhone(order.customer_phone),
    amount: Number(order.total_amount || 0) + Number(order.onsite_extra_amount || 0),
    partnerPrice: Number(order.partner_price ?? order.partner_payment_amount ?? 0),
    vatType: order.vat_type || 'included',
    paymentStatus: order.payment_status,
    paid: toPaidState(order.payment_status),
    receiptType: order.receipt_type,
    receiptStatus: order.receipt_status,
    photo: toPhotoState(rawStatus),
    delivered: toDeliveredState(rawStatus),
  };
}

function createDateFilter(preset) {
  const today = getAppTodayDate();
  if (preset === 'upcoming') {
    // 오늘부터(미래 + 미정) — start/end는 비워두고 matchesVisitDateFilter에서 처리한다.
    return { preset, start: '', end: '' };
  }
  if (preset === 'today') {
    const value = formatDateValue(today);
    return { preset, start: value, end: value };
  }
  if (preset === 'tomorrow') {
    const value = formatDateValue(addDays(today, 1));
    return { preset, start: value, end: value };
  }
  if (preset === 'week') {
    return {
      preset,
      start: formatDateValue(startOfWeek(today)),
      end: formatDateValue(addDays(startOfWeek(today), 6)),
    };
  }
  if (preset === 'month') {
    const firstDay = new Date(today.getFullYear(), today.getMonth(), 1);
    const lastDay = new Date(today.getFullYear(), today.getMonth() + 1, 0);
    return {
      preset,
      start: formatDateValue(firstDay),
      end: formatDateValue(lastDay),
    };
  }
  if (preset === 'yesterday') {
    const value = formatDateValue(addDays(today, -1));
    return { preset, start: value, end: value };
  }
  if (preset === 'lastweek') {
    const lastMonday = addDays(startOfWeek(today), -7);
    return {
      preset,
      start: formatDateValue(lastMonday),
      end: formatDateValue(addDays(lastMonday, 6)),
    };
  }
  if (preset === 'last14') {
    // 지난 14일(오늘 포함 최근 2주)
    return {
      preset,
      start: formatDateValue(addDays(today, -13)),
      end: formatDateValue(today),
    };
  }
  return { preset: 'all', start: '', end: '' };
}

function createInitialDateFilter(initialTab, initialDatePreset) {
  if (initialDatePreset) {
    return createDateFilter(initialDatePreset);
  }
  if (initialTab === 'tomorrow_notice') {
    return createDateFilter('tomorrow');
  }
  if (['payment_check', 'photo_review', 'deliver', 'partner_pending'].includes(initialTab)) {
    return createDateFilter('all');
  }
  if (['monthly_done', 'monthly_revenue'].includes(initialTab)) {
    return createDateFilter('month');
  }
  // 기본 진입은 '오늘부터'(미래+미정)만 노출, '전체'를 눌러야 과거까지 본다.
  return createDateFilter('upcoming');
}

function normalizeDateRange(start, end) {
  if (start && end && start > end) {
    return { start: end, end: start };
  }
  return { start, end };
}

function formatDateFilterSummary(dateFilter) {
  if (dateFilter.preset === 'upcoming') {
    return '오늘 이후 방문';
  }
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

function formatDate(value) {
  if (!value) {
    return '';
  }

  const date = parseDateValue(value);
  if (!date) {
    return value;
  }
  return `${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

function formatFullDate(value) {
  if (!value) {
    return '';
  }

  const [year, month, day] = value.split('-');
  return `${year}.${month}.${day}`;
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

function formatWon(value) {
  const amount = Number(value || 0);
  const sign = amount < 0 ? '-' : '';
  return `${sign}₩${Math.abs(amount).toLocaleString()}`;
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

import { Badge, Icon, Sparkline, StatusBadge } from '../../../components/common/ui';
import { KPI, QUEUES, RECENT_PHOTOS, RECENT_SENDS, TODAY_JOBS, TOMORROW_JOBS } from '../../../mocks/cleaningOpsData';
import { getDashboardRecentActivity, getDashboardSummary, listAdminOrders } from '../../../api/admin';
import { useApiResource } from '../../../api/useApiResource';

// Admin Dashboard — KPI grid + work queues + today/tomorrow + recent

export function Dashboard({ onOpenOrder, onNav, onCreateOrder }) {
  const summary = useApiResource(getDashboardSummary);
  const orders = useApiResource(listAdminOrders);
  const recentActivity = useApiResource(getDashboardRecentActivity);
  const kpis = summary.data ? toKpis(summary.data) : KPI;
  const queues = summary.data ? toQueues(summary.data) : QUEUES;
  const todayJobs = orders.data ? toDashJobs(orders.data, 'today') : TODAY_JOBS;
  const tomorrowJobs = orders.data ? toDashJobs(orders.data, 'tomorrow') : TOMORROW_JOBS;
  const recentPhotos = recentActivity.data ? toRecentPhotos(recentActivity.data.photos) : RECENT_PHOTOS;
  const recentSends = recentActivity.data ? toRecentSends(recentActivity.data.messages) : RECENT_SENDS;
  const workCount = summary.data ? queues.reduce((sum, item) => sum + Number(item.count || 0), 0) : 0;

  return (
    <div data-testid="admin-dashboard-page" className="scroll" style={{ flex: 1, overflow: 'auto', padding: 20, background: 'var(--bg)' }}>
      <div style={{ maxWidth: 1320, margin: '0 auto' }}>

        {/* Greeting */}
        <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginBottom: 14 }}>
          <div>
            <div style={{ fontSize: 11.5, color: 'var(--text-tertiary)', marginBottom: 2 }}>{formatDashboardDate(new Date())}</div>
            <h2 style={{ margin: 0, fontSize: 18, fontWeight: 600, letterSpacing: '-0.02em' }}>
              안녕하세요 전소영님 <span style={{ color: 'var(--text-tertiary)', fontWeight: 400 }}>— 지금 처리할 일 {summary.isLoading ? '-' : workCount}건이 있습니다</span>
            </h2>
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            <button className="btn btn--secondary btn--sm">
              <Icon name="refresh" size={12}/> 새로고침
            </button>
            <button data-testid="dashboard-create-order" className="btn btn--primary btn--sm" onClick={onCreateOrder}>
              <Icon name="plus" size={12}/> 신규 주문 등록
            </button>
          </div>
        </div>

        {/* KPI grid — 7 cards in one row, last one wider */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 10, marginBottom: 16 }}>
          {kpis.map((k, i) => (
            <div key={i} className="card" style={{ padding: 12, position: 'relative', overflow: 'hidden' }}>
              <div style={{ fontSize: 11.5, color: 'var(--text-tertiary)', fontWeight: 500, letterSpacing: '-0.005em' }}>{k.label}</div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginTop: 4 }}>
                <span style={{ fontSize: 22, fontWeight: 600, letterSpacing: '-0.03em', color: 'var(--text)' }}>{k.value}</span>
                {k.suffix && <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{k.suffix}</span>}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 6 }}>
                <span style={{
                  fontSize: 10.5, fontWeight: 600,
                  color: k.delta.startsWith('+') ? 'var(--success-fg)' : k.delta.startsWith('-') ? 'var(--danger-fg)' : 'var(--text-tertiary)',
                }}>{k.delta}</span>
                <Sparkline values={k.trend} color={`var(--${k.tone === 'brand' ? 'brand' : k.tone === 'success' ? 'success-fg' : k.tone === 'danger' ? 'danger-fg' : k.tone === 'warn' ? 'warn-fg' : k.tone === 'purple' ? 'purple-fg' : 'info-fg'})`} width={50} height={18}/>
              </div>
            </div>
          ))}
        </div>

        {/* Work queues */}
        <div style={{ marginBottom: 18 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 8 }}>
            <h3 style={{ margin: 0, fontSize: 13, fontWeight: 600, letterSpacing: '-0.01em' }}>업무 큐</h3>
            <span style={{ fontSize: 11.5, color: 'var(--text-tertiary)' }}>클릭하면 해당 필터로 이동합니다</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 10 }}>
            {queues.map((q) => (
              <button key={q.key} onClick={() => onNav && onNav(q.targetPage || 'orders', { ordersTab: q.ordersTab || 'all' })}
                className="card"
                style={{
                  padding: 12, textAlign: 'left', cursor: 'pointer',
                  border: '1px solid var(--border)',
                  background: 'var(--surface)',
                  display: 'flex', flexDirection: 'column', gap: 8,
                  transition: 'all 100ms',
                }}
                onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'var(--brand)'; e.currentTarget.style.boxShadow = 'var(--shadow-sm)'; }}
                onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.boxShadow = 'none'; }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{
                    width: 24, height: 24, borderRadius: 5,
                    background: `var(--${q.tone}-bg)`, color: `var(--${q.tone}-fg)`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}>
                    <Icon name={q.icon} size={13}/>
                  </span>
                  <Icon name="arrowRight" size={12} color="var(--text-quaternary)"/>
                </div>
                <div>
                  <div style={{ fontSize: 11.5, color: 'var(--text-tertiary)', fontWeight: 500 }}>{q.title}</div>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginTop: 2 }}>
                    <span style={{ fontSize: 22, fontWeight: 600, letterSpacing: '-0.03em' }}>{q.count}</span>
                    <span style={{ fontSize: 11, color: 'var(--text-quaternary)' }}>건</span>
                  </div>
                </div>
                <div style={{ fontSize: 10.5, color: 'var(--text-quaternary)' }}>{q.desc}</div>
              </button>
            ))}
          </div>
        </div>

        {/* 2-column: today/tomorrow + photos/sends */}
        <div style={{ display: 'grid', gridTemplateColumns: '1.55fr 1fr', gap: 12 }}>
          {/* Today + tomorrow */}
          <div className="card" style={{ overflow: 'hidden' }}>
            <DashList
              title="오늘 작업"
              subtitle={`오늘 · ${summary.isLoading ? '-' : todayJobs.length}건`}
              jobs={todayJobs}
              onOpen={onOpenOrder}
              accent="info"
              isLoading={orders.isLoading}
              error={orders.error}
            />
            <div style={{ height: 1, background: 'var(--divider)' }}/>
            <DashList
              title="내일 작업"
              subtitle={`내일 · ${summary.isLoading ? '-' : tomorrowJobs.length}건`}
              jobs={tomorrowJobs}
              onOpen={onOpenOrder}
              accent="warn"
              muted
              isLoading={orders.isLoading}
              error={orders.error}
            />
          </div>

          {/* Recent photos + sends */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div className="card" style={{ padding: 0 }}>
              <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--divider)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Icon name="image" size={13} color="var(--text-tertiary)"/>
                  <span style={{ fontSize: 12.5, fontWeight: 600 }}>최근 사진 업로드</span>
                </div>
                <button className="btn btn--ghost btn--sm" style={{ height: 22, padding: '0 6px', fontSize: 11 }} onClick={() => onNav && onNav('photos')}>전체 보기</button>
              </div>
              <div>
                {recentActivity.isLoading && <DashMessage text="최근 사진을 불러오는 중입니다." />}
                {!recentActivity.isLoading && recentActivity.error && <DashMessage text="최근 사진을 불러오지 못했습니다." tone="danger" />}
                {!recentActivity.isLoading && !recentActivity.error && recentPhotos.length === 0 && <DashMessage text="최근 업로드 사진이 없습니다." />}
                {!recentActivity.isLoading && !recentActivity.error && recentPhotos.map((p, i) => (
                  <button key={p.photoId || i} onClick={() => onOpenOrder && onOpenOrder(p.orderId || p.id)} style={{
                    width: '100%',
                    display: 'flex', alignItems: 'center', gap: 10,
                    padding: '8px 14px',
                    border: 'none',
                    borderBottom: i < recentPhotos.length - 1 ? '1px solid var(--divider)' : 'none',
                    background: 'transparent',
                    textAlign: 'left',
                    cursor: 'pointer',
                  }}>
                    {p.fileUrl ? (
                      <img src={p.fileUrl} alt={p.label} style={{ width: 36, height: 36, borderRadius: 6, objectFit: 'cover', flexShrink: 0, background: 'var(--bg-muted)' }} />
                    ) : (
                      <div className="placeholder-img" style={{ width: 36, height: 36, fontSize: 9, flexShrink: 0 }}>IMG</div>
                    )}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 12, fontWeight: 500, display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-tertiary)' }}>{p.orderId || p.id}</span>
                        {p.label}
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 1 }}>{p.count} · {p.time}</div>
                    </div>
                    {p.tone === 'wait' && <Badge tone="warn" dot>검수대기</Badge>}
                    {p.tone === 'approved' && <Badge tone="success" dot>승인</Badge>}
                    {p.tone === 'partial' && <Badge tone="info" dot>업로드중</Badge>}
                  </button>
                ))}
              </div>
            </div>

            <div className="card" style={{ padding: 0 }}>
              <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--divider)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Icon name="send" size={13} color="var(--text-tertiary)"/>
                  <span style={{ fontSize: 12.5, fontWeight: 600 }}>최근 발송 이력</span>
                </div>
                <button className="btn btn--ghost btn--sm" style={{ height: 22, padding: '0 6px', fontSize: 11 }}>전체 보기</button>
              </div>
              <div>
                {recentActivity.isLoading && <DashMessage text="최근 발송 이력을 불러오는 중입니다." />}
                {!recentActivity.isLoading && recentActivity.error && <DashMessage text="최근 발송 이력을 불러오지 못했습니다." tone="danger" />}
                {!recentActivity.isLoading && !recentActivity.error && recentSends.length === 0 && <DashMessage text="최근 발송 이력이 없습니다." />}
                {!recentActivity.isLoading && !recentActivity.error && recentSends.map((s, i) => (
                  <button key={s.id || i} onClick={() => onOpenOrder && onOpenOrder(s.orderId)} style={{
                    width: '100%',
                    display: 'flex', alignItems: 'center', gap: 10,
                    padding: '7px 14px',
                    border: 'none',
                    borderBottom: i < recentSends.length - 1 ? '1px solid var(--divider)' : 'none',
                    background: 'transparent',
                    textAlign: 'left',
                    cursor: 'pointer',
                    fontSize: 12,
                  }}>
                    <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-tertiary)', width: 36 }}>{s.time}</span>
                    <span style={{ minWidth: 64, fontSize: 11, color: 'var(--text-secondary)' }}>{s.kind}</span>
                    <span style={{ flex: 1, color: 'var(--text)', overflow: 'hidden', textOverflow: 'ellipsis' }}>{s.target}</span>
                    <span style={{ fontSize: 10.5, color: 'var(--text-tertiary)' }}>{s.via}</span>
                    {s.state === 'delivered' && <Badge tone="success">전송</Badge>}
                    {s.state === 'read' && <Badge tone="info">읽음</Badge>}
                    {s.state === 'failed' && <Badge tone="danger">실패</Badge>}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function DashList({ title, subtitle, jobs, onOpen, accent, muted = false, isLoading = false, error = null }) {
  return (
    <div>
      <div style={{ padding: '10px 14px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--divider)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: `var(--${accent}-fg)` }}/>
          <span style={{ fontSize: 12.5, fontWeight: 600 }}>{title}</span>
          <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{subtitle}</span>
        </div>
        <button className="btn btn--ghost btn--sm" style={{ height: 22, padding: '0 6px', fontSize: 11 }}>일정표</button>
      </div>
      <div>
        {isLoading && <DashMessage text="작업을 불러오는 중입니다." />}
        {!isLoading && error && <DashMessage text="작업 목록을 불러오지 못했습니다." tone="danger" />}
        {!isLoading && !error && jobs.length === 0 && <DashMessage text="표시할 작업이 없습니다." />}
        {!isLoading && !error && jobs.map((j, i) => (
          <button key={j.id} onClick={() => onOpen && onOpen(j.id)}
            style={{
              width: '100%', textAlign: 'left',
              display: 'grid', gridTemplateColumns: '60px 80px 1fr 110px 90px',
              alignItems: 'center', gap: 10,
              padding: '7px 14px',
              border: 'none',
              borderBottom: i < jobs.length - 1 ? '1px solid var(--divider)' : 'none',
              background: muted ? 'var(--bg-subtle)' : 'transparent',
              cursor: 'pointer',
              fontSize: 12.5,
              opacity: muted ? 0.92 : 1,
            }}>
            <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-tertiary)' }}>{j.id}</span>
            <span style={{ fontSize: 11.5, color: 'var(--text-secondary)' }}>{j.time}</span>
            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              <span style={{ fontWeight: 500 }}>{j.product}</span>
              <span style={{ color: 'var(--text-tertiary)', marginLeft: 8, fontSize: 11.5 }}>{j.addr}</span>
            </span>
            <span style={{ fontSize: 11.5, color: 'var(--text-secondary)' }}>{j.team}</span>
            <StatusBadge status={j.status}/>
          </button>
        ))}
      </div>
    </div>
  );
}

function DashMessage({ text, tone = 'muted' }) {
  return (
    <div style={{
      padding: '12px 14px',
      color: tone === 'danger' ? 'var(--danger-fg)' : 'var(--text-tertiary)',
      fontSize: 12,
    }}>
      {text}
    </div>
  );
}

function toKpis(summary) {
  return [
    { label: '오늘 작업 예정', value: summary.today_jobs, delta: 'API', trend: [0, 0, 0, 0, summary.today_jobs || 0], tone: 'info' },
    { label: '내일 안내 대상', value: summary.tomorrow_notice_targets, delta: 'API', trend: [0, 0, 0, 0, summary.tomorrow_notice_targets || 0], tone: 'warn' },
    { label: '사진 검수 대기', value: summary.photo_review_pending, delta: 'API', trend: [0, 0, 0, 0, summary.photo_review_pending || 0], tone: 'purple' },
    { label: '고객 전달 필요', value: summary.customer_delivery_needed, delta: 'API', trend: [0, 0, 0, 0, summary.customer_delivery_needed || 0], tone: 'warn' },
    { label: '결제 확인 필요', value: summary.payment_check_needed, delta: 'API', trend: [0, 0, 0, 0, summary.payment_check_needed || 0], tone: 'danger' },
    { label: '이번 달 완료', value: summary.monthly_completed, delta: 'API', trend: [0, 0, 0, 0, summary.monthly_completed || 0], tone: 'success', suffix: '건' },
    { label: '이번 달 계약금액', value: formatWon(summary.monthly_revenue), delta: 'API', trend: [0, 0, 0, 0, summary.monthly_revenue || 0], tone: 'brand' },
  ];
}

function toQueues(summary) {
  return [
    { key: 'partner_pending', title: '협력사 확인 필요', count: summary.partner_pending, tone: 'warn', icon: 'clock', desc: '배정 후 확인 대기', targetPage: 'orders', ordersTab: 'partner_pending' },
    { key: 'tomorrow_notify', title: '내일 안내 발송 필요', count: summary.tomorrow_notice_targets, tone: 'warn', icon: 'send', desc: '내일 작업 예정', targetPage: 'orders', ordersTab: 'tomorrow_notice' },
    { key: 'today_work', title: '오늘 작업 예정', count: summary.today_jobs, tone: 'info', icon: 'truck', desc: '진행/예정 작업', targetPage: 'orders', ordersTab: 'today' },
    { key: 'photo_review', title: '사진 검수 대기', count: summary.photo_review_pending, tone: 'purple', icon: 'image', desc: '관리자 승인 필요', targetPage: 'photos' },
    { key: 'customer_deliver', title: '고객 전달 필요', count: summary.customer_delivery_needed, tone: 'warn', icon: 'sparkles', desc: '검수 완료 후 전달', targetPage: 'photos' },
    { key: 'payment_check', title: '결제 확인 필요', count: summary.payment_check_needed, tone: 'danger', icon: 'creditCard', desc: '잔금/미수 확인', targetPage: 'orders', ordersTab: 'payment_check' },
  ];
}

function toDashJobs(orders, target) {
  const today = startOfLocalDay(new Date());
  const wanted = new Date(today);
  if (target === 'tomorrow') {
    wanted.setDate(wanted.getDate() + 1);
  }

  return orders
    .filter((order) => isSameDate(order.scheduled_date, wanted))
    .filter((order) => (
      target === 'tomorrow'
        ? ['일정확정', '전날안내필요'].includes(order.status)
        : ['작업예정', '작업진행', '사진검수대기'].includes(order.status)
    ))
    .slice(0, 5)
    .map((order) => ({
      id: order.id,
      time: order.requested_time || '-',
      product: order.size_or_quantity ? `${order.service_name} ${order.size_or_quantity}` : order.service_name,
      addr: order.customer_address,
      team: order.team_name || '미배정',
      status: order.status,
    }));
}

function toRecentPhotos(photos) {
  return photos.map((photo) => ({
    photoId: photo.photo_id,
    orderId: photo.order_id,
    label: photo.size_or_quantity ? `${photo.service_name} ${photo.size_or_quantity}` : photo.service_name,
    count: `${photoTypeLabel(photo.photo_type)} · ${photo.customer_name}${photo.team_name ? ` · ${photo.team_name}` : ''}`,
    time: formatRelativeTime(photo.uploaded_at),
    tone: photo.is_customer_visible ? 'approved' : 'wait',
    fileUrl: photo.file_url,
  }));
}

function toRecentSends(messages) {
  return messages.map((message) => ({
    id: message.id,
    orderId: message.order_id,
    time: formatShortTime(message.sent_at || message.created_at),
    kind: messageTypeLabel(message.message_type),
    target: `${message.recipient_name} ${maskPhone(message.recipient_phone)}`,
    via: String(message.channel || '').toUpperCase(),
    state: message.status === 'failed' ? 'failed' : 'delivered',
  }));
}

function isSameDate(value, target) {
  if (!value) {
    return false;
  }
  const date = new Date(`${value}T00:00:00`);
  return date.getFullYear() === target.getFullYear()
    && date.getMonth() === target.getMonth()
    && date.getDate() === target.getDate();
}

function startOfLocalDay(value) {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate());
}

function formatWon(value) {
  return `₩${Number(value || 0).toLocaleString()}`;
}

function photoTypeLabel(type) {
  if (type === 'before') return '비포';
  if (type === 'after') return '애프터';
  return '기타';
}

function messageTypeLabel(type) {
  const labels = {
    customer_schedule_confirmed: '일정확정',
    customer_day_before: '전날안내',
    partner_assignment: '협력사배정',
    customer_photo_ready: '완료사진',
  };
  return labels[type] || type;
}

function formatShortTime(value) {
  if (!value) {
    return '-';
  }
  const date = new Date(value);
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
}

function formatRelativeTime(value) {
  if (!value) {
    return '-';
  }
  const diffMs = Date.now() - new Date(value).getTime();
  const minutes = Math.max(0, Math.floor(diffMs / 60000));
  if (minutes < 1) return '방금 전';
  if (minutes < 60) return `${minutes}분 전`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}시간 전`;
  return `${Math.floor(hours / 24)}일 전`;
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

function formatDashboardDate(value) {
  const weekdays = ['일요일', '월요일', '화요일', '수요일', '목요일', '금요일', '토요일'];
  return `${value.getFullYear()}년 ${value.getMonth() + 1}월 ${value.getDate()}일 ${weekdays[value.getDay()]} · ${formatShortTime(value.toISOString())}`;
}

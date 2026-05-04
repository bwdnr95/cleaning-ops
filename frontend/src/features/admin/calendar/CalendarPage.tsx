import React from 'react';

import { listAdminCalendarOrders, listPartners } from '../../../api/admin';
import { Icon } from '../../../components/common/ui';
import { useApiResource } from '../../../api/useApiResource';

export function CalendarPage({ onOpenOrder, onCreateOrder }) {
  const [view, setView] = React.useState('month');
  const [siteOpen, setSiteOpen] = React.useState(true);
  const [selectedPartnerId, setSelectedPartnerId] = React.useState('');
  const [currentMonth, setCurrentMonth] = React.useState(() => startOfMonth(new Date()));
  const year = currentMonth.getFullYear();
  const month = currentMonth.getMonth() + 1;
  const calendarKey = `${year}-${month}`;
  const loadCalendar = React.useCallback(
    () => listAdminCalendarOrders({ year, month }),
    [year, month],
  );
  const calendar = useApiResource(loadCalendar, calendarKey);
  const partners = useApiResource(listPartners);
  const allOrders = calendar.data || [];
  const orders = selectedPartnerId ? allOrders.filter((order) => order.partner_id === selectedPartnerId) : allOrders;
  const sites = toSites(partners.data || [], allOrders);
  const daysInMonth = new Date(year, month, 0).getDate();
  const firstDayOfWeek = new Date(year, month - 1, 1).getDay();
  const totalCells = Math.ceil((daysInMonth + firstDayOfWeek) / 7) * 7;
  const today = new Date();
  const isCurrentRealMonth = today.getFullYear() === year && today.getMonth() + 1 === month;
  const eventsByDay = groupOrdersByDay(orders);

  const cells = Array.from({ length: totalCells }).map((_, index) => {
    const dayNum = index - firstDayOfWeek + 1;
    if (dayNum < 1 || dayNum > daysInMonth) {
      return { empty: true };
    }
    return {
      day: dayNum,
      dow: index % 7,
      events: eventsByDay.get(dayNum) || [],
    };
  });

  const moveMonth = (delta) => {
    setCurrentMonth((value) => new Date(value.getFullYear(), value.getMonth() + delta, 1));
  };

  return (
    <div style={{ flex: 1, display: 'flex', minHeight: 0, background: 'var(--bg)' }}>
      {siteOpen && (
        <aside style={{
          width: 220,
          flexShrink: 0,
          background: 'var(--surface)',
          borderRight: '1px solid var(--border)',
          display: 'flex',
          flexDirection: 'column',
        }}>
          <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--divider)', display: 'flex', alignItems: 'center' }}>
            <span style={{ fontSize: 12, fontWeight: 600 }}>협력사 선택</span>
            <div style={{ flex: 1 }}/>
            <button onClick={() => setSiteOpen(false)} className="btn btn--ghost btn--sm" style={{ padding: '0 4px' }}>
              <Icon name="x" size={12}/>
            </button>
          </div>
          <div style={{ padding: '8px 10px', borderBottom: '1px solid var(--divider)' }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              padding: '0 8px',
              height: 28,
              background: 'var(--bg-subtle)',
              border: '1px solid var(--border)',
              borderRadius: 6,
              fontSize: 11.5,
              color: 'var(--text-tertiary)',
            }}>
              <Icon name="search" size={12}/> 협력사 필터
            </div>
          </div>
          <div className="scroll" style={{ flex: 1, overflow: 'auto', padding: '6px 0' }}>
            {sites.map((site) => {
              const active = site.id === (selectedPartnerId || 'all');
              return (
                <button key={site.id} onClick={() => setSelectedPartnerId(site.id === 'all' ? '' : site.id)}
                  style={{
                    width: '100%',
                    textAlign: 'left',
                    padding: '6px 14px',
                    border: 'none',
                    borderLeft: active ? '2px solid var(--brand)' : '2px solid transparent',
                    background: active ? 'var(--brand-bg)' : 'transparent',
                    color: active ? 'var(--brand)' : 'var(--text-secondary)',
                    fontSize: 12,
                    fontWeight: active ? 600 : 500,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                  }}>
                  <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{site.name}</span>
                  <span style={{ fontSize: 10.5, color: active ? 'var(--brand)' : 'var(--text-quaternary)' }}>{site.count}</span>
                </button>
              );
            })}
          </div>
        </aside>
      )}

      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <div style={{
          padding: '10px 20px',
          background: 'var(--surface)',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
        }}>
          {!siteOpen && (
            <button onClick={() => setSiteOpen(true)} className="btn btn--ghost btn--sm" style={{ padding: '0 6px' }}>
              <Icon name="list" size={13}/>
            </button>
          )}
          <button className="btn btn--secondary btn--sm" onClick={() => setCurrentMonth(startOfMonth(new Date()))}>오늘</button>
          <div style={{ display: 'flex' }}>
            <button className="btn btn--ghost btn--sm" style={{ padding: '0 4px' }} onClick={() => moveMonth(-1)}><Icon name="chevronLeft" size={13}/></button>
            <button className="btn btn--ghost btn--sm" style={{ padding: '0 4px' }} onClick={() => moveMonth(1)}><Icon name="chevronRight" size={13}/></button>
          </div>
          <h2 style={{ margin: 0, fontSize: 15, fontWeight: 700 }}>{year}년 {month}월</h2>
          <span style={{ fontSize: 11.5, color: 'var(--text-tertiary)' }}>
            {selectedPartnerId ? sites.find((site) => site.id === selectedPartnerId)?.name : '전체 협력사'} · 총 {orders.length}건
          </span>
          <div style={{ flex: 1 }}/>
          <Legend tone="warn" label="대기"/>
          <Legend tone="info" label="진행"/>
          <Legend tone="success" label="완료"/>
          <Legend tone="purple" label="작업중"/>
          <div style={{ width: 1, height: 18, background: 'var(--border)' }}/>
          <div style={{
            display: 'flex',
            background: 'var(--bg-subtle)',
            border: '1px solid var(--border)',
            borderRadius: 6,
            padding: 2,
          }}>
            {['month', 'week', 'day'].map((item) => (
              <button key={item} onClick={() => setView(item)}
                style={{
                  padding: '0 10px',
                  height: 22,
                  border: 'none',
                  borderRadius: 4,
                  background: view === item ? 'var(--surface)' : 'transparent',
                  color: view === item ? 'var(--text)' : 'var(--text-tertiary)',
                  fontSize: 11.5,
                  fontWeight: view === item ? 600 : 500,
                  cursor: 'pointer',
                  boxShadow: view === item ? 'var(--shadow-xs)' : 'none',
                }}>
                {item === 'month' ? '월' : item === 'week' ? '주' : '일'}
              </button>
            ))}
          </div>
          <button className="btn btn--primary btn--sm" onClick={onCreateOrder}>
            <Icon name="plus" size={12}/> 일정 추가
          </button>
        </div>

        <div className="scroll" style={{ flex: 1, overflow: 'auto', background: 'var(--bg)' }}>
          {calendar.isLoading && <CalendarState text="일정을 불러오는 중입니다." />}
          {!calendar.isLoading && calendar.error && <CalendarState text="일정을 불러오지 못했습니다." tone="danger" />}
          {!calendar.isLoading && !calendar.error && (
            <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 600 }}>
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(7, 1fr)',
                borderBottom: '1px solid var(--border)',
                background: 'var(--surface)',
              }}>
                {['일', '월', '화', '수', '목', '금', '토'].map((day, index) => (
                  <div key={day} style={{
                    padding: '8px 12px',
                    fontSize: 11,
                    fontWeight: 600,
                    color: index === 0 ? 'var(--danger-fg)' : index === 6 ? 'var(--info-fg)' : 'var(--text-tertiary)',
                    letterSpacing: '0.04em',
                    borderRight: index < 6 ? '1px solid var(--divider)' : 'none',
                  }}>{day}</div>
                ))}
              </div>

              <div style={{
                flex: 1,
                display: 'grid',
                gridTemplateColumns: 'repeat(7, 1fr)',
                gridAutoRows: '1fr',
                minHeight: 0,
              }}>
                {cells.map((cell, index) => {
                  if (cell.empty) {
                    return <div key={index} style={{
                      background: 'var(--bg-subtle)',
                      borderRight: index % 7 < 6 ? '1px solid var(--divider)' : 'none',
                      borderBottom: '1px solid var(--divider)',
                    }}/>;
                  }

                  const isToday = isCurrentRealMonth && cell.day === today.getDate();
                  return (
                    <div key={index} style={{
                      minHeight: 110,
                      padding: 6,
                      background: 'var(--surface)',
                      borderRight: index % 7 < 6 ? '1px solid var(--divider)' : 'none',
                      borderBottom: '1px solid var(--divider)',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 2,
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 2 }}>
                        {isToday ? (
                          <span style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            width: 20,
                            height: 20,
                            borderRadius: '50%',
                            background: 'var(--brand)',
                            color: '#fff',
                            fontSize: 11,
                            fontWeight: 700,
                          }}>{cell.day}</span>
                        ) : (
                          <span style={{
                            fontSize: 11.5,
                            fontWeight: 600,
                            color: cell.dow === 0 ? 'var(--danger-fg)' : cell.dow === 6 ? 'var(--info-fg)' : 'var(--text)',
                            paddingLeft: 2,
                          }}>{cell.day}</span>
                        )}
                        {cell.events.length > 0 && (
                          <span style={{ fontSize: 9.5, color: 'var(--text-quaternary)' }}>· {cell.events.length}건</span>
                        )}
                      </div>
                      {cell.events.slice(0, 3).map((event) => (
                        <button key={event.id} onClick={() => onOpenOrder && onOpenOrder(event.id)}
                          style={{
                            padding: '2px 5px',
                            background: event.tone === 'warn' ? 'var(--warn-bg)' : 'transparent',
                            border: 'none',
                            borderLeft: `2px solid var(--${event.tone}-fg)`,
                            borderRadius: 3,
                            fontSize: 10.5,
                            color: 'var(--text)',
                            display: 'flex',
                            alignItems: 'center',
                            gap: 4,
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            cursor: 'pointer',
                            textAlign: 'left',
                          }}>
                          <span style={{ color: 'var(--text-tertiary)', fontSize: 9.5, flexShrink: 0 }}>{event.time}</span>
                          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{event.title}</span>
                        </button>
                      ))}
                      {cell.events.length > 3 && (
                        <div style={{ fontSize: 10, color: 'var(--text-tertiary)', padding: '0 5px' }}>
                          + {cell.events.length - 3}건 더보기
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

function CalendarState({ text, tone = 'muted' }) {
  return (
    <div style={{
      padding: 20,
      color: tone === 'danger' ? 'var(--danger-fg)' : 'var(--text-tertiary)',
      fontSize: 12.5,
    }}>
      {text}
    </div>
  );
}

function Legend({ tone, label }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11, color: 'var(--text-tertiary)' }}>
      <span style={{ width: 8, height: 8, borderRadius: 2, background: `var(--${tone}-fg)` }}/>
      {label}
    </span>
  );
}

function startOfMonth(date) {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

function groupOrdersByDay(orders) {
  const groups = new Map();
  for (const order of orders) {
    if (!order.scheduled_date) {
      continue;
    }
    const day = Number(order.scheduled_date.slice(8, 10));
    const event = {
      id: order.id,
      time: order.requested_time || '-',
      title: order.size_or_quantity ? `${order.service_name} ${order.size_or_quantity}` : order.service_name,
      tone: statusTone(order.status),
    };
    groups.set(day, [...(groups.get(day) || []), event]);
  }
  return groups;
}

function toSites(partners, orders) {
  const counts = new Map();
  for (const order of orders) {
    if (order.partner_id) {
      counts.set(order.partner_id, (counts.get(order.partner_id) || 0) + 1);
    }
  }
  const partnerSites = partners.map((partner) => ({
    id: partner.id,
    name: partner.name,
    count: counts.get(partner.id) || 0,
  }));
  return [
    { id: 'all', name: '전체 협력사', count: orders.length },
    ...partnerSites,
  ];
}

function statusTone(status) {
  if (['협력사확인중', '전날안내필요', '사진검수대기', '고객전달필요'].includes(status)) {
    return 'warn';
  }
  if (['작업진행'].includes(status)) {
    return 'purple';
  }
  if (['고객전달완료', '서비스완료'].includes(status)) {
    return 'success';
  }
  return 'info';
}

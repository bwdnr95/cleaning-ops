import React from 'react';

import { listAdminNotifications, type AdminNotification } from '../../../api/notifications';
import { useApiResource } from '../../../api/useApiResource';
import { Badge, Icon } from '../../../components/common/ui';

export function AdminNotificationsBell() {
  const [isOpen, setIsOpen] = React.useState(false);
  const containerRef = React.useRef<HTMLDivElement>(null);
  const notifications = useApiResource(listAdminNotifications);
  const reloadRef = React.useRef(notifications.reload);
  const items = notifications.data || [];
  reloadRef.current = notifications.reload;

  React.useEffect(() => {
    const timer = window.setInterval(() => reloadRef.current(), 30000);
    return () => window.clearInterval(timer);
  }, []);

  React.useEffect(() => {
    if (!isOpen) {
      return undefined;
    }

    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsOpen(false);
      }
    };
    const closeOnOutsideClick = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('keydown', closeOnEscape);
    document.addEventListener('mousedown', closeOnOutsideClick);
    return () => {
      document.removeEventListener('keydown', closeOnEscape);
      document.removeEventListener('mousedown', closeOnOutsideClick);
    };
  }, [isOpen]);

  return (
    <div ref={containerRef} style={{ position: 'relative' }}>
      <button
        type="button"
        data-testid="admin-notifications-button"
        className="btn btn--ghost btn--sm"
        aria-label="운영 알림"
        aria-expanded={isOpen}
        onClick={() => setIsOpen((current) => !current)}
        style={{ position: 'relative', width: 34, padding: 0 }}
      >
        <Icon name="bell" size={15} />
        {items.length > 0 && (
          <span style={badgeDotStyle}>{items.length > 9 ? '9+' : items.length}</span>
        )}
      </button>
      {isOpen && (
        <div data-testid="admin-notifications-panel" role="region" aria-label="운영 알림 목록" style={panelStyle}>
          <div style={panelHeaderStyle}>
            <span>운영 알림</span>
            <button type="button" aria-label="알림 새로고침" className="btn btn--ghost btn--sm" onClick={() => notifications.reload()} style={{ padding: '0 6px' }}>
              <Icon name="refresh" size={12} />
            </button>
          </div>
          {notifications.isLoading ? (
            <div style={stateStyle}>알림을 불러오는 중입니다.</div>
          ) : notifications.error ? (
            <div style={stateStyle}>알림을 불러오지 못했습니다.</div>
          ) : items.length === 0 ? (
            <div style={stateStyle}>새 알림이 없습니다.</div>
          ) : (
            <div style={{ maxHeight: 390, overflow: 'auto' }}>
              {items.map((item) => (
                <NotificationItem key={item.id} item={item} onOpen={() => setIsOpen(false)} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function NotificationItem({ item, onOpen }: { readonly item: AdminNotification; readonly onOpen: () => void }) {
  const openOrder = () => {
    onOpen();
    if (typeof window !== 'undefined') {
      window.location.hash = `#orders/${encodeURIComponent(item.order_id)}`;
    }
  };

  return (
    <button
      type="button"
      data-testid={`admin-notification-${item.id}`}
      onClick={openOrder}
      style={itemStyle}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 5 }}>
        <Badge tone={actorTone(item.actor_label)}>{item.actor_label}</Badge>
        <span style={{ flex: 1, fontSize: 11, color: 'var(--text-tertiary)', textAlign: 'right' }}>
          {formatNotificationTime(item.created_at)}
        </span>
      </div>
      <div style={{ fontSize: 12.5, fontWeight: 800, color: 'var(--text)', marginBottom: 3 }}>
        {item.title}
      </div>
      <div style={{ fontSize: 11.5, color: 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {item.customer_name} · {item.service_name}
      </div>
      {item.description && (
        <div className="multiline-text" style={{ marginTop: 5, fontSize: 11.5, color: 'var(--text-tertiary)', lineHeight: 1.45 }}>
          {item.description}
        </div>
      )}
    </button>
  );
}

function actorTone(actorLabel: string) {
  if (actorLabel === '고객') {
    return 'warn';
  }
  if (actorLabel === '협력사') {
    return 'brand';
  }
  return 'neutral';
}

function formatNotificationTime(value?: string | null) {
  if (!value) {
    return '-';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '-';
  }
  return new Intl.DateTimeFormat('ko-KR', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

const badgeDotStyle: React.CSSProperties = {
  position: 'absolute',
  top: -3,
  right: -2,
  minWidth: 16,
  height: 16,
  padding: '0 4px',
  borderRadius: 999,
  background: 'var(--danger-fg)',
  color: '#fff',
  fontSize: 10,
  fontWeight: 800,
  lineHeight: '16px',
};

const panelStyle: React.CSSProperties = {
  position: 'absolute',
  top: 36,
  right: 0,
  zIndex: 1200,
  width: 360,
  maxWidth: 'calc(100vw - 24px)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  background: 'var(--surface)',
  boxShadow: '0 18px 44px rgba(15, 23, 42, 0.18)',
  overflow: 'hidden',
};

const panelHeaderStyle: React.CSSProperties = {
  height: 38,
  padding: '0 10px',
  borderBottom: '1px solid var(--divider)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  fontSize: 12.5,
  fontWeight: 800,
};

const stateStyle: React.CSSProperties = {
  padding: 16,
  fontSize: 12,
  color: 'var(--text-tertiary)',
};

const itemStyle: React.CSSProperties = {
  display: 'block',
  width: '100%',
  textAlign: 'left',
  padding: '10px 12px',
  border: 'none',
  borderBottom: '1px solid var(--divider)',
  background: 'var(--surface)',
  cursor: 'pointer',
};

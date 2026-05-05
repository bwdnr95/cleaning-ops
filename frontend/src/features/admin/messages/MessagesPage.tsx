import React from 'react';

import { listAdminMessages } from '../../../api/messages';
import { Badge, Icon } from '../../../components/common/ui';
import { useApiResource } from '../../../api/useApiResource';

export function MessagesPage() {
  const messagesResource = useApiResource(listAdminMessages);
  const messages = messagesResource.data || [];
  const stats = toStats(messages);

  return (
    <div data-testid="admin-messages-page" style={{ flex: 1, overflow: 'auto', background: 'var(--bg)', padding: 20 }}>
      <div style={{ maxWidth: 1220, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
          <StatCard label="전체 발송" value={messages.length} icon="send" />
          <StatCard label="성공" value={stats.sent} icon="check" tone="success" />
          <StatCard label="실패" value={stats.failed} icon="x" tone="danger" />
          <StatCard label="고객 링크" value={stats.customerLinks} icon="fileText" tone="info" />
        </div>

        <section className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{
            height: 42,
            padding: '0 14px',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            borderBottom: '1px solid var(--divider)',
          }}>
            <Icon name="history" size={14} color="var(--text-tertiary)" />
            <strong style={{ fontSize: 13 }}>발송 이력</strong>
            <div style={{ flex: 1 }} />
            <button className="btn btn--ghost btn--sm" onClick={messagesResource.reload}>
              <Icon name="refresh" size={12}/> 새로고침
            </button>
          </div>

          {messagesResource.isLoading && <StateLine text="발송 이력을 불러오는 중입니다." />}
          {!messagesResource.isLoading && messagesResource.error && <StateLine text="발송 이력을 불러오지 못했습니다." tone="danger" />}
          {!messagesResource.isLoading && !messagesResource.error && messages.length === 0 && <StateLine text="아직 발송 이력이 없습니다." />}
          {!messagesResource.isLoading && !messagesResource.error && messages.length > 0 && (
            <div style={{ display: 'grid', gridTemplateColumns: '140px 150px 110px 1fr 92px 82px', fontSize: 12 }}>
              {['발송시각', '유형', '수신자', '내용', '채널', '상태'].map((header) => (
                <HeaderCell key={header}>{header}</HeaderCell>
              ))}
              {messages.map((message) => (
                <React.Fragment key={message.id}>
                  <BodyCell mono>{formatDateTime(message.sent_at || message.created_at)}</BodyCell>
                  <BodyCell>{messageTypeLabel(message.message_type)}</BodyCell>
                  <BodyCell>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{message.recipient_name}</div>
                      <div className="mono" style={{ color: 'var(--text-tertiary)', fontSize: 10.5 }}>{maskPhone(message.recipient_phone)}</div>
                    </div>
                  </BodyCell>
                  <BodyCell>
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {message.content}
                    </span>
                  </BodyCell>
                  <BodyCell>{String(message.channel || '').toUpperCase()}</BodyCell>
                  <BodyCell>
                    <Badge tone={message.status === 'sent' ? 'success' : 'danger'} dot>{messageStatusLabel(message.status)}</Badge>
                  </BodyCell>
                </React.Fragment>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

function StatCard({ label, value, icon, tone = 'neutral' }) {
  return (
    <div className="card" style={{ padding: 14, display: 'flex', alignItems: 'center', gap: 10 }}>
      <span style={{
        width: 30,
        height: 30,
        borderRadius: 6,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: `var(--${tone}-bg, var(--neutral-bg))`,
        color: `var(--${tone}-fg, var(--neutral-fg))`,
      }}>
        <Icon name={icon} size={14} />
      </span>
      <div>
        <div style={{ fontSize: 20, fontWeight: 700, lineHeight: 1 }}>{value}</div>
        <div style={{ marginTop: 4, fontSize: 11.5, color: 'var(--text-tertiary)' }}>{label}</div>
      </div>
    </div>
  );
}

function HeaderCell({ children }) {
  return (
    <div style={{
      padding: '9px 12px',
      borderBottom: '1px solid var(--border)',
      color: 'var(--text-tertiary)',
      fontSize: 11,
      fontWeight: 600,
      background: 'var(--bg-subtle)',
    }}>
      {children}
    </div>
  );
}

function BodyCell({ children, mono = false }) {
  return (
    <div style={{
      minWidth: 0,
      minHeight: 44,
      padding: '9px 12px',
      borderBottom: '1px solid var(--divider)',
      display: 'flex',
      alignItems: 'center',
      color: 'var(--text)',
      fontFamily: mono ? 'var(--font-mono)' : 'inherit',
    }}>
      {children}
    </div>
  );
}

function StateLine({ text, tone = 'muted' }) {
  return (
    <div style={{
      padding: 18,
      fontSize: 12.5,
      color: tone === 'danger' ? 'var(--danger-fg)' : 'var(--text-tertiary)',
    }}>
      {text}
    </div>
  );
}

function toStats(messages) {
  return {
    sent: messages.filter((message) => message.status === 'sent').length,
    failed: messages.filter((message) => message.status === 'failed').length,
    customerLinks: messages.filter((message) => ['customer_schedule_confirmed', 'customer_day_before', 'customer_photo_ready'].includes(message.message_type)).length,
  };
}

function messageTypeLabel(type) {
  if (type === 'customer_schedule_confirmed') return '일정확정 안내';
  if (type === 'customer_day_before') return '전날 안내';
  if (type === 'partner_assignment') return '협력사 배정';
  if (type === 'customer_photo_ready') return '사진 링크';
  return type;
}

function messageStatusLabel(status) {
  if (status === 'sent') return '성공';
  if (status === 'failed') return '실패';
  return status || '-';
}

function formatDateTime(value) {
  if (!value) {
    return '-';
  }
  const date = new Date(value);
  return `${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
}

function maskPhone(phone) {
  if (!phone) {
    return '-';
  }
  const digits = phone.replace(/\D/g, '');
  if (digits.length < 8) {
    return phone;
  }
  return `${digits.slice(0, 3)}-${digits.slice(3, 5)}**-${digits.slice(-4)}`;
}

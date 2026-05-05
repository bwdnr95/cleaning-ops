import React from 'react';

import { getAdminOrder, listPartners, updateAdminOrder } from '../../../api/admin';
import {
  sendCustomerDayBefore,
  sendCustomerPhotoReady,
  sendCustomerScheduleConfirmed,
  sendPartnerAssignment,
} from '../../../api/messages';
import { DatePicker } from '../../../components/common/DatePicker';
import { Avatar, Badge, Icon, StatusBadge } from '../../../components/common/ui';
import { ORDER_STATUSES } from '../../../domain/orderStatus';
import {
  PARTNER_PAYMENT_STATUSES,
  PAYMENT_STATUSES,
  partnerPaymentStatusLabel,
  paymentStatusLabel,
} from '../../../domain/paymentStatus';
import { useApiResource } from '../../../api/useApiResource';

export function OrderDetailPage({ orderId, onBack, onEdit, onNav }) {
  const loadOrder = React.useCallback(() => getAdminOrder(orderId), [orderId]);
  const orderResource = useApiResource(loadOrder, orderId);
  const partnersResource = useApiResource(listPartners);
  const order = orderResource.data;
  const [selectedStatus, setSelectedStatus] = React.useState('');
  const [selectedPartnerId, setSelectedPartnerId] = React.useState('');
  const [selectedScheduledDate, setSelectedScheduledDate] = React.useState('');
  const [selectedRequestedTime, setSelectedRequestedTime] = React.useState('');
  const [selectedPaymentStatus, setSelectedPaymentStatus] = React.useState('');
  const [selectedPartnerPaymentStatus, setSelectedPartnerPaymentStatus] = React.useState('');
  const [isSaving, setIsSaving] = React.useState(false);
  const [notice, setNotice] = React.useState(null);
  const [error, setError] = React.useState(null);

  React.useEffect(() => {
    if (order) {
      setSelectedStatus(order.status);
      setSelectedPartnerId(order.partner_id || '');
      setSelectedScheduledDate(order.scheduled_date || '');
      setSelectedRequestedTime(order.requested_time || '');
      setSelectedPaymentStatus(order.payment_status || '');
      setSelectedPartnerPaymentStatus(order.partner_payment_status || '');
    }
  }, [order]);

  const handleStatusChange = async () => {
    await runAction(async () => {
      await updateAdminOrder(order.id, { status: selectedStatus });
      setNotice('상태 변경을 타임라인에 기록했습니다.');
      orderResource.reload();
    });
  };

  const handlePartnerAssign = async () => {
    const partner = (partnersResource.data || []).find((item) => item.id === selectedPartnerId);
    await runAction(async () => {
      await updateAdminOrder(order.id, {
        partner_id: selectedPartnerId || null,
        team_name: partner?.name || null,
      });
      setNotice('협력사 배정을 타임라인에 기록했습니다.');
      orderResource.reload();
    });
  };

  const handleScheduleUpdate = async () => {
    await runAction(async () => {
      await updateAdminOrder(order.id, {
        scheduled_date: selectedScheduledDate || null,
        requested_time: selectedRequestedTime || null,
      });
      setNotice('방문 일정 변경을 타임라인에 기록했습니다.');
      orderResource.reload();
    });
  };

  const handlePaymentUpdate = async () => {
    await runAction(async () => {
      await updateAdminOrder(order.id, {
        payment_status: selectedPaymentStatus || null,
        partner_payment_status: selectedPartnerPaymentStatus || null,
      });
      setNotice('결제/정산 변경을 타임라인에 기록했습니다.');
      orderResource.reload();
    });
  };

  const handleSendCustomerScheduleConfirmed = async () => {
    await runAction(async () => {
      await sendCustomerScheduleConfirmed(order.id);
      setNotice('고객 일정확정 안내를 발송했습니다.');
      orderResource.reload();
    });
  };

  const handleSendCustomerDayBefore = async () => {
    await runAction(async () => {
      await sendCustomerDayBefore(order.id);
      setNotice('고객 전날 안내를 발송했습니다.');
      orderResource.reload();
    });
  };

  const handleSendPartnerAssignment = async () => {
    await runAction(async () => {
      await sendPartnerAssignment(order.id);
      setNotice('협력사 배정 안내를 발송했습니다.');
      orderResource.reload();
    });
  };

  const handleSendCustomerPhotoReady = async () => {
    await runAction(async () => {
      await sendCustomerPhotoReady(order.id);
      setNotice('고객 사진 확인 링크를 발송했습니다.');
      orderResource.reload();
    });
  };

  const runAction = async (action) => {
    setError(null);
    setNotice(null);
    setIsSaving(true);
    try {
      await action();
    } catch (requestError) {
      setError(toActionErrorMessage(requestError));
    } finally {
      setIsSaving(false);
    }
  };

  if (orderResource.isLoading) {
    return <DetailState text="주문 상세를 불러오는 중입니다." onBack={onBack} />;
  }

  if (orderResource.error) {
    return <DetailState text="주문 상세를 불러오지 못했습니다." tone="danger" onBack={onBack} />;
  }

  if (!order) {
    return <DetailState text="주문을 찾을 수 없습니다." onBack={onBack} />;
  }

  const visiblePhotos = order.photos || [];
  const messageLogs = order.message_logs || [];
  const timeline = order.timeline || [];
  const selectedPartner = (partnersResource.data || []).find((partner) => partner.id === order.partner_id);
  const hasScheduleChanges = selectedScheduledDate !== (order.scheduled_date || '') || selectedRequestedTime !== (order.requested_time || '');

  return (
    <div data-testid="admin-order-detail-page" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, background: 'var(--bg)' }}>
      <div style={{
        padding: '10px 20px',
        background: 'var(--surface)',
        borderBottom: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'center',
        gap: 10,
      }}>
        <button className="btn btn--ghost btn--sm" onClick={onBack} style={{ padding: '0 6px' }}>
          <Icon name="chevronLeft" size={13}/> 목록
        </button>
        <span style={{ width: 1, height: 16, background: 'var(--border)' }}/>
        <span className="mono" style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>{order.id}</span>
        <h2 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>{formatService(order)}</h2>
        <StatusBadge status={order.status}/>
        <div style={{ flex: 1 }}/>
        <button className="btn btn--ghost btn--sm" onClick={orderResource.reload}>
          <Icon name="refresh" size={12}/> 새로고침
        </button>
        <button className="btn btn--secondary btn--sm" onClick={onEdit}>
          수정
        </button>
        <button className="btn btn--ghost btn--sm" onClick={() => onNav?.('calendar')}>
          <Icon name="calendar" size={12}/> 일정표
        </button>
      </div>

      <div className="scroll" style={{ flex: 1, overflow: 'auto', padding: 20 }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 16, maxWidth: 1320, margin: '0 auto' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <Section title="고객 정보" icon="user">
              <KV col={2}>
                <KVItem label="고객명" value={order.customer_name}/>
                <KVItem label="연락처" value={formatPhone(order.customer_phone)} mono/>
                <KVItem label="유입 경로" value={order.source_channel || '-'}/>
                <KVItem label="고객 링크 토큰" value={order.customer_token} mono/>
                <KVItem label="주소" value={order.customer_address} span={2}/>
                <KVItem label="요청사항" value={order.special_request || '-'} span={2} multiline/>
              </KV>
            </Section>

            <Section title="상품 / 일정" icon="package">
              <KV col={2}>
                <KVItem label="상품명" value={order.service_name}/>
                <KVItem label="수량/규격" value={order.size_or_quantity || '-'}/>
                <KVItem label="방문 예정일" value={order.scheduled_date || '미정'}/>
                <KVItem label="요청 시간" value={order.requested_time || '-'}/>
                <KVItem label="상세" value={order.service_detail || '-'} span={2} multiline/>
              </KV>
            </Section>

            <Section title="금액 / 결제" icon="creditCard">
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 0 }}>
                <Money label="총 금액" value={order.total_amount}/>
                <Money label="계약금" value={order.deposit_amount}/>
                <Money label="잔금" value={order.balance_amount}/>
                <Money label="현장 추가" value={order.onsite_extra_amount}/>
              </div>
              <div style={{ marginTop: 10 }}>
                <KV col={2}>
                  <KVItem label="결제 상태" value={paymentStatusLabel(order.payment_status)}/>
                  <KVItem label="VAT" value={order.vat_type || '-'}/>
                  <KVItem label="결제 메모" value={order.payment_memo || '-'} span={2} multiline/>
                  <KVItem label="증빙 메모" value={order.evidence_memo || '-'} span={2} multiline/>
                </KV>
              </div>
            </Section>

            <Section title="협력사 배정" icon="truck">
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <Avatar name={(order.team_name || selectedPartner?.name || '미')[0]} size={36} tone="info"/>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 600 }}>{order.team_name || selectedPartner?.name || '미배정'}</div>
                  <div style={{ fontSize: 11.5, color: 'var(--text-tertiary)', marginTop: 2 }}>
                    협력사 ID: {order.partner_id || '-'} · 정산 상태: {partnerPaymentStatusLabel(order.partner_payment_status)}
                  </div>
                </div>
                <Badge tone={order.partner_id ? 'success' : 'warn'} dot>
                  {order.partner_id ? '배정됨' : '미배정'}
                </Badge>
              </div>
            </Section>

            <Section title="사진" icon="image" badge={<Badge tone="warn">{visiblePhotos.filter((photo) => !photo.is_customer_visible).length} 미승인</Badge>}>
              {visiblePhotos.length === 0 ? (
                <EmptyLine text="업로드된 사진이 없습니다." />
              ) : (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 8 }}>
                  {visiblePhotos.map((photo) => (
                    <div key={photo.id} style={{ border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden', background: 'var(--surface)' }}>
                      <img src={photo.file_url} alt={photo.file_name || photo.photo_type}
                        style={{ display: 'block', width: '100%', aspectRatio: '1', objectFit: 'cover', background: 'var(--bg-muted)' }} />
                      <div style={{ padding: 6, display: 'flex', alignItems: 'center', gap: 4 }}>
                        <Badge tone={photo.is_customer_visible ? 'success' : 'warn'}>{photoTypeLabel(photo.photo_type)}</Badge>
                        <span style={{ fontSize: 10.5, color: 'var(--text-tertiary)' }}>{photo.is_customer_visible ? '공개' : '비공개'}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Section>

            <Section title="발송 이력" icon="send">
              {messageLogs.length === 0 ? (
                <EmptyLine text="발송 이력이 없습니다." />
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {messageLogs.map((log) => (
                    <div key={log.id} style={{ display: 'grid', gridTemplateColumns: '120px 1fr 70px', gap: 10, alignItems: 'center', fontSize: 12, padding: '8px 0', borderBottom: '1px solid var(--divider)' }}>
                      <span className="mono" style={{ color: 'var(--text-tertiary)', fontSize: 10.5 }}>{formatDateTime(log.sent_at || log.created_at)}</span>
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{messageTypeLabel(log.message_type)} · {log.recipient_name}</span>
                      <Badge tone={log.status === 'sent' ? 'success' : 'danger'}>{messageStatusLabel(log.status)}</Badge>
                    </div>
                  ))}
                </div>
              )}
            </Section>
          </div>

          <aside style={{ display: 'flex', flexDirection: 'column', gap: 12, position: 'sticky', top: 0, alignSelf: 'flex-start' }}>
            <div className="card" style={{ padding: 14 }}>
              <PanelTitle>상태 변경</PanelTitle>
              <select className="input" value={selectedStatus} onChange={(event) => setSelectedStatus(event.target.value)} style={{ width: '100%', height: 34, marginBottom: 8 }}>
                {ORDER_STATUSES.map((status) => <option key={status} value={status}>{status}</option>)}
              </select>
              <button className="btn btn--primary btn--block" disabled={isSaving || selectedStatus === order.status} onClick={() => void handleStatusChange()}>
                <Icon name="check" size={13}/> 상태 저장
              </button>
            </div>

            <div className="card" style={{ padding: 14 }}>
              <PanelTitle>협력사 배정</PanelTitle>
              <select className="input" value={selectedPartnerId} onChange={(event) => setSelectedPartnerId(event.target.value)} style={{ width: '100%', height: 34, marginBottom: 8 }}>
                <option value="">미배정</option>
                {(partnersResource.data || []).map((partner) => (
                  <option key={partner.id} value={partner.id}>{partner.name}</option>
                ))}
              </select>
              <button className="btn btn--secondary btn--block" disabled={isSaving || selectedPartnerId === (order.partner_id || '')} onClick={() => void handlePartnerAssign()}>
                <Icon name="user" size={13}/> 배정 저장
              </button>
            </div>

            <div className="card" style={{ padding: 14 }}>
              <PanelTitle>방문 일정</PanelTitle>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 5, marginBottom: 8 }}>
                <span style={{ fontSize: 10.5, color: 'var(--text-tertiary)', fontWeight: 600 }}>방문 예정일</span>
                <DatePicker
                  testId="detail-scheduled-date"
                  value={selectedScheduledDate}
                  onChange={setSelectedScheduledDate}
                  placeholder="방문일 선택"
                />
              </label>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 5, marginBottom: 8 }}>
                <span style={{ fontSize: 10.5, color: 'var(--text-tertiary)', fontWeight: 600 }}>요청 시간</span>
                <input
                  data-testid="detail-requested-time"
                  className="input"
                  value={selectedRequestedTime}
                  onChange={(event) => setSelectedRequestedTime(event.target.value)}
                  placeholder="14:00 또는 오후 2-5시"
                  style={{ width: '100%', height: 34 }}
                />
              </label>
              <button
                data-testid="detail-schedule-save"
                className="btn btn--secondary btn--block"
                disabled={isSaving || !hasScheduleChanges}
                onClick={() => void handleScheduleUpdate()}
              >
                <Icon name="calendar" size={13}/> 일정 저장
              </button>
            </div>

            <div className="card" style={{ padding: 14 }}>
              <PanelTitle>결제 / 정산</PanelTitle>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 5, marginBottom: 8 }}>
                <span style={{ fontSize: 10.5, color: 'var(--text-tertiary)', fontWeight: 600 }}>고객 결제 상태</span>
                <select className="input" value={selectedPaymentStatus} onChange={(event) => setSelectedPaymentStatus(event.target.value)} style={{ width: '100%', height: 34 }}>
                  <option value="">미입력</option>
                  {PAYMENT_STATUSES.map((status) => (
                    <option key={status.value} value={status.value}>{status.label}</option>
                  ))}
                </select>
              </label>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 5, marginBottom: 8 }}>
                <span style={{ fontSize: 10.5, color: 'var(--text-tertiary)', fontWeight: 600 }}>협력사 정산 상태</span>
                <select className="input" value={selectedPartnerPaymentStatus} onChange={(event) => setSelectedPartnerPaymentStatus(event.target.value)} style={{ width: '100%', height: 34 }}>
                  <option value="">미입력</option>
                  {PARTNER_PAYMENT_STATUSES.map((status) => (
                    <option key={status.value} value={status.value}>{status.label}</option>
                  ))}
                </select>
              </label>
              <button
                className="btn btn--secondary btn--block"
                disabled={
                  isSaving
                  || (
                    selectedPaymentStatus === (order.payment_status || '')
                    && selectedPartnerPaymentStatus === (order.partner_payment_status || '')
                  )
                }
                onClick={() => void handlePaymentUpdate()}
              >
                <Icon name="creditCard" size={13}/> 결제/정산 저장
              </button>
            </div>

            <div className="card" style={{ padding: 14 }}>
              <PanelTitle>안내 발송</PanelTitle>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <button data-testid="send-customer-schedule-confirmed" className="btn btn--secondary btn--block" disabled={isSaving} onClick={() => void handleSendCustomerScheduleConfirmed()}>
                  <Icon name="send" size={13}/> 일정확정 안내
                </button>
                <button data-testid="send-customer-day-before" className="btn btn--secondary btn--block" disabled={isSaving} onClick={() => void handleSendCustomerDayBefore()}>
                  <Icon name="send" size={13}/> 전날 안내
                </button>
                <button data-testid="send-partner-assignment" className="btn btn--secondary btn--block" disabled={isSaving || !order.partner_id} onClick={() => void handleSendPartnerAssignment()}>
                  <Icon name="truck" size={13}/> 협력사 배정 안내
                </button>
              </div>
            </div>

            <div className="card" style={{ padding: 14 }}>
              <PanelTitle>관련 화면</PanelTitle>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <button data-testid="detail-nav-calendar" className="btn btn--secondary btn--block" onClick={() => onNav?.('calendar')}>
                  <Icon name="calendar" size={13}/> 일정 캘린더
                </button>
                <button data-testid="detail-nav-photos" className="btn btn--secondary btn--block" onClick={() => onNav?.('photos')}>
                  <Icon name="image" size={13}/> 사진검수
                </button>
                <button data-testid="detail-nav-messages" className="btn btn--secondary btn--block" onClick={() => onNav?.('sends')}>
                  <Icon name="send" size={13}/> 발송이력
                </button>
              </div>
            </div>

            <div className="card" style={{ padding: 14 }}>
              <PanelTitle>고객 전달</PanelTitle>
              <div className="mono" style={{ padding: '7px 9px', background: 'var(--bg-subtle)', border: '1px solid var(--border)', borderRadius: 6, fontSize: 10.5, color: 'var(--text-tertiary)', marginBottom: 8, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                /c/{order.customer_token}
              </div>
              <button data-testid="send-customer-photo-ready" className="btn btn--secondary btn--block" disabled={isSaving} onClick={() => void handleSendCustomerPhotoReady()}>
                <Icon name="send" size={13}/> 사진 링크 발송
              </button>
            </div>

            {(notice || error) && (
              <div data-testid={error ? 'admin-action-error' : 'admin-action-notice'} style={{
                padding: 10,
                borderRadius: 6,
                background: error ? 'var(--danger-bg)' : 'var(--success-bg)',
                color: error ? 'var(--danger-fg)' : 'var(--success-fg)',
                fontSize: 12,
              }}>
                {error || notice}
              </div>
            )}

            <div className="card" style={{ padding: 14 }}>
              <PanelTitle>타임라인</PanelTitle>
              {timeline.length === 0 ? (
                <EmptyLine text="타임라인 기록이 없습니다." />
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                  {timeline.map((event, index) => (
                    <div key={event.id} style={{ display: 'flex', gap: 10, paddingBottom: index === timeline.length - 1 ? 0 : 12 }}>
                      <span style={{ width: 8, height: 8, borderRadius: '50%', background: index === timeline.length - 1 ? 'var(--brand)' : 'var(--border-strong)', marginTop: 4, flexShrink: 0 }}/>
                      <div style={{ flex: 1, fontSize: 11.5 }}>
                        <div style={{ color: 'var(--text-tertiary)', fontSize: 10.5, marginBottom: 1 }}>{formatDateTime(event.created_at)}</div>
                        <div style={{ color: 'var(--text)', fontWeight: 500 }}>{event.title}</div>
                        <div style={{ color: 'var(--text-tertiary)', marginTop: 1 }}>{timelineEventLabel(event.event_type)}</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}

function DetailState({ text, tone = 'muted', onBack }) {
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: 'var(--bg)' }}>
      <div style={{ padding: '10px 20px', background: 'var(--surface)', borderBottom: '1px solid var(--border)' }}>
        <button className="btn btn--ghost btn--sm" onClick={onBack}>
          <Icon name="chevronLeft" size={13}/> 목록
        </button>
      </div>
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: tone === 'danger' ? 'var(--danger-fg)' : 'var(--text-tertiary)', fontSize: 13 }}>
        {text}
      </div>
    </div>
  );
}

function Section({ title, icon, badge = null, children }) {
  return (
    <div className="card" style={{ padding: 0 }}>
      <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--divider)', display: 'flex', alignItems: 'center', gap: 8 }}>
        <Icon name={icon} size={13} color="var(--text-tertiary)"/>
        <span style={{ fontSize: 12.5, fontWeight: 600 }}>{title}</span>
        {badge}
      </div>
      <div style={{ padding: 14 }}>{children}</div>
    </div>
  );
}

function PanelTitle({ children }) {
  return <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 600, letterSpacing: '0.04em', marginBottom: 8 }}>{children}</div>;
}

function KV({ children, col = 2 }) {
  return <div style={{ display: 'grid', gridTemplateColumns: `repeat(${col}, 1fr)`, gap: '10px 16px' }}>{children}</div>;
}

function KVItem({ label, value, mono = false, span = undefined, multiline = false }) {
  return (
    <div style={{ gridColumn: span ? `span ${span}` : 'auto' }}>
      <div style={{ fontSize: 10.5, color: 'var(--text-tertiary)', fontWeight: 500, marginBottom: 3 }}>{label}</div>
      <div style={{
        fontSize: 12.5,
        color: 'var(--text)',
        fontFamily: mono ? 'var(--font-mono)' : 'inherit',
        lineHeight: multiline ? 1.5 : 1.4,
      }}>
        {value}
      </div>
    </div>
  );
}

function Money({ label, value }) {
  return (
    <div style={{ padding: '0 14px', borderRight: '1px solid var(--divider)' }}>
      <div style={{ fontSize: 10.5, color: 'var(--text-tertiary)', fontWeight: 500, marginBottom: 3 }}>{label}</div>
      <div style={{ fontSize: 15, fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>{formatWon(value)}</div>
    </div>
  );
}

function EmptyLine({ text }) {
  return <div style={{ color: 'var(--text-tertiary)', fontSize: 12 }}>{text}</div>;
}

function formatService(order) {
  return order.size_or_quantity ? `${order.service_name} ${order.size_or_quantity}` : order.service_name;
}

function formatWon(value) {
  const amount = Number(value || 0);
  return amount ? `₩${amount.toLocaleString()}` : '-';
}

function formatPhone(value) {
  if (!value) {
    return '-';
  }
  const digits = value.replace(/\D/g, '');
  if (digits.length === 11) {
    return `${digits.slice(0, 3)}-${digits.slice(3, 7)}-${digits.slice(7)}`;
  }
  return value;
}

function formatDateTime(value) {
  if (!value) {
    return '-';
  }
  const date = new Date(value);
  return `${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
}

function photoTypeLabel(type) {
  if (type === 'before') return '비포';
  if (type === 'after') return '애프터';
  return '기타';
}

function messageTypeLabel(type) {
  if (type === 'customer_schedule_confirmed') return '일정확정';
  if (type === 'customer_day_before') return '전날안내';
  if (type === 'partner_assignment') return '협력사배정';
  if (type === 'customer_photo_ready') return '사진전달';
  return type;
}

function messageStatusLabel(status) {
  if (status === 'sent') return '성공';
  if (status === 'failed') return '실패';
  return status || '-';
}

function timelineEventLabel(type) {
  const labels = {
    created: '주문 생성',
    status_changed: '상태 변경',
    partner_assigned: '협력사 배정',
    message_sent: '안내 발송',
    photo_uploaded: '사진 업로드',
    photo_approved: '사진 승인',
    customer_link_sent: '고객 링크 발송',
    memo_added: '메모 추가',
    payment_updated: '결제/정산 변경',
  };
  return labels[type] || type;
}

function toActionErrorMessage(error) {
  if (error?.message === 'partner_not_assigned') {
    return '협력사 배정 후 안내를 발송할 수 있습니다.';
  }
  if (error?.message === 'no_customer_visible_photos') {
    return '고객 공개 승인된 사진이 있어야 사진 링크를 발송할 수 있습니다.';
  }
  return '요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.';
}

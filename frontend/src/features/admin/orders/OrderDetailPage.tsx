import React from 'react';

import { deleteAdminOrder, getAdminOrder, listPartners, updateAdminOrder } from '../../../api/admin';
import {
  getAdminMessageSettings,
  previewAdminMessage,
  sendAdminMessage,
} from '../../../api/messages';
import { DatePicker } from '../../../components/common/DatePicker';
import { Avatar, Badge, Icon, StatusBadge } from '../../../components/common/ui';
import { ORDER_STATUS_OPTIONS, orderStatusLabel, orderWorkflowStatusValue } from '../../../domain/orderStatus';
import {
  PARTNER_PAYMENT_STATUSES,
  PAYMENT_STATUSES,
  partnerPaymentStatusLabel,
  paymentStatusLabel,
} from '../../../domain/paymentStatus';
import { RECEIPT_STATUSES, RECEIPT_TYPES, receiptBadge } from '../../../domain/receiptType';
import { formatQuantity } from '../../../domain/format';
import { formatPhone } from '../../../domain/phone';
import { formatAppDateTime } from '../../../domain/time';
import { useApiResource } from '../../../api/useApiResource';

const MESSAGE_ACTIONS = {
  customerScheduleConfirmed: {
    messageType: 'customer_schedule_confirmed',
    recipientType: 'customer',
    title: '일정확정 안내',
    successText: '고객 일정확정 안내를 발송했습니다.',
  },
  customerDayBefore: {
    messageType: 'customer_day_before',
    recipientType: 'customer',
    title: '전날 안내',
    successText: '고객 전날 안내를 발송했습니다.',
  },
  partnerAssignment: {
    messageType: 'partner_assignment',
    recipientType: 'partner',
    title: '협력사 배정 안내',
    successText: '협력사 배정 안내를 발송했습니다.',
  },
  customerPhotoReady: {
    messageType: 'customer_photo_ready',
    recipientType: 'customer',
    title: '사진 링크 발송',
    successText: '고객 사진 확인 링크를 발송했습니다.',
  },
  customerBalanceDue: {
    messageType: 'customer_balance_due',
    recipientType: 'customer',
    title: '잔금 안내',
    successText: '고객 잔금 안내를 발송했습니다.',
  },
  customerQuote: {
    messageType: 'customer_quote',
    recipientType: 'customer',
    title: '견적 안내',
    successText: '고객 견적 안내를 발송했습니다.',
  },
};

const WORK_DONE_STATUS = '고객전달필요';

export function OrderDetailPage({ orderId, onBack, onEdit, onDuplicate, onNav, onOpenOrder }) {
  const loadOrder = React.useCallback(() => getAdminOrder(orderId), [orderId]);
  const orderResource = useApiResource(loadOrder, orderId);
  const partnersResource = useApiResource(listPartners);
  const messageSettingsResource = useApiResource(getAdminMessageSettings);
  const order = orderResource.data;
  const [selectedStatus, setSelectedStatus] = React.useState('');
  const [selectedPartnerId, setSelectedPartnerId] = React.useState('');
  const [selectedScheduledDate, setSelectedScheduledDate] = React.useState('');
  const [selectedRequestedTime, setSelectedRequestedTime] = React.useState('');
  const [selectedPaymentStatus, setSelectedPaymentStatus] = React.useState('');
  const [selectedPartnerPaymentStatus, setSelectedPartnerPaymentStatus] = React.useState('');
  const [selectedReceiptType, setSelectedReceiptType] = React.useState('');
  const [selectedReceiptStatus, setSelectedReceiptStatus] = React.useState('');
  const [selectedOnsiteExtra, setSelectedOnsiteExtra] = React.useState('');
  const [isSaving, setIsSaving] = React.useState(false);
  const [isDeleting, setIsDeleting] = React.useState(false);
  const [notice, setNotice] = React.useState(null);
  const [error, setError] = React.useState(null);
  const [messageDraft, setMessageDraft] = React.useState(null);
  const [messagePreviewChannel, setMessagePreviewChannel] = React.useState('sms');
  const [messagePreviewData, setMessagePreviewData] = React.useState(null);
  const [messagePreviewError, setMessagePreviewError] = React.useState(null);
  const [isPreviewLoading, setIsPreviewLoading] = React.useState(false);

  React.useEffect(() => {
    if (order) {
      setSelectedStatus(orderWorkflowStatusValue(order.status, order.payment_status));
      setSelectedPartnerId(order.partner_id || '');
      setSelectedScheduledDate(order.scheduled_date || '');
      setSelectedRequestedTime(order.requested_time || '');
      setSelectedPaymentStatus(order.payment_status || '');
      setSelectedPartnerPaymentStatus(order.partner_payment_status || '');
      setSelectedReceiptType(order.receipt_type || '');
      setSelectedReceiptStatus(order.receipt_status || '');
      setSelectedOnsiteExtra(order.onsite_extra_amount != null ? String(order.onsite_extra_amount) : '');
    }
  }, [order]);

  // 섹션별 저장이 분리돼 있어, 여러 곳을 고치고 일부만 저장한 채 이동하면 나머지 변경이 유실된다.
  // 미저장 변경이 있으면 새로고침/창닫기와 화면 이동을 가드한다.
  const hasUnsavedChanges = Boolean(order) && (
    selectedStatus !== orderWorkflowStatusValue(order.status, order.payment_status)
    || selectedPartnerId !== (order.partner_id || '')
    || selectedScheduledDate !== (order.scheduled_date || '')
    || selectedRequestedTime !== (order.requested_time || '')
    || selectedPaymentStatus !== (order.payment_status || '')
    || selectedPartnerPaymentStatus !== (order.partner_payment_status || '')
    || selectedReceiptType !== (order.receipt_type || '')
    || selectedReceiptStatus !== (order.receipt_status || '')
    || Number(selectedOnsiteExtra || 0) !== Number(order.onsite_extra_amount || 0)
  );

  React.useEffect(() => {
    if (!hasUnsavedChanges) {
      return undefined;
    }
    const handleBeforeUnload = (event) => {
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [hasUnsavedChanges]);

  const confirmLeaveIfDirty = React.useCallback(
    () => !hasUnsavedChanges || window.confirm('저장하지 않은 변경이 있습니다. 저장하지 않고 이동할까요?'),
    [hasUnsavedChanges],
  );

  const navigateWithGuard = React.useCallback(
    (page) => { if (confirmLeaveIfDirty()) { onNav?.(page); } },
    [confirmLeaveIfDirty, onNav],
  );

  const handleStatusChange = async () => {
    // 작업완료(고객전달필요)로 '처음' 진입하는지 — 진입 시 잔금 안내 미리보기를 자동으로 띄운다.
    const enteredWorkDone = selectedStatus === WORK_DONE_STATUS && order.status !== WORK_DONE_STATUS;
    await runAction(async () => {
      const selectedStatusLabel = orderStatusLabel(selectedStatus);
      await updateAdminOrder(order.id, { status: selectedStatus });
      orderResource.reload();
      if (enteredWorkDone) {
        // 잔금 안내 미리보기를 자동 표시 → 운영자가 확인 후 발송(미발송 누락 방지 + 오발송 방지).
        await openMessagePreview(MESSAGE_ACTIONS.customerBalanceDue);
      } else {
        setNotice(`${selectedStatusLabel} 상태 변경을 타임라인에 기록했습니다.`);
      }
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
      // 현장추가금은 총금액에 더해지고, 늘어난 만큼 잔금에 반영한다(계약금=선금은 유지).
      const onsite = Number(selectedOnsiteExtra || 0);
      const balance = Math.max(
        Number(order.total_amount || 0) + onsite - Number(order.deposit_amount || 0),
        0,
      );
      await updateAdminOrder(order.id, {
        payment_status: selectedPaymentStatus || null,
        partner_payment_status: selectedPartnerPaymentStatus || null,
        receipt_type: selectedReceiptType || null,
        receipt_status: selectedReceiptType === 'none'
          ? 'not_applicable'
          : (selectedReceiptStatus || null),
        onsite_extra_amount: onsite,
        balance_amount: balance,
      });
      setNotice('결제/정산 변경을 타임라인에 기록했습니다.');
      orderResource.reload();
    });
  };

  const fetchMessagePreview = async (draft, channel) => {
    setIsPreviewLoading(true);
    setMessagePreviewError(null);
    try {
      const preview = await previewAdminMessage(order.id, draft.messageType, draft.recipientType, channel);
      setMessagePreviewData(preview);
      return preview;
    } catch (requestError) {
      const actionError = toActionErrorMessage(requestError);
      setMessagePreviewData(null);
      setMessagePreviewError(actionError);
      throw requestError;
    } finally {
      setIsPreviewLoading(false);
    }
  };

  const openMessagePreview = async (draft) => {
    setError(null);
    setNotice(null);
    setMessageDraft(draft);
    setMessagePreviewChannel('sms');
    setMessagePreviewData(null);
    setMessagePreviewError(null);
    try {
      await fetchMessagePreview(draft, 'sms');
    } catch (requestError) {
      setMessageDraft(null);
      setError(toActionErrorMessage(requestError));
    }
  };

  const handlePreviewChannelChange = async (channel) => {
    if (!messageDraft || channel === messagePreviewChannel) {
      return;
    }
    setMessagePreviewChannel(channel);
    try {
      await fetchMessagePreview(messageDraft, channel);
    } catch {
      // The modal keeps the inline preview error so the operator can switch channels.
    }
  };

  const closeMessagePreview = () => {
    setMessageDraft(null);
    setMessagePreviewData(null);
    setMessagePreviewError(null);
    setMessagePreviewChannel('sms');
  };

  const handleConfirmMessageSend = async () => {
    if (!messageDraft) {
      return;
    }
    await runAction(async () => {
      const sent = await sendAdminMessage(
        order.id,
        messageDraft.messageType,
        messageDraft.recipientType,
        messagePreviewChannel,
      );
      closeMessagePreview();
      const channelLabel = messageChannelLabel(sent.channel || messagePreviewChannel);
      if (isMessageFailure(sent.status)) {
        setError(`${messageDraft.title} 발송 결과: ${messageStatusLabel(sent.status)} (${channelLabel}) - ${messageProviderErrorText(sent)}`);
      } else {
        setNotice(`${messageDraft.successText} (${channelLabel})`);
      }
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

  const handleDelete = async () => {
    if (!order) return;
    const ok = window.confirm(
      `이 주문(${order.id})을 삭제하시겠습니까?\n\n`
      + '운영 기록(타임라인, 메시지 로그, 사진)은 보존되지만 목록에서는 사라집니다.',
    );
    if (!ok) return;

    setError(null);
    setNotice(null);
    setIsDeleting(true);
    try {
      await deleteAdminOrder(order.id);
      onBack();
    } catch (requestError) {
      setError(`삭제 실패: ${requestError instanceof Error ? requestError.message : String(requestError)}`);
    } finally {
      setIsDeleting(false);
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
  const isStatusDirty = selectedStatus !== orderWorkflowStatusValue(order.status, order.payment_status);
  const isPartnerDirty = selectedPartnerId !== (order.partner_id || '');
  const isPaymentDirty = selectedPaymentStatus !== (order.payment_status || '')
    || selectedPartnerPaymentStatus !== (order.partner_payment_status || '')
    || selectedReceiptType !== (order.receipt_type || '')
    || selectedReceiptStatus !== (order.receipt_status || '')
    || Number(selectedOnsiteExtra || 0) !== Number(order.onsite_extra_amount || 0);
  // 현장추가금을 반영한 총금액/잔금(계약금은 그대로). 잔금 = 총금액 - 계약금.
  const onsiteExtraNumber = Number(selectedOnsiteExtra || 0);
  const grandTotalWithOnsite = Number(order.total_amount || 0) + onsiteExtraNumber;
  const recomputedBalance = Math.max(grandTotalWithOnsite - Number(order.deposit_amount || 0), 0);
  const kakaoChannelUrl = normalizeHttpUrl(messageSettingsResource.data?.kakao_channel_url);

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
        <button className="btn btn--ghost btn--sm" onClick={() => { if (confirmLeaveIfDirty()) onBack(); }} style={{ padding: '0 6px' }}>
          <Icon name="chevronLeft" size={13}/> 목록
        </button>
        <span style={{ width: 1, height: 16, background: 'var(--border)' }}/>
        <h2 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>{formatService(order)}</h2>
        <StatusBadge status={orderWorkflowStatusValue(order.status, order.payment_status)}/>
        {hasUnsavedChanges && (
          <span data-testid="detail-unsaved-indicator" style={{
            display: 'inline-flex', alignItems: 'center', gap: 5,
            fontSize: 11, fontWeight: 600, color: 'var(--warn-fg)',
            background: 'var(--warn-bg)', borderRadius: 5, padding: '2px 8px',
          }}>
            <span style={{ width: 5, height: 5, borderRadius: '50%', background: 'var(--warn-fg)' }}/>
            저장 안 한 변경
          </span>
        )}
        <div style={{ flex: 1 }}/>
        <button className="btn btn--ghost btn--sm" onClick={orderResource.reload}>
          <Icon name="refresh" size={12}/> 새로고침
        </button>
        <button data-testid="order-detail-edit" className="btn btn--secondary btn--sm" onClick={() => { if (confirmLeaveIfDirty()) onEdit(); }}>
          수정
        </button>
        {onDuplicate && (
          <button data-testid="order-detail-duplicate" className="btn btn--ghost btn--sm" onClick={() => { if (confirmLeaveIfDirty()) onDuplicate(); }}>
            <Icon name="copy" size={12}/> 복제
          </button>
        )}
        <button className="btn btn--ghost btn--sm" onClick={() => navigateWithGuard('calendar')}>
          <Icon name="calendar" size={12}/> 일정표
        </button>
        <button
          data-testid="order-detail-delete"
          className="btn btn--ghost btn--sm"
          style={{ color: 'var(--danger-fg)' }}
          onClick={() => void handleDelete()}
          disabled={isDeleting}
        >
          <Icon name="x" size={12}/> {isDeleting ? '삭제 중' : '삭제'}
        </button>
      </div>

      <div className="scroll" style={{ flex: 1, overflow: 'auto', padding: 20 }}>
        <div className="page-shell" style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 16 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <Section title="고객 정보" icon="user">
              <KV col={2}>
                <KVItem label="고객명" value={order.customer_name}/>
                <KVItem label="연락처" value={formatPhone(order.customer_phone)} mono/>
                <KVItem label="유입 경로" value={order.source_channel || '-'}/>
                <KVItem
                  label="주소"
                  value={[order.customer_address, order.customer_address_detail].filter(Boolean).join(' ')}
                  span={2}
                />
                <KVItem label="요청사항" value={order.special_request || '-'} span={2} multiline/>
              </KV>
              {kakaoChannelUrl && (
                <div style={{ marginTop: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
                  <a
                    data-testid="order-kakao-consult-link"
                    className="btn btn--secondary btn--sm"
                    href={kakaoChannelUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <Icon name="send" size={13}/> 카카오톡 상담
                  </a>
                </div>
              )}
            </Section>

            <Section title="상품 / 일정" icon="package">
              <KV col={2}>
                <KVItem label="상품명" value={order.service_name}/>
                <KVItem label="수량/규격" value={formatQuantity(order.size_or_quantity) || '-'}/>
                <KVItem label="방문 예정일" value={order.scheduled_date || '미정'}/>
                <KVItem label="요청 시간" value={order.requested_time || '-'}/>
                <KVItem label="상세" value={order.service_detail || '-'} span={2} multiline/>
              </KV>
            </Section>

            <Section title="금액 / 결제" icon="creditCard">
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 0 }}>
                <Money label="총금액(VAT포함)" value={(Number(order.consumer_price ?? order.total_amount) || 0) + (Number(order.onsite_extra_amount) || 0)}/>
                <Money label="현장 추가" value={order.onsite_extra_amount}/>
                <Money label="계약금" value={order.deposit_amount}/>
                <Money label="잔금" value={order.balance_amount}/>
                <Money label="할인가" value={order.discount_amount}/>
              </div>
              <div style={{ marginTop: 10 }}>
                <KV col={2}>
                  <KVItem label="결제 상태" value={paymentStatusLabel(order.payment_status)}/>
                  <KVItem label="증빙 자료" value={receiptBadge(order.receipt_type, order.receipt_status).text}/>
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
                    정산 상태: {order.partner_id && !order.partner_payment_status ? '미정산' : partnerPaymentStatusLabel(order.partner_payment_status)}
                  </div>
                  <div style={{ fontSize: 11.5, color: 'var(--text-tertiary)', marginTop: 2 }}>
                    도급가(VAT 포함) {formatWon(order.partner_price ?? order.partner_payment_amount)} · 정산일 {order.partner_settled_at ? formatDateTime(order.partner_settled_at) : '-'}
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
                    <div key={log.id} style={{ display: 'grid', gridTemplateColumns: '120px 1fr 96px', gap: 10, alignItems: 'center', fontSize: 12, padding: '8px 0', borderBottom: '1px solid var(--divider)' }}>
                      <span className="mono" style={{ color: 'var(--text-tertiary)', fontSize: 10.5 }}>{formatDateTime(log.sent_at || log.created_at)}</span>
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {messageTypeLabel(log.message_type)} · {log.recipient_name} · {messageProviderLabel(log)}
                      </span>
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 3, minWidth: 0 }}>
                        <Badge tone={messageStatusTone(log.status)}>{messageStatusLabel(log.status)}</Badge>
                        {isMessageFailure(log.status) && (
                          <span title={log.error_message || log.provider_error_code || ''} style={{ maxWidth: '100%', color: 'var(--danger-fg)', fontSize: 10, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {messageProviderErrorText(log)}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Section>
          </div>

          <aside style={{ display: 'flex', flexDirection: 'column', gap: 12, position: 'sticky', top: 0, alignSelf: 'flex-start' }}>
            {order.sibling_lines && order.sibling_lines.length > 0 && (
              <div className="card" style={{ padding: 14 }}>
                <PanelTitle>이 그룹의 다른 라인</PanelTitle>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {order.sibling_lines.map((sibling) => (
                    <button
                      key={sibling.id}
                      type="button"
                      data-testid={`order-sibling-${sibling.id}`}
                      onClick={() => onOpenOrder?.(sibling.id)}
                      style={{
                        display: 'block',
                        width: '100%',
                        border: '1px solid var(--divider)',
                        borderRadius: 6,
                        background: 'var(--surface)',
                        padding: 8,
                        textAlign: 'left',
                        cursor: 'pointer',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                        <span style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 12.5, fontWeight: 600 }}>
                          {sibling.service_name}
                        </span>
                        <StatusBadge status={orderWorkflowStatusValue(sibling.status, sibling.payment_status)} dot={false}/>
                      </div>
                      <div style={{ fontSize: 11.5, color: 'var(--text-tertiary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {sibling.team_name || '미배정'} · {formatWon(sibling.total_amount)}
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className="card" style={{ padding: 14 }}>
              <PanelTitle dirty={isStatusDirty}>상태 변경</PanelTitle>
              <select data-testid="detail-status-select" className="input" value={selectedStatus} onChange={(event) => setSelectedStatus(event.target.value)} style={{ width: '100%', height: 34, marginBottom: 8 }}>
                {ORDER_STATUS_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select>
              <button data-testid="detail-status-save" className={`btn btn--block ${isStatusDirty ? 'btn--primary' : 'btn--secondary'}`} disabled={isSaving || !isStatusDirty} onClick={() => void handleStatusChange()}>
                <Icon name="check" size={13}/> 상태 저장
              </button>
            </div>

            <div className="card" style={{ padding: 14 }}>
              <PanelTitle dirty={isPartnerDirty}>협력사 배정</PanelTitle>
              <select className="input" value={selectedPartnerId} onChange={(event) => setSelectedPartnerId(event.target.value)} style={{ width: '100%', height: 34, marginBottom: 8 }}>
                <option value="">미배정</option>
                {(partnersResource.data || []).map((partner) => (
                  <option key={partner.id} value={partner.id}>{partner.name}</option>
                ))}
              </select>
              <button className={`btn btn--block ${isPartnerDirty ? 'btn--primary' : 'btn--secondary'}`} disabled={isSaving || !isPartnerDirty} onClick={() => void handlePartnerAssign()}>
                <Icon name="user" size={13}/> 배정 저장
              </button>
            </div>

            <div className="card" style={{ padding: 14 }}>
              <PanelTitle dirty={hasScheduleChanges}>방문 일정</PanelTitle>
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
                className={`btn btn--block ${hasScheduleChanges ? 'btn--primary' : 'btn--secondary'}`}
                disabled={isSaving || !hasScheduleChanges}
                onClick={() => void handleScheduleUpdate()}
              >
                <Icon name="calendar" size={13}/> 일정 저장
              </button>
            </div>

            <div className="card" style={{ padding: 14 }}>
              <PanelTitle dirty={isPaymentDirty}>결제 / 정산</PanelTitle>
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
                <span style={{ fontSize: 10.5, color: 'var(--text-tertiary)', fontWeight: 600 }}>증빙 자료</span>
                <select
                  data-testid="detail-receipt-type"
                  className="input"
                  value={selectedReceiptType}
                  onChange={(event) => {
                    const next = event.target.value;
                    setSelectedReceiptType(next);
                    // 발급X면 2차 상태를 '해당없음'으로 자동 고정.
                    if (next === 'none') setSelectedReceiptStatus('not_applicable');
                    else if (selectedReceiptStatus === 'not_applicable') setSelectedReceiptStatus('');
                  }}
                  style={{ width: '100%', height: 34 }}
                >
                  <option value="">미입력</option>
                  {RECEIPT_TYPES.map((item) => (
                    <option key={item.value} value={item.value}>{item.label}</option>
                  ))}
                </select>
                <select
                  data-testid="detail-receipt-status"
                  className="input"
                  value={selectedReceiptStatus}
                  disabled={selectedReceiptType === 'none' || selectedReceiptType === ''}
                  onChange={(event) => setSelectedReceiptStatus(event.target.value)}
                  style={{ width: '100%', height: 34 }}
                >
                  <option value="">발급 상태 선택</option>
                  {RECEIPT_STATUSES.map((item) => (
                    <option key={item.value} value={item.value}>{item.label}</option>
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
              <label style={{ display: 'flex', flexDirection: 'column', gap: 5, marginBottom: 8 }}>
                <span style={{ fontSize: 10.5, color: 'var(--text-tertiary)', fontWeight: 600 }}>현장 추가금</span>
                <input
                  data-testid="detail-onsite-extra"
                  className="input"
                  inputMode="numeric"
                  value={selectedOnsiteExtra}
                  onChange={(event) => setSelectedOnsiteExtra(event.target.value.replace(/[^\d]/g, ''))}
                  placeholder="0"
                  style={{ width: '100%', height: 34 }}
                />
                <span style={{ fontSize: 10.5, color: 'var(--text-tertiary)' }}>
                  총금액 {formatWon(grandTotalWithOnsite)} · 잔금 {formatWon(recomputedBalance)} · 계약금 {formatWon(order.deposit_amount)} 유지
                </span>
              </label>
              <button
                className={`btn btn--block ${isPaymentDirty ? 'btn--primary' : 'btn--secondary'}`}
                disabled={isSaving || !isPaymentDirty}
                onClick={() => void handlePaymentUpdate()}
              >
                <Icon name="creditCard" size={13}/> 결제/정산 저장
              </button>
            </div>

            <div className="card" style={{ padding: 14 }}>
              <PanelTitle>안내 발송</PanelTitle>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <button data-testid="send-customer-schedule-confirmed" className="btn btn--secondary btn--block" disabled={isSaving || isPreviewLoading} onClick={() => void openMessagePreview(MESSAGE_ACTIONS.customerScheduleConfirmed)}>
                  <Icon name="send" size={13}/> 일정확정 안내
                </button>
                <button data-testid="send-customer-day-before" className="btn btn--secondary btn--block" disabled={isSaving || isPreviewLoading} onClick={() => void openMessagePreview(MESSAGE_ACTIONS.customerDayBefore)}>
                  <Icon name="send" size={13}/> 전날 안내
                </button>
                <button data-testid="send-partner-assignment" className="btn btn--secondary btn--block" disabled={isSaving || isPreviewLoading || !order.partner_id} onClick={() => void openMessagePreview(MESSAGE_ACTIONS.partnerAssignment)}>
                  <Icon name="truck" size={13}/> 협력사 배정 안내
                </button>
                <button data-testid="send-customer-balance-due" className="btn btn--secondary btn--block" disabled={isSaving || isPreviewLoading} onClick={() => void openMessagePreview(MESSAGE_ACTIONS.customerBalanceDue)}>
                  <Icon name="creditCard" size={13}/> 잔금 안내
                </button>
                <button data-testid="send-customer-quote" className="btn btn--secondary btn--block" disabled={isSaving || isPreviewLoading} onClick={() => void openMessagePreview(MESSAGE_ACTIONS.customerQuote)}>
                  <Icon name="send" size={13}/> 견적 안내
                </button>
              </div>
            </div>

            <div className="card" style={{ padding: 14 }}>
              <PanelTitle>관련 화면</PanelTitle>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <button data-testid="detail-nav-calendar" className="btn btn--secondary btn--block" onClick={() => navigateWithGuard('calendar')}>
                  <Icon name="calendar" size={13}/> 일정 캘린더
                </button>
                <button data-testid="detail-nav-photos" className="btn btn--secondary btn--block" onClick={() => navigateWithGuard('photos')}>
                  <Icon name="image" size={13}/> 사진검수
                </button>
                <button data-testid="detail-nav-messages" className="btn btn--secondary btn--block" onClick={() => navigateWithGuard('sends')}>
                  <Icon name="send" size={13}/> 발송이력
                </button>
              </div>
            </div>

            <div className="card" style={{ padding: 14 }}>
              <PanelTitle>고객 전달</PanelTitle>
              <div style={{ fontSize: 11.5, color: 'var(--text-tertiary)', marginBottom: 8, lineHeight: 1.45 }}>
                고객이 예약 정보와 공개 사진을 확인하는 링크입니다. 복사해서 고객에게 바로 보내세요.
              </div>
              {order.customer_token ? (
                <div style={{ marginBottom: 8 }}>
                  <CopyLinkButton
                    testId="copy-customer-link"
                    label="고객 링크 복사"
                    link={`${window.location.origin}/c/${order.customer_token}`}
                  />
                </div>
              ) : (
                <div style={{ fontSize: 11.5, color: 'var(--warn-fg)', marginBottom: 8 }}>
                  아직 고객 링크가 생성되지 않았습니다.
                </div>
              )}
              <button data-testid="send-customer-photo-ready" className="btn btn--secondary btn--block" disabled={isSaving || isPreviewLoading} onClick={() => void openMessagePreview(MESSAGE_ACTIONS.customerPhotoReady)}>
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
      <MessagePreviewModal
        draft={messageDraft}
        channel={messagePreviewChannel}
        preview={messagePreviewData}
        previewError={messagePreviewError}
        isLoading={isPreviewLoading}
        isSaving={isSaving}
        onChannelChange={handlePreviewChannelChange}
        onClose={closeMessagePreview}
        onConfirm={handleConfirmMessageSend}
      />
    </div>
  );
}

function MessagePreviewModal({
  draft,
  channel,
  preview,
  previewError,
  isLoading,
  isSaving,
  onChannelChange,
  onClose,
  onConfirm,
}) {
  if (!draft) {
    return null;
  }

  const warnings = preview?.warnings || [];
  const variables = preview?.kakao_variables ? Object.entries(preview.kakao_variables) : [];
  const isAlimtalk = channel === 'alimtalk';
  const canSend = Boolean(preview && preview.can_send !== false && !previewError && !isLoading && !isSaving);

  return (
    <div
      data-testid="message-preview-modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="message-preview-title"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 50,
        background: 'rgba(15, 23, 42, 0.38)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 20,
      }}
    >
      <div
        className="card"
        style={{
          width: 'min(640px, 100%)',
          maxHeight: 'min(760px, calc(100vh - 40px))',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--divider)', display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div id="message-preview-title" style={{ fontSize: 14, fontWeight: 700 }}>{draft.title}</div>
            <div style={{ marginTop: 3, fontSize: 11.5, color: 'var(--text-tertiary)' }}>
              {preview ? `${preview.recipient_name} · ${formatPhone(preview.recipient_phone)}` : '발송 정보를 확인하는 중입니다.'}
            </div>
          </div>
          <button className="btn btn--ghost btn--sm" onClick={onClose} aria-label="닫기" style={{ padding: '0 6px' }}>
            <Icon name="x" size={14}/>
          </button>
        </div>

        <div className="scroll" style={{ padding: 16, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div>
            <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 600, marginBottom: 8 }}>발송 채널</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
              <button
                data-testid="message-preview-channel-sms"
                className={`btn ${channel === 'sms' ? 'btn--primary' : 'btn--secondary'}`}
                disabled={isLoading || isSaving}
                aria-pressed={channel === 'sms'}
                onClick={() => void onChannelChange('sms')}
              >
                SMS
              </button>
              <button
                data-testid="message-preview-channel-alimtalk"
                className={`btn ${channel === 'alimtalk' ? 'btn--primary' : 'btn--secondary'}`}
                disabled={isLoading || isSaving}
                aria-pressed={channel === 'alimtalk'}
                onClick={() => void onChannelChange('alimtalk')}
              >
                알림톡
              </button>
            </div>
          </div>

          {previewError && (
            <div
              data-testid="message-preview-error"
              style={{ padding: 10, borderRadius: 6, background: 'var(--danger-bg)', color: 'var(--danger-fg)', fontSize: 12 }}
            >
              {previewError}
            </div>
          )}

          {isLoading ? (
            <div style={{ padding: 12, border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text-tertiary)', fontSize: 12 }}>
              미리보기를 불러오는 중입니다.
            </div>
          ) : (
            preview && (
              <>
                {isAlimtalk && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                      <Badge tone={preview.kakao_pf_id_configured ? 'success' : 'warn'}>
                        PF ID {preview.kakao_pf_id_configured ? '설정됨' : '미설정'}
                      </Badge>
                      <Badge tone={preview.kakao_template_configured ? 'success' : 'warn'}>
                        템플릿 {preview.kakao_template_configured ? '설정됨' : '미설정'}
                      </Badge>
                      <Badge tone={preview.fallback_sms_enabled ? 'info' : 'neutral'}>
                        SMS fallback {preview.fallback_sms_enabled ? 'ON' : 'OFF'}
                      </Badge>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: 8, fontSize: 12 }}>
                      <span style={{ color: 'var(--text-tertiary)' }}>템플릿 ID</span>
                      <span data-testid="message-preview-template-id" className="mono" style={{ color: 'var(--text)' }}>
                        {preview.kakao_template_id || '미설정'}
                      </span>
                    </div>
                    {variables.length > 0 && (
                      <div style={{ border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden' }}>
                        {variables.map(([key, value]) => (
                          <div key={key} style={{ display: 'grid', gridTemplateColumns: '150px 1fr', gap: 8, padding: '8px 10px', borderBottom: '1px solid var(--divider)', fontSize: 11.5 }}>
                            <span className="mono" style={{ color: 'var(--text-tertiary)', minWidth: 0 }}>{key}</span>
                            <span style={{ minWidth: 0, wordBreak: 'break-word' }}>{String(value)}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {warnings.length > 0 && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {warnings.map((warning) => (
                      <div
                        key={warning}
                        data-testid="message-preview-warning"
                        style={{ padding: 10, borderRadius: 6, background: 'var(--warn-bg)', color: 'var(--warn-fg)', fontSize: 12 }}
                      >
                        {messagePreviewWarningLabel(warning)}
                      </div>
                    ))}
                  </div>
                )}

                <div>
                  <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 600, marginBottom: 8 }}>
                    {isAlimtalk ? 'SMS fallback 문구' : '발송 문구'}
                  </div>
                  <pre
                    data-testid="message-preview-content"
                    style={{
                      margin: 0,
                      padding: 12,
                      border: '1px solid var(--border)',
                      borderRadius: 8,
                      background: 'var(--bg-subtle)',
                      color: 'var(--text)',
                      fontFamily: 'var(--font-mono)',
                      fontSize: 11.5,
                      lineHeight: 1.55,
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                    }}
                  >
                    {isAlimtalk ? preview.fallback_sms_content || preview.content : preview.content}
                  </pre>
                </div>
              </>
            )
          )}
        </div>

        <div style={{ padding: 14, borderTop: '1px solid var(--divider)', display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <button className="btn btn--ghost" onClick={onClose} disabled={isSaving}>취소</button>
          <button data-testid="message-preview-send" className="btn btn--primary" onClick={() => void onConfirm()} disabled={!canSend}>
            <Icon name="send" size={13}/> 발송
          </button>
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

function PanelTitle({ children, dirty = false }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
      <span style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 600, letterSpacing: '0.04em' }}>{children}</span>
      {dirty && (
        <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--warn-fg)', background: 'var(--warn-bg)', borderRadius: 4, padding: '1px 5px' }}>
          변경됨
        </span>
      )}
    </div>
  );
}

// 고객 링크를 운영자가 손으로 드래그·복사하지 않도록 클립보드 복사 버튼을 제공한다.
// 원시 토큰은 노출하지 않고, 복사 시 고객에게 바로 보낼 수 있는 전체 URL을 복사한다.
function CopyLinkButton({ link, label = '링크 복사', testId = undefined }) {
  const [copied, setCopied] = React.useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  return (
    <button
      type="button"
      data-testid={testId}
      className={`btn btn--block ${copied ? 'btn--primary' : 'btn--secondary'}`}
      onClick={() => void handleCopy()}
    >
      <Icon name={copied ? 'check' : 'copy'} size={13}/> {copied ? '링크가 복사되었습니다' : label}
    </button>
  );
}

function KV({ children, col = 2 }) {
  return <div style={{ display: 'grid', gridTemplateColumns: `repeat(${col}, 1fr)`, gap: '10px 16px' }}>{children}</div>;
}

function KVItem({ label, value, mono = false, span = undefined, multiline = false }) {
  return (
    <div style={{ gridColumn: span ? `span ${span}` : 'auto' }}>
      <div style={{ fontSize: 10.5, color: 'var(--text-tertiary)', fontWeight: 500, marginBottom: 3 }}>{label}</div>
      <div
        className={multiline ? 'multiline-text' : undefined}
        style={{
          fontSize: 12.5,
          color: 'var(--text)',
          fontFamily: mono ? 'var(--font-mono)' : 'inherit',
          lineHeight: multiline ? 1.5 : 1.4,
        }}
      >
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
  const quantity = formatQuantity(order.size_or_quantity);
  return quantity ? `${order.service_name} ${quantity}` : order.service_name;
}

function formatWon(value) {
  const amount = Number(value || 0);
  return amount ? `₩${amount.toLocaleString()}` : '-';
}

function formatDateTime(value) {
  return formatAppDateTime(value);
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
  if (type === 'customer_balance_due') return '잔금안내';
  if (type === 'customer_quote') return '견적서';
  if (type === 'partner_customer_info') return '협력사 고객정보';
  return type;
}

function messageStatusLabel(status) {
  if (status === 'sent') return '요청성공';
  if (status === 'failed') return '요청실패';
  if (status === 'delivered') return '배송완료';
  if (status === 'delivery_failed') return '배송실패';
  return status || '-';
}

function messageStatusTone(status) {
  if (status === 'delivered') return 'success';
  if (status === 'sent') return 'info';
  if (isMessageFailure(status)) return 'danger';
  return 'neutral';
}

function isMessageFailure(status) {
  return status === 'failed' || status === 'delivery_failed';
}

function messageProviderLabel(log) {
  if (log.provider === 'mock') return 'Mock';
  if (log.provider === 'solapi') {
    return log.provider_group_id || log.provider_message_id
      ? `SOL API ${log.provider_group_id || log.provider_message_id}`
      : 'SOL API';
  }
  if (log.provider === 'configuration_error') return 'Config';
  return log.provider || 'Provider 미기록';
}

function messageProviderErrorText(log) {
  const map = {
    missing_recipient: '수신번호 없음',
    solapi_missing_credentials: 'SOL API 인증 설정 누락',
    solapi_missing_sender_number: 'SOL API 발신번호 누락',
    solapi_missing_kakao_pf_id: 'SOL API 카카오 채널 ID 누락',
    solapi_missing_kakao_template_id: '알림톡 승인 템플릿 ID 누락',
    solapi_http_error: 'SOL API HTTP 오류',
    solapi_request_failed: 'SOL API 요청 실패',
    solapi_invalid_response: 'SOL API 응답 오류',
    solapi_provider_failed: 'SOL API 발송 실패',
    unsupported_message_provider: 'Provider 설정 오류',
  };
  return map[log.provider_error_code] || log.provider_status_message || log.error_message || '실패 사유 미상';
}

function messageChannelLabel(channel) {
  if (channel === 'sms') return 'SMS';
  if (channel === 'lms') return 'LMS';
  if (channel === 'alimtalk') return '알림톡';
  return channel || '-';
}

function messagePreviewWarningLabel(warning) {
  const map = {
    solapi_missing_kakao_pf_id: 'SOL API 카카오 채널 ID가 아직 설정되지 않았습니다.',
    solapi_missing_kakao_template_id: '이 메시지 타입의 승인 템플릿 ID가 아직 설정되지 않았습니다.',
    alimtalk_fallback_sms_enabled: '알림톡 설정이 준비되지 않으면 같은 문구를 SMS로 fallback 발송합니다.',
  };
  return map[warning] || warning;
}

function normalizeHttpUrl(value) {
  const input = String(value || '').trim();
  if (!input) {
    return '';
  }
  try {
    const url = new URL(input);
    return ['http:', 'https:'].includes(url.protocol) ? url.toString() : '';
  } catch {
    return '';
  }
}

function timelineEventLabel(type) {
  const labels = {
    created: '주문 생성',
    status_changed: '상태 변경',
    partner_assigned: '협력사 배정',
    message_sent: '안내 발송',
    photo_uploaded: '사진 업로드',
    photo_approved: '사진 공개',
    photo_revoked: '사진 비공개 처리',
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

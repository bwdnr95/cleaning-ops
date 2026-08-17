import { toApiAssetUrl } from '../../../api/client';
import { Avatar, Badge } from '../../../components/common/ui';
import { formatQuantity } from '../../../domain/format';
import { formatPhone } from '../../../domain/phone';
import { partnerPaymentStatusLabel, paymentStatusLabel } from '../../../domain/paymentStatus';
import { receiptBadge } from '../../../domain/receiptType';
import { sourceChannelLabel } from '../../../domain/sourceChannel';
import {
  formatDateTime,
  formatWon,
  messageProviderErrorText,
  messageProviderLabel,
  messageStatusLabel,
  messageStatusTone,
  messageTypeLabel,
  isMessageFailure,
} from './OrderDetailFormat';
import type { AdminOrderDetail, AdminPartnerOption, OrderDetailMessageLog, OrderDetailPhoto } from './OrderDetailModel';
import { OrderDetailPhotoSection } from './OrderDetailPhotoSection';
import { EmptyLine, KV, KVItem, Money, Section } from './OrderDetailPrimitives';

interface OrderDetailSummarySectionsProps {
  readonly order: AdminOrderDetail;
  readonly selectedPartner?: AdminPartnerOption;
  readonly visiblePhotos: readonly OrderDetailPhoto[];
  readonly messageLogs: readonly OrderDetailMessageLog[];
  readonly kakaoChannelUrl: string;
}

export function OrderDetailSummarySections({
  order,
  selectedPartner,
  visiblePhotos,
  messageLogs,
  kakaoChannelUrl,
}: OrderDetailSummarySectionsProps) {
  const partnerMemos = (order.timeline || []).filter((event) => (
    event.event_type === 'memo_added'
    && event.event_metadata?.author_role === 'partner'
  ));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <Section title="고객 정보" icon="user">
        <KV col={2}>
          <KVItem label="고객명" value={order.customer_name}/>
          <KVItem label="연락처" value={formatPhone(order.customer_phone)} mono/>
          <KVItem label="유입 경로" value={sourceChannelLabel(order.source_channel)}/>
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
              카카오톡 상담
            </a>
          </div>
        )}
        {order.as_memo && (
          <div
            data-testid="admin-order-as-memo"
            style={{ marginTop: 12, padding: 12, borderRadius: 8, border: '1px solid var(--warn-border)', background: 'var(--warn-bg)' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
              <Badge tone={order.as_requested ? 'danger' : 'warn'}>
                {order.as_requested ? 'AS 전달됨' : '고객 AS 접수'}
              </Badge>
              <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text)' }}>AS 요청 메모</span>
            </div>
            <div className="multiline-text" style={{ fontSize: 12.5, lineHeight: 1.5, color: 'var(--warn-fg)' }}>
              {order.as_memo}
            </div>
          </div>
        )}
        {partnerMemos.length > 0 && (
          <div
            data-testid="admin-partner-memos"
            style={{ marginTop: 12, padding: 12, borderRadius: 8, border: '1px solid var(--border)', background: 'var(--bg-subtle)' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
              <Badge tone="brand">협력사</Badge>
              <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text)' }}>작업 메모</span>
            </div>
            <div style={{ display: 'grid', gap: 8 }}>
              {partnerMemos.map((memo) => (
                <div key={memo.id}>
                  <div className="multiline-text" style={{ fontSize: 12.5, lineHeight: 1.5, color: 'var(--text)' }}>
                    {memo.description || '-'}
                  </div>
                  <div style={{ marginTop: 3, fontSize: 10.5, color: 'var(--text-tertiary)' }}>
                    {formatDateTime(memo.created_at)}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </Section>

      <Section title="상품 / 일정" icon="package">
        <KV col={2}>
          <KVItem label="상품명" value={order.service_name}/>
          <KVItem label="수량/규격" value={formatQuantity(order.size_or_quantity) || '-'}/>
          <KVItem
            label="방문 예정일"
            value={(order.visit_dates || (order.scheduled_date ? [order.scheduled_date] : [])).join(' · ') || '미정'}
            multiline
          />
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

      <Section title="작업 기록" icon="clock">
        <KV col={3}>
          <KVItem label="진입시간" value={formatDateTime(order.work_started_at) || '-'}/>
          <KVItem label="작업완료시간" value={formatDateTime(order.work_completed_at) || '-'}/>
          <KVItem
            label="고객 서명"
            value={order.customer_signature_file_url ? (
              <a
                href={toApiAssetUrl(order.customer_signature_file_url)}
                target="_blank"
                rel="noopener noreferrer"
                style={{ color: 'var(--brand)', fontWeight: 700, textDecoration: 'none' }}
              >
                서명 보기
              </a>
            ) : '-'}
          />
        </KV>
      </Section>

      <OrderDetailPhotoSection visiblePhotos={visiblePhotos} />

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
  );
}

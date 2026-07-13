import React from 'react';

import { getAdminMessageSettings, listAdminMessages, resolveUnknownMessageOutcome, sendAdminMessage } from '../../../api/messages';
import { DatePicker } from '../../../components/common/DatePicker';
import { PaginationBar, paginateItems } from '../../../components/common/Pagination';
import { Badge, Icon } from '../../../components/common/ui';
import { useApiResource } from '../../../api/useApiResource';
import { formatPhone } from '../../../domain/phone';
import { formatAppDateTime, formatAppDateValue } from '../../../domain/time';

const MESSAGE_TYPE_OPTIONS = [
  { value: 'all', label: '전체' },
  { value: 'customer_schedule_confirmed', label: '일정확정' },
  { value: 'customer_day_before', label: '전날안내' },
  { value: 'partner_assignment', label: '협력사배정' },
  { value: 'customer_photo_ready', label: '사진전달' },
  { value: 'customer_balance_due', label: '잔금안내' },
  { value: 'customer_quote', label: '견적서' },
  { value: 'partner_customer_info', label: '협력사 고객정보' },
  { value: 'partner_as_request', label: '협력사 AS' },
  { value: 'customer_as_notice', label: '고객 AS' },
  { value: 'customer_access_link', label: '접속링크' },
];

const STATUS_OPTIONS = [
  { value: 'all', label: '전체' },
  { value: 'pending', label: '결과 확인 중' },
  { value: 'sent', label: '요청성공' },
  { value: 'delivered', label: '배송완료' },
  { value: 'failed', label: '요청실패' },
  { value: 'delivery_failed', label: '배송실패' },
];

export function MessagesPage({ onOpenOrder }) {
  const messagesResource = useApiResource(listAdminMessages);
  const settingsResource = useApiResource(getAdminMessageSettings);
  const messages = messagesResource.data || [];
  const messageSettings = settingsResource.data || null;
  const [query, setQuery] = React.useState('');
  const [typeFilter, setTypeFilter] = React.useState('all');
  const [statusFilter, setStatusFilter] = React.useState('all');
  const [dateStart, setDateStart] = React.useState('');
  const [dateEnd, setDateEnd] = React.useState('');
  const [page, setPage] = React.useState(1);
  const [pageSize, setPageSize] = React.useState(20);
  const [isResending, setIsResending] = React.useState(false);
  const [notice, setNotice] = React.useState(null);
  const [error, setError] = React.useState(null);
  const stats = toStats(messages);
  const filtered = messages.filter((message) => (
    matchesQuery(message, query)
    && matchesType(message, typeFilter)
    && matchesStatus(message, statusFilter)
    && matchesDate(message, dateStart, dateEnd)
  ));
  const pagedMessages = React.useMemo(
    () => paginateItems(filtered, page, pageSize),
    [filtered, page, pageSize],
  );

  React.useEffect(() => {
    setPage(1);
  }, [query, typeFilter, statusFilter, dateStart, dateEnd]);

  const handleResend = async (message) => {
    setNotice(null);
    setError(null);
    setIsResending(true);
    try {
      // 재발송은 원본 발송 채널을 보존한다(원본이 알림톡이면 알림톡으로). 채널이 비면 SMS 기본값.
      const resent = await sendAdminMessage(
        message.order_id,
        message.message_type,
        message.recipient_type,
        message.channel || 'sms',
      );
      const reason = isMessageFailure(resent.status) ? ` (${providerErrorText(resent)})` : '';
      if (isMessagePending(resent.status)) {
        setError('SOL API 수락 여부를 확인 중입니다. SOLAPI 콘솔 확인 전에는 다시 발송하지 마세요.');
      } else {
        setNotice(`${shortOrderId(message.order_id)} ${messageTypeLabel(message.message_type)} 재발송 결과: ${messageStatusLabel(resent.status)}${reason}`);
      }
      messagesResource.reload();
    } catch (requestError) {
      setError(toActionErrorMessage(requestError));
    } finally {
      setIsResending(false);
    }
  };

  const handleResolveUnknown = async (message, resolution) => {
    const isConfirmedSent = resolution === 'confirmed_sent';
    const prompt = isConfirmedSent
      ? 'SOLAPI 콘솔에서 실제 발송됨을 확인했나요? 확인 시 이 발송을 성공 처리합니다.'
      : 'SOLAPI 콘솔에서 실제 미발송을 확인했나요? 확인 시 실패 처리되어 재발송할 수 있습니다.';
    if (!window.confirm(prompt)) return;
    setNotice(null);
    setError(null);
    setIsResending(true);
    try {
      await resolveUnknownMessageOutcome(message.id, resolution);
      setNotice(isConfirmedSent ? 'SOLAPI 발송 성공으로 수동 확정했습니다.' : 'SOLAPI 미발송으로 수동 확정했습니다. 이제 재발송할 수 있습니다.');
      messagesResource.reload();
    } catch (requestError) {
      setError(toActionErrorMessage(requestError));
    } finally {
      setIsResending(false);
    }
  };

  return (
    <div data-testid="admin-messages-page" style={{ flex: 1, overflow: 'auto', background: 'var(--bg)', padding: 20 }}>
      <div className="page-shell" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
          <StatCard label="전체 발송" value={messages.length} icon="send" />
          <StatCard label="성공" value={stats.sent} icon="check" tone="success" />
          <StatCard label="실패" value={stats.failed} icon="x" tone="danger" />
          <StatCard label="고객 링크" value={stats.customerLinks} icon="fileText" tone="info" />
        </div>

        {messageSettings && <MessageSettingsStrip settings={messageSettings} />}

        <section className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{
            minHeight: 48,
            padding: '9px 14px',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            borderBottom: '1px solid var(--divider)',
            flexWrap: 'wrap',
          }}>
            <Icon name="history" size={14} color="var(--text-tertiary)" />
            <strong style={{ fontSize: 13 }}>발송 이력</strong>
            <span style={{ fontSize: 11.5, color: 'var(--text-tertiary)' }}>
              SOL API 전환 시에도 이 화면에서 발송 성공/실패와 재발송을 추적합니다.
            </span>
            <div style={{ flex: 1 }} />
            <button className="btn btn--ghost btn--sm" onClick={messagesResource.reload}>
              <Icon name="refresh" size={12}/> 새로고침
            </button>
          </div>

          <div style={{
            padding: '10px 14px',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            borderBottom: '1px solid var(--divider)',
            flexWrap: 'wrap',
          }}>
            <SearchBox value={query} onChange={setQuery} />
            <Segmented
              testPrefix="messages-type"
              value={typeFilter}
              options={MESSAGE_TYPE_OPTIONS}
              onChange={setTypeFilter}
            />
            <Segmented
              testPrefix="messages-status"
              value={statusFilter}
              options={STATUS_OPTIONS}
              onChange={setStatusFilter}
            />
            <DatePicker
              compact
              testId="messages-date-start"
              ariaLabel="발송일 시작"
              placeholder="시작일"
              value={dateStart}
              onChange={setDateStart}
            />
            <span style={{ color: 'var(--text-quaternary)', fontSize: 12 }}>~</span>
            <DatePicker
              compact
              testId="messages-date-end"
              ariaLabel="발송일 종료"
              placeholder="종료일"
              value={dateEnd}
              onChange={setDateEnd}
            />
            {(query || typeFilter !== 'all' || statusFilter !== 'all' || dateStart || dateEnd) && (
              <button
                type="button"
                data-testid="messages-filter-clear"
                className="btn btn--ghost btn--sm"
                onClick={() => {
                  setQuery('');
                  setTypeFilter('all');
                  setStatusFilter('all');
                  setDateStart('');
                  setDateEnd('');
                }}
              >
                필터 해제
              </button>
            )}
          </div>

          {notice && <StateLine testId="messages-action-notice" text={notice} tone="success" />}
          {error && <StateLine testId="messages-action-error" text={error} tone="danger" />}
          {messagesResource.isLoading && <StateLine text="발송 이력을 불러오는 중입니다." />}
          {!messagesResource.isLoading && messagesResource.error && <StateLine text="발송 이력을 불러오지 못했습니다." tone="danger" />}
          {!messagesResource.isLoading && !messagesResource.error && filtered.length === 0 && <StateLine text="표시할 발송 이력이 없습니다." />}
          {!messagesResource.isLoading && !messagesResource.error && filtered.length > 0 && (
            <div
              role="region"
              aria-label="발송 이력 표"
              tabIndex={0}
              style={{ width: '100%', overflowX: 'auto' }}
            >
            <div role="table" aria-rowcount={pagedMessages.length + 1} style={{ minWidth: 1112, display: 'grid', gridTemplateColumns: '126px 104px 124px 128px minmax(220px, 1fr) 70px 120px 108px 112px', fontSize: 12 }}>
              <div role="row" style={{ display: 'contents' }}>
                {['발송시각', '고객', '유형', '수신자', '내용', '채널', 'Provider', '상태', '관리'].map((header) => (
                  <HeaderCell key={header}>{header}</HeaderCell>
                ))}
              </div>
              {pagedMessages.map((message) => (
                <div role="row" style={{ display: 'contents' }} key={message.id}>
                  <BodyCell mono>{formatDateTime(message.sent_at || message.created_at)}</BodyCell>
                  <BodyCell>
                    <button
                      type="button"
                      data-testid={`message-open-order-${message.order_id}`}
                      onClick={() => onOpenOrder?.(message.order_id)}
                      title="주문 상세 열기"
                      style={linkButtonStyle}
                    >
                      {message.order_customer_name || shortOrderId(message.order_id)}
                    </button>
                  </BodyCell>
                  <BodyCell>{messageTypeLabel(message.message_type)}</BodyCell>
                  <BodyCell>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{message.recipient_name}</div>
                      <div className="mono" style={{ color: 'var(--text-tertiary)', fontSize: 10.5 }}>{formatPhone(message.recipient_phone)}</div>
                    </div>
                  </BodyCell>
                  <BodyCell>
                    <span title={message.content} style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {message.content}
                    </span>
                  </BodyCell>
                  <BodyCell>{channelLabel(message.channel)}</BodyCell>
                  <BodyCell>
                    <div style={{ minWidth: 0, display: 'flex', flexDirection: 'column', gap: 3 }}>
                      <span style={{ fontWeight: 700 }}>{providerLabel(message.provider)}</span>
                      <span className="mono" title={providerRef(message)} style={{ color: 'var(--text-tertiary)', fontSize: 10.5, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {providerRef(message)}
                      </span>
                    </div>
                  </BodyCell>
                  <BodyCell>
                    <div style={{ minWidth: 0, display: 'flex', flexDirection: 'column', gap: 4 }}>
                      <Badge tone={messageStatusTone(message.status)} dot>{messageStatusLabel(message.status)}</Badge>
                      {(isMessageFailure(message.status) || isMessagePending(message.status)) && (
                        <span title={message.error_message || message.provider_error_code || ''} style={{ color: isMessagePending(message.status) ? 'var(--warn-fg)' : 'var(--danger-fg)', fontSize: 10.5, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {isMessagePending(message.status) && !isResolvableUnknown(message)
                            ? 'Provider 처리 결과 대기 중'
                            : providerErrorText(message)}
                        </span>
                      )}
                    </div>
                  </BodyCell>
                  <BodyCell>
                    <div style={{ display: 'inline-flex', gap: 5 }}>
                      {isResolvableUnknown(message) ? (
                        <>
                          <button
                            type="button"
                            data-testid={`message-resolve-sent-${message.id}`}
                            className="btn btn--secondary btn--sm"
                            disabled={isResending}
                            onClick={() => void handleResolveUnknown(message, 'confirmed_sent')}
                          >
                            발송 확인
                          </button>
                          <button
                            type="button"
                            data-testid={`message-resolve-not-sent-${message.id}`}
                            className="btn btn--secondary btn--sm"
                            disabled={isResending}
                            onClick={() => void handleResolveUnknown(message, 'confirmed_not_sent')}
                          >
                            미발송 확인
                          </button>
                        </>
                      ) : isMessagePending(message.status) ? (
                        <span style={{ color: 'var(--text-tertiary)', fontSize: 11 }}>
                          처리 결과 대기
                        </span>
                      ) : (
                        <button
                          type="button"
                          data-testid={`message-resend-${message.id}`}
                          className="btn btn--secondary btn--sm"
                          disabled={isResending}
                          onClick={() => void handleResend(message)}
                        >
                          재발송
                        </button>
                      )}
                    </div>
                  </BodyCell>
                </div>
              ))}
            </div>
            </div>
          )}
          {!messagesResource.isLoading && !messagesResource.error && filtered.length > 0 && (
            <PaginationBar
              testId="messages-pagination"
              totalItems={filtered.length}
              page={page}
              pageSize={pageSize}
              onPageChange={setPage}
              onPageSizeChange={setPageSize}
              itemLabel="건"
            />
          )}
        </section>
      </div>
    </div>
  );
}

function SearchBox({ value, onChange }) {
  return (
    <label style={{
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      padding: '0 10px',
      height: 30,
      minWidth: 250,
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: 8,
      color: 'var(--text-tertiary)',
      fontSize: 12,
    }}>
      <Icon name="search" size={13}/>
      <input
        data-testid="messages-search"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder="주문번호, 고객/협력사, 내용 검색"
        aria-label="발송 이력 검색"
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
    </label>
  );
}

function Segmented({ testPrefix, value, options, onChange }) {
  return (
    <div style={{ display: 'inline-flex', gap: 2, padding: 2, background: 'var(--bg-subtle)', border: '1px solid var(--border)', borderRadius: 8 }}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          data-testid={`${testPrefix}-${option.value}`}
          aria-pressed={value === option.value}
          onClick={() => onChange(option.value)}
          style={{
            height: 24,
            padding: '0 8px',
            border: 'none',
            borderRadius: 6,
            background: value === option.value ? 'var(--surface)' : 'transparent',
            color: value === option.value ? 'var(--text)' : 'var(--text-secondary)',
            boxShadow: value === option.value ? 'var(--shadow-xs)' : 'none',
            fontSize: 11.5,
            fontWeight: 600,
            cursor: 'pointer',
            whiteSpace: 'nowrap',
          }}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

function MessageSettingsStrip({ settings }) {
  const templateReadyCount = Object.values(settings.kakao_templates_configured || {})
    .filter(Boolean).length;
  const templateTotal = Object.keys(settings.kakao_templates_configured || {}).length;
  const hasWarnings = (settings.warnings || []).length > 0;
  return (
    <section className="card" data-testid="messages-settings-strip" style={{ padding: 12, display: 'grid', gridTemplateColumns: '1.1fr repeat(4, minmax(0, 0.8fr))', gap: 8, alignItems: 'center' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 9, minWidth: 0 }}>
        <span style={{
          width: 30,
          height: 30,
          borderRadius: 6,
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: hasWarnings ? 'var(--warn-bg)' : 'var(--success-bg)',
          color: hasWarnings ? 'var(--warn-fg)' : 'var(--success-fg)',
        }}>
          <Icon name={hasWarnings ? 'lock' : 'check'} size={14} />
        </span>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 12.5, fontWeight: 700 }}>{providerLabel(settings.provider)}</div>
          <div style={{ marginTop: 2, fontSize: 11, color: hasWarnings ? 'var(--warn-fg)' : 'var(--text-tertiary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {hasWarnings ? settingsWarningText(settings.warnings[0]) : '실발송 준비 완료'}
          </div>
        </div>
      </div>
      <ReadinessPill label="SMS" ready={settings.can_send_sms} />
      <ReadinessPill label="알림톡" ready={settings.can_send_alimtalk} />
      <ReadinessPill label="Webhook" ready={settings.solapi_webhook_configured} />
      <ReadinessPill label={`템플릿 ${templateReadyCount}/${templateTotal}`} ready={templateTotal > 0 && templateReadyCount === templateTotal} />
    </section>
  );
}

function ReadinessPill({ label, ready }) {
  return (
    <div style={{
      minHeight: 34,
      padding: '7px 9px',
      border: '1px solid var(--border)',
      borderRadius: 6,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: 8,
      fontSize: 11.5,
    }}>
      <span style={{ color: 'var(--text-secondary)', fontWeight: 600 }}>{label}</span>
      <Badge tone={ready ? 'success' : 'warn'} dot>{ready ? '준비' : '점검'}</Badge>
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
    <div role="columnheader" style={{
      padding: '9px 12px',
      borderBottom: '1px solid var(--border)',
      color: 'var(--text-secondary)',
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
    <div role="cell" style={{
      minWidth: 0,
      minHeight: 46,
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

function StateLine({ text, tone = 'muted', testId = undefined }) {
  const color = tone === 'danger'
    ? 'var(--danger-fg)'
    : tone === 'success'
      ? 'var(--success-fg)'
      : 'var(--text-tertiary)';
  return (
    <div data-testid={testId} style={{
      padding: 18,
      fontSize: 12.5,
      color,
    }}>
      {text}
    </div>
  );
}

function toStats(messages) {
  return {
    sent: messages.filter((message) => ['sent', 'delivered'].includes(message.status)).length,
    failed: messages.filter((message) => ['failed', 'delivery_failed'].includes(message.status)).length,
    customerLinks: messages.filter((message) => ['customer_schedule_confirmed', 'customer_day_before', 'customer_photo_ready', 'customer_balance_due', 'customer_as_notice', 'customer_access_link'].includes(message.message_type)).length,
  };
}

function matchesQuery(message, query) {
  const keyword = query.trim().toLowerCase();
  if (!keyword) {
    return true;
  }
  return [
    message.order_id,
    message.recipient_name,
    message.recipient_phone,
    message.message_type,
    message.content,
    message.error_message,
    message.provider,
    message.provider_error_code,
    message.provider_group_id,
    message.provider_message_id,
  ].some((value) => String(value || '').toLowerCase().includes(keyword));
}

function matchesType(message, typeFilter) {
  return typeFilter === 'all' || message.message_type === typeFilter;
}

function matchesStatus(message, statusFilter) {
  return statusFilter === 'all' || message.status === statusFilter;
}

function matchesDate(message, start, end) {
  if (!start && !end) {
    return true;
  }
  const value = toDateValue(message.sent_at || message.created_at);
  if (!value) {
    return false;
  }
  const range = normalizeDateRange(start, end);
  if (range.start && value < range.start) {
    return false;
  }
  if (range.end && value > range.end) {
    return false;
  }
  return true;
}

function normalizeDateRange(start, end) {
  if (start && end && start > end) {
    return { start: end, end: start };
  }
  return { start, end };
}

function toDateValue(value) {
  if (!value) {
    return '';
  }
  return formatAppDateValue(value);
}

function messageTypeLabel(type) {
  if (type === 'customer_schedule_confirmed') return '일정확정 안내';
  if (type === 'customer_day_before') return '전날 안내';
  if (type === 'partner_assignment') return '협력사 배정';
  if (type === 'customer_photo_ready') return '사진 전달';
  if (type === 'customer_balance_due') return '잔금 안내';
  if (type === 'customer_quote') return '견적서';
  if (type === 'partner_customer_info') return '협력사 고객정보';
  if (type === 'partner_as_request') return '협력사 AS 요청';
  if (type === 'customer_as_notice') return '고객 AS 안내';
  if (type === 'customer_access_link') return '고객 접속 링크';
  return type;
}

function messageStatusLabel(status) {
  if (status === 'pending') return '결과 확인 중';
  if (status === 'sent') return '요청성공';
  if (status === 'failed') return '요청실패';
  if (status === 'delivered') return '배송완료';
  if (status === 'delivery_failed') return '배송실패';
  return status || '-';
}

function messageStatusTone(status) {
  if (status === 'delivered') return 'success';
  if (status === 'sent') return 'info';
  if (isMessagePending(status)) return 'warn';
  if (isMessageFailure(status)) return 'danger';
  return 'neutral';
}

function isMessageFailure(status) {
  return status === 'failed' || status === 'delivery_failed';
}

function isMessagePending(status) {
  return status === 'pending';
}

function isResolvableUnknown(message) {
  return message.provider === 'solapi'
    && isMessagePending(message.status)
    && ['solapi_outcome_unknown', 'solapi_invalid_response'].includes(message.provider_error_code || '');
}

function channelLabel(channel) {
  if (channel === 'sms') return 'SMS';
  if (channel === 'lms') return 'LMS';
  if (channel === 'alimtalk') return '알림톡';
  return String(channel || '-').toUpperCase();
}

function providerLabel(provider) {
  if (provider === 'mock') return 'Mock';
  if (provider === 'solapi') return 'SOL API';
  if (provider === 'configuration_error') return 'Config';
  return provider || '-';
}

function providerRef(message) {
  return message.provider_group_id || message.provider_message_id || '-';
}

function providerErrorText(message) {
  const code = message.provider_error_code || '';
  const map = {
    missing_recipient: '수신번호 없음',
    solapi_missing_credentials: 'SOL API 인증 설정 누락',
    solapi_missing_sender_number: 'SOL API 발신번호 누락',
    solapi_missing_kakao_channel_id: 'SOL API 카카오 채널 ID 누락',
    solapi_missing_kakao_pf_id: 'SOL API 카카오 발신 프로필 ID 누락',
    solapi_missing_kakao_template_id: '알림톡 승인 템플릿 ID 누락',
    solapi_http_error: 'SOL API HTTP 오류',
    solapi_request_failed: 'SOL API 요청 실패',
    solapi_invalid_response: 'SOL API 응답 오류',
    solapi_outcome_unknown: 'SOL API 수락 여부 확인 필요',
    solapi_provider_failed: 'SOL API 발송 실패',
    unsupported_message_provider: 'Provider 설정 오류',
  };
  return map[code] || message.provider_status_message || message.error_message || '실패 사유 미상';
}

function settingsWarningText(code) {
  const map = {
    message_provider_mock: 'Mock 발송 모드',
    solapi_missing_credentials: 'SOL API 인증 설정 필요',
    solapi_missing_sender_number: '발신번호 설정 필요',
    solapi_missing_webhook_secret: 'Webhook secret 설정 필요',
    solapi_missing_kakao_channel_id: '카카오 채널 ID 설정 필요',
    solapi_missing_kakao_template_ids: '알림톡 템플릿 ID 설정 필요',
    unsupported_message_provider: 'Provider 설정 확인 필요',
  };
  return map[code] || '메시지 설정 확인 필요';
}

function formatDateTime(value) {
  return formatAppDateTime(value);
}

// 친화적 주문번호(cleanjob-0358, seed-order-2450 등)는 그대로 보여주고,
// UUID처럼 긴 무작위 식별자만 앞 8자로 줄인다.
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function shortOrderId(orderId) {
  const id = String(orderId || '');
  if (UUID_PATTERN.test(id)) {
    return `${id.slice(0, 8)}…`;
  }
  return id;
}

function toActionErrorMessage(error) {
  const detail = error?.detail || error?.message || '';
  const map = {
    order_not_found: '주문을 찾지 못했습니다.',
    partner_not_assigned: '협력사 배정 후 재발송할 수 있습니다.',
    partner_not_found: '배정된 협력사를 찾지 못했습니다.',
    no_customer_visible_photos: '고객에게 공개된 사진이 있어야 재발송할 수 있습니다.',
    customer_balance_not_due: '미수금이 있는 주문에만 잔금 안내를 재발송할 수 있습니다.',
    as_request_required: 'AS 요청 처리 후에만 AS 안내를 재발송할 수 있습니다.',
    message_outcome_unknown: 'SOL API 수락 여부를 확인 중입니다. 콘솔 확인 후 발송 또는 미발송으로 확정해주세요.',
    message_send_in_progress: '같은 안내의 발송 결과를 처리 중입니다. 잠시 후 다시 확인해주세요.',
    message_not_unknown_pending: '이미 처리됐거나 수동 확정 대상이 아닌 발송입니다. 이력을 새로고침해주세요.',
    invalid_unknown_outcome_resolution: '수동 확정 값이 올바르지 않습니다.',
    invalid_recipient_type: '수신자 유형이 올바르지 않습니다.',
  };
  return map[detail] || '재발송을 처리하지 못했습니다.';
}

const linkButtonStyle = {
  padding: 0,
  border: 'none',
  background: 'transparent',
  color: 'var(--brand)',
  fontSize: 12,
  fontWeight: 700,
  cursor: 'pointer',
  fontFamily: 'var(--font-mono)',
};

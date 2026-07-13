import React from 'react';

import { submitCustomerAsRequest, verifyCustomerOrder } from '../../api/customer';
import { ApiError, toApiAssetUrl } from '../../api/client';
import { BrandLogo } from '../../components/common/BrandLogo';
import { Badge, Icon } from '../../components/common/ui';
import { paymentStatusLabel } from '../../domain/paymentStatus';
import { formatQuantity } from '../../domain/format';
import { formatPhone } from '../../domain/phone';
import { readCapturedCustomerToken } from '../../domain/customerTokenPrivacy';
import { parseDateValue } from '../../domain/time';

export function CustomerReservation() {
  const initialLink = React.useMemo(readInitialCustomerLink, []);
  const [customerToken, setCustomerToken] = React.useState(initialLink.token);
  const [phoneSuffix, setPhoneSuffix] = React.useState('');
  const [order, setOrder] = React.useState(null);
  const [error, setError] = React.useState(null);
  const [isVerifying, setIsVerifying] = React.useState(false);

  const handleVerify = async (event) => {
    event.preventDefault();
    setError(null);
    setIsVerifying(true);

    try {
      const verifiedOrder = await verifyCustomerOrder(customerToken.trim(), phoneSuffix.trim());
      setOrder(verifiedOrder);
    } catch (requestError) {
      setError(toCustomerErrorMessage(requestError));
    } finally {
      setIsVerifying(false);
    }
  };

  const handleSubmitAftercare = async (orderId, memo) => {
    const updatedOrder = await submitCustomerAsRequest(
      customerToken.trim(),
      phoneSuffix.trim(),
      orderId,
      memo,
    );
    setOrder(updatedOrder);
  };

  return (
    <div style={pageStyle}>
      <CustomerHeader />

      {!order ? (
        <VerificationGate
          customerToken={customerToken}
          phoneSuffix={phoneSuffix}
          error={error}
          isVerifying={isVerifying}
          isTokenFromLink={initialLink.isFromUrl}
          onCustomerTokenChange={setCustomerToken}
          onPhoneSuffixChange={setPhoneSuffix}
          onVerify={handleVerify}
        />
      ) : (
        <ReservationContent
          order={order}
          onReset={() => {
            setOrder(null);
            setPhoneSuffix('');
            setError(null);
          }}
          onSubmitAftercare={handleSubmitAftercare}
        />
      )}
    </div>
  );
}

function CustomerHeader() {
  return (
    <header style={headerStyle}>
      <BrandLogo size="md" />
      <div style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-secondary)', fontWeight: 700, letterSpacing: '0.04em' }}>
        예약 확인센터
      </div>
    </header>
  );
}

function VerificationGate({
  customerToken,
  phoneSuffix,
  error,
  isVerifying,
  isTokenFromLink,
  onCustomerTokenChange,
  onPhoneSuffixChange,
  onVerify,
}) {
  return (
    <div
      role="region"
      aria-label="고객 예약 인증"
      className="scroll"
      style={{ flex: 1, overflow: 'auto', padding: '28px 20px' }}
    >
      <form data-testid="customer-verify-form" onSubmit={onVerify} style={gateCardStyle}>
        <div style={shieldStyle}>
          <Icon name="shield" size={20} />
        </div>
        <div style={eyebrowStyle}>고객 전용 보안 확인</div>
        <h1 style={gateTitleStyle}>
          연락처 뒷자리로<br />
          예약 정보를 확인합니다
        </h1>
        <p className="ko-copy" style={gateCopyStyle}>
          문자로 받은 링크와 예약 연락처 마지막 4자리가 일치할 때만 예약 상세와 공개된 사진을 보여드립니다.
        </p>

        {!isTokenFromLink && (
          <label style={fieldStyle}>
            <span style={labelStyle}>링크 토큰</span>
          <input
            data-testid="customer-token-input"
            value={customerToken}
              onChange={(event) => onCustomerTokenChange(event.target.value)}
              placeholder="문자 링크의 확인 코드"
              autoComplete="off"
              style={inputStyle}
              required
            />
          </label>
        )}

        {isTokenFromLink && (
          <div className="ko-copy" style={linkNoticeStyle}>
            <Icon name="lock" size={13} />
            문자 링크가 확인되었습니다. 연락처 뒷자리만 입력해주세요.
          </div>
        )}

        <label style={fieldStyle}>
          <span style={labelStyle}>전화번호 뒤 4자리</span>
          <input
            className="customer-auth-input"
            data-testid="customer-phone-suffix"
            value={phoneSuffix}
            onChange={(event) => onPhoneSuffixChange(event.target.value.replace(/\D/g, '').slice(0, 4))}
            placeholder="1234"
            inputMode="numeric"
            pattern="[0-9]{4}"
            autoComplete="one-time-code"
            style={{ ...inputStyle, fontSize: 22, letterSpacing: '0.16em', fontWeight: 700 }}
            required
          />
        </label>

        {error && (
          <div
            role="alert"
            aria-live="assertive"
            data-testid="customer-verify-error"
            style={errorStyle}
          >
            {error}
          </div>
        )}

        <button
          type="submit"
          data-testid="customer-verify-submit"
          disabled={isVerifying || phoneSuffix.length !== 4 || !customerToken.trim()}
          style={{
            ...primaryButtonStyle,
            background: isVerifying || phoneSuffix.length !== 4 || !customerToken.trim() ? 'var(--text-secondary)' : 'var(--text)',
            cursor: isVerifying ? 'default' : 'pointer',
          }}
        >
          {isVerifying ? '확인 중' : '예약 확인'}
        </button>
      </form>

      <p className="ko-copy" style={privacyNoteStyle}>
        인증 전에는 예약 상세, 주소, 사진을 표시하지 않습니다.<br />
        링크가 만료되었거나 인증이 되지 않으면 고객센터로 문의해주세요.
      </p>
    </div>
  );
}

function ReservationContent({ order, onReset, onSubmitAftercare }) {
  const lines = order.lines || [];
  const primaryLine = lines[0] || null;

  return (
    <div
      role="region"
      aria-label="예약 상세"
      data-testid="customer-order-page"
      className="scroll"
      style={{ flex: 1, overflow: 'auto' }}
      tabIndex={0}
    >
      <section style={{ padding: '24px 20px 16px' }}>
        <div style={eyebrowStyle}>{statusHeadline(primaryLine)}</div>
        <h1 style={contentTitleStyle}>
          {order.customer_name} 님<br />
          <span style={{ color: 'var(--text-secondary)', fontWeight: 600 }}>{visitHeadline(primaryLine)}</span>
        </h1>

        <div style={{ display: 'flex', gap: 6, marginTop: 14, flexWrap: 'wrap' }}>
          {primaryLine && (
            <Badge tone={customerStatusTone(primaryLine.status, primaryLine.aftercare_status)} dot>
              {customerStatusLabel(primaryLine.status, primaryLine.aftercare_status)}
            </Badge>
          )}
          <Badge tone="brand">{lines.length}개 라인</Badge>
        </div>
      </section>

      <section style={{ padding: '0 16px' }}>
        <div style={summaryCardStyle}>
          <CustomerRow icon="mapPin" label="방문지">
            {[order.customer_address, order.customer_address_detail].filter(Boolean).join(' ')}
          </CustomerRow>
          <CustomerRow icon="phone" label="예약 연락처">
            <span className="mono" data-testid="customer-visible-phone">{formatPhone(order.customer_phone)}</span>
          </CustomerRow>
        </div>
      </section>

      <VisitGuide />

      <section style={{ padding: '0 16px 20px', display: 'flex', flexDirection: 'column', gap: 12 }}>
        {lines.length === 0 ? (
          <div style={summaryCardStyle}>
            <SummaryBlock title="예약 정보">예약 정보가 없습니다.</SummaryBlock>
          </div>
        ) : (
          lines.map((line) => (
            <ReservationLineCard
              key={line.id}
              line={line}
              customerVisiblePayment={order.customer_visible_payment}
              onSubmitAftercare={(memo) => onSubmitAftercare(line.id, memo)}
            />
          ))
        )}
      </section>

      <section style={{ padding: '0 16px 24px' }}>
        <button type="button" style={secondaryButtonStyle} onClick={onReset}>
          <Icon name="lock" size={13} /> 다시 인증하기
        </button>
      </section>

      <TrustFooter />
    </div>
  );
}

function ReservationLineCard({ line, customerVisiblePayment, onSubmitAftercare }) {
  const quantity = formatQuantity(line.size_or_quantity);

  return (
    <section data-testid={`customer-line-${line.id}`} style={summaryCardStyle}>
      <SummaryBlock title="방문 일시">
        <div style={{ fontSize: 18, fontWeight: 800, letterSpacing: '-0.02em' }}>{formatKoreanDate(line.scheduled_date)}</div>
        <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 3 }}>{line.requested_time || '시간 협의 중'}</div>
      </SummaryBlock>
      <CustomerRow icon="package" label="서비스">
        {line.service_name}
        {quantity && <span style={mutedInlineStyle}> · {quantity}</span>}
        {line.service_detail && <div style={mutedLineStyle}>{line.service_detail}</div>}
      </CustomerRow>
      <CustomerRow icon="bell" label="진행상황">
        <Badge tone={customerStatusTone(line.status, line.aftercare_status)} dot>
          {customerStatusLabel(line.status, line.aftercare_status)}
        </Badge>
        {line.special_request && <div style={mutedLineStyle}>{line.special_request}</div>}
      </CustomerRow>
      {customerVisiblePayment && (
        <CustomerRow icon="creditCard" label="결제 안내">
          <PaymentSummary line={line} />
        </CustomerRow>
      )}
      <CustomerPhotos photos={line.photos || []} />
      <CustomerAftercareAction
        status={line.aftercare_status}
        onSubmit={onSubmitAftercare}
      />
    </section>
  );
}

function CustomerAftercareAction({ status, onSubmit }) {
  const [isOpen, setIsOpen] = React.useState(false);
  const [memo, setMemo] = React.useState('');
  const [error, setError] = React.useState('');
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  if (!status) {
    return null;
  }
  if (status === 'pending') {
    return (
      <div data-testid="customer-aftercare-pending" style={aftercarePendingStyle} aria-live="polite">
        <div style={aftercareTitleStyle}>AS 접수가 완료되었습니다</div>
        <div style={aftercareCopyStyle}>운영팀 확인 후 협력사 처리 일정과 함께 안내드리겠습니다.</div>
      </div>
    );
  }
  if (status === 'in_progress') {
    return (
      <div data-testid="customer-aftercare-in-progress" style={aftercareProgressStyle} aria-live="polite">
        <div style={aftercareTitleStyle}>AS 요청을 처리 중입니다</div>
        <div style={aftercareCopyStyle}>협력사가 재방문 일정을 확인해 연락드릴 예정입니다.</div>
      </div>
    );
  }

  const trimmedMemo = memo.trim();
  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!trimmedMemo) {
      setError('확인이 필요한 내용을 입력해주세요.');
      return;
    }
    setError('');
    setIsSubmitting(true);
    try {
      await onSubmit(trimmedMemo);
    } catch (requestError) {
      setError(toAftercareErrorMessage(requestError));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div data-testid="customer-aftercare-action" style={aftercareAvailableStyle}>
      <div style={aftercareTitleStyle}>작업 후 확인이 필요하신가요?</div>
      <div style={aftercareCopyStyle}>사진과 작업 결과를 확인한 뒤 보완이 필요한 내용을 접수할 수 있습니다.</div>
      {!isOpen ? (
        <button
          type="button"
          data-testid="customer-aftercare-open"
          style={aftercareOpenButtonStyle}
          onClick={() => setIsOpen(true)}
        >
          AS 접수
        </button>
      ) : (
        <form onSubmit={(event) => void handleSubmit(event)} style={aftercareFormStyle}>
          <label style={aftercareFieldStyle}>
            <span style={labelStyle}>확인이 필요한 내용</span>
            <textarea
              data-testid="customer-aftercare-memo"
              value={memo}
              onChange={(event) => {
                setMemo(event.target.value.slice(0, 2000));
                if (error) setError('');
              }}
              rows={4}
              maxLength={2000}
              placeholder="보완이 필요한 위치와 내용을 적어주세요."
              style={aftercareTextareaStyle}
              disabled={isSubmitting}
              required
            />
          </label>
          {error && <div role="alert" style={aftercareErrorStyle}>{error}</div>}
          <div style={aftercareActionsStyle}>
            <button
              type="button"
              style={aftercareCancelButtonStyle}
              onClick={() => {
                setIsOpen(false);
                setMemo('');
                setError('');
              }}
              disabled={isSubmitting}
            >
              취소
            </button>
            <button
              type="submit"
              data-testid="customer-aftercare-submit"
              style={{
                ...aftercareSubmitButtonStyle,
                opacity: isSubmitting || !trimmedMemo ? 0.55 : 1,
              }}
              disabled={isSubmitting || !trimmedMemo}
            >
              {isSubmitting ? '접수 중' : '접수하기'}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}

function SummaryBlock({ title, children }) {
  return (
    <div style={{ padding: '16px 18px', borderBottom: '1px solid var(--divider)' }}>
      <div style={smallLabelStyle}>{title}</div>
      {children}
    </div>
  );
}

function CustomerRow({ icon, label, children, last = false }) {
  return (
    <div style={{
      display: 'flex',
      gap: 12,
      padding: '13px 18px',
      borderBottom: last ? 'none' : '1px solid var(--divider)',
    }}>
      <span style={rowIconStyle}>
        <Icon name={icon} size={13} />
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={smallLabelStyle}>{label}</div>
        <div style={{ fontSize: 13.5, color: 'var(--text)', lineHeight: 1.5 }}>{children}</div>
      </div>
    </div>
  );
}

function PaymentSummary({ line }) {
  if (line.total_amount == null) {
    return <span style={{ color: 'var(--text-tertiary)', fontSize: 12.5 }}>결제 안내는 별도로 안내드립니다.</span>;
  }

  return (
    <>
      <span style={{ fontWeight: 700 }}>{formatWon(line.total_amount)}</span>
      <div style={mutedLineStyle}>
        {line.deposit_amount != null && <>계약금 {formatWon(line.deposit_amount)}</>}
        {line.deposit_amount != null && line.balance_amount != null && ' · '}
        {line.balance_amount != null && <>잔금 {formatWon(line.balance_amount)}</>}
      </div>
      {line.payment_status && <div style={mutedLineStyle}>상태: {paymentStatusLabel(line.payment_status)}</div>}
    </>
  );
}

function VisitGuide() {
  return (
    <section style={{ padding: '16px 16px 8px' }}>
      <div style={guideStyle}>
        <div style={{ ...smallLabelStyle, color: 'var(--warn-fg)', display: 'flex', alignItems: 'center', gap: 5 }}>
          <Icon name="bell" size={11} /> 방문 전 안내
        </div>
        <ul style={{ margin: '8px 0 0', padding: '0 0 0 16px', fontSize: 12.5, color: 'var(--warn-fg)', lineHeight: 1.65, wordBreak: 'keep-all' }}>
          <li>작업 공간 주변 물건은 가능한 범위에서 미리 이동해주세요.</li>
          <li>현장 상황에 따라 작업 시간은 조금 달라질 수 있습니다.</li>
          <li>완료 사진은 이 페이지에 표시됩니다.</li>
        </ul>
      </div>
    </section>
  );
}

function CustomerPhotos({ photos }) {
  const groups = [
    { key: 'before', title: '비포' },
    { key: 'after', title: '애프터' },
    { key: 'etc', title: '기타' },
  ].map((group) => ({
    ...group,
    photos: photos.filter((photo) => photo.photo_type === group.key),
  })).filter((group) => group.photos.length > 0);

  return (
    <section data-testid="customer-photos" style={{ padding: '12px 16px 24px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
        <span style={{ fontSize: 13, fontWeight: 800 }}>작업 완료 사진</span>
        <Badge tone={photos.length ? 'success' : 'neutral'}>{photos.length ? `${photos.length}장 공개` : '대기중'}</Badge>
      </div>

      {photos.length === 0 ? (
        <PhotoPending />
      ) : (
        <div style={photoCardStyle}>
          {groups.map((group) => (
            <div key={group.key}>
              <div style={{ ...smallLabelStyle, marginBottom: 8 }}>{group.title}</div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 8 }}>
                {group.photos.map((photo) => (
                  <figure key={photo.id} style={{ margin: 0 }}>
                    <img
                      data-testid={`customer-photo-${photo.id}`}
                      src={toApiAssetUrl(photo.file_url)}
                      alt={photo.file_name || `${group.title} 사진`}
                      loading="lazy"
                      style={photoImageStyle}
                    />
                    {photo.file_name && <figcaption style={captionStyle}>{photo.file_name}</figcaption>}
                  </figure>
                ))}
              </div>
            </div>
          ))}
          <div style={{ fontSize: 11.5, color: 'var(--text-tertiary)', lineHeight: 1.45 }}>
            협력사가 업로드해 공개된 사진만 표시됩니다.
          </div>
        </div>
      )}
    </section>
  );
}

function PhotoPending() {
  return (
    <div data-testid="customer-photo-pending" style={photoPendingStyle}>
      <div style={photoPendingIconStyle}>
        <Icon name="camera" size={18} />
      </div>
      <div style={{ fontSize: 13, color: 'var(--text-secondary)', fontWeight: 700, marginBottom: 3 }}>
        협력사가 사진을 올리면 이곳에 표시됩니다
      </div>
      <div style={{ fontSize: 11.5, color: 'var(--text-tertiary)' }}>
        업로드된 공개 사진만 볼 수 있습니다.
      </div>
    </div>
  );
}

function TrustFooter() {
  return (
    <footer style={{ padding: '0 16px 26px' }}>
      <div style={trustGridStyle}>
        {[
          { icon: 'shield', label: '보안 확인', sub: '링크 인증' },
          { icon: 'star', label: '공개 사진', sub: '업로드 후 표시' },
          { icon: 'sparkles', label: '고객센터', sub: '1688-9512' },
        ].map((item) => (
          <div key={item.label} style={{ textAlign: 'center' }}>
            <div style={{ display: 'inline-flex', color: 'var(--text-secondary)', marginBottom: 4 }}>
              <Icon name={item.icon} size={14} />
            </div>
            <div style={{ fontSize: 10.5, color: 'var(--text-secondary)', fontWeight: 600 }}>{item.label}</div>
            <div style={{ fontSize: 12, fontWeight: 700 }}>{item.sub}</div>
          </div>
        ))}
      </div>

      <a href="tel:16889512" style={callButtonStyle}>
        <Icon name="phone" size={14} /> 1688-9512
      </a>

      <div style={{ textAlign: 'center', fontSize: 10.5, color: 'var(--text-secondary)', marginTop: 16, lineHeight: 1.5 }}>
        이 페이지는 예약 고객 전용 링크입니다.<br />
        연락처 뒷자리 인증으로 보호됩니다.
      </div>
    </footer>
  );
}

function readInitialCustomerLink() {
  const capturedToken = readCapturedCustomerToken();

  return {
    token: capturedToken,
    isFromUrl: Boolean(capturedToken),
  };
}

function toCustomerErrorMessage(error) {
  if (error instanceof ApiError) {
    if (error.status === 404) {
      return '링크 또는 전화번호 뒷자리가 일치하지 않습니다.';
    }
    if (error.status === 422) {
      return '전화번호 뒤 4자리 숫자를 입력해주세요.';
    }
    if (error.status === 410) {
      return '만료된 링크입니다. 고객센터로 문의해주세요.';
    }
    return '예약 정보를 확인하지 못했습니다. 잠시 후 다시 시도해주세요.';
  }

  return '예약 정보를 확인하지 못했습니다.';
}

function toAftercareErrorMessage(error) {
  if (error instanceof ApiError) {
    if (error.status === 409) {
      return '이미 접수된 AS 요청이 있습니다. 운영팀 확인을 기다려주세요.';
    }
    if (error.status === 404) {
      return '예약 인증 정보를 다시 확인해주세요.';
    }
    if (error.status === 422) {
      return '확인이 필요한 내용을 입력해주세요.';
    }
    return 'AS를 접수하지 못했습니다. 잠시 후 다시 시도해주세요.';
  }
  return 'AS를 접수하지 못했습니다.';
}

function statusHeadline(line) {
  if (line?.aftercare_status === 'pending') {
    return 'AS 접수를 확인하고 있습니다';
  }
  if (line?.aftercare_status === 'in_progress') {
    return 'AS 요청을 처리 중입니다';
  }
  const status = line?.status;
  if (['고객전달필요', '고객전달완료', '서비스완료'].includes(status)) {
    return '작업 결과를 확인해주세요';
  }
  if (status === '취소') {
    return '예약이 취소되었습니다';
  }
  if (status === '사진검수대기') {
    return '작업 확인 중입니다';
  }
  return '예약이 확인되었습니다';
}

function customerStatusLabel(status, aftercareStatus) {
  if (aftercareStatus === 'pending') {
    return 'AS 접수 확인 중';
  }
  if (aftercareStatus === 'in_progress') {
    return 'AS 처리 중';
  }
  if (status === '취소') {
    return '예약 취소';
  }
  if (['고객전달필요', '고객전달완료', '서비스완료'].includes(status)) {
    return '작업 완료';
  }
  if (status === '작업진행') {
    return '작업 진행 중';
  }
  if (status === '사진검수대기') {
    return '확인 중';
  }
  if (['일정확정', '전날안내필요', '전날안내완료', '작업예정'].includes(status)) {
    return '방문 예정';
  }
  return '예약 확인 중';
}

function customerStatusTone(status, aftercareStatus) {
  if (aftercareStatus === 'pending') {
    return 'warn';
  }
  if (aftercareStatus === 'in_progress') {
    return 'info';
  }
  if (status === '취소') {
    return 'danger';
  }
  if (['고객전달필요', '고객전달완료', '서비스완료'].includes(status)) {
    return 'success';
  }
  if (status === '작업진행') {
    return 'info';
  }
  return 'neutral';
}

function visitHeadline(line) {
  if (!line || !line.scheduled_date) {
    return '방문 일정은 확정 후 안내드립니다.';
  }

  const formattedDate = formatKoreanDate(line.scheduled_date);
  if (['pending', 'in_progress'].includes(line.aftercare_status)) {
    return `기존\u00a0방문일 · ${formattedDate}`;
  }
  if (['고객전달필요', '고객전달완료', '서비스완료'].includes(line.status)) {
    return `${formattedDate} 작업이\u00a0완료되었습니다`;
  }
  if (line.status === '취소') {
    return `${formattedDate} 예약이\u00a0취소되었습니다`;
  }
  return `${formattedDate} 방문\u00a0예정입니다`;
}

function formatKoreanDate(value) {
  if (!value) {
    return '일정 확인 중';
  }
  const date = parseDateValue(value);
  if (!date) {
    return value;
  }
  const weekday = ['일', '월', '화', '수', '목', '금', '토'][date.getDay()];
  return `${date.getFullYear()}년 ${date.getMonth() + 1}월 ${date.getDate()}일 ${weekday}요일`;
}

function formatWon(value) {
  return `${Number(value || 0).toLocaleString()}원`;
}

function css(style) {
  return style;
}

const pageStyle = css({
  minHeight: '100%',
  height: '100%',
  width: '100%',
  maxWidth: 768,
  margin: '0 auto',
  display: 'flex',
  flexDirection: 'column',
  background: 'var(--bg-subtle)',
  overflow: 'hidden',
  fontFamily: 'var(--font)',
  color: 'var(--text)',
});

const headerStyle = css({
  padding: '18px 20px 14px',
  background: 'var(--surface)',
  borderBottom: '1px solid var(--border)',
  display: 'flex',
  alignItems: 'center',
  gap: 9,
  flexShrink: 0,
});

const gateCardStyle = css({
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: 20,
});

const shieldStyle = css({
  width: 42,
  height: 42,
  borderRadius: 12,
  background: 'var(--bg-muted)',
  color: 'var(--text)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  marginBottom: 14,
});

const eyebrowStyle = css({
  fontSize: 11.5,
  color: 'var(--text-secondary)',
  letterSpacing: '0.04em',
  fontWeight: 800,
  marginBottom: 6,
});

const gateTitleStyle = css({
  margin: 0,
  fontSize: 22,
  fontWeight: 800,
  letterSpacing: '-0.025em',
  lineHeight: 1.3,
});

const gateCopyStyle = css({
  margin: '10px 0 18px',
  color: 'var(--text-secondary)',
  fontSize: 13,
  lineHeight: 1.55,
});

const fieldStyle = css({
  display: 'flex',
  flexDirection: 'column',
  gap: 6,
  marginBottom: 12,
});

const labelStyle = css({
  color: 'var(--text-secondary)',
  fontSize: 12,
  fontWeight: 800,
});

const inputStyle = css({
  width: '100%',
  height: 46,
  border: '1px solid var(--border-strong)',
  borderRadius: 10,
  padding: '0 12px',
  fontSize: 16,
  background: 'var(--surface)',
  color: 'var(--text)',
});

const linkNoticeStyle = css({
  display: 'flex',
  alignItems: 'center',
  gap: 7,
  marginBottom: 12,
  padding: '10px 12px',
  borderRadius: 10,
  background: 'var(--bg-muted)',
  color: 'var(--text-secondary)',
  fontSize: 12,
  lineHeight: 1.45,
});

const errorStyle = css({
  padding: '10px 12px',
  borderRadius: 10,
  background: 'var(--danger-bg)',
  border: '1px solid var(--danger-border)',
  color: 'var(--danger-fg)',
  fontSize: 12.5,
  lineHeight: 1.45,
  marginBottom: 12,
});

const primaryButtonStyle = css({
  width: '100%',
  height: 46,
  borderRadius: 12,
  border: 'none',
  color: 'var(--surface)',
  fontSize: 14,
  fontWeight: 800,
});

const privacyNoteStyle = css({
  margin: '16px 0 0',
  padding: '0 12px',
  color: 'var(--text-secondary)',
  fontSize: 11.5,
  lineHeight: 1.5,
  textAlign: 'center',
});

const contentTitleStyle = css({
  margin: 0,
  fontSize: 22,
  fontWeight: 800,
  letterSpacing: '-0.025em',
  lineHeight: 1.3,
  wordBreak: 'keep-all',
});

const summaryCardStyle = css({
  background: 'var(--surface)',
  borderRadius: 8,
  border: '1px solid var(--border)',
  overflow: 'hidden',
});

const smallLabelStyle = css({
  fontSize: 10.5,
  color: 'var(--text-secondary)',
  fontWeight: 800,
  letterSpacing: '0.06em',
  marginBottom: 4,
});

const rowIconStyle = css({
  width: 28,
  height: 28,
  borderRadius: 7,
  flexShrink: 0,
  background: 'var(--bg-muted)',
  color: 'var(--text)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  marginTop: 2,
});

const mutedInlineStyle = css({
  color: 'var(--text-tertiary)',
  fontSize: 12.5,
});

const mutedLineStyle = css({
  color: 'var(--text-tertiary)',
  fontSize: 12,
  marginTop: 3,
  lineHeight: 1.45,
  whiteSpace: 'pre-wrap',
  wordBreak: 'break-word',
});

const guideStyle = css({
  background: 'var(--warn-bg)',
  border: '1px solid var(--warn-border)',
  borderRadius: 8,
  padding: '12px 14px',
});

const photoCardStyle = css({
  background: 'var(--surface)',
  borderRadius: 8,
  border: '1px solid var(--border)',
  padding: 12,
  display: 'flex',
  flexDirection: 'column',
  gap: 14,
});

const photoImageStyle = css({
  width: '100%',
  aspectRatio: '1',
  objectFit: 'cover',
  borderRadius: 10,
  border: '1px solid var(--border)',
  background: 'var(--bg-muted)',
  display: 'block',
});

const captionStyle = css({
  marginTop: 4,
  fontSize: 10.5,
  color: 'var(--text-secondary)',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
});

const photoPendingStyle = css({
  background: 'var(--surface)',
  borderRadius: 8,
  border: '1px dashed var(--border-strong)',
  padding: '32px 20px',
  textAlign: 'center',
});

const photoPendingIconStyle = css({
  width: 40,
  height: 40,
  borderRadius: 10,
  background: 'var(--bg-muted)',
  color: 'var(--text-tertiary)',
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  marginBottom: 8,
});

const aftercareAvailableStyle = css({
  padding: 16,
  borderTop: '1px solid var(--border)',
  background: 'var(--surface)',
});

const aftercarePendingStyle = css({
  padding: 16,
  borderTop: '1px solid var(--border)',
  background: 'var(--warn-bg)',
  color: 'var(--warn-fg)',
});

const aftercareProgressStyle = css({
  padding: 16,
  borderTop: '1px solid var(--border)',
  background: 'var(--info-bg)',
  color: 'var(--info-fg)',
});

const aftercareTitleStyle = css({
  fontSize: 13.5,
  fontWeight: 800,
  lineHeight: 1.4,
});

const aftercareCopyStyle = css({
  marginTop: 4,
  color: 'currentColor',
  fontSize: 12,
  lineHeight: 1.55,
});

const aftercareOpenButtonStyle = css({
  width: '100%',
  height: 42,
  marginTop: 12,
  border: 'none',
  borderRadius: 10,
  background: 'var(--text)',
  color: 'var(--surface)',
  fontSize: 13,
  fontWeight: 800,
  cursor: 'pointer',
});

const aftercareFormStyle = css({
  display: 'grid',
  gap: 12,
  marginTop: 12,
});

const aftercareFieldStyle = css({
  display: 'grid',
  gap: 6,
});

const aftercareTextareaStyle = css({
  width: '100%',
  minHeight: 108,
  border: '1px solid var(--border-strong)',
  borderRadius: 10,
  padding: 12,
  resize: 'vertical',
  background: 'var(--surface)',
  color: 'var(--text)',
  fontFamily: 'var(--font)',
  fontSize: 16,
  lineHeight: 1.5,
});

const aftercareErrorStyle = css({
  padding: '10px 12px',
  border: '1px solid var(--danger-bg)',
  borderRadius: 8,
  background: 'var(--danger-bg)',
  color: 'var(--danger-fg)',
  fontSize: 12,
  lineHeight: 1.45,
});

const aftercareActionsStyle = css({
  display: 'grid',
  gridTemplateColumns: '1fr 1.5fr',
  gap: 8,
});

const aftercareCancelButtonStyle = css({
  height: 42,
  border: '1px solid var(--border-strong)',
  borderRadius: 10,
  background: 'var(--surface)',
  color: 'var(--text-secondary)',
  fontSize: 13,
  fontWeight: 700,
  cursor: 'pointer',
});

const aftercareSubmitButtonStyle = css({
  height: 42,
  border: 'none',
  borderRadius: 10,
  background: 'var(--text)',
  color: 'var(--surface)',
  fontSize: 13,
  fontWeight: 800,
  cursor: 'pointer',
});

const secondaryButtonStyle = css({
  width: '100%',
  height: 42,
  borderRadius: 10,
  border: '1px solid var(--border-strong)',
  background: 'var(--surface)',
  color: 'var(--text)',
  fontSize: 13,
  fontWeight: 800,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: 6,
});

const trustGridStyle = css({
  display: 'grid',
  gridTemplateColumns: '1fr 1fr 1fr',
  gap: 8,
  padding: '14px 4px',
  borderTop: '1px solid var(--border)',
  borderBottom: '1px solid var(--border)',
});

const callButtonStyle = css({
  marginTop: 14,
  height: 42,
  borderRadius: 10,
  background: 'var(--text)',
  color: 'var(--surface)',
  border: 'none',
  fontSize: 13,
  fontWeight: 800,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: 6,
  textDecoration: 'none',
});

import React from 'react';

import { verifyCustomerOrder } from '../../api/customer';
import { ApiError } from '../../api/client';
import { Badge, Icon } from '../../components/common/ui';
import { paymentStatusLabel } from '../../domain/paymentStatus';

const CUSTOMER_TOKEN_STORAGE_KEY = 'cleaning_ops_customer_token';

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
      sessionStorage.setItem(CUSTOMER_TOKEN_STORAGE_KEY, customerToken.trim());
      setOrder(verifiedOrder);
    } catch (requestError) {
      setError(toCustomerErrorMessage(requestError));
    } finally {
      setIsVerifying(false);
    }
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
        <ReservationContent order={order} onReset={() => setOrder(null)} />
      )}
    </div>
  );
}

function CustomerHeader() {
  return (
    <header style={headerStyle}>
      <div style={brandMarkStyle}>C</div>
      <div>
        <div style={{ fontSize: 14, fontWeight: 800, letterSpacing: '-0.01em' }}>Cleaning Ops</div>
        <div style={{ fontSize: 11, color: '#64748b', marginTop: 1 }}>예약 확인센터 · 1588-2480</div>
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
    <main className="scroll" style={{ flex: 1, overflow: 'auto', padding: '28px 20px' }}>
      <form onSubmit={onVerify} style={gateCardStyle}>
        <div style={shieldStyle}>
          <Icon name="shield" size={20} />
        </div>
        <div style={eyebrowStyle}>고객 전용 보안 확인</div>
        <h1 style={gateTitleStyle}>
          연락처 뒷자리로<br />
          예약 정보를 확인합니다
        </h1>
        <p style={gateCopyStyle}>
          문자로 받은 링크와 예약 연락처 마지막 4자리가 일치할 때만 예약 상세와 승인된 사진을 보여드립니다.
        </p>

        {!isTokenFromLink && (
          <label style={fieldStyle}>
            <span style={labelStyle}>링크 토큰</span>
            <input
              value={customerToken}
              onChange={(event) => onCustomerTokenChange(event.target.value)}
              placeholder="문자 링크의 token"
              autoComplete="off"
              style={inputStyle}
              required
            />
          </label>
        )}

        {isTokenFromLink && (
          <div style={linkNoticeStyle}>
            <Icon name="lock" size={13} />
            문자 링크가 확인되었습니다. 연락처 뒷자리만 입력해주세요.
          </div>
        )}

        <label style={fieldStyle}>
          <span style={labelStyle}>전화번호 뒤 4자리</span>
          <input
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

        {error && <div style={errorStyle}>{error}</div>}

        <button
          type="submit"
          disabled={isVerifying || phoneSuffix.length !== 4 || !customerToken.trim()}
          style={{
            ...primaryButtonStyle,
            background: isVerifying || phoneSuffix.length !== 4 || !customerToken.trim() ? '#475569' : '#0f172a',
            cursor: isVerifying ? 'default' : 'pointer',
          }}
        >
          {isVerifying ? '확인 중' : '예약 확인'}
        </button>
      </form>

      <p style={privacyNoteStyle}>
        인증 전에는 예약 상세, 주소, 사진을 표시하지 않습니다.<br />
        링크가 만료되었거나 인증이 되지 않으면 고객센터로 문의해주세요.
      </p>
    </main>
  );
}

function ReservationContent({ order, onReset }) {
  return (
    <main className="scroll" style={{ flex: 1, overflow: 'auto' }}>
      <section style={{ padding: '24px 20px 16px' }}>
        <div style={eyebrowStyle}>{statusHeadline(order.status)}</div>
        <h1 style={contentTitleStyle}>
          {order.customer_name} 님<br />
          <span style={{ color: '#475569', fontWeight: 600 }}>{visitHeadline(order)}</span>
        </h1>

        <div style={{ display: 'flex', gap: 6, marginTop: 14, flexWrap: 'wrap' }}>
          <Badge tone="success" dot>{order.status}</Badge>
          <Badge tone="brand">{order.service_name}</Badge>
        </div>
      </section>

      <section style={{ padding: '0 16px' }}>
        <div style={summaryCardStyle}>
          <SummaryBlock title="방문 일시">
            <div style={{ fontSize: 18, fontWeight: 800, letterSpacing: '-0.02em' }}>{formatKoreanDate(order.scheduled_date)}</div>
            <div style={{ fontSize: 13, color: '#475569', marginTop: 3 }}>{order.requested_time || '시간 협의 중'}</div>
          </SummaryBlock>

          <CustomerRow icon="mapPin" label="방문지">
            {order.customer_address}
          </CustomerRow>
          <CustomerRow icon="package" label="서비스">
            {order.service_name}
            {order.size_or_quantity && <span style={mutedInlineStyle}> · {order.size_or_quantity}</span>}
            {order.service_detail && <div style={mutedLineStyle}>{order.service_detail}</div>}
          </CustomerRow>
          <CustomerRow icon="bell" label="요청사항">
            {order.special_request || '별도 요청사항이 없습니다.'}
          </CustomerRow>
          <CustomerRow icon="creditCard" label="결제 안내" last>
            <PaymentSummary order={order} />
          </CustomerRow>
        </div>
      </section>

      <VisitGuide />
      <CustomerPhotos photos={order.photos || []} />

      <section style={{ padding: '0 16px 24px' }}>
        <button style={secondaryButtonStyle} onClick={onReset}>
          <Icon name="lock" size={13} /> 다시 인증하기
        </button>
      </section>

      <TrustFooter />
    </main>
  );
}

function SummaryBlock({ title, children }) {
  return (
    <div style={{ padding: '16px 18px', borderBottom: '1px solid #f1f5f4' }}>
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
      borderBottom: last ? 'none' : '1px solid #f1f5f4',
    }}>
      <span style={rowIconStyle}>
        <Icon name={icon} size={13} />
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={smallLabelStyle}>{label}</div>
        <div style={{ fontSize: 13.5, color: '#0f172a', lineHeight: 1.5 }}>{children}</div>
      </div>
    </div>
  );
}

function PaymentSummary({ order }) {
  if (order.total_amount == null) {
    return <span style={{ color: '#64748b', fontSize: 12.5 }}>결제 안내는 별도로 안내드립니다.</span>;
  }

  return (
    <>
      <span style={{ fontWeight: 700 }}>{formatWon(order.total_amount)}</span>
      <div style={mutedLineStyle}>
        {order.deposit_amount != null && <>계약금 {formatWon(order.deposit_amount)}</>}
        {order.deposit_amount != null && order.balance_amount != null && ' · '}
        {order.balance_amount != null && <>잔금 {formatWon(order.balance_amount)}</>}
      </div>
      {order.payment_status && <div style={mutedLineStyle}>상태: {paymentStatusLabel(order.payment_status)}</div>}
    </>
  );
}

function VisitGuide() {
  return (
    <section style={{ padding: '16px 16px 8px' }}>
      <div style={guideStyle}>
        <div style={{ ...smallLabelStyle, color: '#b45309', display: 'flex', alignItems: 'center', gap: 5 }}>
          <Icon name="bell" size={11} /> 방문 전 안내
        </div>
        <ul style={{ margin: '8px 0 0', padding: '0 0 0 16px', fontSize: 12.5, color: '#78350f', lineHeight: 1.65 }}>
          <li>작업 공간 주변 물건은 가능한 범위에서 미리 이동해주세요.</li>
          <li>현장 상황에 따라 작업 시간은 조금 달라질 수 있습니다.</li>
          <li>완료 사진은 관리자 검수 후 이 페이지에서 확인할 수 있습니다.</li>
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
    <section style={{ padding: '12px 16px 24px' }}>
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
                      src={photo.file_url}
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
          <div style={{ fontSize: 11.5, color: '#94a3b8', lineHeight: 1.45 }}>
            관리자 검수가 완료되어 고객 공개 승인된 사진만 표시합니다.
          </div>
        </div>
      )}
    </section>
  );
}

function PhotoPending() {
  return (
    <div style={photoPendingStyle}>
      <div style={photoPendingIconStyle}>
        <Icon name="camera" size={18} />
      </div>
      <div style={{ fontSize: 13, color: '#475569', fontWeight: 700, marginBottom: 3 }}>
        작업 완료 후 사진이 표시됩니다
      </div>
      <div style={{ fontSize: 11.5, color: '#94a3b8' }}>
        관리자 검수와 고객 공개 승인이 끝난 사진만 볼 수 있습니다.
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
          { icon: 'star', label: '검수 사진', sub: '승인 후 공개' },
          { icon: 'sparkles', label: '고객센터', sub: '1588-2480' },
        ].map((item) => (
          <div key={item.label} style={{ textAlign: 'center' }}>
            <div style={{ display: 'inline-flex', color: '#475569', marginBottom: 4 }}>
              <Icon name={item.icon} size={14} />
            </div>
            <div style={{ fontSize: 10.5, color: '#94a3b8', fontWeight: 600 }}>{item.label}</div>
            <div style={{ fontSize: 12, fontWeight: 700 }}>{item.sub}</div>
          </div>
        ))}
      </div>

      <a href="tel:15882480" style={callButtonStyle}>
        <Icon name="phone" size={14} /> 1588-2480
      </a>

      <div style={{ textAlign: 'center', fontSize: 10.5, color: '#94a3b8', marginTop: 16, lineHeight: 1.5 }}>
        이 페이지는 예약 고객 전용 링크입니다.<br />
        연락처 뒷자리 인증으로 보호됩니다.
      </div>
    </footer>
  );
}

function readInitialCustomerLink() {
  const pathToken = readTokenFromPath(window.location.pathname);
  const params = new URLSearchParams(window.location.search);
  const queryToken = params.get('t') || params.get('token') || params.get('customer_token');
  const storedToken = sessionStorage.getItem(CUSTOMER_TOKEN_STORAGE_KEY);
  const token = pathToken || queryToken || storedToken || '';

  return {
    token,
    isFromUrl: Boolean(pathToken || queryToken),
  };
}

function readTokenFromPath(pathname) {
  const match = pathname.match(/^\/(?:c|customer)\/([^/?#]+)/);
  if (!match) {
    return '';
  }

  try {
    return decodeURIComponent(match[1]);
  } catch {
    return match[1];
  }
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

function statusHeadline(status) {
  if (['고객전달필요', '고객전달완료', '서비스완료'].includes(status)) {
    return '작업 결과를 확인해주세요';
  }
  if (status === '취소') {
    return '예약이 취소되었습니다';
  }
  return '예약이 확인되었습니다';
}

function visitHeadline(order) {
  if (!order.scheduled_date) {
    return '방문 일정은 확정 후 안내드립니다.';
  }
  return `${formatKoreanDate(order.scheduled_date)} 방문 예정입니다`;
}

function formatKoreanDate(value) {
  if (!value) {
    return '일정 확인 중';
  }
  const date = new Date(`${value}T00:00:00`);
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
  display: 'flex',
  flexDirection: 'column',
  background: '#f7f6f3',
  overflow: 'hidden',
  fontFamily: 'var(--font)',
  color: '#0f172a',
});

const headerStyle = css({
  padding: '18px 20px 14px',
  background: 'linear-gradient(180deg, #ffffff 0%, #f7f6f3 100%)',
  borderBottom: '1px solid rgba(15,23,42,0.06)',
  display: 'flex',
  alignItems: 'center',
  gap: 9,
  flexShrink: 0,
});

const brandMarkStyle = css({
  width: 30,
  height: 30,
  borderRadius: 7,
  background: '#0f172a',
  color: '#fff',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  fontSize: 13,
  fontWeight: 800,
  letterSpacing: '-0.04em',
});

const gateCardStyle = css({
  background: '#fff',
  border: '1px solid rgba(15,23,42,0.06)',
  borderRadius: 16,
  padding: 20,
  boxShadow: '0 1px 3px rgba(15,23,42,0.04), 0 10px 24px rgba(15,23,42,0.05)',
});

const shieldStyle = css({
  width: 42,
  height: 42,
  borderRadius: 12,
  background: '#f1f5f4',
  color: '#0f172a',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  marginBottom: 14,
});

const eyebrowStyle = css({
  fontSize: 11.5,
  color: '#64748b',
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
  color: '#64748b',
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
  color: '#475569',
  fontSize: 12,
  fontWeight: 800,
});

const inputStyle = css({
  width: '100%',
  height: 46,
  border: '1px solid #d4d9e1',
  borderRadius: 10,
  padding: '0 12px',
  fontSize: 16,
  outline: 'none',
  background: '#fff',
  color: '#0f172a',
});

const linkNoticeStyle = css({
  display: 'flex',
  alignItems: 'center',
  gap: 7,
  marginBottom: 12,
  padding: '10px 12px',
  borderRadius: 10,
  background: '#f1f5f4',
  color: '#475569',
  fontSize: 12,
  lineHeight: 1.45,
});

const errorStyle = css({
  padding: '10px 12px',
  borderRadius: 10,
  background: '#fef2f2',
  border: '1px solid #fecaca',
  color: '#b91c1c',
  fontSize: 12.5,
  lineHeight: 1.45,
  marginBottom: 12,
});

const primaryButtonStyle = css({
  width: '100%',
  height: 46,
  borderRadius: 12,
  border: 'none',
  color: '#fff',
  fontSize: 14,
  fontWeight: 800,
});

const privacyNoteStyle = css({
  margin: '16px 0 0',
  padding: '0 12px',
  color: '#64748b',
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
});

const summaryCardStyle = css({
  background: '#fff',
  borderRadius: 14,
  border: '1px solid rgba(15,23,42,0.06)',
  boxShadow: '0 1px 3px rgba(15,23,42,0.04), 0 4px 12px rgba(15,23,42,0.04)',
  overflow: 'hidden',
});

const smallLabelStyle = css({
  fontSize: 10.5,
  color: '#94a3b8',
  fontWeight: 800,
  letterSpacing: '0.06em',
  marginBottom: 4,
});

const rowIconStyle = css({
  width: 28,
  height: 28,
  borderRadius: 7,
  flexShrink: 0,
  background: '#f1f5f4',
  color: '#0f172a',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  marginTop: 2,
});

const mutedInlineStyle = css({
  color: '#64748b',
  fontSize: 12.5,
});

const mutedLineStyle = css({
  color: '#64748b',
  fontSize: 12,
  marginTop: 3,
  lineHeight: 1.45,
});

const guideStyle = css({
  background: '#fffaeb',
  border: '1px solid #fde68a',
  borderRadius: 12,
  padding: '12px 14px',
});

const photoCardStyle = css({
  background: '#fff',
  borderRadius: 12,
  border: '1px solid rgba(15,23,42,0.06)',
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
  border: '1px solid #e4e8ee',
  background: '#f1f5f4',
  display: 'block',
});

const captionStyle = css({
  marginTop: 4,
  fontSize: 10.5,
  color: '#94a3b8',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
});

const photoPendingStyle = css({
  background: '#fff',
  borderRadius: 12,
  border: '1px dashed #d4d9e1',
  padding: '32px 20px',
  textAlign: 'center',
});

const photoPendingIconStyle = css({
  width: 40,
  height: 40,
  borderRadius: 10,
  background: '#f1f5f4',
  color: '#94a3b8',
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  marginBottom: 8,
});

const secondaryButtonStyle = css({
  width: '100%',
  height: 42,
  borderRadius: 10,
  border: '1px solid #d4d9e1',
  background: '#fff',
  color: '#0f172a',
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
  borderTop: '1px solid rgba(15,23,42,0.06)',
  borderBottom: '1px solid rgba(15,23,42,0.06)',
});

const callButtonStyle = css({
  marginTop: 14,
  height: 42,
  borderRadius: 10,
  background: '#0f172a',
  color: '#fff',
  border: 'none',
  fontSize: 13,
  fontWeight: 800,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: 6,
  textDecoration: 'none',
});

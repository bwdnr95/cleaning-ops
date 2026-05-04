import React from 'react';

import { verifyCustomerOrder } from '../../api/customer';
import { ApiError } from '../../api/client';
import { Badge, Icon } from '../../components/common/ui';

const CUSTOMER_TOKEN_STORAGE_KEY = 'cleaning_ops_customer_token';

// Customer reservation page — premium, trustworthy, mobile-first

export function CustomerReservation() {
  const [customerToken, setCustomerToken] = React.useState(readInitialCustomerToken);
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
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: '#f7f6f3', overflow: 'hidden', fontFamily: 'var(--font)' }}>
      <CustomerHeader />

      {!order ? (
        <VerificationGate
          customerToken={customerToken}
          phoneSuffix={phoneSuffix}
          error={error}
          isVerifying={isVerifying}
          onCustomerTokenChange={setCustomerToken}
          onPhoneSuffixChange={setPhoneSuffix}
          onVerify={handleVerify}
        />
      ) : (
        <ReservationContent order={order} />
      )}
    </div>
  );
}

function CustomerHeader() {
  return (
    <div style={{
      padding: '18px 20px 14px',
      background: 'linear-gradient(180deg, #ffffff 0%, #f7f6f3 100%)',
      borderBottom: '1px solid rgba(15,23,42,0.06)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div style={{
          width: 28, height: 28, borderRadius: 7,
          background: '#0f172a', color: '#fff',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 13, fontWeight: 700, letterSpacing: '-0.04em',
        }}>C</div>
        <div>
          <div style={{ fontSize: 13, fontWeight: 700, letterSpacing: '-0.01em' }}>클린오피스 코리아</div>
          <div style={{ fontSize: 10.5, color: '#64748b' }}>cleanops.kr · 1588-2480</div>
        </div>
      </div>
    </div>
  );
}

function VerificationGate({
  customerToken,
  phoneSuffix,
  error,
  isVerifying,
  onCustomerTokenChange,
  onPhoneSuffixChange,
  onVerify,
}) {
  return (
    <div className="scroll" style={{ flex: 1, overflow: 'auto', padding: '28px 20px' }}>
      <form onSubmit={onVerify} style={{
        background: '#fff',
        border: '1px solid rgba(15,23,42,0.06)',
        borderRadius: 16,
        padding: 20,
        boxShadow: '0 1px 3px rgba(15,23,42,0.04), 0 10px 24px rgba(15,23,42,0.05)',
      }}>
        <div style={{
          width: 42,
          height: 42,
          borderRadius: 12,
          background: '#f1f5f4',
          color: '#0f172a',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          marginBottom: 14,
        }}>
          <Icon name="shield" size={20} />
        </div>
        <div style={{ fontSize: 11.5, color: '#64748b', letterSpacing: '0.04em', fontWeight: 700, marginBottom: 6 }}>
          고객 전용 링크
        </div>
        <h1 style={{ margin: 0, fontSize: 22, fontWeight: 750, letterSpacing: '-0.025em', lineHeight: 1.3 }}>
          연락처 뒷자리로<br />
          예약 정보를 확인합니다.
        </h1>
        <p style={{ margin: '10px 0 18px', color: '#64748b', fontSize: 13, lineHeight: 1.55 }}>
          문자로 받은 링크와 예약자 연락처 마지막 4자리가 일치할 때만 예약 상세를 보여드립니다.
        </p>

        <label style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 12 }}>
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

        <label style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 12 }}>
          <span style={labelStyle}>전화번호 뒷 4자리</span>
          <input
            value={phoneSuffix}
            onChange={(event) => onPhoneSuffixChange(event.target.value.replace(/\D/g, '').slice(0, 4))}
            placeholder="1234"
            inputMode="numeric"
            pattern="[0-9]{4}"
            autoComplete="one-time-code"
            style={inputStyle}
            required
          />
        </label>

        {error && (
          <div style={{
            padding: '10px 12px',
            borderRadius: 10,
            background: '#fef2f2',
            border: '1px solid #fecaca',
            color: '#b91c1c',
            fontSize: 12.5,
            lineHeight: 1.45,
            marginBottom: 12,
          }}>
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={isVerifying || phoneSuffix.length !== 4 || !customerToken.trim()}
          style={{
            width: '100%',
            height: 46,
            borderRadius: 12,
            border: 'none',
            background: isVerifying ? '#475569' : '#0f172a',
            color: '#fff',
            fontSize: 14,
            fontWeight: 700,
            cursor: isVerifying ? 'default' : 'pointer',
          }}
        >
          {isVerifying ? '확인 중' : '예약 확인'}
        </button>
      </form>

      <div style={{
        marginTop: 16,
        padding: '12px 14px',
        color: '#64748b',
        fontSize: 11.5,
        lineHeight: 1.5,
        textAlign: 'center',
      }}>
        본 페이지는 예약 고객 전용입니다.<br />
        링크가 만료되었거나 인증이 되지 않으면 고객센터로 문의해주세요.
      </div>
    </div>
  );
}

function ReservationContent({ order }) {
  return (
    <div className="scroll" style={{ flex: 1, overflow: 'auto' }}>
      <div style={{ padding: '24px 20px 16px' }}>
        <div style={{ fontSize: 11.5, color: '#64748b', letterSpacing: '0.04em', fontWeight: 600, marginBottom: 6 }}>
          {statusHeadline(order.status)}
        </div>
        <h1 style={{ margin: 0, fontSize: 22, fontWeight: 700, letterSpacing: '-0.025em', lineHeight: 1.3 }}>
          {order.customer_name} 님,<br/>
          <span style={{ color: '#475569', fontWeight: 500 }}>{visitHeadline(order)}</span>
        </h1>

        <div style={{ display: 'flex', gap: 6, marginTop: 14, flexWrap: 'wrap' }}>
          <Badge tone="success" dot>{order.status}</Badge>
          <Badge tone="brand">{order.service_name}</Badge>
        </div>
      </div>

      <div style={{ padding: '0 16px' }}>
        <div style={{
          background: '#fff', borderRadius: 14,
          border: '1px solid rgba(15,23,42,0.06)',
          boxShadow: '0 1px 3px rgba(15,23,42,0.04), 0 4px 12px rgba(15,23,42,0.04)',
          overflow: 'hidden',
        }}>
          <div style={{ padding: '16px 18px', borderBottom: '1px solid #f1f5f4' }}>
            <div style={{ fontSize: 10.5, color: '#94a3b8', fontWeight: 600, letterSpacing: '0.06em', marginBottom: 4 }}>방문 일시</div>
            <div style={{ fontSize: 18, fontWeight: 700, letterSpacing: '-0.02em' }}>{formatKoreanDate(order.scheduled_date)}</div>
            <div style={{ fontSize: 13, color: '#475569', marginTop: 2 }}>{order.requested_time || '시간 협의 중'}</div>
          </div>

          <CustRow icon="mapPin" label="방문지">
            {order.customer_address}
          </CustRow>
          <CustRow icon="package" label="서비스">
            {order.service_name}<br/>
            <span style={{ color: '#64748b', fontSize: 12 }}>{order.size_or_quantity || order.service_detail || '상세 내용 확인 중'}</span>
          </CustRow>
          <CustRow icon="bell" label="요청사항">
            {order.special_request || '별도 요청 사항이 없습니다.'}
          </CustRow>
          <CustRow icon="creditCard" label="결제" last>
            {order.total_amount == null ? (
              <span style={{ color: '#64748b', fontSize: 12 }}>결제 정보는 별도 안내드립니다.</span>
            ) : (
              <>
                <span style={{ fontWeight: 600 }}>{formatWon(order.total_amount)}</span>
                {order.deposit_amount != null && <span style={{ color: '#64748b', fontSize: 12 }}> · 계약금 {formatWon(order.deposit_amount)}</span>}<br/>
                {order.balance_amount != null && <span style={{ color: '#94a3b8', fontSize: 11.5 }}>잔금 {formatWon(order.balance_amount)}</span>}
              </>
            )}
          </CustRow>
        </div>
      </div>

      <div style={{ padding: '16px 16px 8px' }}>
        <div style={{
          background: '#fffaeb', border: '1px solid #fde68a',
          borderRadius: 12, padding: '12px 14px',
        }}>
          <div style={{ fontSize: 11, color: '#b45309', fontWeight: 700, letterSpacing: '0.04em', marginBottom: 6, display: 'flex', alignItems: 'center', gap: 4 }}>
            <Icon name="bell" size={11}/> 방문 전 안내
          </div>
          <ul style={{ margin: 0, padding: '0 0 0 16px', fontSize: 12.5, color: '#78350f', lineHeight: 1.6 }}>
            <li>작업 공간 주변 물건은 사전에 이동 부탁드립니다</li>
            <li>작업 중 현장 상황에 따라 소음이 발생할 수 있습니다</li>
            <li>완료 사진은 관리자 검수 후 이 페이지에서 확인할 수 있습니다</li>
          </ul>
        </div>
      </div>

      <CustomerPhotos photos={order.photos || []} />

      <TrustFooter />
    </div>
  );
}

function CustomerPhotos({ photos }) {
  const hasPhotos = photos.length > 0;
  const groups = [
    { key: 'before', title: '비포' },
    { key: 'after', title: '애프터' },
    { key: 'etc', title: '기타' },
  ].map((group) => ({
    ...group,
    photos: photos.filter((photo) => photo.photo_type === group.key),
  })).filter((group) => group.photos.length > 0);

  return (
    <div style={{ padding: '12px 16px 24px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
        <span style={{ fontSize: 13, fontWeight: 700 }}>작업 완료 사진</span>
        <Badge tone={hasPhotos ? 'success' : 'neutral'}>{hasPhotos ? `${photos.length}장 공개` : '대기중'}</Badge>
      </div>

      {!hasPhotos ? (
        <PhotoPending />
      ) : (
        <div style={{
          background: '#fff',
          borderRadius: 12,
          border: '1px solid rgba(15,23,42,0.06)',
          padding: 12,
          display: 'flex',
          flexDirection: 'column',
          gap: 14,
        }}>
          {groups.map((group) => (
            <div key={group.key}>
              <div style={{ fontSize: 11, color: '#64748b', fontWeight: 700, letterSpacing: '0.04em', marginBottom: 8 }}>
                {group.title}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 8 }}>
                {group.photos.map((photo) => (
                  <figure key={photo.id} style={{ margin: 0 }}>
                    <img
                      src={photo.file_url}
                      alt={photo.file_name || `${group.title} 사진`}
                      loading="lazy"
                      style={{
                        width: '100%',
                        aspectRatio: '1',
                        objectFit: 'cover',
                        borderRadius: 10,
                        border: '1px solid #e4e8ee',
                        background: '#f1f5f4',
                        display: 'block',
                      }}
                    />
                    {photo.file_name && (
                      <figcaption style={{
                        marginTop: 4,
                        fontSize: 10.5,
                        color: '#94a3b8',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}>
                        {photo.file_name}
                      </figcaption>
                    )}
                  </figure>
                ))}
              </div>
            </div>
          ))}
          <div style={{ fontSize: 11.5, color: '#94a3b8', lineHeight: 1.45 }}>
            관리자 검수가 완료되어 고객 공개 승인된 사진만 표시됩니다.
          </div>
        </div>
      )}
    </div>
  );
}

function PhotoPending() {
  return (
    <div style={{
      background: '#fff', borderRadius: 12,
      border: '1px dashed #d4d9e1',
      padding: '32px 20px', textAlign: 'center',
    }}>
      <div style={{
        width: 40, height: 40, borderRadius: 10,
        background: '#f1f5f4', color: '#94a3b8',
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        marginBottom: 8,
      }}>
        <Icon name="camera" size={18}/>
      </div>
      <div style={{ fontSize: 13, color: '#475569', fontWeight: 500, marginBottom: 2 }}>
        작업 완료 후 비포 / 애프터 사진이 이곳에 표시됩니다
      </div>
      <div style={{ fontSize: 11.5, color: '#94a3b8' }}>
        담당자가 검수한 사진만 공개됩니다
      </div>
    </div>
  );
}

function TrustFooter() {
  return (
    <div style={{ padding: '0 16px 24px' }}>
      <div style={{
        display: 'grid', gridTemplateColumns: '1fr 1fr 1fr',
        gap: 8, padding: '14px 4px',
        borderTop: '1px solid rgba(15,23,42,0.06)',
        borderBottom: '1px solid rgba(15,23,42,0.06)',
      }}>
        {[
          { icon: 'shield', label: '책임보험', sub: '5억원' },
          { icon: 'star', label: '평균 평점', sub: '4.86 / 5' },
          { icon: 'sparkles', label: '재시공', sub: '7일 무상' },
        ].map((t, i) => (
          <div key={i} style={{ textAlign: 'center' }}>
            <div style={{ display: 'inline-flex', color: '#475569', marginBottom: 4 }}>
              <Icon name={t.icon} size={14}/>
            </div>
            <div style={{ fontSize: 10.5, color: '#94a3b8', fontWeight: 500 }}>{t.label}</div>
            <div style={{ fontSize: 12, fontWeight: 600 }}>{t.sub}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', gap: 6, marginTop: 14 }}>
        <button style={{
          flex: 1, height: 42, borderRadius: 10,
          background: '#0f172a', color: '#fff', border: 'none',
          fontSize: 13, fontWeight: 600,
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
        }}>
          <Icon name="phone" size={14}/> 1588-2480
        </button>
        <button style={{
          flex: 1, height: 42, borderRadius: 10,
          background: '#fff', color: '#0f172a',
          border: '1px solid #d4d9e1',
          fontSize: 13, fontWeight: 600,
        }}>
          일정 변경 문의
        </button>
      </div>

      <div style={{ textAlign: 'center', fontSize: 10.5, color: '#94a3b8', marginTop: 16, lineHeight: 1.5 }}>
        본 페이지는 예약 고객 전용 링크입니다.<br/>
        연락처 뒷자리 4자리 인증으로 보호됩니다.
      </div>
    </div>
  );
}

function CustRow({ icon, label, children, last = false }) {
  return (
    <div style={{
      display: 'flex', gap: 12, padding: '12px 18px',
      borderBottom: last ? 'none' : '1px solid #f1f5f4',
    }}>
      <span style={{
        width: 28, height: 28, borderRadius: 7, flexShrink: 0,
        background: '#f1f5f4', color: '#0f172a',
        display: 'flex', alignItems: 'center', justifyContent: 'center', marginTop: 2,
      }}>
        <Icon name={icon} size={13}/>
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 10.5, color: '#94a3b8', fontWeight: 600, letterSpacing: '0.04em', marginBottom: 3 }}>{label}</div>
        <div style={{ fontSize: 13.5, color: '#0f172a', lineHeight: 1.5 }}>{children}</div>
      </div>
    </div>
  );
}

function readInitialCustomerToken() {
  const params = new URLSearchParams(window.location.search);
  return params.get('t')
    || params.get('token')
    || params.get('customer_token')
    || sessionStorage.getItem(CUSTOMER_TOKEN_STORAGE_KEY)
    || '';
}

function toCustomerErrorMessage(error) {
  if (error instanceof ApiError) {
    if (error.status === 404) {
      return '링크 또는 전화번호 뒷자리가 일치하지 않습니다.';
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
    return '방문 일정은 확정 후 안내드리겠습니다.';
  }
  return `${formatKoreanDate(order.scheduled_date)} 방문 예정입니다.`;
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

const labelStyle = {
  color: '#475569',
  fontSize: 12,
  fontWeight: 700,
};

const inputStyle = {
  width: '100%',
  height: 44,
  border: '1px solid #d4d9e1',
  borderRadius: 10,
  padding: '0 12px',
  fontSize: 16,
  outline: 'none',
  background: '#fff',
};

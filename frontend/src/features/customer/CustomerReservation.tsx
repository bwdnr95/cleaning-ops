import React from 'react';

import { submitCustomerAsRequest, verifyCustomerOrder } from '../../api/customer';
import { ApiError, toApiAssetUrl } from '../../api/client';
import { BrandLogo } from '../../components/common/BrandLogo';
import { PhotoLightbox } from '../../components/common/PhotoLightbox';
import { Badge, Icon } from '../../components/common/ui';
import { paymentStatusLabel } from '../../domain/paymentStatus';
import { formatQuantity } from '../../domain/format';
import { formatPhone } from '../../domain/phone';
import { parseDateValue } from '../../domain/time';

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
        <ReservationContent
          order={order}
          customerToken={customerToken}
          phoneSuffix={phoneSuffix}
          onOrderUpdate={setOrder}
          onReset={() => setOrder(null)}
        />
      )}
    </div>
  );
}

function CustomerHeader() {
  return (
    <header style={headerStyle}>
      <BrandLogo size="md" />
      <div style={{ marginLeft: 'auto', fontSize: 10.5, color: '#94a3b8', fontWeight: 600, letterSpacing: '0.04em' }}>
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
    <main className="scroll" style={{ flex: 1, overflow: 'auto', padding: '28px 20px' }}>
      <form data-testid="customer-verify-form" onSubmit={onVerify} style={gateCardStyle}>
        <div style={shieldStyle}>
          <Icon name="shield" size={20} />
        </div>
        <div style={eyebrowStyle}>고객 전용 보안 확인</div>
        <h1 style={gateTitleStyle}>
          연락처 뒷자리로<br />
          예약 정보를 확인합니다
        </h1>
        <p style={gateCopyStyle}>
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
          <div style={linkNoticeStyle}>
            <Icon name="lock" size={13} />
            문자 링크가 확인되었습니다. 연락처 뒷자리만 입력해주세요.
          </div>
        )}

        <label style={fieldStyle}>
          <span style={labelStyle}>전화번호 뒤 4자리</span>
          <input
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

        {error && <div data-testid="customer-verify-error" style={errorStyle}>{error}</div>}

        <button
          type="submit"
          data-testid="customer-verify-submit"
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

function ReservationContent({ order, customerToken, phoneSuffix, onOrderUpdate, onReset }) {
  const lines = order.lines || [];
  const primaryLine = lines[0] || null;

  return (
    <main data-testid="customer-order-page" className="scroll" style={{ flex: 1, overflow: 'auto' }}>
      <section style={{ padding: '24px 20px 16px' }}>
        <div style={eyebrowStyle}>{statusHeadline(primaryLine?.status)}</div>
        <h1 style={contentTitleStyle}>
          {order.customer_name} 님<br />
          <span style={{ color: '#475569', fontWeight: 600 }}>{visitHeadline(primaryLine)}</span>
        </h1>

        <div style={{ display: 'flex', gap: 6, marginTop: 14, flexWrap: 'wrap' }}>
          {primaryLine && <Badge tone={customerStatusTone(primaryLine.status)} dot>{customerStatusLabel(primaryLine.status)}</Badge>}
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
              customerToken={customerToken}
              phoneSuffix={phoneSuffix}
              onOrderUpdate={onOrderUpdate}
            />
          ))
        )}
      </section>

      <section style={{ padding: '0 16px 24px' }}>
        <button style={secondaryButtonStyle} onClick={onReset}>
          <Icon name="lock" size={13} /> 다시 인증하기
        </button>
      </section>

      <TrustFooter />
    </main>
  );
}

function ReservationLineCard({ line, customerVisiblePayment, customerToken, phoneSuffix, onOrderUpdate }) {
  const quantity = formatQuantity(line.size_or_quantity);

  return (
    <section data-testid={`customer-line-${line.id}`} style={summaryCardStyle}>
      <SummaryBlock title="방문 일시">
        <div style={{ fontSize: 18, fontWeight: 800, letterSpacing: '-0.02em' }}>{formatKoreanDate(line.scheduled_date)}</div>
        <div style={{ fontSize: 13, color: '#475569', marginTop: 3 }}>{line.requested_time || '시간 협의 중'}</div>
      </SummaryBlock>
      <CustomerRow icon="package" label="서비스">
        {line.service_name}
        {quantity && <span style={mutedInlineStyle}> · {quantity}</span>}
        {line.service_detail && <div style={mutedLineStyle}>{line.service_detail}</div>}
      </CustomerRow>
      <CustomerRow icon="bell" label="진행상황">
        <Badge tone={customerStatusTone(line.status)} dot>{customerStatusLabel(line.status)}</Badge>
        {line.special_request && <div style={mutedLineStyle}>{line.special_request}</div>}
      </CustomerRow>
      {customerVisiblePayment && (
        <CustomerRow icon="creditCard" label="결제 안내">
          <PaymentSummary line={line} />
        </CustomerRow>
      )}
      <CustomerPhotos photos={line.photos || []} />
      {canCustomerRequestAs(line.status) && (
        <CustomerAsRequestForm
          line={line}
          customerToken={customerToken}
          phoneSuffix={phoneSuffix}
          onOrderUpdate={onOrderUpdate}
        />
      )}
    </section>
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

function PaymentSummary({ line }) {
  if (line.total_amount == null) {
    return <span style={{ color: '#64748b', fontSize: 12.5 }}>결제 안내는 별도로 안내드립니다.</span>;
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
        <div style={{ ...smallLabelStyle, color: '#b45309', display: 'flex', alignItems: 'center', gap: 5 }}>
          <Icon name="bell" size={11} /> 방문 전 안내
        </div>
        <ul style={guideListStyle}>
          <li>작업 공간 주변 물건은 가능한 범위에서 미리 이동해주세요.</li>
          <li>현장 상황에 따라 작업 시간은 조금 달라질 수 있습니다.</li>
          <li>완료 사진은 이 페이지에 표시됩니다.</li>
        </ul>
      </div>
    </section>
  );
}

function CustomerPhotos({ photos }) {
  const [openPhotoId, setOpenPhotoId] = React.useState<string | null>(null);
  const groups = [
    { key: 'before', title: '비포' },
    { key: 'after', title: '애프터' },
    { key: 'etc', title: '기타' },
  ].map((group) => ({
    ...group,
    photos: photos.filter((photo) => photo.photo_type === group.key),
  })).filter((group) => group.photos.length > 0);
  const lightboxPhotos = React.useMemo(
    () => photos.map((photo) => ({
      id: photo.id,
      src: toApiAssetUrl(photo.file_url),
      alt: photo.file_name || `${customerPhotoTypeLabel(photo.photo_type)} 사진`,
      caption: photo.file_name || customerPhotoTypeLabel(photo.photo_type),
    })),
    [photos],
  );

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
                    <button
                      type="button"
                      data-testid={`customer-photo-${photo.id}`}
                      aria-label={`${group.title} 사진 크게 보기`}
                      onClick={() => setOpenPhotoId(photo.id)}
                      style={{ display: 'block', width: '100%', padding: 0, border: 'none', background: 'transparent', cursor: 'zoom-in' }}
                    >
                      <img
                        src={toApiAssetUrl(photo.file_url)}
                        alt={photo.file_name || `${group.title} 사진`}
                        loading="lazy"
                        style={photoImageStyle}
                      />
                    </button>
                    {photo.file_name && <figcaption style={captionStyle}>{photo.file_name}</figcaption>}
                  </figure>
                ))}
              </div>
            </div>
          ))}
          <div style={{ fontSize: 11.5, color: '#94a3b8', lineHeight: 1.45 }}>
            협력사가 업로드해 공개된 사진만 표시됩니다.
          </div>
        </div>
      )}
      <PhotoLightbox
        photos={lightboxPhotos}
        openPhotoId={openPhotoId}
        onOpenPhoto={setOpenPhotoId}
        onClose={() => setOpenPhotoId(null)}
      />
    </section>
  );
}

function customerPhotoTypeLabel(photoType) {
  if (photoType === 'before') {
    return '비포';
  }
  if (photoType === 'after') {
    return '애프터';
  }
  return '기타';
}

function CustomerAsRequestForm({ line, customerToken, phoneSuffix, onOrderUpdate }) {
  const [memo, setMemo] = React.useState('');
  const [files, setFiles] = React.useState<File[]>([]);
  const [error, setError] = React.useState(null);
  const [notice, setNotice] = React.useState(null);
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const cameraInputRef = React.useRef<HTMLInputElement | null>(null);
  const albumInputRef = React.useRef<HTMLInputElement | null>(null);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(event.target.files || []);
    setFiles((currentFiles) => mergeCustomerAsFiles(currentFiles, selectedFiles));
    event.target.value = '';
  };

  const handleFileRemove = (fileKey) => {
    setFiles((currentFiles) => currentFiles.filter((file) => customerAsFileKey(file) !== fileKey));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    const trimmedMemo = memo.trim();
    if (!trimmedMemo) {
      setError('AS 요청 내용을 입력해주세요.');
      return;
    }

    setError(null);
    setNotice(null);
    setIsSubmitting(true);
    try {
      const updatedOrder = await submitCustomerAsRequest(customerToken, {
        orderId: line.id,
        phoneSuffix,
        memo: trimmedMemo,
        files,
      });
      onOrderUpdate(updatedOrder);
      setMemo('');
      setFiles([]);
      setNotice('AS 요청이 접수되었습니다. 운영팀 확인 후 안내드리겠습니다.');
    } catch (requestError) {
      setError(toCustomerAsErrorMessage(requestError));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <section data-testid={`customer-as-request-${line.id}`} style={asRequestSectionStyle}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
        <Icon name="bell" size={13} />
        <span style={{ fontSize: 13, fontWeight: 800 }}>AS 접수</span>
        {line.status === '고객확인필요' && <Badge tone="warn">확인 중</Badge>}
      </div>
      <div style={asNoticeStyle}>
        인테리어 추가 시공 및 입주 이후 사항은 AS 대상에 해당되지 않습니다.
      </div>
      <form onSubmit={handleSubmit} style={{ display: 'grid', gap: 8 }}>
        <textarea
          data-testid={`customer-as-memo-${line.id}`}
          value={memo}
          maxLength={1000}
          rows={4}
          placeholder="AS가 필요한 부분을 적어주세요."
          onChange={(event) => setMemo(event.target.value)}
          style={asTextareaStyle}
          disabled={isSubmitting}
          required
        />
        <div style={asFileActionsStyle}>
          <button
            type="button"
            style={asFileButtonStyle}
            disabled={isSubmitting}
            onClick={() => cameraInputRef.current?.click()}
          >
            <Icon name="camera" size={13} />
            촬영
          </button>
          <button
            type="button"
            style={asFileButtonStyle}
            disabled={isSubmitting}
            onClick={() => albumInputRef.current?.click()}
          >
            <Icon name="image" size={13} />
            앨범 선택
          </button>
          <input
            ref={cameraInputRef}
            data-testid={`customer-as-camera-files-${line.id}`}
            type="file"
            accept="image/*"
            capture="environment"
            onChange={handleFileChange}
            style={{ display: 'none' }}
            disabled={isSubmitting}
          />
          <input
            ref={albumInputRef}
            data-testid={`customer-as-files-${line.id}`}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            multiple
            onChange={handleFileChange}
            style={{ display: 'none' }}
            disabled={isSubmitting}
          />
        </div>
        {files.length > 0 && (
          <CustomerAsSelectedPhotos
            files={files}
            disabled={isSubmitting}
            onRemove={handleFileRemove}
          />
        )}
        {error && <div data-testid={`customer-as-error-${line.id}`} style={errorStyle}>{error}</div>}
        {notice && <div data-testid={`customer-as-notice-${line.id}`} style={asSuccessStyle}>{notice}</div>}
        <button
          type="submit"
          data-testid={`customer-as-submit-${line.id}`}
          disabled={isSubmitting || !memo.trim()}
          style={{
            ...primaryButtonStyle,
            height: 44,
            background: isSubmitting || !memo.trim() ? 'var(--text-quaternary)' : 'var(--text)',
            cursor: isSubmitting ? 'default' : 'pointer',
          }}
        >
          {isSubmitting ? '접수 중' : 'AS 접수하기'}
        </button>
      </form>
    </section>
  );
}

function CustomerAsSelectedPhotos({ files, disabled, onRemove }) {
  const previews = React.useMemo(
    () => {
      const canCreateObjectUrl = typeof URL !== 'undefined' && typeof URL.createObjectURL === 'function';
      return files.map((file) => ({
        key: customerAsFileKey(file),
        name: file.name || '촬영 사진',
        url: canCreateObjectUrl ? URL.createObjectURL(file) : '',
      }));
    },
    [files],
  );

  React.useEffect(() => () => {
    if (typeof URL !== 'undefined' && typeof URL.revokeObjectURL === 'function') {
      previews.forEach((preview) => {
        if (preview.url) {
          URL.revokeObjectURL(preview.url);
        }
      });
    }
  }, [previews]);

  return (
    <div style={asPreviewWrapStyle}>
      <div style={asFileSummaryStyle}>{files.length}장 선택됨</div>
      <div style={asPreviewGridStyle}>
        {previews.map((preview, index) => (
          <figure key={preview.key} style={asPreviewItemStyle}>
            {preview.url ? (
              <img src={preview.url} alt={preview.name} style={asPreviewImageStyle} />
            ) : (
              <div style={asPreviewPlaceholderStyle}>이미지</div>
            )}
            <figcaption style={asPreviewCaptionStyle}>{preview.name}</figcaption>
            <button
              type="button"
              data-testid={`customer-as-remove-file-${index}`}
              aria-label={`${preview.name} 삭제`}
              disabled={disabled}
              onClick={() => onRemove(preview.key)}
              style={asPreviewRemoveButtonStyle(disabled)}
            >
              <Icon name="x" size={13} />
            </button>
          </figure>
        ))}
      </div>
    </div>
  );
}

function mergeCustomerAsFiles(currentFiles: File[], selectedFiles: File[]): File[] {
  const nextFiles = [...currentFiles];
  const seen = new Set(currentFiles.map(customerAsFileKey));
  for (const file of selectedFiles) {
    const key = customerAsFileKey(file);
    if (!seen.has(key)) {
      seen.add(key);
      nextFiles.push(file);
    }
  }
  return nextFiles;
}

function customerAsFileKey(file: File): string {
  return `${file.name}:${file.size}:${file.lastModified}`;
}

function PhotoPending() {
  return (
    <div data-testid="customer-photo-pending" style={photoPendingStyle}>
      <div style={photoPendingIconStyle}>
        <Icon name="camera" size={18} />
      </div>
      <div style={{ fontSize: 13, color: '#475569', fontWeight: 700, marginBottom: 3 }}>
        협력사가 사진을 올리면 이곳에 표시됩니다
      </div>
      <div style={{ fontSize: 11.5, color: '#94a3b8' }}>
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
            <div style={{ display: 'inline-flex', color: '#475569', marginBottom: 4 }}>
              <Icon name={item.icon} size={14} />
            </div>
            <div style={{ fontSize: 10.5, color: '#94a3b8', fontWeight: 600 }}>{item.label}</div>
            <div style={{ fontSize: 12, fontWeight: 700 }}>{item.sub}</div>
          </div>
        ))}
      </div>

      <a href="tel:16889512" style={callButtonStyle}>
        <Icon name="phone" size={14} /> 1688-9512
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

function toCustomerAsErrorMessage(error) {
  if (error instanceof ApiError) {
    if (error.status === 413 && error.detail === 'too_many_as_photos') {
      return 'AS 사진은 한 번에 최대 10장까지 첨부할 수 있습니다.';
    }
    if (error.status === 413 && error.detail === 'as_photos_total_too_large') {
      return '첨부 사진의 전체 용량이 너무 큽니다.';
    }
    if (error.status === 413) {
      return '첨부 사진 용량이 너무 큽니다.';
    }
    if (error.status === 400 && error.detail === 'unsupported_photo_type') {
      return 'JPG/PNG/WebP 사진만 첨부할 수 있습니다.';
    }
    if (error.status === 409 && error.detail === 'as_request_already_pending') {
      return '이미 접수된 AS 요청을 운영팀에서 확인 중입니다.';
    }
    if (error.status === 409 && error.detail === 'as_request_already_accepted') {
      return '이미 AS 접수가 완료되어 담당자가 확인 중입니다.';
    }
    if (error.status === 409) {
      return '현재 상태에서는 AS 접수를 할 수 없습니다.';
    }
    if (error.status === 404) {
      return '예약 정보를 다시 확인해주세요.';
    }
  }
  return 'AS 요청을 접수하지 못했습니다. 잠시 후 다시 시도해주세요.';
}

function statusHeadline(status) {
  if (status === '고객확인필요') {
    return 'AS 요청을 확인 중입니다';
  }
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

function customerStatusLabel(status) {
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
  if (status === '고객확인필요') {
    return 'AS 확인 중';
  }
  if (['일정확정', '전날안내필요', '전날안내완료', '작업예정'].includes(status)) {
    return '방문 예정';
  }
  return '예약 확인 중';
}

function customerStatusTone(status) {
  if (status === '취소') {
    return 'danger';
  }
  if (['고객전달필요', '고객전달완료', '서비스완료'].includes(status)) {
    return 'success';
  }
  if (status === '작업진행') {
    return 'info';
  }
  if (status === '고객확인필요') {
    return 'warn';
  }
  return 'neutral';
}

function canCustomerRequestAs(status) {
  return ['고객전달필요', '고객전달완료', '서비스완료'].includes(status);
}

function visitHeadline(order) {
  if (!order || !order.scheduled_date) {
    return '방문 일정은 확정 후 안내드립니다.';
  }
  return `${formatKoreanDate(order.scheduled_date)} 방문 예정입니다`;
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
  wordBreak: 'keep-all',
  overflowWrap: 'break-word',
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
  whiteSpace: 'pre-wrap',
  wordBreak: 'keep-all',
  overflowWrap: 'break-word',
});

const guideStyle = css({
  background: '#fffaeb',
  border: '1px solid #fde68a',
  borderRadius: 12,
  padding: '12px 14px',
});

const guideListStyle = css({
  margin: '8px 0 0',
  padding: '0 0 0 16px',
  fontSize: 12.5,
  color: '#78350f',
  lineHeight: 1.65,
  wordBreak: 'keep-all',
  overflowWrap: 'break-word',
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

const asRequestSectionStyle = css({
  margin: '0 16px 16px',
  padding: 12,
  borderRadius: 12,
  border: '1px solid var(--border)',
  background: 'var(--surface)',
});

const asNoticeStyle = css({
  padding: '9px 10px',
  borderRadius: 10,
  background: 'var(--warn-bg)',
  border: '1px solid var(--warn-border)',
  color: 'var(--warn-fg)',
  fontSize: 12,
  lineHeight: 1.5,
  fontWeight: 700,
  marginBottom: 10,
});

const asTextareaStyle = css({
  width: '100%',
  minHeight: 96,
  border: '1px solid var(--border-strong)',
  borderRadius: 10,
  padding: 10,
  fontSize: 13,
  lineHeight: 1.5,
  fontFamily: 'inherit',
  resize: 'vertical',
  color: 'var(--text)',
  background: 'var(--surface)',
});

const asFileActionsStyle = css({
  display: 'grid',
  gridTemplateColumns: '1fr 1fr',
  gap: 8,
});

const asFileButtonStyle = css({
  width: '100%',
  minHeight: 44,
  borderRadius: 10,
  border: '1px dashed var(--border-strong)',
  background: 'var(--surface)',
  color: 'var(--text-secondary)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: 6,
  fontSize: 12.5,
  fontWeight: 800,
  cursor: 'pointer',
});

const asFileSummaryStyle = css({
  color: 'var(--text-tertiary)',
  fontSize: 11.5,
  fontWeight: 700,
});

const asPreviewWrapStyle = css({
  display: 'grid',
  gap: 8,
});

const asPreviewGridStyle = css({
  display: 'grid',
  gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
  gap: 8,
});

const asPreviewItemStyle = css({
  margin: 0,
  position: 'relative',
  minWidth: 0,
});

const asPreviewImageStyle = css({
  width: '100%',
  aspectRatio: '1',
  objectFit: 'cover',
  display: 'block',
  borderRadius: 8,
  border: '1px solid var(--border)',
  background: 'var(--bg-subtle)',
});

const asPreviewPlaceholderStyle = css({
  ...asPreviewImageStyle,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  color: 'var(--text-tertiary)',
  fontSize: 11,
  fontWeight: 800,
});

const asPreviewCaptionStyle = css({
  marginTop: 4,
  fontSize: 10.5,
  lineHeight: 1.25,
  color: 'var(--text-tertiary)',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
});

function asPreviewRemoveButtonStyle(disabled): React.CSSProperties {
  return {
    position: 'absolute',
    top: -6,
    right: -6,
    width: 24,
    height: 24,
    borderRadius: 999,
    border: '1px solid rgba(15,23,42,0.12)',
    background: '#fff',
    color: 'var(--danger-fg)',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    boxShadow: '0 2px 8px rgba(15,23,42,0.16)',
    cursor: disabled ? 'default' : 'pointer',
  };
}

const asSuccessStyle = css({
  padding: '10px 12px',
  borderRadius: 10,
  background: 'var(--success-bg)',
  border: '1px solid var(--success-border)',
  color: 'var(--success-fg)',
  fontSize: 12.5,
  lineHeight: 1.45,
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

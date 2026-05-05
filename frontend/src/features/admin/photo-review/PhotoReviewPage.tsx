import React from 'react';

import { sendCustomerPhotoReady } from '../../../api/messages';
import { approvePhoto, listPhotoReviewQueue } from '../../../api/photos';
import { useApiResource } from '../../../api/useApiResource';
import { Badge, Icon } from '../../../components/common/ui';

export function PhotoReviewPage() {
  const queue = useApiResource(listPhotoReviewQueue);
  const [selectedIdx, setSelectedIdx] = React.useState(0);
  const [activePhotoId, setActivePhotoId] = React.useState(null);
  const [isApproving, setIsApproving] = React.useState(false);
  const [isSending, setIsSending] = React.useState(false);
  const [sentMessage, setSentMessage] = React.useState(null);
  const [error, setError] = React.useState(null);

  const items = queue.data || [];
  const selected = items[selectedIdx] || items[0] || null;
  const photos = selected?.photos || [];
  const pendingPhotos = photos.filter((photo) => !photo.is_customer_visible);
  const activePhoto = photos.find((photo) => photo.id === activePhotoId) || photos[0] || null;

  React.useEffect(() => {
    setSelectedIdx(0);
    setActivePhotoId(null);
  }, [queue.data]);

  const handleApprove = async (photoId) => {
    setError(null);
    setIsApproving(true);
    try {
      await approvePhoto(photoId);
      queue.reload();
    } catch {
      setError('사진 승인 처리에 실패했습니다.');
    } finally {
      setIsApproving(false);
    }
  };

  const handleApproveAll = async () => {
    setError(null);
    setIsApproving(true);
    try {
      for (const photo of pendingPhotos) {
        await approvePhoto(photo.id);
      }
      queue.reload();
    } catch {
      setError('일괄 승인 처리에 실패했습니다.');
    } finally {
      setIsApproving(false);
    }
  };

  const handleSendCustomerLink = async () => {
    setError(null);
    setSentMessage(null);
    setIsSending(true);
    try {
      const log = await sendCustomerPhotoReady(selected.order_id);
      setSentMessage(log.status === 'sent' ? '고객 링크를 발송했습니다.' : '발송 실패 기록이 남았습니다.');
      queue.reload();
    } catch {
      setError('고객 링크 발송에 실패했습니다.');
    } finally {
      setIsSending(false);
    }
  };

  if (queue.isLoading) {
    return <ReviewState text="검수 대기 사진을 불러오는 중입니다." />;
  }

  if (queue.error) {
    return <ReviewState text="검수 대기 사진을 불러오지 못했습니다." tone="danger" />;
  }

  if (!selected) {
    return <ReviewState text="검수 대기 사진이 없습니다." />;
  }

  return (
    <div data-testid="admin-photo-review-page" style={{ flex: 1, display: 'grid', gridTemplateColumns: '260px 1fr 300px', minHeight: 0, background: 'var(--bg)' }}>
      <aside style={{ background: 'var(--surface)', borderRight: '1px solid var(--border)', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--divider)', display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 12.5, fontWeight: 600 }}>검수 / 전달</span>
          <Badge tone="warn">{items.length}</Badge>
          <div style={{ flex: 1 }}/>
          <button className="btn btn--ghost btn--sm" style={{ padding: '0 4px' }} onClick={queue.reload}>
            <Icon name="refresh" size={12}/>
          </button>
        </div>
        <div className="scroll" style={{ flex: 1, overflow: 'auto' }}>
          {items.map((item, index) => {
            const isActive = index === selectedIdx;
            return (
              <button key={item.order_id} onClick={() => { setSelectedIdx(index); setActivePhotoId(null); }}
                style={{
                  display: 'block', width: '100%', textAlign: 'left',
                  padding: '10px 14px',
                  border: 'none',
                  borderBottom: '1px solid var(--divider)',
                  borderLeft: isActive ? '2px solid var(--brand)' : '2px solid transparent',
                  background: isActive ? 'var(--brand-bg)' : 'transparent',
                  cursor: 'pointer',
                }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
                  <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-tertiary)' }}>{item.order_id}</span>
                  <Badge tone={item.pending_photo_count > 0 ? 'warn' : 'success'}>
                    {item.pending_photo_count > 0 ? `${item.pending_photo_count} 검수` : '전달 대기'}
                  </Badge>
                </div>
                <div style={{ fontSize: 12, fontWeight: 500, marginBottom: 2 }}>{formatServiceName(item)}</div>
                <div style={{ fontSize: 11, color: 'var(--text-tertiary)', display: 'flex', justifyContent: 'space-between' }}>
                  <span>{item.customer_name} · {item.team_name || '미배정'}</span>
                  <span className="mono">승인 {item.approved_photo_count} / 대기 {item.pending_photo_count}</span>
                </div>
              </button>
            );
          })}
        </div>
      </aside>

      <main style={{ display: 'flex', flexDirection: 'column', minHeight: 0, background: 'var(--bg-subtle)' }}>
        <div style={{ padding: '10px 16px', background: 'var(--surface)', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 10 }}>
          <span className="mono" style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>{selected.order_id}</span>
          <span style={{ fontSize: 13, fontWeight: 600 }}>{formatServiceName(selected)}</span>
          <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>· {selected.customer_name} · {selected.team_name || '미배정'}</span>
          <div style={{ flex: 1 }}/>
          <span style={{ fontSize: 11.5, color: 'var(--text-tertiary)' }}>미승인 {selected.pending_photo_count}장 · 승인 {selected.approved_photo_count}장</span>
        </div>

        <div style={{ flex: 1, padding: 20, display: 'flex', flexDirection: 'column', gap: 12, minHeight: 0 }}>
          <div style={{
            flex: 1,
            minHeight: 0,
            border: '1px solid var(--border)',
            borderRadius: 8,
            background: 'var(--surface)',
            overflow: 'hidden',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}>
            {activePhoto ? (
              <img
                src={activePhoto.file_url}
                alt={activePhoto.file_name || '검수 사진'}
                style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain', display: 'block' }}
              />
            ) : (
              <div style={{ textAlign: 'center', color: 'var(--text-tertiary)', fontSize: 13, lineHeight: 1.6 }}>
                <Icon name="send" size={22}/>
                <div style={{ marginTop: 8, fontWeight: 600, color: 'var(--text-secondary)' }}>승인 대기 사진이 없습니다</div>
                <div>고객 링크 발송이 필요한 주문입니다.</div>
              </div>
            )}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(8, 1fr)', gap: 6 }}>
            {photos.map((photo) => {
              const isActive = activePhoto?.id === photo.id;
              return (
                <button key={photo.id} onClick={() => setActivePhotoId(photo.id)}
                  style={{
                    padding: 0,
                    border: isActive ? '2px solid var(--brand)' : '2px solid transparent',
                    borderRadius: 6,
                    background: 'transparent',
                    cursor: 'pointer',
                    overflow: 'hidden',
                  }}>
                  <img src={photo.file_url} alt={photo.file_name || photo.photo_type}
                    style={{ width: '100%', aspectRatio: '1', objectFit: 'cover', display: 'block', background: 'var(--bg-muted)' }} />
                </button>
              );
            })}
          </div>
        </div>
      </main>

      <aside style={{ background: 'var(--surface)', borderLeft: '1px solid var(--border)', display: 'flex', flexDirection: 'column', overflow: 'auto' }}>
        <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--divider)' }}>
          <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 600, letterSpacing: '0.04em', marginBottom: 6 }}>주문 정보</div>
          <KVStack>
            <KVRow label="고객" value={selected.customer_name}/>
            <KVRow label="방문일" value={`${selected.scheduled_date || '미정'} · ${selected.requested_time || '-'}`}/>
            <KVRow label="협력사" value={selected.team_name || '미배정'}/>
            <KVRow label="상태" value={selected.status}/>
            <KVRow label="승인" value={`${selected.approved_photo_count}장`}/>
            <KVRow label="대기" value={`${selected.pending_photo_count}장`}/>
          </KVStack>
        </div>

        <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--divider)' }}>
          <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 600, letterSpacing: '0.04em', marginBottom: 6 }}>선택 사진</div>
          {activePhoto ? (
            <KVStack>
              <KVRow label="유형" value={photoTypeLabel(activePhoto.photo_type)}/>
              <KVRow label="파일" value={activePhoto.file_name || '-'} small/>
              <KVRow label="공개" value={activePhoto.is_customer_visible ? '공개' : '비공개'}/>
            </KVStack>
          ) : (
            <div style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>선택된 사진이 없습니다.</div>
          )}
        </div>

        {error && (
          <div style={{ margin: 14, padding: 10, borderRadius: 6, background: 'var(--danger-bg)', color: 'var(--danger-fg)', fontSize: 12 }}>
            {error}
          </div>
        )}
        {sentMessage && (
          <div style={{ margin: 14, padding: 10, borderRadius: 6, background: 'var(--success-bg)', color: 'var(--success-fg)', fontSize: 12 }}>
            {sentMessage}
          </div>
        )}

        <div style={{ flex: 1 }}/>

        <div style={{ padding: 14, borderTop: '1px solid var(--divider)', display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{
            padding: 10, marginBottom: 4,
            background: 'var(--brand-bg)',
            border: '1px solid var(--brand-bg-hover)',
            borderRadius: 6,
            fontSize: 11.5, color: 'var(--text-secondary)',
          }}>
            <div style={{ fontWeight: 600, color: 'var(--brand)', marginBottom: 2 }}>승인 후 자동 처리</div>
            승인된 사진만 고객 페이지에 노출되고 주문은 고객 전달 단계로 이동합니다.
          </div>
          <button data-testid="photo-approve-selected" className="btn btn--primary btn--block btn--lg" disabled={!activePhoto || activePhoto.is_customer_visible || isApproving} onClick={() => activePhoto && void handleApprove(activePhoto.id)}>
            <Icon name="check" size={14}/> 선택 사진 승인
          </button>
          <button className="btn btn--secondary btn--block" disabled={pendingPhotos.length === 0 || isApproving} onClick={() => void handleApproveAll()}>
            <Icon name="eye" size={13}/> 미승인 모두 승인
          </button>
          <button data-testid="photo-send-customer-link" className="btn btn--secondary btn--block" disabled={isSending || !selected.can_send_customer_link} onClick={() => void handleSendCustomerLink()}>
            <Icon name="send" size={13}/> 고객 링크 발송
          </button>
        </div>
      </aside>
    </div>
  );
}

function ReviewState({ text, tone = 'muted' }) {
  return (
    <div data-testid="admin-photo-review-page" style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: tone === 'danger' ? 'var(--danger-fg)' : 'var(--text-tertiary)', background: 'var(--bg)' }}>
      {text}
    </div>
  );
}

function formatServiceName(item) {
  return item.size_or_quantity ? `${item.service_name} ${item.size_or_quantity}` : item.service_name;
}

function photoTypeLabel(type) {
  if (type === 'before') return '비포';
  if (type === 'after') return '애프터';
  return '기타';
}

function KVStack({ children }) {
  return <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>{children}</div>;
}

function KVRow({ label, value, small = false }) {
  return (
    <div style={{ display: 'flex', gap: 8, fontSize: small ? 11.5 : 12 }}>
      <span style={{ width: 50, color: 'var(--text-tertiary)', flexShrink: 0 }}>{label}</span>
      <span style={{ flex: 1, color: 'var(--text)' }}>{value}</span>
    </div>
  );
}

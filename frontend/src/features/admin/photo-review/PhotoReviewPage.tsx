import React from 'react';

import { sendCustomerPhotoReady } from '../../../api/messages';
import { approvePhoto, listPhotoReviewQueue } from '../../../api/photos';
import { toApiAssetUrl } from '../../../api/client';
import { useApiResource } from '../../../api/useApiResource';
import { Badge, Icon } from '../../../components/common/ui';

const FILTERS = [
  { key: 'all', label: '전체' },
  { key: 'review', label: '검수대기' },
  { key: 'delivery', label: '전달가능' },
  { key: 'done', label: '전달완료' },
];

export function PhotoReviewPage({ onOpenOrder, onNav }) {
  const queue = useApiResource(listPhotoReviewQueue);
  const [filter, setFilter] = React.useState('all');
  const [selectedIdx, setSelectedIdx] = React.useState(0);
  const [selectedOrderId, setSelectedOrderId] = React.useState(null);
  const [activePhotoId, setActivePhotoId] = React.useState(null);
  const [approvedPhotoIds, setApprovedPhotoIds] = React.useState(() => new Set());
  const [isApproving, setIsApproving] = React.useState(false);
  const [isSending, setIsSending] = React.useState(false);
  const [sentMessage, setSentMessage] = React.useState(null);
  const [error, setError] = React.useState(null);

  const items = queue.data || [];
  const filteredItems = items.filter((item) => filter === 'all' || reviewStage(item).key === filter);
  const selectedById = selectedOrderId ? items.find((item) => item.order_id === selectedOrderId) : null;
  const selected = selectedById || filteredItems[selectedIdx] || filteredItems[0] || null;
  const photos = (selected?.photos || []).map((photo) => (
    approvedPhotoIds.has(photo.id) ? { ...photo, is_customer_visible: true } : photo
  ));
  const pendingPhotos = photos.filter((photo) => !photo.is_customer_visible);
  const approvedPhotos = photos.filter((photo) => photo.is_customer_visible);
  const activePhoto = photos.find((photo) => photo.id === activePhotoId) || pendingPhotos[0] || photos[0] || null;
  const counts = {
    all: items.length,
    review: items.filter((item) => reviewStage(item).key === 'review').length,
    delivery: items.filter((item) => reviewStage(item).key === 'delivery').length,
    done: items.filter((item) => reviewStage(item).key === 'done').length,
  };
  const selectedStage = selected ? reviewStage(selected) : null;
  const canSendCustomerLink = Boolean(
    selected
      && selectedStage?.key !== 'done'
      && (selected.can_send_customer_link || (approvedPhotos.length > 0 && pendingPhotos.length === 0)),
  );

  React.useEffect(() => {
    setSelectedIdx(0);
    setActivePhotoId(null);
    setApprovedPhotoIds(new Set());
  }, [queue.data, filter]);

  const handleApprove = async (photoId) => {
    setError(null);
    setSentMessage(null);
    setIsApproving(true);
    try {
      await approvePhoto(photoId);
      setApprovedPhotoIds((current) => {
        const next = new Set(current);
        next.add(photoId);
        return next;
      });
      queue.reload();
    } catch {
      setError('사진 승인 처리에 실패했습니다.');
    } finally {
      setIsApproving(false);
    }
  };

  const handleApproveAll = async () => {
    setError(null);
    setSentMessage(null);
    setIsApproving(true);
    let approvedCount = 0;
    const failedApprovals = [];
    const approvedIds = [];
    try {
      for (const photo of pendingPhotos) {
        try {
          await approvePhoto(photo.id);
          approvedCount += 1;
          approvedIds.push(photo.id);
        } catch {
          failedApprovals.push(photo.file_name || photo.id);
        }
      }
      if (approvedIds.length > 0) {
        setApprovedPhotoIds((current) => {
          const next = new Set(current);
          approvedIds.forEach((photoId) => next.add(photoId));
          return next;
        });
      }
      if (approvedCount > 0) {
        setSentMessage(`${approvedCount}장 공개 승인했습니다.`);
      }
      if (failedApprovals.length > 0) {
        const failedNames = failedApprovals.slice(0, 3).join(', ');
        const moreCount = failedApprovals.length > 3 ? ` 외 ${failedApprovals.length - 3}개` : '';
        setError(`${failedApprovals.length}장 승인 실패: ${failedNames}${moreCount}`);
      }
      queue.reload();
    } finally {
      setIsApproving(false);
    }
  };

  const handleSendCustomerLink = async () => {
    if (!selected || !canSendCustomerLink) {
      return;
    }
    setError(null);
    setSentMessage(null);
    setIsSending(true);
    try {
      const log = await sendCustomerPhotoReady(selected.order_id);
      if (log.status === 'sent') {
        setSentMessage('고객 링크를 발송했습니다.');
      } else {
        setError(`고객 링크 발송 실패 기록이 남았습니다. ${providerErrorText(log)}`);
      }
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

  if (items.length === 0) {
    return <PhotoReviewEmptyState onNav={onNav} onRefresh={queue.reload} />;
  }

  return (
    <div data-testid="admin-photo-review-page" style={{ flex: 1, display: 'grid', gridTemplateColumns: '280px 1fr 330px', minHeight: 0, background: 'var(--bg)' }}>
      <aside style={{ background: 'var(--surface)', borderRight: '1px solid var(--border)', display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--divider)', display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 12.5, fontWeight: 700 }}>사진 검수 게이트</span>
          <Badge tone="warn">{counts.review}</Badge>
          <div style={{ flex: 1 }}/>
          <button className="btn btn--ghost btn--sm" style={{ padding: '0 4px' }} onClick={queue.reload} aria-label="사진검수 새로고침">
            <Icon name="refresh" size={12}/>
          </button>
        </div>

        <div style={{ padding: '8px 10px', borderBottom: '1px solid var(--divider)', display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 6 }}>
          {FILTERS.map((item) => (
            <button
              key={item.key}
              type="button"
              data-testid={`photo-filter-${item.key}`}
              aria-pressed={filter === item.key}
              onClick={() => setFilter(item.key)}
              style={{
                height: 28,
                border: 'none',
                borderRadius: 7,
                background: filter === item.key ? 'var(--brand-bg)' : 'transparent',
                color: filter === item.key ? 'var(--brand)' : 'var(--text-tertiary)',
                fontSize: 11.5,
                fontWeight: 700,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 5,
              }}
            >
              {item.label}
              <span style={{ color: filter === item.key ? 'var(--brand)' : 'var(--text-quaternary)' }}>{counts[item.key]}</span>
            </button>
          ))}
        </div>

        <div className="scroll" style={{ flex: 1, overflow: 'auto' }}>
          {filteredItems.length === 0 ? (
            <div style={{ padding: 14, fontSize: 12, color: 'var(--text-tertiary)' }}>해당 상태의 사진 검수 건이 없습니다.</div>
          ) : filteredItems.map((item, index) => {
            const isActive = item.order_id === selected?.order_id;
            const stage = reviewStage(item);
            return (
              <button
                key={item.order_id}
                data-testid={`photo-review-item-${item.order_id}`}
                onClick={() => { setSelectedIdx(index); setSelectedOrderId(item.order_id); setActivePhotoId(null); setApprovedPhotoIds(new Set()); setSentMessage(null); setError(null); }}
                style={{
                  display: 'block',
                  width: '100%',
                  textAlign: 'left',
                  padding: '10px 14px',
                  border: 'none',
                  borderBottom: '1px solid var(--divider)',
                  borderLeft: isActive ? '2px solid var(--brand)' : '2px solid transparent',
                  background: isActive ? 'var(--brand-bg)' : 'transparent',
                  cursor: 'pointer',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                  <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-tertiary)' }}>{item.order_id}</span>
                  <Badge tone={stage.tone}>{stage.label}</Badge>
                </div>
                <div style={{ fontSize: 12.5, fontWeight: 700, marginBottom: 3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{formatServiceName(item)}</div>
                <div style={{ fontSize: 11, color: 'var(--text-tertiary)', display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.customer_name} · {item.team_name || '미배정'}</span>
                  <span className="mono" style={{ flexShrink: 0 }}>승인 {item.approved_photo_count} / 대기 {item.pending_photo_count}</span>
                </div>
              </button>
            );
          })}
        </div>
      </aside>

      <main style={{ display: 'flex', flexDirection: 'column', minHeight: 0, background: 'var(--bg-subtle)' }}>
        <div style={{ padding: '10px 16px', background: 'var(--surface)', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 10 }}>
          <span className="mono" style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>{selected?.order_id}</span>
          <span style={{ fontSize: 13, fontWeight: 700 }}>{selected ? formatServiceName(selected) : '-'}</span>
          {selectedStage && <Badge tone={selectedStage.tone}>{selectedStage.label}</Badge>}
          <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>· {selected?.customer_name} · {selected?.team_name || '미배정'}</span>
          <div style={{ flex: 1 }}/>
          <button className="btn btn--ghost btn--sm" onClick={() => selected && onOpenOrder?.(selected.order_id)}>
            주문 상세
          </button>
          <span style={{ fontSize: 11.5, color: 'var(--text-tertiary)' }}>비공개 {pendingPhotos.length}장 · 공개 {approvedPhotos.length}장</span>
        </div>

        <div style={{ padding: '10px 16px', background: 'var(--surface)', borderBottom: '1px solid var(--divider)' }}>
          <GateSteps stage={selectedStage?.key || 'review'} />
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
                src={toApiAssetUrl(activePhoto.file_url)}
                alt={activePhoto.file_name || '검수 사진'}
                style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain', display: 'block' }}
              />
            ) : (
              <div style={{ textAlign: 'center', color: 'var(--text-tertiary)', fontSize: 13, lineHeight: 1.6 }}>
                <Icon name="image" size={22}/>
                <div style={{ marginTop: 8, fontWeight: 600, color: 'var(--text-secondary)' }}>표시할 사진이 없습니다</div>
                <div>협력사가 업로드한 사진이 있으면 이곳에서 검수합니다.</div>
              </div>
            )}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(8, minmax(0, 1fr))', gap: 6 }}>
            {photos.map((photo) => {
              const isActive = activePhoto?.id === photo.id;
              return (
                <button
                  key={photo.id}
                  data-testid={`photo-thumb-${photo.id}`}
                  onClick={() => setActivePhotoId(photo.id)}
                  style={{
                    position: 'relative',
                    padding: 0,
                    border: isActive ? '2px solid var(--brand)' : '2px solid transparent',
                    borderRadius: 6,
                    background: 'transparent',
                    cursor: 'pointer',
                    overflow: 'hidden',
                  }}
                >
                  <img src={toApiAssetUrl(photo.file_url)} alt={photo.file_name || photo.photo_type}
                    style={{ width: '100%', aspectRatio: '1', objectFit: 'cover', display: 'block', background: 'var(--bg-muted)' }} />
                  <span style={{
                    position: 'absolute',
                    left: 4,
                    bottom: 4,
                    height: 18,
                    padding: '0 5px',
                    borderRadius: 5,
                    background: photo.is_customer_visible ? 'var(--success-bg)' : 'var(--warn-bg)',
                    color: photo.is_customer_visible ? 'var(--success-fg)' : 'var(--warn-fg)',
                    fontSize: 10,
                    fontWeight: 700,
                    display: 'inline-flex',
                    alignItems: 'center',
                  }}>
                    {photo.is_customer_visible ? '공개' : '비공개'}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </main>

      <aside style={{ background: 'var(--surface)', borderLeft: '1px solid var(--border)', display: 'flex', flexDirection: 'column', overflow: 'auto' }}>
        <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--divider)' }}>
          <PanelTitle>관리자 승인 게이트</PanelTitle>
          <div style={{ padding: 10, borderRadius: 8, background: 'var(--bg-subtle)', border: '1px solid var(--border)', fontSize: 12, lineHeight: 1.55, color: 'var(--text-secondary)' }}>
            협력사 업로드 사진은 기본 비공개입니다. 관리자가 공개 승인한 사진만 고객 링크에서 보입니다.
          </div>
        </div>

        <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--divider)' }}>
          <PanelTitle>주문 정보</PanelTitle>
          <KVStack>
            <KVRow label="고객" value={selected?.customer_name || '-'}/>
            <KVRow label="방문일" value={`${selected?.scheduled_date || '미정'} · ${selected?.requested_time || '-'}`}/>
            <KVRow label="협력사" value={selected?.team_name || '미배정'}/>
            <KVRow label="상태" value={selected?.status || '-'}/>
            <KVRow label="공개" value={`${approvedPhotos.length}장`}/>
            <KVRow label="비공개" value={`${pendingPhotos.length}장`}/>
          </KVStack>
        </div>

        <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--divider)' }}>
          <PanelTitle>선택 사진</PanelTitle>
          {activePhoto ? (
            <KVStack>
              <KVRow label="유형" value={photoTypeLabel(activePhoto.photo_type)}/>
              <KVRow label="파일" value={activePhoto.file_name || '-'} small/>
              <KVRow label="고객공개" value={activePhoto.is_customer_visible ? '공개됨' : '비공개'}/>
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
          <div data-testid="photo-send-notice" style={{ margin: 14, padding: 10, borderRadius: 6, background: 'var(--success-bg)', color: 'var(--success-fg)', fontSize: 12 }}>
            {sentMessage}
          </div>
        )}

        <div style={{ flex: 1 }}/>

        <div style={{ padding: 14, borderTop: '1px solid var(--divider)', display: 'flex', flexDirection: 'column', gap: 6 }}>
          <button data-testid="photo-approve-selected" className="btn btn--primary btn--block btn--lg" disabled={!activePhoto || activePhoto.is_customer_visible || isApproving} onClick={() => activePhoto && void handleApprove(activePhoto.id)}>
            <Icon name="check" size={14}/> 선택 사진 공개 승인
          </button>
          <button data-testid="photo-approve-all" className="btn btn--secondary btn--block" disabled={pendingPhotos.length === 0 || isApproving} onClick={() => void handleApproveAll()}>
            <Icon name="eye" size={13}/> 비공개 사진 모두 승인
          </button>
          <button data-testid="photo-send-customer-link" className="btn btn--secondary btn--block" disabled={isSending || !canSendCustomerLink} onClick={() => void handleSendCustomerLink()}>
            <Icon name="send" size={13}/> 고객 사진 링크 발송
          </button>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, marginTop: 4 }}>
            <button data-testid="photo-open-order" className="btn btn--ghost btn--sm" onClick={() => selected && onOpenOrder?.(selected.order_id)}>
              주문 상세
            </button>
            <button data-testid="photo-open-messages" className="btn btn--ghost btn--sm" onClick={() => onNav?.('sends')}>
              발송이력
            </button>
          </div>
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

function PhotoReviewEmptyState({ onNav, onRefresh }) {
  const metrics = [
    { label: '검수대기', value: '0장', tone: 'warn', icon: 'camera' },
    { label: '전달가능', value: '0건', tone: 'brand', icon: 'send' },
    { label: '전달완료', value: '0건', tone: 'success', icon: 'check' },
  ];

  return (
    <div data-testid="admin-photo-review-page" style={{ flex: 1, display: 'grid', gridTemplateColumns: '280px 1fr 330px', minHeight: 0, background: 'var(--bg)' }}>
      <aside style={{ background: 'var(--surface)', borderRight: '1px solid var(--border)', display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--divider)', display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 12.5, fontWeight: 700 }}>사진 검수 게이트</span>
          <Badge tone="success">0</Badge>
          <div style={{ flex: 1 }}/>
          <button className="btn btn--ghost btn--sm" style={{ padding: '0 4px' }} onClick={onRefresh} aria-label="사진검수 새로고침">
            <Icon name="refresh" size={12}/>
          </button>
        </div>

        <div style={{ padding: '8px 10px', borderBottom: '1px solid var(--divider)', display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 6 }}>
          {FILTERS.map((item) => (
            <button
              key={item.key}
              type="button"
              data-testid={`photo-filter-${item.key}`}
              aria-pressed={item.key === 'all'}
              style={{
                height: 28,
                border: 'none',
                borderRadius: 7,
                background: item.key === 'all' ? 'var(--brand-bg)' : 'transparent',
                color: item.key === 'all' ? 'var(--brand)' : 'var(--text-tertiary)',
                fontSize: 11.5,
                fontWeight: 700,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 5,
              }}
            >
              {item.label}
              <span style={{ color: item.key === 'all' ? 'var(--brand)' : 'var(--text-quaternary)' }}>0</span>
            </button>
          ))}
        </div>

        <div style={{ padding: 14, borderBottom: '1px solid var(--divider)' }}>
          <div style={{ padding: 10, borderRadius: 8, border: '1px solid var(--success-bg)', background: 'var(--success-bg)', color: 'var(--success-fg)', fontSize: 12, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 7 }}>
            <Icon name="check" size={14}/>
            검수 큐 정상
          </div>
        </div>

        <div style={{ padding: '10px 14px', display: 'grid', gap: 8 }}>
          {metrics.map((item) => (
            <div key={item.label} style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '9px 0', borderBottom: '1px solid var(--divider)' }}>
              <span style={{ width: 26, height: 26, borderRadius: 7, background: `var(--${item.tone}-bg, var(--brand-bg))`, color: `var(--${item.tone}-fg, var(--brand))`, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                <Icon name={item.icon} size={14}/>
              </span>
              <span style={{ flex: 1, fontSize: 12, color: 'var(--text-secondary)', fontWeight: 700 }}>{item.label}</span>
              <span className="mono" style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>{item.value}</span>
            </div>
          ))}
        </div>
      </aside>

      <main style={{ display: 'flex', flexDirection: 'column', minHeight: 0, background: 'var(--bg-subtle)' }}>
        <div style={{ padding: '10px 16px', background: 'var(--surface)', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 13, fontWeight: 700 }}>사진 검수</span>
          <Badge tone="success">대기 없음</Badge>
          <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>오늘 고객 전달을 막고 있는 사진이 없습니다</span>
          <div style={{ flex: 1 }}/>
          <button className="btn btn--ghost btn--sm" onClick={onRefresh}>
            <Icon name="refresh" size={12}/> 새로고침
          </button>
        </div>

        <div style={{ padding: '10px 16px', background: 'var(--surface)', borderBottom: '1px solid var(--divider)' }}>
          <GateSteps stage="review" />
        </div>

        <div style={{ flex: 1, minHeight: 0, padding: 20, display: 'grid', gridTemplateRows: 'minmax(0, 1fr) auto', gap: 12 }}>
          <div style={{
            minHeight: 0,
            border: '1px solid var(--border)',
            borderRadius: 8,
            background: 'var(--surface)',
            display: 'grid',
            gridTemplateColumns: 'minmax(240px, 420px) 1fr',
            overflow: 'hidden',
          }}>
            <div style={{ padding: 30, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 12 }}>
              <span style={{ width: 42, height: 42, borderRadius: 8, background: 'var(--success-bg)', color: 'var(--success-fg)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
                <Icon name="inbox" size={22}/>
              </span>
              <div>
                <div data-testid="photo-empty-title" style={{ fontSize: 18, lineHeight: 1.25, fontWeight: 800, marginBottom: 6 }}>검수 대기 사진이 없습니다</div>
                <div style={{ fontSize: 12.5, lineHeight: 1.6, color: 'var(--text-secondary)' }}>
                  협력사가 작업 사진을 올리면 주문별로 이 큐에 들어오고, 공개 승인 후 고객 사진 링크를 보낼 수 있습니다.
                </div>
              </div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 4 }}>
                <button className="btn btn--primary btn--sm" onClick={() => onNav?.('orders')}>
                  <Icon name="list" size={13}/> 주문 목록
                </button>
                <button className="btn btn--secondary btn--sm" onClick={() => onNav?.('sends')}>
                  <Icon name="history" size={13}/> 발송 이력
                </button>
              </div>
            </div>

            <div style={{ padding: 24, borderLeft: '1px solid var(--divider)', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(76px, 1fr))', alignContent: 'center', gap: 10 }}>
              {[0, 1, 2, 3, 4, 5].map((item) => (
                <div key={item} style={{
                  aspectRatio: '1',
                  borderRadius: 7,
                  border: '1px dashed var(--border)',
                  background: item % 2 === 0 ? 'var(--bg)' : 'var(--bg-muted)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'var(--text-quaternary)',
                }}>
                  <Icon name="image" size={18}/>
                </div>
              ))}
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 10 }}>
            {metrics.map((item) => (
              <div key={item.label} style={{ height: 56, border: '1px solid var(--border)', borderRadius: 8, background: 'var(--surface)', padding: '9px 11px', display: 'flex', alignItems: 'center', gap: 9 }}>
                <span style={{ width: 28, height: 28, borderRadius: 7, background: `var(--${item.tone}-bg, var(--brand-bg))`, color: `var(--${item.tone}-fg, var(--brand))`, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                  <Icon name={item.icon} size={14}/>
                </span>
                <div style={{ minWidth: 0 }}>
                  <div className="mono" style={{ fontSize: 15, fontWeight: 800, lineHeight: 1.1 }}>{item.value}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 3 }}>{item.label}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </main>

      <aside style={{ background: 'var(--surface)', borderLeft: '1px solid var(--border)', display: 'flex', flexDirection: 'column', overflow: 'auto' }}>
        <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--divider)' }}>
          <PanelTitle>운영 상태</PanelTitle>
          <KVStack>
            <KVRow label="검수대기" value="0장"/>
            <KVRow label="전달가능" value="0건"/>
            <KVRow label="전달완료" value="0건"/>
            <KVRow label="공개 대기" value="없음"/>
          </KVStack>
        </div>

        <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--divider)' }}>
          <PanelTitle>고객 공개 원칙</PanelTitle>
          <div style={{ padding: 10, borderRadius: 8, background: 'var(--bg-subtle)', border: '1px solid var(--border)', fontSize: 12, lineHeight: 1.55, color: 'var(--text-secondary)' }}>
            협력사 사진은 업로드 직후 비공개이며, 관리자 승인 후에만 고객 링크에 표시됩니다.
          </div>
        </div>

        <div style={{ flex: 1 }}/>

        <div style={{ padding: 14, borderTop: '1px solid var(--divider)', display: 'flex', flexDirection: 'column', gap: 6 }}>
          <button className="btn btn--secondary btn--block" onClick={onRefresh}>
            <Icon name="refresh" size={13}/> 큐 새로고침
          </button>
          <button className="btn btn--ghost btn--block" onClick={() => onNav?.('orders')}>
            주문 목록
          </button>
        </div>
      </aside>
    </div>
  );
}

function GateSteps({ stage }) {
  const steps = [
    { key: 'review', label: '관리자 검수' },
    { key: 'delivery', label: '고객 전달 가능' },
    { key: 'done', label: '전달 완료' },
  ];
  const currentIndex = steps.findIndex((item) => item.key === stage);
  const activeIndex = currentIndex < 0 ? 0 : currentIndex;

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
      {steps.map((item, index) => {
        const isActive = index === activeIndex;
        const isDone = index < activeIndex;
        return (
          <div key={item.key} style={{
            height: 34,
            borderRadius: 8,
            border: `1px solid ${isActive ? 'var(--brand)' : 'var(--border)'}`,
            background: isActive ? 'var(--brand-bg)' : isDone ? 'var(--success-bg)' : 'var(--surface)',
            color: isActive ? 'var(--brand)' : isDone ? 'var(--success-fg)' : 'var(--text-tertiary)',
            fontSize: 12,
            fontWeight: 700,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 6,
          }}>
            <span style={{ width: 16, height: 16, borderRadius: '50%', background: isActive ? 'var(--brand)' : isDone ? 'var(--success-fg)' : 'var(--neutral-bg)', color: isActive || isDone ? '#fff' : 'var(--neutral-fg)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: 10 }}>
              {index + 1}
            </span>
            {item.label}
          </div>
        );
      })}
    </div>
  );
}

function reviewStage(item) {
  if (['고객전달완료', '서비스완료'].includes(item.status)) {
    return { key: 'done', label: '전달완료', tone: 'success' };
  }
  if (item.pending_photo_count > 0) {
    return { key: 'review', label: `${item.pending_photo_count}장 검수`, tone: 'warn' };
  }
  if (item.can_send_customer_link) {
    return { key: 'delivery', label: '전달가능', tone: 'brand' };
  }
  return { key: 'delivery', label: '승인완료', tone: 'success' };
}

function formatServiceName(item) {
  return item.size_or_quantity ? `${item.service_name} ${item.size_or_quantity}` : item.service_name;
}

function photoTypeLabel(type) {
  if (type === 'before') return '비포';
  if (type === 'after') return '애프터';
  return '기타';
}

function providerErrorText(message) {
  const code = message.provider_error_code || '';
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
  return map[code] || message.provider_status_message || message.error_message || '실패 사유 미상';
}

function PanelTitle({ children }) {
  return <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 700, letterSpacing: '0.04em', marginBottom: 7 }}>{children}</div>;
}

function KVStack({ children }) {
  return <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>{children}</div>;
}

function KVRow({ label, value, small = false }) {
  return (
    <div style={{ display: 'flex', gap: 8, fontSize: small ? 11.5 : 12 }}>
      <span style={{ width: 56, color: 'var(--text-tertiary)', flexShrink: 0 }}>{label}</span>
      <span style={{ flex: 1, color: 'var(--text)' }}>{value}</span>
    </div>
  );
}

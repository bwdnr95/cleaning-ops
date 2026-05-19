import React from 'react';

import { sendCustomerPhotoReady } from '../../../api/messages';
import { listPhotoReviewQueue, revokePhoto } from '../../../api/photos';
import { toApiAssetUrl } from '../../../api/client';
import { useApiResource } from '../../../api/useApiResource';
import { PaginationBar, paginateItems } from '../../../components/common/Pagination';
import { Badge, Icon } from '../../../components/common/ui';

const FILTERS = [
  { key: 'all', label: '전체' },
  { key: 'pending_link', label: '링크 미발송' },
  { key: 'done', label: '전달완료' },
];

export function PhotoReviewPage({ onOpenOrder, onNav }) {
  const queue = useApiResource(listPhotoReviewQueue);
  const [filter, setFilter] = React.useState('all');
  const [page, setPage] = React.useState(1);
  const [pageSize, setPageSize] = React.useState(10);
  const [selectedIdx, setSelectedIdx] = React.useState(0);
  const [selectedOrderId, setSelectedOrderId] = React.useState(null);
  const [activePhotoId, setActivePhotoId] = React.useState(null);
  const [isApproving, setIsApproving] = React.useState(false);
  const [isSending, setIsSending] = React.useState(false);
  const [sentMessage, setSentMessage] = React.useState(null);
  const [error, setError] = React.useState(null);

  const items = queue.data || [];
  const filteredItems = items.filter((item) => filter === 'all' || reviewStage(item).key === filter);
  const pagedItems = React.useMemo(
    () => paginateItems(filteredItems, page, pageSize),
    [filteredItems, page, pageSize],
  );
  const selectedById = selectedOrderId ? items.find((item) => item.order_id === selectedOrderId) : null;
  const selected = selectedById || pagedItems[selectedIdx] || pagedItems[0] || filteredItems[0] || null;
  const photos = selected?.photos || [];
  const pendingPhotos = photos.filter((photo) => !photo.is_customer_visible);
  const approvedPhotos = photos.filter((photo) => photo.is_customer_visible);
  const activePhoto = photos.find((photo) => photo.id === activePhotoId) || photos[0] || null;
  const counts = {
    all: items.length,
    pending_link: items.filter((item) => reviewStage(item).key === 'pending_link').length,
    done: items.filter((item) => reviewStage(item).key === 'done').length,
  };
  const selectedStage = selected ? reviewStage(selected) : null;
  const canSendCustomerLink = Boolean(selected?.can_send_customer_link);

  React.useEffect(() => {
    setPage(1);
    setSelectedIdx(0);
    setSelectedOrderId(null);
    setActivePhotoId(null);
  }, [filter]);

  React.useEffect(() => {
    setSelectedIdx(0);
    setActivePhotoId(null);
  }, [queue.data]);

  const handleRevoke = async (photoId) => {
    setError(null);
    setSentMessage(null);
    setIsApproving(true);
    try {
      await revokePhoto(photoId);
      queue.reload();
    } catch {
      setError('사진 비공개 처리에 실패했습니다.');
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
          <span style={{ fontSize: 12.5, fontWeight: 700 }}>사진 모니터링</span>
          <Badge tone="warn">{counts.pending_link}</Badge>
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
            <div style={{ padding: 14, fontSize: 12, color: 'var(--text-tertiary)' }}>해당 상태의 사진 건이 없습니다.</div>
          ) : pagedItems.map((item, index) => {
            const isActive = item.order_id === selected?.order_id;
            const stage = reviewStage(item);
            return (
              <button
                key={item.order_id}
                data-testid={`photo-review-item-${item.order_id}`}
                onClick={() => { setSelectedIdx(index); setSelectedOrderId(item.order_id); setActivePhotoId(null); setSentMessage(null); setError(null); }}
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
                  <span className="mono" style={{ flexShrink: 0 }}>공개 {item.approved_photo_count} / 비공개 {item.pending_photo_count}</span>
                </div>
              </button>
            );
          })}
        </div>
        {filteredItems.length > 0 && (
          <PaginationBar
            testId="photo-review-pagination"
            totalItems={filteredItems.length}
            page={page}
            pageSize={pageSize}
            onPageChange={(nextPage) => {
              setPage(nextPage);
              setSelectedIdx(0);
              setSelectedOrderId(null);
              setActivePhotoId(null);
            }}
            onPageSizeChange={setPageSize}
            itemLabel="건"
          />
        )}
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
          <PanelTitle>자동 공개 모니터링</PanelTitle>
          <div style={{ padding: 10, borderRadius: 8, background: 'var(--bg-subtle)', border: '1px solid var(--border)', fontSize: 12, lineHeight: 1.55, color: 'var(--text-secondary)' }}>
            협력사 업로드 사진은 고객에게 즉시 공개됩니다. 잘못 올라온 사진만 비공개로 되돌리고 고객 사진 링크를 발송하거나 재전송합니다.
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
          <button
            data-testid="photo-send-customer-link"
            className="btn btn--primary btn--block btn--lg"
            disabled={isSending || !selected || !canSendCustomerLink}
            onClick={() => void handleSendCustomerLink()}
          >
            <Icon name="send" size={14}/>
            {selected?.last_customer_link_sent_at ? '고객 사진 링크 재전송' : '고객 사진 링크 발송'}
          </button>
          <button
            data-testid="photo-revoke-selected"
            className="btn btn--secondary btn--block"
            disabled={!activePhoto || !activePhoto.is_customer_visible || isApproving}
            onClick={() => activePhoto && void handleRevoke(activePhoto.id)}
          >
            <Icon name="eye" size={13}/> 선택 사진 비공개로 되돌리기
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
    { label: '링크 미발송', value: '0건', tone: 'warn', icon: 'camera' },
    { label: '공개 사진', value: '0장', tone: 'brand', icon: 'send' },
    { label: '전달완료', value: '0건', tone: 'success', icon: 'check' },
  ];

  return (
    <div data-testid="admin-photo-review-page" style={{ flex: 1, display: 'grid', gridTemplateColumns: '280px 1fr 330px', minHeight: 0, background: 'var(--bg)' }}>
      <aside style={{ background: 'var(--surface)', borderRight: '1px solid var(--border)', display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--divider)', display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 12.5, fontWeight: 700 }}>사진 모니터링</span>
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
          <span style={{ fontSize: 13, fontWeight: 700 }}>사진 모니터링</span>
          <Badge tone="success">대기 없음</Badge>
          <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>고객 링크 발송을 기다리는 사진 주문이 없습니다</span>
          <div style={{ flex: 1 }}/>
          <button className="btn btn--ghost btn--sm" onClick={onRefresh}>
            <Icon name="refresh" size={12}/> 새로고침
          </button>
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
                <div data-testid="photo-empty-title" style={{ fontSize: 18, lineHeight: 1.25, fontWeight: 800, marginBottom: 6 }}>사진 모니터링 큐가 비었습니다</div>
                <div style={{ fontSize: 12.5, lineHeight: 1.6, color: 'var(--text-secondary)' }}>
                  협력사가 사진을 올리면 고객에게 자동 공개됩니다. 이 화면에서는 비공개 되돌리기와 고객 사진 링크 발송 상태를 관리합니다.
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
            <KVRow label="링크 미발송" value="0건"/>
            <KVRow label="공개 사진" value="0장"/>
            <KVRow label="전달완료" value="0건"/>
            <KVRow label="비공개 사진" value="없음"/>
          </KVStack>
        </div>

        <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--divider)' }}>
          <PanelTitle>고객 공개 원칙</PanelTitle>
          <div style={{ padding: 10, borderRadius: 8, background: 'var(--bg-subtle)', border: '1px solid var(--border)', fontSize: 12, lineHeight: 1.55, color: 'var(--text-secondary)' }}>
            협력사 사진은 업로드 직후 고객에게 공개됩니다. 운영자는 잘못된 사진을 비공개로 되돌리고 고객 사진 링크를 여러 번 발송할 수 있습니다.
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

function reviewStage(item) {
  if (item.status === '취소') {
    return { key: 'done', label: '취소', tone: 'success' };
  }
  if (item.approved_photo_count > 0 && !item.last_customer_link_sent_at) {
    return { key: 'pending_link', label: '링크 미발송', tone: 'warn' };
  }
  if (item.approved_photo_count > 0 && item.last_customer_link_sent_at) {
    return { key: 'done', label: '전달완료', tone: 'success' };
  }
  return { key: 'pending_link', label: '대기', tone: 'brand' };
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

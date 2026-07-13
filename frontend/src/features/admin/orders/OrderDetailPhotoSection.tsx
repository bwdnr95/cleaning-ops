import React from 'react';

import { PhotoLightbox } from '../../../components/common/PhotoLightbox';
import { ProtectedApiImage } from '../../../components/common/ProtectedApiImage';
import { Badge } from '../../../components/common/ui';
import { photoTypeLabel } from './OrderDetailFormat';
import type { OrderDetailPhoto } from './OrderDetailModel';
import { EmptyLine, Section } from './OrderDetailPrimitives';

const PHOTO_GROUPS = [
  { key: 'before', title: '비포', tone: 'neutral' },
  { key: 'after', title: '애프터', tone: 'success' },
  { key: 'etc', title: '기타', tone: 'brand' },
  { key: 'customer_as', title: '고객 AS 접수', tone: 'warn' },
];

interface OrderDetailPhotoSectionProps {
  readonly visiblePhotos: readonly OrderDetailPhoto[];
}

export function OrderDetailPhotoSection({ visiblePhotos }: OrderDetailPhotoSectionProps) {
  const [openPhotoId, setOpenPhotoId] = React.useState<string | null>(null);
  const lightboxPhotos = React.useMemo(
    () => visiblePhotos.map((photo) => ({
      id: photo.id,
      src: photo.file_url,
      alt: photo.file_name || photoTypeLabel(photo.photo_type),
      caption: `${photoTypeLabel(photo.photo_type)} · ${photo.is_customer_visible ? '공개' : '비공개'}`,
      isProtected: true,
    })),
    [visiblePhotos],
  );

  return (
    <>
      <Section title="비포 / 애프터 사진" icon="image" badge={<Badge tone="warn">{visiblePhotos.filter((photo) => !photo.is_customer_visible).length} 비공개</Badge>}>
        {visiblePhotos.length === 0 ? (
          <EmptyLine text="업로드된 사진이 없습니다." />
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: 10 }}>
            {PHOTO_GROUPS.map((group) => (
              <PhotoGroupColumn
                key={group.key}
                title={group.title}
                tone={group.tone}
                photos={visiblePhotos.filter((photo) => adminPhotoGroupKey(photo) === group.key)}
                onOpenPhoto={setOpenPhotoId}
              />
            ))}
          </div>
        )}
      </Section>
      <PhotoLightbox
        photos={lightboxPhotos}
        openPhotoId={openPhotoId}
        onOpenPhoto={setOpenPhotoId}
        onClose={() => setOpenPhotoId(null)}
      />
    </>
  );
}

interface PhotoGroupColumnProps {
  readonly title: string;
  readonly tone: string;
  readonly photos: readonly OrderDetailPhoto[];
  readonly onOpenPhoto: (photoId: string) => void;
}

function PhotoGroupColumn({ title, tone, photos, onOpenPhoto }: PhotoGroupColumnProps) {
  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 8, background: 'var(--surface)', overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 10px', borderBottom: '1px solid var(--divider)' }}>
        <Badge tone={tone}>{title}</Badge>
        <span style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 700 }}>{photos.length}장</span>
      </div>
      {photos.length === 0 ? (
        <div style={{ minHeight: 104, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-tertiary)', fontSize: 11.5 }}>
          사진 없음
        </div>
      ) : (
        <div style={{ padding: 8, display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 8 }}>
          {photos.map((photo) => (
            <div
              key={photo.id}
              style={{
                border: '1px solid var(--border)',
                borderRadius: 7,
                overflow: 'hidden',
                background: 'var(--surface)',
                contentVisibility: 'auto',
                containIntrinsicSize: '96px 128px',
              }}
            >
              <button
                type="button"
                data-testid={`admin-order-photo-${photo.id}`}
                aria-label={`${photoTypeLabel(photo.photo_type)} 사진 크게 보기`}
                onClick={() => onOpenPhoto(photo.id)}
                style={{ display: 'block', width: '100%', padding: 0, border: 'none', background: 'transparent', cursor: 'zoom-in' }}
              >
                <ProtectedOrderPhotoImage photo={photo} />
              </button>
              <div style={{ padding: 6, display: 'flex', alignItems: 'center', gap: 4 }}>
                <Badge tone={photo.is_customer_visible ? 'success' : 'warn'}>{photo.is_customer_visible ? '공개' : '비공개'}</Badge>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function adminPhotoGroupKey(photo: OrderDetailPhoto): string {
  if (photo.photo_source === 'customer_as') {
    return 'customer_as';
  }
  if (photo.photo_type === 'before' || photo.photo_type === 'after') {
    return photo.photo_type;
  }
  return 'etc';
}

function ProtectedOrderPhotoImage({ photo }: { readonly photo: OrderDetailPhoto }) {
  return (
    <ProtectedApiImage
      src={photo.file_url}
      alt={photo.file_name || photoTypeLabel(photo.photo_type)}
      style={photoImageStyle}
      placeholderStyle={photoPlaceholderStyle}
    />
  );
}

const photoImageStyle: React.CSSProperties = {
  display: 'block',
  width: '100%',
  aspectRatio: '1',
  objectFit: 'cover',
  background: 'var(--bg-muted)',
};

const photoPlaceholderStyle: React.CSSProperties = {
  width: '100%',
  aspectRatio: '1',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  background: 'var(--bg-muted)',
  color: 'var(--text-tertiary)',
  fontSize: 11,
  fontWeight: 700,
};

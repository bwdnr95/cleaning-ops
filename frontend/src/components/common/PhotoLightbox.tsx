import React from 'react';
import { createPortal } from 'react-dom';

import { ProtectedApiImage } from './ProtectedApiImage';
import { Icon } from './ui';

export interface PhotoLightboxItem {
  readonly id: string;
  readonly src: string | null | undefined;
  readonly alt: string;
  readonly caption?: string | null;
  readonly isProtected?: boolean;
}

interface PhotoLightboxProps {
  readonly photos: readonly PhotoLightboxItem[];
  readonly openPhotoId: string | null;
  readonly onOpenPhoto: (photoId: string) => void;
  readonly onClose: () => void;
}

export function PhotoLightbox({ photos, openPhotoId, onOpenPhoto, onClose }: PhotoLightboxProps) {
  const index = photos.findIndex((photo) => photo.id === openPhotoId);
  const photo = index >= 0 ? photos[index] : null;

  React.useEffect(() => {
    if (!photo) {
      return undefined;
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      }
      if (event.key === 'ArrowLeft') {
        openSiblingPhoto(photos, index, -1, onOpenPhoto);
      }
      if (event.key === 'ArrowRight') {
        openSiblingPhoto(photos, index, 1, onOpenPhoto);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [index, onClose, onOpenPhoto, photo, photos]);

  if (!photo || typeof document === 'undefined') {
    return null;
  }

  const body = (
    <div
      role="dialog"
      aria-modal="true"
      data-testid="photo-lightbox"
      onClick={onClose}
      style={overlayStyle}
    >
      <div onClick={(event) => event.stopPropagation()} style={dialogStyle}>
        <button type="button" aria-label="닫기" onClick={onClose} style={closeButtonStyle}>
          <Icon name="x" size={18} />
        </button>
        {photos.length > 1 && (
          <>
            <button type="button" aria-label="이전 사진" onClick={() => openSiblingPhoto(photos, index, -1, onOpenPhoto)} style={{ ...navButtonStyle, left: 12 }}>
              <Icon name="chevronLeft" size={22} />
            </button>
            <button type="button" aria-label="다음 사진" onClick={() => openSiblingPhoto(photos, index, 1, onOpenPhoto)} style={{ ...navButtonStyle, right: 12 }}>
              <Icon name="chevronRight" size={22} />
            </button>
          </>
        )}
        <div style={imageWrapStyle}>
          {photo.isProtected ? (
            <ProtectedApiImage
              src={photo.src}
              alt={photo.alt}
              loading="eager"
              style={imageStyle}
              placeholderStyle={placeholderStyle}
            />
          ) : (
            <img src={photo.src || ''} alt={photo.alt} style={imageStyle} />
          )}
        </div>
        {(photo.caption || photos.length > 1) && (
          <div style={captionStyle}>
            <span>{photo.caption || photo.alt}</span>
            <span className="mono">{index + 1} / {photos.length}</span>
          </div>
        )}
      </div>
    </div>
  );

  return createPortal(body, document.body);
}

function openSiblingPhoto(
  photos: readonly PhotoLightboxItem[],
  index: number,
  direction: 1 | -1,
  onOpenPhoto: (photoId: string) => void,
) {
  if (photos.length <= 1) {
    return;
  }
  const nextIndex = (index + direction + photos.length) % photos.length;
  onOpenPhoto(photos[nextIndex].id);
}

const overlayStyle: React.CSSProperties = {
  position: 'fixed',
  inset: 0,
  zIndex: 4000,
  background: 'rgba(15, 23, 42, 0.82)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  padding: 16,
};

const dialogStyle: React.CSSProperties = {
  position: 'relative',
  width: 'min(1120px, calc(100vw - 32px))',
  maxHeight: 'calc(100dvh - 32px)',
  display: 'grid',
  gridTemplateRows: 'minmax(0, 1fr) auto',
  gap: 10,
};

const imageWrapStyle: React.CSSProperties = {
  minHeight: 0,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
};

const imageStyle: React.CSSProperties = {
  maxWidth: '100%',
  maxHeight: 'calc(100dvh - 92px)',
  objectFit: 'contain',
  display: 'block',
  borderRadius: 8,
};

const placeholderStyle: React.CSSProperties = {
  width: 'min(420px, 80vw)',
  height: 260,
  borderRadius: 8,
  background: 'var(--surface)',
  color: 'var(--text-tertiary)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  fontSize: 13,
  fontWeight: 700,
};

const closeButtonStyle: React.CSSProperties = {
  position: 'absolute',
  top: -4,
  right: -4,
  width: 38,
  height: 38,
  border: '1px solid rgba(255,255,255,0.22)',
  borderRadius: 8,
  background: 'rgba(15,23,42,0.72)',
  color: '#fff',
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  cursor: 'pointer',
};

const navButtonStyle: React.CSSProperties = {
  position: 'absolute',
  top: '50%',
  transform: 'translateY(-50%)',
  width: 40,
  height: 48,
  border: '1px solid rgba(255,255,255,0.18)',
  borderRadius: 8,
  background: 'rgba(15,23,42,0.58)',
  color: '#fff',
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  cursor: 'pointer',
};

const captionStyle: React.CSSProperties = {
  minHeight: 34,
  padding: '8px 10px',
  borderRadius: 8,
  background: 'rgba(15,23,42,0.76)',
  color: '#fff',
  fontSize: 12,
  fontWeight: 700,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: 12,
};

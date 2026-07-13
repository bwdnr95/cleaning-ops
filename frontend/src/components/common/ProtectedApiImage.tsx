import React from 'react';

import { apiBlobRequest, toApiAssetUrl } from '../../api/client';

interface ProtectedApiImageProps {
  readonly src: string | null | undefined;
  readonly alt: string;
  readonly style?: React.CSSProperties;
  readonly className?: string;
  readonly testId?: string;
  readonly loading?: 'eager' | 'lazy';
  readonly placeholderText?: string;
  readonly placeholderStyle?: React.CSSProperties;
}

export function ProtectedApiImage({
  src,
  alt,
  style,
  className,
  testId,
  loading = 'lazy',
  placeholderText = '불러오는 중',
  placeholderStyle,
}: ProtectedApiImageProps) {
  const [loadTarget, setLoadTarget] = React.useState<HTMLElement | null>(null);
  const shouldLoad = useImageLoadGate({ loading, resetKey: src || '', target: loadTarget });
  const imageSrc = useProtectedApiObjectUrl(src, shouldLoad);
  const setPlaceholderRef = React.useCallback((node: HTMLDivElement | null) => {
    setLoadTarget(node);
  }, []);
  const setImageRef = React.useCallback((node: HTMLImageElement | null) => {
    setLoadTarget(node);
  }, []);

  if (!imageSrc) {
    return <div ref={setPlaceholderRef} style={placeholderStyle}>{placeholderText}</div>;
  }
  return (
    <img
      ref={setImageRef}
      data-testid={testId}
      className={className}
      src={imageSrc}
      alt={alt}
      loading={loading}
      decoding="async"
      style={style}
    />
  );
}

function useImageLoadGate({
  loading,
  resetKey,
  target,
}: {
  readonly loading: 'eager' | 'lazy';
  readonly resetKey: string;
  readonly target: HTMLElement | null;
}) {
  const [shouldLoad, setShouldLoad] = React.useState(loading === 'eager');

  React.useEffect(() => {
    if (loading === 'eager' || shouldLoad) {
      setShouldLoad(true);
      return undefined;
    }
    if (!target) {
      return undefined;
    }
    if (typeof IntersectionObserver === 'undefined') {
      setShouldLoad(true);
      return undefined;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setShouldLoad(true);
          observer.disconnect();
        }
      },
      { rootMargin: '600px 0px' },
    );
    observer.observe(target);
    return () => observer.disconnect();
  }, [loading, shouldLoad, target]);

  React.useEffect(() => {
    setShouldLoad(loading === 'eager');
  }, [loading, resetKey]);

  return shouldLoad;
}

function useProtectedApiObjectUrl(src: string | null | undefined, shouldLoad: boolean) {
  const [imageSrc, setImageSrc] = React.useState(() => (
    isProtectedApiAsset(src) ? '' : toApiAssetUrl(src || '')
  ));

  React.useEffect(() => {
    if (!src) {
      setImageSrc('');
      return undefined;
    }
    if (!isProtectedApiAsset(src)) {
      setImageSrc(toApiAssetUrl(src));
      return undefined;
    }
    if (!shouldLoad) {
      setImageSrc('');
      return undefined;
    }

    let isActive = true;
    let objectUrl = '';
    const controller = new AbortController();
    void (async () => {
      try {
        const blob = await apiBlobRequest(src, { signal: controller.signal });
        objectUrl = URL.createObjectURL(blob);
        if (isActive) {
          setImageSrc(objectUrl);
        }
      } catch (error) {
        if (controller.signal.aborted) {
          return;
        }
        void error;
        if (isActive) {
          setImageSrc('');
        }
      }
    })();

    return () => {
      isActive = false;
      controller.abort();
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [shouldLoad, src]);

  return imageSrc;
}

function isProtectedApiAsset(src: string | null | undefined) {
  if (!src) {
    return false;
  }
  try {
    return new URL(src, window.location.origin).pathname.startsWith('/api/');
  } catch {
    return src.startsWith('/api/');
  }
}

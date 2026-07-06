import React from 'react';

type BrandLogoSize = 'sm' | 'md' | 'lg';

type BrandLogoProps = {
  readonly size?: BrandLogoSize;
  readonly caption?: string;
  readonly className?: string;
};

const BRAND_LOGO_SIZES = {
  sm: { frameWidth: 72, frameHeight: 38, logoHeight: 28, radius: 8, captionSize: 10.5 },
  md: { frameWidth: 84, frameHeight: 44, logoHeight: 32, radius: 8, captionSize: 11 },
  lg: { frameWidth: 104, frameHeight: 54, logoHeight: 39, radius: 8, captionSize: 11.5 },
} as const;

export function BrandLogo({ size = 'md', caption, className }: BrandLogoProps) {
  const spec = BRAND_LOGO_SIZES[size];

  return (
    <div className={className} style={{ display: 'inline-flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
      <span
        style={{
          width: spec.frameWidth,
          height: spec.frameHeight,
          borderRadius: spec.radius,
          background: 'var(--text)',
          border: '1px solid var(--border-strong)',
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
          boxShadow: 'var(--shadow-xs)',
        }}
      >
        <img
          src="/cleanjob-logo.png"
          alt="클린잡"
          width={150}
          height={90}
          style={{ height: spec.logoHeight, width: 'auto', display: 'block' }}
        />
      </span>
      {caption && (
        <span
          style={{
            color: 'var(--text-tertiary)',
            fontSize: spec.captionSize,
            fontWeight: 800,
            letterSpacing: '0.04em',
            whiteSpace: 'nowrap',
          }}
        >
          {caption}
        </span>
      )}
    </div>
  );
}

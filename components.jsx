// Shared components for Cleaning Ops Control Center

const STATUS_MAP = {
  '신규접수':     { tone: 'neutral', label: '신규접수' },
  '상담중':       { tone: 'purple',  label: '상담중' },
  '협력사확인중': { tone: 'warn',    label: '협력사확인중' },
  '일정확정':     { tone: 'info',    label: '일정확정' },
  '전날안내필요': { tone: 'warn',    label: '전날안내필요' },
  '전날안내완료': { tone: 'info',    label: '전날안내완료' },
  '작업예정':     { tone: 'info',    label: '작업예정' },
  '작업진행':     { tone: 'info',    label: '작업진행' },
  '사진검수대기': { tone: 'warn',    label: '사진검수대기' },
  '고객전달필요': { tone: 'warn',    label: '고객전달필요' },
  '고객전달완료': { tone: 'success', label: '고객전달완료' },
  '서비스완료':   { tone: 'success', label: '서비스완료' },
  '취소':         { tone: 'danger',  label: '취소' },
};

function StatusBadge({ status, dot = true }) {
  const cfg = STATUS_MAP[status] || { tone: 'neutral', label: status };
  return (
    <span className={`badge badge--${cfg.tone}`}>
      {dot && <span className="dot"></span>}
      {cfg.label}
    </span>
  );
}

function Badge({ tone = 'neutral', children, dot }) {
  return (
    <span className={`badge badge--${tone}`}>
      {dot && <span className="dot"></span>}
      {children}
    </span>
  );
}

// Minimal stroke icons (24×24 viewBox, 1.6 stroke)
function Icon({ name, size = 16, color = 'currentColor', strokeWidth = 1.6 }) {
  const paths = {
    search: <><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></>,
    plus: <><path d="M12 5v14M5 12h14"/></>,
    filter: <><path d="M3 5h18M6 12h12M10 19h4"/></>,
    chevronDown: <><path d="m6 9 6 6 6-6"/></>,
    chevronRight: <><path d="m9 6 6 6-6 6"/></>,
    chevronLeft: <><path d="m15 6-6 6 6 6"/></>,
    bell: <><path d="M6 8a6 6 0 1 1 12 0c0 7 3 7 3 9H3c0-2 3-2 3-9Z"/><path d="M10 21a2 2 0 0 0 4 0"/></>,
    check: <><path d="m5 12 5 5 9-11"/></>,
    x: <><path d="M6 6l12 12M18 6L6 18"/></>,
    camera: <><rect x="3" y="6" width="18" height="14" rx="2"/><circle cx="12" cy="13" r="4"/><path d="M8 6V4h8v2"/></>,
    image: <><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-5-5L5 21"/></>,
    user: <><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></>,
    phone: <><path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2Z"/></>,
    mapPin: <><path d="M12 22s8-7 8-13a8 8 0 1 0-16 0c0 6 8 13 8 13Z"/><circle cx="12" cy="9" r="3"/></>,
    calendar: <><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/></>,
    clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
    send: <><path d="M22 2 11 13M22 2l-7 20-4-9-9-4 20-7Z"/></>,
    list: <><path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/></>,
    grid: <><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></>,
    settings: <><path d="M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z"/><path d="M19 12c0 .5-.05 1-.13 1.4l2 1.6-2 3.4-2.4-.9c-.7.6-1.5 1-2.4 1.3L13.6 22h-3.2l-.46-2.2c-.9-.3-1.7-.7-2.4-1.3l-2.4.9-2-3.4 2-1.6A6.5 6.5 0 0 1 5 12c0-.5.05-1 .13-1.4l-2-1.6 2-3.4 2.4.9c.7-.6 1.5-1 2.4-1.3L10.4 2h3.2l.46 2.2c.9.3 1.7.7 2.4 1.3l2.4-.9 2 3.4-2 1.6c.08.4.13.9.13 1.4Z"/></>,
    home: <><path d="M3 11l9-8 9 8v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1V11Z"/></>,
    package: <><path d="m12 3 9 5v8l-9 5-9-5V8l9-5Z"/><path d="M3 8l9 5 9-5M12 13v9"/></>,
    truck: <><rect x="1" y="6" width="14" height="11" rx="1"/><path d="M15 9h5l3 4v4h-8M6 21a2 2 0 1 0 0-4 2 2 0 0 0 0 4ZM18 21a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z"/></>,
    creditCard: <><rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 10h20"/></>,
    history: <><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5M12 7v5l3 2"/></>,
    upload: <><path d="M12 16V4M6 10l6-6 6 6M4 20h16"/></>,
    moreHorizontal: <><circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/></>,
    arrowRight: <><path d="M5 12h14M13 5l7 7-7 7"/></>,
    arrowLeft: <><path d="M19 12H5M11 5l-7 7 7 7"/></>,
    eye: <><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></>,
    lock: <><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 1 1 8 0v4"/></>,
    shield: <><path d="M12 3 4 6v6c0 5 3.5 8.5 8 9 4.5-.5 8-4 8-9V6l-8-3Z"/></>,
    sparkles: <><path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M5.6 18.4l2.8-2.8M15.6 8.4l2.8-2.8"/></>,
    inbox: <><path d="M3 13h5l1 3h6l1-3h5M5 5h14l2 8v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-6l2-8Z"/></>,
    trending: <><path d="m22 7-9 9-4-4-7 7"/><path d="M16 7h6v6"/></>,
    refresh: <><path d="M21 12a9 9 0 1 1-3-6.7M21 4v5h-5"/></>,
    fileText: <><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9l-6-6Z"/><path d="M14 3v6h6M9 13h6M9 17h4"/></>,
    star: <><path d="m12 3 2.7 5.5 6 .9-4.4 4.2 1 6L12 17l-5.4 2.7 1-6L3.3 9.4l6-.9L12 3Z"/></>,
    chevronUp: <><path d="m6 15 6-6 6 6"/></>,
    sun: <><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5 19 19M5 19l1.5-1.5M17.5 6.5 19 5"/></>,
    moon: <><path d="M21 13A9 9 0 1 1 11 3a7 7 0 0 0 10 10Z"/></>,
  };
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round">
      {paths[name] || null}
    </svg>
  );
}

function Avatar({ name, size = 24, tone = 'brand' }) {
  const initial = (name || '?').slice(0, 1);
  const tones = {
    brand:   { bg: 'var(--brand-bg)',   fg: 'var(--brand)' },
    info:    { bg: 'var(--info-bg)',    fg: 'var(--info-fg)' },
    success: { bg: 'var(--success-bg)', fg: 'var(--success-fg)' },
    warn:    { bg: 'var(--warn-bg)',    fg: 'var(--warn-fg)' },
    purple:  { bg: 'var(--purple-bg)',  fg: 'var(--purple-fg)' },
    neutral: { bg: 'var(--neutral-bg)', fg: 'var(--neutral-fg)' },
  };
  const t = tones[tone] || tones.brand;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      width: size, height: size, borderRadius: '50%',
      background: t.bg, color: t.fg,
      fontSize: size * 0.45, fontWeight: 600, letterSpacing: '-0.02em',
    }}>{initial}</span>
  );
}

function Sparkline({ values, color = 'var(--brand)', width = 80, height = 24 }) {
  const max = Math.max(...values), min = Math.min(...values);
  const range = max - min || 1;
  const step = width / (values.length - 1);
  const pts = values.map((v, i) => `${i * step},${height - ((v - min) / range) * height}`).join(' ');
  return (
    <svg width={width} height={height} style={{ overflow: 'visible' }}>
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

Object.assign(window, { STATUS_MAP, StatusBadge, Badge, Icon, Avatar, Sparkline });

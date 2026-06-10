import React from 'react';
import { createPortal } from 'react-dom';

import { Icon } from '../../../components/common/ui';

interface PartnerOption {
  id: string;
  name: string;
}

interface Props {
  partners: PartnerOption[];
  value: string; // 'all' | partnerId
  onChange: (next: string) => void;
}

const MENU_WIDTH = 248;
const MENU_OFFSET = 6;
const VIEWPORT_GAP = 8;

// 협력사 필터: 수십 개를 인라인 칩으로 깔지 않고, 검색형 드롭다운으로 제공한다.
// (캘린더의 검색형 협력사 리스트와 동일한 사용 경험)
export function PartnerFilterSelect({ partners, value, onChange }: Props) {
  const rootRef = React.useRef<HTMLDivElement | null>(null);
  const popupRef = React.useRef<HTMLDivElement | null>(null);
  const searchRef = React.useRef<HTMLInputElement | null>(null);
  const [isOpen, setIsOpen] = React.useState(false);
  const [query, setQuery] = React.useState('');
  const [position, setPosition] = React.useState<{ top: number; left: number } | null>(null);

  const selectedName = value === 'all'
    ? '전체 협력사'
    : partners.find((partner) => partner.id === value)?.name || '선택 협력사';

  const filtered = React.useMemo(() => {
    const keyword = query.trim().toLowerCase();
    if (!keyword) {
      return partners;
    }
    return partners.filter((partner) => String(partner.name || '').toLowerCase().includes(keyword));
  }, [partners, query]);

  const updatePosition = React.useCallback(() => {
    const root = rootRef.current;
    if (!root) {
      return;
    }
    const rect = root.getBoundingClientRect();
    const viewportWidth = window.innerWidth || document.documentElement.clientWidth;
    const left = Math.max(VIEWPORT_GAP, Math.min(rect.left, viewportWidth - MENU_WIDTH - VIEWPORT_GAP));
    setPosition({ top: rect.bottom + MENU_OFFSET, left });
  }, []);

  React.useLayoutEffect(() => {
    if (!isOpen) {
      setPosition(null);
      return undefined;
    }
    updatePosition();
    window.addEventListener('resize', updatePosition);
    window.addEventListener('scroll', updatePosition, true);
    return () => {
      window.removeEventListener('resize', updatePosition);
      window.removeEventListener('scroll', updatePosition, true);
    };
  }, [isOpen, updatePosition]);

  React.useEffect(() => {
    if (!isOpen) {
      return undefined;
    }
    const handleMouseDown = (event: MouseEvent) => {
      const target = event.target as Node;
      const insideRoot = rootRef.current?.contains(target);
      const insidePopup = popupRef.current?.contains(target);
      if (!insideRoot && !insidePopup) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleMouseDown);
    return () => document.removeEventListener('mousedown', handleMouseDown);
  }, [isOpen]);

  React.useEffect(() => {
    if (isOpen) {
      setQuery('');
      window.setTimeout(() => searchRef.current?.focus(), 0);
    }
  }, [isOpen]);

  const select = (next: string) => {
    onChange(next);
    setIsOpen(false);
  };

  return (
    <div ref={rootRef} style={{ position: 'relative' }}>
      <button
        type="button"
        data-testid="orders-partner-filter"
        aria-label="협력사 필터"
        aria-expanded={isOpen}
        onClick={() => setIsOpen((current) => !current)}
        style={{
          height: 30,
          padding: '0 10px',
          display: 'inline-flex',
          alignItems: 'center',
          gap: 7,
          maxWidth: 220,
          border: `1px solid ${isOpen ? 'var(--brand)' : 'var(--border)'}`,
          borderRadius: 8,
          background: value === 'all' ? 'var(--surface)' : 'var(--brand-bg)',
          boxShadow: isOpen ? '0 0 0 3px var(--brand-bg)' : 'var(--shadow-xs)',
          color: value === 'all' ? 'var(--text-secondary)' : 'var(--brand)',
          fontSize: 12,
          fontWeight: 500,
          cursor: 'pointer',
        }}
      >
        <Icon name="user" size={12} />
        <span style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {selectedName}
        </span>
        <Icon name={isOpen ? 'chevronUp' : 'chevronDown'} size={11} />
      </button>

      {isOpen && position && createPortal((
        <div
          ref={popupRef}
          data-testid="orders-partner-filter-menu"
          style={{
            position: 'fixed',
            top: position.top,
            left: position.left,
            zIndex: 1000,
            width: MENU_WIDTH,
            border: '1px solid var(--border)',
            borderRadius: 8,
            background: 'var(--surface)',
            boxShadow: 'var(--shadow-md)',
            overflow: 'hidden',
          }}
        >
          <div style={{ padding: 8, borderBottom: '1px solid var(--divider)' }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 7,
                padding: '0 9px',
                height: 30,
                border: '1px solid var(--border)',
                borderRadius: 7,
                background: 'var(--bg)',
                color: 'var(--text-tertiary)',
              }}
            >
              <Icon name="search" size={13} />
              <input
                ref={searchRef}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="협력사 검색"
                aria-label="협력사 검색"
                style={{
                  flex: 1,
                  minWidth: 0,
                  border: 'none',
                  outline: 'none',
                  background: 'transparent',
                  color: 'var(--text)',
                  fontSize: 12,
                }}
              />
            </div>
          </div>
          <div className="scroll" style={{ maxHeight: 280, overflowY: 'auto', padding: 4 }}>
            <PartnerFilterOption label="전체 협력사" active={value === 'all'} onClick={() => select('all')} />
            {filtered.length === 0 ? (
              <div style={{ padding: '10px 10px', color: 'var(--text-quaternary)', fontSize: 12 }}>
                검색 결과가 없습니다.
              </div>
            ) : (
              filtered.map((partner) => (
                <PartnerFilterOption
                  key={partner.id}
                  testId={`orders-partner-option-${partner.id}`}
                  label={partner.name}
                  active={value === partner.id}
                  onClick={() => select(partner.id)}
                />
              ))
            )}
          </div>
        </div>
      ), document.body)}
    </div>
  );
}

function PartnerFilterOption({
  label,
  active,
  onClick,
  testId = undefined,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
  testId?: string;
}) {
  return (
    <button
      type="button"
      data-testid={testId}
      aria-pressed={active}
      onClick={onClick}
      style={{
        width: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 8,
        padding: '7px 9px',
        border: 'none',
        borderRadius: 6,
        background: active ? 'var(--brand-bg)' : 'transparent',
        color: active ? 'var(--brand)' : 'var(--text-secondary)',
        fontSize: 12,
        fontWeight: active ? 600 : 500,
        cursor: 'pointer',
        textAlign: 'left',
      }}
    >
      <span style={{ minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{label}</span>
      {active && <Icon name="check" size={13} />}
    </button>
  );
}

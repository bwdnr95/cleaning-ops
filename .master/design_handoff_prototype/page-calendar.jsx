// Calendar view — month grid with site filter sidebar

const SITES = [
  { id: 'all',     name: '전체 현장', count: 142, active: true },
  { id: 'gangnam', name: '강남점',    count: 28 },
  { id: 'mapo',    name: '마포점',    count: 18 },
  { id: 'songpa',  name: '잠실점',    count: 22 },
  { id: 'seocho',  name: '반포점',    count: 14 },
  { id: 'yeoido',  name: '여의도점',  count: 11 },
  { id: 'yongsan', name: '한남점',    count: 9 },
  { id: 'seongsu', name: '성수점',    count: 16 },
  { id: 'magok',   name: '마곡점',    count: 12 },
  { id: 'bundang', name: '분당점',    count: 8 },
  { id: 'incheon', name: '인천점',    count: 4 },
];

// Pre-baked May 2026 events
const CAL_EVENTS = {
  1: [{ time: '오전', title: '입주청소 32평', tone: 'info' }, { time: '오후', title: '에어컨 2대', tone: 'info' }],
  2: [{ time: '오전', title: '사무실 80평', tone: 'purple', highlight: true }, { time: '오전', title: '입주청소 28평', tone: 'info' }, { time: '오후', title: '에어컨 4대', tone: 'warn' }, { time: '오후', title: '준공청소', tone: 'info' }],
  3: [{ time: '오전', title: '이사청소 32평', tone: 'warn' }, { time: '오후', title: '입주청소 45평', tone: 'warn' }],
  4: [{ time: '오전', title: '에어컨 2대', tone: 'info' }],
  5: [{ time: '오후', title: '상가청소', tone: 'info' }],
  7: [{ time: '오전', title: '입주청소 38평', tone: 'success' }, { time: '오후', title: '준공청소', tone: 'info' }],
  8: [{ time: '오전', title: '사무실 정기', tone: 'info' }],
  9: [{ time: '오후', title: '이사청소 24평', tone: 'info' }, { time: '오후', title: '에어컨 3대', tone: 'info' }],
  11: [{ time: '오전', title: '입주청소 50평', tone: 'info' }, { time: '오전', title: '준공청소', tone: 'info' }],
  12: [{ time: '오후', title: '에어컨 6대', tone: 'warn' }],
  14: [{ time: '오전', title: '입주청소 32평', tone: 'success' }, { time: '오후', title: '사무실 60평', tone: 'success' }],
  15: [{ time: '오전', title: '이사청소', tone: 'info' }],
  16: [{ time: '오후', title: '에어컨 2대', tone: 'info' }, { time: '오후', title: '준공청소', tone: 'info' }],
  18: [{ time: '오전', title: '입주청소 45평', tone: 'info' }],
  19: [{ time: '오후', title: '상가청소', tone: 'success' }],
  21: [{ time: '오전', title: '준공청소 60평', tone: 'success' }, { time: '오후', title: '입주청소', tone: 'info' }],
  22: [{ time: '오전', title: '에어컨 4대', tone: 'info' }],
  23: [{ time: '오후', title: '이사청소 28평', tone: 'info' }, { time: '오후', title: '사무실', tone: 'info' }],
  25: [{ time: '오전', title: '입주청소 38평', tone: 'success' }],
  26: [{ time: '오후', title: '에어컨 3대', tone: 'info' }],
  28: [{ time: '오전', title: '준공청소', tone: 'info' }, { time: '오후', title: '입주청소', tone: 'info' }],
  29: [{ time: '오전', title: '사무실 80평', tone: 'info' }],
  30: [{ time: '오후', title: '에어컨 5대', tone: 'warn' }],
};

function CalendarPage() {
  const [view, setView] = React.useState('month'); // month | week
  const [siteOpen, setSiteOpen] = React.useState(true);
  const [selectedSite, setSelectedSite] = React.useState('all');

  // May 2026 starts Friday (day-of-week 5). 31 days.
  const daysInMonth = 31;
  const firstDayOfWeek = 5; // Fri
  const totalCells = Math.ceil((daysInMonth + firstDayOfWeek) / 7) * 7;
  const today = 2;

  const cells = Array.from({ length: totalCells }).map((_, i) => {
    const dayNum = i - firstDayOfWeek + 1;
    if (dayNum < 1 || dayNum > daysInMonth) return { empty: true };
    return { day: dayNum, dow: i % 7, events: CAL_EVENTS[dayNum] || [] };
  });

  return (
    <div style={{ flex: 1, display: 'flex', minHeight: 0, background: 'var(--bg)' }}>
      {/* Site selector */}
      {siteOpen && (
        <aside style={{
          width: 200, flexShrink: 0,
          background: 'var(--surface)',
          borderRight: '1px solid var(--border)',
          display: 'flex', flexDirection: 'column',
        }}>
          <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--divider)', display: 'flex', alignItems: 'center' }}>
            <span style={{ fontSize: 12, fontWeight: 600 }}>현장 선택</span>
            <div style={{ flex: 1 }}/>
            <button onClick={() => setSiteOpen(false)} className="btn btn--ghost btn--sm" style={{ padding: '0 4px' }}>
              <Icon name="x" size={12}/>
            </button>
          </div>
          <div style={{ padding: '8px 10px', borderBottom: '1px solid var(--divider)' }}>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '0 8px', height: 28,
              background: 'var(--bg-subtle)',
              border: '1px solid var(--border)', borderRadius: 6,
              fontSize: 11.5, color: 'var(--text-tertiary)',
            }}>
              <Icon name="search" size={12}/> 현장 검색
            </div>
          </div>
          <div className="scroll" style={{ flex: 1, overflow: 'auto', padding: '6px 0' }}>
            {SITES.map((s) => {
              const active = s.id === selectedSite;
              return (
                <button key={s.id} onClick={() => setSelectedSite(s.id)}
                  style={{
                    width: '100%', textAlign: 'left',
                    padding: '6px 14px',
                    border: 'none', borderLeft: active ? '2px solid var(--brand)' : '2px solid transparent',
                    background: active ? 'var(--brand-bg)' : 'transparent',
                    color: active ? 'var(--brand)' : 'var(--text-secondary)',
                    fontSize: 12, fontWeight: active ? 600 : 500,
                    cursor: 'pointer',
                    display: 'flex', alignItems: 'center', gap: 6,
                  }}>
                  <span style={{ flex: 1 }}>{s.name}</span>
                  <span style={{ fontSize: 10.5, color: active ? 'var(--brand)' : 'var(--text-quaternary)' }}>{s.count}</span>
                </button>
              );
            })}
          </div>
        </aside>
      )}

      {/* Main */}
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {/* Calendar toolbar */}
        <div style={{
          padding: '10px 20px',
          background: 'var(--surface)',
          borderBottom: '1px solid var(--border)',
          display: 'flex', alignItems: 'center', gap: 10,
        }}>
          {!siteOpen && (
            <button onClick={() => setSiteOpen(true)} className="btn btn--ghost btn--sm" style={{ padding: '0 6px' }}>
              <Icon name="list" size={13}/>
            </button>
          )}
          <button className="btn btn--secondary btn--sm">오늘</button>
          <div style={{ display: 'flex' }}>
            <button className="btn btn--ghost btn--sm" style={{ padding: '0 4px' }}><Icon name="chevronLeft" size={13}/></button>
            <button className="btn btn--ghost btn--sm" style={{ padding: '0 4px' }}><Icon name="chevronRight" size={13}/></button>
          </div>
          <h2 style={{ margin: 0, fontSize: 15, fontWeight: 700, letterSpacing: '-0.02em' }}>2026년 5월</h2>
          <span style={{ fontSize: 11.5, color: 'var(--text-tertiary)' }}>
            {selectedSite === 'all' ? '전체 현장' : SITES.find(s => s.id === selectedSite)?.name} · 총 56건
          </span>

          <div style={{ flex: 1 }}/>

          {/* Legend */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 11, color: 'var(--text-tertiary)' }}>
            <Legend tone="warn"    label="대기"/>
            <Legend tone="info"    label="진행"/>
            <Legend tone="success" label="완료"/>
            <Legend tone="purple"  label="작업중"/>
          </div>

          <div style={{ width: 1, height: 18, background: 'var(--border)' }}/>

          {/* View switcher */}
          <div style={{
            display: 'flex',
            background: 'var(--bg-subtle)',
            border: '1px solid var(--border)',
            borderRadius: 6, padding: 2,
          }}>
            {['month', 'week', 'day'].map((v) => (
              <button key={v} onClick={() => setView(v)}
                style={{
                  padding: '0 10px', height: 22,
                  border: 'none', borderRadius: 4,
                  background: view === v ? 'var(--surface)' : 'transparent',
                  color: view === v ? 'var(--text)' : 'var(--text-tertiary)',
                  fontSize: 11.5, fontWeight: view === v ? 600 : 500,
                  cursor: 'pointer',
                  boxShadow: view === v ? 'var(--shadow-xs)' : 'none',
                }}>
                {v === 'month' ? '월' : v === 'week' ? '주' : '일'}
              </button>
            ))}
          </div>

          <button className="btn btn--primary btn--sm">
            <Icon name="plus" size={12}/> 일정 추가
          </button>
        </div>

        {/* Calendar grid */}
        <div className="scroll" style={{ flex: 1, overflow: 'auto', background: 'var(--bg)' }}>
          <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 600 }}>
            {/* Day-of-week header */}
            <div style={{
              display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)',
              borderBottom: '1px solid var(--border)',
              background: 'var(--surface)',
            }}>
              {['일', '월', '화', '수', '목', '금', '토'].map((d, i) => (
                <div key={d} style={{
                  padding: '8px 12px',
                  fontSize: 11, fontWeight: 600,
                  color: i === 0 ? 'var(--danger-fg)' : i === 6 ? 'var(--info-fg)' : 'var(--text-tertiary)',
                  letterSpacing: '0.04em',
                  borderRight: i < 6 ? '1px solid var(--divider)' : 'none',
                }}>{d}</div>
              ))}
            </div>

            {/* Cells */}
            <div style={{
              flex: 1,
              display: 'grid',
              gridTemplateColumns: 'repeat(7, 1fr)',
              gridAutoRows: '1fr',
              minHeight: 0,
            }}>
              {cells.map((c, i) => {
                if (c.empty) return <div key={i} style={{
                  background: 'var(--bg-subtle)',
                  borderRight: i % 7 < 6 ? '1px solid var(--divider)' : 'none',
                  borderBottom: '1px solid var(--divider)',
                }}/>;
                const isToday = c.day === today;
                const isSunday = c.dow === 0;
                const isSaturday = c.dow === 6;
                return (
                  <div key={i} style={{
                    minHeight: 110,
                    padding: 6,
                    background: 'var(--surface)',
                    borderRight: i % 7 < 6 ? '1px solid var(--divider)' : 'none',
                    borderBottom: '1px solid var(--divider)',
                    display: 'flex', flexDirection: 'column', gap: 2,
                    position: 'relative',
                  }}>
                    <div style={{
                      display: 'flex', alignItems: 'center', gap: 4,
                      marginBottom: 2,
                    }}>
                      {isToday ? (
                        <span style={{
                          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                          width: 20, height: 20, borderRadius: '50%',
                          background: 'var(--brand)', color: '#fff',
                          fontSize: 11, fontWeight: 700,
                        }}>{c.day}</span>
                      ) : (
                        <span style={{
                          fontSize: 11.5, fontWeight: 600,
                          color: isSunday ? 'var(--danger-fg)' : isSaturday ? 'var(--info-fg)' : 'var(--text)',
                          paddingLeft: 2,
                        }}>{c.day}</span>
                      )}
                      {c.events.length > 0 && (
                        <span style={{ fontSize: 9.5, color: 'var(--text-quaternary)' }}>· {c.events.length}건</span>
                      )}
                    </div>
                    {c.events.slice(0, 3).map((ev, j) => (
                      <div key={j} style={{
                        padding: '2px 5px',
                        background: ev.highlight ? `var(--${ev.tone}-bg)` : 'transparent',
                        borderLeft: `2px solid var(--${ev.tone}-fg)`,
                        borderRadius: 3,
                        fontSize: 10.5,
                        color: 'var(--text)',
                        display: 'flex', alignItems: 'center', gap: 4,
                        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                        cursor: 'pointer',
                      }}>
                        <span style={{ color: 'var(--text-tertiary)', fontSize: 9.5, flexShrink: 0 }}>{ev.time}</span>
                        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{ev.title}</span>
                      </div>
                    ))}
                    {c.events.length > 3 && (
                      <div style={{ fontSize: 10, color: 'var(--text-tertiary)', padding: '0 5px', cursor: 'pointer' }}>
                        + {c.events.length - 3}건 더보기
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

function Legend({ tone, label }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
      <span style={{ width: 8, height: 8, borderRadius: 2, background: `var(--${tone}-fg)` }}/>
      {label}
    </span>
  );
}

Object.assign(window, { CalendarPage });

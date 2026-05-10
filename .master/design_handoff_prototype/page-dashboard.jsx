// Admin Dashboard — KPI grid + work queues + today/tomorrow + recent

function Dashboard({ onOpenOrder, onNav }) {
  return (
    <div className="scroll" style={{ flex: 1, overflow: 'auto', padding: 20, background: 'var(--bg)' }}>
      <div style={{ maxWidth: 1320, margin: '0 auto' }}>

        {/* Greeting */}
        <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginBottom: 14 }}>
          <div>
            <div style={{ fontSize: 11.5, color: 'var(--text-tertiary)', marginBottom: 2 }}>2026년 5월 2일 토요일 · 오전 9:14</div>
            <h2 style={{ margin: 0, fontSize: 18, fontWeight: 600, letterSpacing: '-0.02em' }}>
              안녕하세요 전소영님 <span style={{ color: 'var(--text-tertiary)', fontWeight: 400 }}>— 오늘 처리할 일 12건이 있습니다</span>
            </h2>
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            <button className="btn btn--secondary btn--sm">
              <Icon name="refresh" size={12}/> 새로고침
            </button>
            <button className="btn btn--primary btn--sm">
              <Icon name="plus" size={12}/> 신규 주문 등록
            </button>
          </div>
        </div>

        {/* KPI grid — 7 cards in one row, last one wider */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 10, marginBottom: 16 }}>
          {KPI.map((k, i) => (
            <div key={i} className="card" style={{ padding: 12, position: 'relative', overflow: 'hidden' }}>
              <div style={{ fontSize: 11.5, color: 'var(--text-tertiary)', fontWeight: 500, letterSpacing: '-0.005em' }}>{k.label}</div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginTop: 4 }}>
                <span style={{ fontSize: 22, fontWeight: 600, letterSpacing: '-0.03em', color: 'var(--text)' }}>{k.value}</span>
                {k.suffix && <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{k.suffix}</span>}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 6 }}>
                <span style={{
                  fontSize: 10.5, fontWeight: 600,
                  color: k.delta.startsWith('+') ? 'var(--success-fg)' : k.delta.startsWith('-') ? 'var(--danger-fg)' : 'var(--text-tertiary)',
                }}>{k.delta}</span>
                <Sparkline values={k.trend} color={`var(--${k.tone === 'brand' ? 'brand' : k.tone === 'success' ? 'success-fg' : k.tone === 'danger' ? 'danger-fg' : k.tone === 'warn' ? 'warn-fg' : k.tone === 'purple' ? 'purple-fg' : 'info-fg'})`} width={50} height={18}/>
              </div>
            </div>
          ))}
        </div>

        {/* Work queues */}
        <div style={{ marginBottom: 18 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 8 }}>
            <h3 style={{ margin: 0, fontSize: 13, fontWeight: 600, letterSpacing: '-0.01em' }}>업무 큐</h3>
            <span style={{ fontSize: 11.5, color: 'var(--text-tertiary)' }}>클릭하면 해당 필터로 이동합니다</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 10 }}>
            {QUEUES.map((q) => (
              <button key={q.key} onClick={() => onNav && onNav('orders')}
                className="card"
                style={{
                  padding: 12, textAlign: 'left', cursor: 'pointer',
                  border: '1px solid var(--border)',
                  background: 'var(--surface)',
                  display: 'flex', flexDirection: 'column', gap: 8,
                  transition: 'all 100ms',
                }}
                onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'var(--brand)'; e.currentTarget.style.boxShadow = 'var(--shadow-sm)'; }}
                onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.boxShadow = 'none'; }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{
                    width: 24, height: 24, borderRadius: 5,
                    background: `var(--${q.tone}-bg)`, color: `var(--${q.tone}-fg)`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}>
                    <Icon name={q.icon} size={13}/>
                  </span>
                  <Icon name="arrowRight" size={12} color="var(--text-quaternary)"/>
                </div>
                <div>
                  <div style={{ fontSize: 11.5, color: 'var(--text-tertiary)', fontWeight: 500 }}>{q.title}</div>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginTop: 2 }}>
                    <span style={{ fontSize: 22, fontWeight: 600, letterSpacing: '-0.03em' }}>{q.count}</span>
                    <span style={{ fontSize: 11, color: 'var(--text-quaternary)' }}>건</span>
                  </div>
                </div>
                <div style={{ fontSize: 10.5, color: 'var(--text-quaternary)' }}>{q.desc}</div>
              </button>
            ))}
          </div>
        </div>

        {/* 2-column: today/tomorrow + photos/sends */}
        <div style={{ display: 'grid', gridTemplateColumns: '1.55fr 1fr', gap: 12 }}>
          {/* Today + tomorrow */}
          <div className="card" style={{ overflow: 'hidden' }}>
            <DashList title="오늘 작업" subtitle="5월 2일 · 5건" jobs={TODAY_JOBS} onOpen={onOpenOrder} accent="info"/>
            <div style={{ height: 1, background: 'var(--divider)' }}/>
            <DashList title="내일 작업" subtitle="5월 3일 · 3건" jobs={TOMORROW_JOBS} onOpen={onOpenOrder} accent="warn" muted/>
          </div>

          {/* Recent photos + sends */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div className="card" style={{ padding: 0 }}>
              <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--divider)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Icon name="image" size={13} color="var(--text-tertiary)"/>
                  <span style={{ fontSize: 12.5, fontWeight: 600 }}>최근 사진 업로드</span>
                </div>
                <button className="btn btn--ghost btn--sm" style={{ height: 22, padding: '0 6px', fontSize: 11 }}>전체 보기</button>
              </div>
              <div>
                {RECENT_PHOTOS.map((p, i) => (
                  <div key={i} style={{
                    display: 'flex', alignItems: 'center', gap: 10,
                    padding: '8px 14px',
                    borderBottom: i < RECENT_PHOTOS.length - 1 ? '1px solid var(--divider)' : 'none',
                  }}>
                    <div className="placeholder-img" style={{ width: 36, height: 36, fontSize: 9, flexShrink: 0 }}>IMG</div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 12, fontWeight: 500, display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-tertiary)' }}>{p.id}</span>
                        {p.label}
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 1 }}>{p.count} · {p.time}</div>
                    </div>
                    {p.tone === 'wait' && <Badge tone="warn" dot>검수대기</Badge>}
                    {p.tone === 'approved' && <Badge tone="success" dot>승인</Badge>}
                    {p.tone === 'partial' && <Badge tone="info" dot>업로드중</Badge>}
                  </div>
                ))}
              </div>
            </div>

            <div className="card" style={{ padding: 0 }}>
              <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--divider)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Icon name="send" size={13} color="var(--text-tertiary)"/>
                  <span style={{ fontSize: 12.5, fontWeight: 600 }}>최근 발송 이력</span>
                </div>
                <button className="btn btn--ghost btn--sm" style={{ height: 22, padding: '0 6px', fontSize: 11 }}>전체 보기</button>
              </div>
              <div>
                {RECENT_SENDS.map((s, i) => (
                  <div key={i} style={{
                    display: 'flex', alignItems: 'center', gap: 10,
                    padding: '7px 14px',
                    borderBottom: i < RECENT_SENDS.length - 1 ? '1px solid var(--divider)' : 'none',
                    fontSize: 12,
                  }}>
                    <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-tertiary)', width: 36 }}>{s.time}</span>
                    <span style={{ minWidth: 64, fontSize: 11, color: 'var(--text-secondary)' }}>{s.kind}</span>
                    <span style={{ flex: 1, color: 'var(--text)', overflow: 'hidden', textOverflow: 'ellipsis' }}>{s.target}</span>
                    <span style={{ fontSize: 10.5, color: 'var(--text-tertiary)' }}>{s.via}</span>
                    {s.state === 'delivered' && <Badge tone="success">전송</Badge>}
                    {s.state === 'read' && <Badge tone="info">읽음</Badge>}
                    {s.state === 'failed' && <Badge tone="danger">실패</Badge>}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function DashList({ title, subtitle, jobs, onOpen, accent, muted }) {
  return (
    <div>
      <div style={{ padding: '10px 14px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--divider)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: `var(--${accent}-fg)` }}/>
          <span style={{ fontSize: 12.5, fontWeight: 600 }}>{title}</span>
          <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{subtitle}</span>
        </div>
        <button className="btn btn--ghost btn--sm" style={{ height: 22, padding: '0 6px', fontSize: 11 }}>일정표</button>
      </div>
      <div>
        {jobs.map((j, i) => (
          <button key={j.id} onClick={() => onOpen && onOpen(j.id)}
            style={{
              width: '100%', textAlign: 'left',
              display: 'grid', gridTemplateColumns: '60px 80px 1fr 110px 90px',
              alignItems: 'center', gap: 10,
              padding: '7px 14px',
              border: 'none',
              borderBottom: i < jobs.length - 1 ? '1px solid var(--divider)' : 'none',
              background: muted ? 'var(--bg-subtle)' : 'transparent',
              cursor: 'pointer',
              fontSize: 12.5,
              opacity: muted ? 0.92 : 1,
            }}>
            <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-tertiary)' }}>{j.id}</span>
            <span style={{ fontSize: 11.5, color: 'var(--text-secondary)' }}>{j.time}</span>
            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              <span style={{ fontWeight: 500 }}>{j.product}</span>
              <span style={{ color: 'var(--text-tertiary)', marginLeft: 8, fontSize: 11.5 }}>{j.addr}</span>
            </span>
            <span style={{ fontSize: 11.5, color: 'var(--text-secondary)' }}>{j.team}</span>
            <StatusBadge status={j.status}/>
          </button>
        ))}
      </div>
    </div>
  );
}

Object.assign(window, { Dashboard });

// Photo review — left list of waiting orders, center before/after compare, right approval flow

const REVIEW_QUEUE = [
  { id: 'CO-2450', product: '에어컨 분해세척 4대', customer: '이서연', team: '클린파트너스', uploaded: '5분 전', counts: '8 / 8', active: true },
  { id: 'CO-2448', product: '사무실 정기청소 80평', customer: '㈜노바테크', team: '청소플러스', uploaded: '32분 전', counts: '12 / 0', partial: true },
  { id: 'CO-2438', product: '입주청소 38평', customer: '한서윤', team: '클린파트너스', uploaded: '1시간 전', counts: '6 / 6' },
  { id: 'CO-2435', product: '준공청소 상가', customer: '메르시', team: '하우스케어', uploaded: '2시간 전', counts: '12 / 14' },
  { id: 'CO-2431', product: '에어컨 분해세척 2대', customer: '강도윤', team: '청소플러스', uploaded: '3시간 전', counts: '4 / 4' },
  { id: 'CO-2429', product: '이사청소 32평', customer: '오세영', team: '하우스케어', uploaded: '5시간 전', counts: '8 / 8' },
];

function PhotoReviewPage() {
  const [selectedIdx, setSelectedIdx] = React.useState(0);
  const [active, setActive] = React.useState(0);
  const [approved, setApproved] = React.useState(new Set([0, 1, 2, 4, 5, 7]));
  const [rejected, setRejected] = React.useState(new Set([3]));

  const selected = REVIEW_QUEUE[selectedIdx];

  const toggle = (set, setter, i) => {
    const next = new Set(set);
    if (next.has(i)) next.delete(i); else next.add(i);
    setter(next);
  };

  const photos = Array.from({ length: 8 }).map((_, i) => ({ idx: i }));

  return (
    <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '260px 1fr 300px', minHeight: 0, background: 'var(--bg)' }}>
      {/* Queue list */}
      <aside style={{ background: 'var(--surface)', borderRight: '1px solid var(--border)', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--divider)', display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 12.5, fontWeight: 600 }}>검수 대기</span>
          <Badge tone="warn">{REVIEW_QUEUE.length}</Badge>
          <div style={{ flex: 1 }}/>
          <button className="btn btn--ghost btn--sm" style={{ padding: '0 4px' }}>
            <Icon name="filter" size={12}/>
          </button>
        </div>
        <div className="scroll" style={{ flex: 1, overflow: 'auto' }}>
          {REVIEW_QUEUE.map((q, i) => {
            const isActive = i === selectedIdx;
            return (
              <button key={q.id} onClick={() => setSelectedIdx(i)}
                style={{
                  display: 'block', width: '100%', textAlign: 'left',
                  padding: '10px 14px',
                  border: 'none',
                  borderBottom: '1px solid var(--divider)',
                  borderLeft: isActive ? '2px solid var(--brand)' : '2px solid transparent',
                  background: isActive ? 'var(--brand-bg)' : 'transparent',
                  cursor: 'pointer',
                }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
                  <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-tertiary)' }}>{q.id}</span>
                  {q.partial && <Badge tone="info">진행중</Badge>}
                </div>
                <div style={{ fontSize: 12, fontWeight: 500, marginBottom: 2 }}>{q.product}</div>
                <div style={{ fontSize: 11, color: 'var(--text-tertiary)', display: 'flex', justifyContent: 'space-between' }}>
                  <span>{q.customer} · {q.team}</span>
                  <span className="mono">{q.counts}</span>
                </div>
                <div style={{ fontSize: 10.5, color: 'var(--text-quaternary)', marginTop: 2 }}>업로드 {q.uploaded}</div>
              </button>
            );
          })}
        </div>
      </aside>

      {/* Center — compare */}
      <main style={{ display: 'flex', flexDirection: 'column', minHeight: 0, background: 'var(--bg-subtle)' }}>
        <div style={{ padding: '10px 16px', background: 'var(--surface)', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 10 }}>
          <span className="mono" style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>{selected.id}</span>
          <span style={{ fontSize: 13, fontWeight: 600 }}>{selected.product}</span>
          <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>· {selected.customer} · {selected.team}</span>
          <div style={{ flex: 1 }}/>
          <span style={{ fontSize: 11.5, color: 'var(--text-tertiary)' }}>
            승인 <span style={{ color: 'var(--success-fg)', fontWeight: 600 }}>{approved.size}</span> / 보류 <span style={{ color: 'var(--danger-fg)', fontWeight: 600 }}>{rejected.size}</span> / 미정 <span style={{ fontWeight: 600 }}>{photos.length * 2 - approved.size - rejected.size}</span>
          </span>
          <button className="btn btn--ghost btn--sm" style={{ padding: '0 6px' }}>
            <Icon name="grid" size={12}/>
          </button>
        </div>

        {/* Big compare */}
        <div style={{ flex: 1, padding: 20, display: 'flex', flexDirection: 'column', gap: 12, minHeight: 0 }}>
          <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, minHeight: 0 }}>
            <ComparePane label="비포" idx={active} placeholder={`B-${active + 1}`} approved={approved.has(active)} rejected={rejected.has(active)} onApprove={() => toggle(approved, setApproved, active)} onReject={() => toggle(rejected, setRejected, active)}/>
            <ComparePane label="애프터" idx={active} placeholder={`A-${active + 1}`} approved={approved.has(active + 8)} rejected={rejected.has(active + 8)} onApprove={() => toggle(approved, setApproved, active + 8)} onReject={() => toggle(rejected, setRejected, active + 8)} after/>
          </div>

          {/* Thumbs strip */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
              <span style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 600 }}>장면 {active + 1} / 8</span>
              <div style={{ flex: 1 }}/>
              <button className="btn btn--ghost btn--sm" onClick={() => setActive(Math.max(0, active - 1))} style={{ padding: '0 6px' }}>
                <Icon name="chevronLeft" size={12}/>
              </button>
              <button className="btn btn--ghost btn--sm" onClick={() => setActive(Math.min(7, active + 1))} style={{ padding: '0 6px' }}>
                <Icon name="chevronRight" size={12}/>
              </button>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(8, 1fr)', gap: 6 }}>
              {photos.map((_, i) => {
                const isActive = i === active;
                const aprB = approved.has(i), aprA = approved.has(i + 8);
                const rejB = rejected.has(i), rejA = rejected.has(i + 8);
                return (
                  <button key={i} onClick={() => setActive(i)}
                    style={{
                      padding: 0, border: isActive ? '2px solid var(--brand)' : '2px solid transparent',
                      borderRadius: 6, background: 'transparent', cursor: 'pointer', position: 'relative',
                    }}>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1, borderRadius: 4, overflow: 'hidden', background: 'var(--border)' }}>
                      <div className="placeholder-img" style={{ aspectRatio: '1', fontSize: 9, borderRadius: 0, border: 'none' }}>B-{i + 1}</div>
                      <div className="placeholder-img" style={{ aspectRatio: '1', fontSize: 9, borderRadius: 0, border: 'none' }}>A-{i + 1}</div>
                    </div>
                    <div style={{ position: 'absolute', top: 2, right: 2, display: 'flex', gap: 1 }}>
                      {(aprB && aprA) && <span style={{ width: 8, height: 8, borderRadius: 2, background: 'var(--success-fg)' }}/>}
                      {(rejB || rejA) && <span style={{ width: 8, height: 8, borderRadius: 2, background: 'var(--danger-fg)' }}/>}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </main>

      {/* Right — approval */}
      <aside style={{ background: 'var(--surface)', borderLeft: '1px solid var(--border)', display: 'flex', flexDirection: 'column', overflow: 'auto' }}>
        <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--divider)' }}>
          <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 600, letterSpacing: '0.04em', marginBottom: 6 }}>주문 정보</div>
          <KVStack>
            <KVRow label="고객" value="이서연 / 010-7***-1129"/>
            <KVRow label="방문일" value="5월 2일 · 오후 2-5시"/>
            <KVRow label="주소" value="서울 마포구 와우산로 88 1102호" small/>
            <KVRow label="협력사" value="클린파트너스 박정훈"/>
          </KVStack>
        </div>

        <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--divider)' }}>
          <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 600, letterSpacing: '0.04em', marginBottom: 6 }}>협력사 메모</div>
          <div style={{
            fontSize: 12, lineHeight: 1.5, color: 'var(--text-secondary)',
            padding: 10, background: 'var(--bg-subtle)', borderRadius: 6,
          }}>
            스탠드 1대 필터 교체 권장 (별도 비용 안내드림). 베란다 새시 곰팡이 따로 견적 필요할 것 같습니다. 송풍 시 약간의 곰팡이 냄새가 남아있어 24시간 후 환기 안내 부탁드립니다.
          </div>
        </div>

        <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--divider)' }}>
          <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 600, letterSpacing: '0.04em', marginBottom: 6 }}>관리자 메모 (내부)</div>
          <textarea
            placeholder="검수 코멘트, 재촬영 요청 사유 등..."
            style={{
              width: '100%', minHeight: 60, padding: 8,
              border: '1px solid var(--border)', borderRadius: 6,
              fontSize: 12, fontFamily: 'inherit', resize: 'vertical',
              background: 'var(--surface)',
            }}/>
        </div>

        <div style={{ flex: 1 }}/>

        <div style={{ padding: 14, borderTop: '1px solid var(--divider)', display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{
            padding: 10, marginBottom: 4,
            background: 'var(--brand-bg)',
            border: '1px solid var(--brand-bg-hover)',
            borderRadius: 6,
            fontSize: 11.5, color: 'var(--text-secondary)',
          }}>
            <div style={{ fontWeight: 600, color: 'var(--brand)', marginBottom: 2 }}>승인 후 자동 처리</div>
            승인된 사진만 고객 페이지에 노출됩니다. 고객 전달 링크가 알림톡으로 발송됩니다.
          </div>
          <button className="btn btn--primary btn--block btn--lg">
            <Icon name="check" size={14}/> 모두 승인 + 고객 전달
          </button>
          <button className="btn btn--secondary btn--block">
            <Icon name="eye" size={13}/> 선택 항목만 공개
          </button>
          <button className="btn btn--danger btn--block">
            <Icon name="refresh" size={13}/> 재촬영 요청
          </button>
        </div>
      </aside>
    </div>
  );
}

function ComparePane({ label, idx, placeholder, approved, rejected, onApprove, onReject, after }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '6px 10px',
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderTopLeftRadius: 8, borderTopRightRadius: 8,
        borderBottom: 'none',
      }}>
        <Badge tone={after ? 'success' : 'neutral'} dot>{label}</Badge>
        <span style={{ fontSize: 11.5, color: 'var(--text-tertiary)' }}>장면 {idx + 1}</span>
        <div style={{ flex: 1 }}/>
        {approved && <Badge tone="success" dot>승인</Badge>}
        {rejected && <Badge tone="danger" dot>보류</Badge>}
        <button onClick={onApprove} className="btn btn--ghost btn--sm" style={{ height: 22, padding: '0 6px', color: approved ? 'var(--success-fg)' : 'var(--text-tertiary)' }}>
          <Icon name="check" size={12}/>
        </button>
        <button onClick={onReject} className="btn btn--ghost btn--sm" style={{ height: 22, padding: '0 6px', color: rejected ? 'var(--danger-fg)' : 'var(--text-tertiary)' }}>
          <Icon name="x" size={12}/>
        </button>
      </div>
      <div className="placeholder-img" style={{
        flex: 1, minHeight: 0,
        borderTopLeftRadius: 0, borderTopRightRadius: 0,
        fontSize: 14, fontWeight: 500,
      }}>
        {placeholder}
      </div>
    </div>
  );
}

function KVStack({ children }) {
  return <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>{children}</div>;
}
function KVRow({ label, value, small }) {
  return (
    <div style={{ display: 'flex', gap: 8, fontSize: small ? 11.5 : 12 }}>
      <span style={{ width: 50, color: 'var(--text-tertiary)', flexShrink: 0 }}>{label}</span>
      <span style={{ flex: 1, color: 'var(--text)' }}>{value}</span>
    </div>
  );
}

Object.assign(window, { PhotoReviewPage });

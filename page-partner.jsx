// Partner mobile — job detail + photo upload (single screen, mobile-first)

function PartnerJobDetail() {
  const [tab, setTab] = React.useState('today');
  const [phase, setPhase] = React.useState('uploading'); // notStarted, inProgress, uploading, done
  const [befores, setBefores] = React.useState([1, 2, 3, 4, 5]);
  const [afters, setAfters] = React.useState([1, 2, 3]);
  const [uploadingIdx, setUploadingIdx] = React.useState(2);

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: '#f4f6f8', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{
        padding: '12px 16px 10px',
        background: '#fff',
        borderBottom: '1px solid var(--border)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <button style={{ padding: 0, border: 'none', background: 'transparent', cursor: 'pointer' }}>
            <Icon name="chevronLeft" size={20}/>
          </button>
          <span className="mono" style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>CO-2450</span>
          <StatusBadge status="작업진행"/>
          <div style={{ flex: 1 }}/>
          <button style={{ padding: 4, border: 'none', background: 'transparent' }}>
            <Icon name="moreHorizontal" size={18}/>
          </button>
        </div>
        <h2 style={{ margin: 0, fontSize: 17, fontWeight: 700, letterSpacing: '-0.02em' }}>에어컨 분해세척 4대</h2>
        <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginTop: 2 }}>벽걸이 2대 + 스탠드 2대</div>
      </div>

      {/* Body */}
      <div className="scroll" style={{ flex: 1, overflow: 'auto', padding: 12 }}>
        {/* Quick info card */}
        <div style={{
          background: '#fff', borderRadius: 10, padding: 14, marginBottom: 10,
          border: '1px solid var(--border)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10, paddingBottom: 10, borderBottom: '1px solid var(--divider)' }}>
            <span style={{ width: 32, height: 32, borderRadius: 8, background: 'var(--info-bg)', color: 'var(--info-fg)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Icon name="calendar" size={16}/>
            </span>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 14, fontWeight: 700 }}>5월 2일 토요일</div>
              <div style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>오후 2시 - 5시</div>
            </div>
            <Badge tone="warn" dot>오늘</Badge>
          </div>

          <div style={{ display: 'flex', gap: 10, marginBottom: 10 }}>
            <span style={{ width: 16, marginTop: 2 }}><Icon name="mapPin" size={14} color="var(--text-tertiary)"/></span>
            <div style={{ flex: 1, fontSize: 13, lineHeight: 1.5 }}>
              서울 마포구 와우산로 88<br/>
              <span style={{ color: 'var(--text-tertiary)' }}>합정스카이뷰 1102호</span>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
            <button style={{
              height: 36, border: '1px solid var(--border)', borderRadius: 8,
              background: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5,
              fontSize: 12.5, fontWeight: 500,
            }}>
              <Icon name="mapPin" size={14} color="var(--brand)"/> 지도 열기
            </button>
            <button style={{
              height: 36, border: '1px solid var(--border)', borderRadius: 8,
              background: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5,
              fontSize: 12.5, fontWeight: 500,
            }}>
              <Icon name="phone" size={14} color="var(--success-fg)"/> 고객 전화
            </button>
          </div>
        </div>

        {/* Customer + request */}
        <div style={{ background: '#fff', borderRadius: 10, padding: 14, marginBottom: 10, border: '1px solid var(--border)' }}>
          <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 600, letterSpacing: '0.04em', marginBottom: 6 }}>고객</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <Avatar name="이" size={28} tone="brand"/>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13.5, fontWeight: 600 }}>이서연 님</div>
              <div className="mono" style={{ fontSize: 11.5, color: 'var(--text-tertiary)' }}>010-7***-1129</div>
            </div>
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 600, letterSpacing: '0.04em', marginBottom: 6 }}>특별 요청</div>
          <div style={{
            padding: 10, background: 'var(--warn-bg)', border: '1px solid var(--warn-border)',
            borderRadius: 8, fontSize: 12.5, lineHeight: 1.5, color: '#78350f',
          }}>
            🐶 강아지 있음 · 베란다 곰팡이 심함 · 오후 2시 이후 방문 가능
          </div>
        </div>

        {/* Photos */}
        <div style={{ background: '#fff', borderRadius: 10, padding: 14, marginBottom: 10, border: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <span style={{ fontSize: 13, fontWeight: 600 }}>비포 사진</span>
            <Badge tone="neutral">{befores.length}장</Badge>
            <div style={{ flex: 1 }}/>
            <button style={{
              height: 26, padding: '0 10px', border: 'none', borderRadius: 6,
              background: 'var(--brand-bg)', color: 'var(--brand)',
              fontSize: 12, fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 4,
            }}>
              <Icon name="plus" size={12}/> 추가
            </button>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 6 }}>
            {befores.map((b, i) => (
              <div key={i} className="placeholder-img" style={{ aspectRatio: '1', fontSize: 9, position: 'relative' }}>
                B-{b}
                <span style={{ position: 'absolute', top: 3, right: 3, width: 14, height: 14, borderRadius: '50%', background: 'rgba(0,0,0,0.6)', color: '#fff', fontSize: 9, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>×</span>
              </div>
            ))}
            <button onClick={() => setBefores([...befores, befores.length + 1])} style={{
              aspectRatio: '1', border: '1.5px dashed var(--border-strong)', borderRadius: 6,
              background: 'var(--bg-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'center',
              cursor: 'pointer', flexDirection: 'column', gap: 2, color: 'var(--text-tertiary)',
            }}>
              <Icon name="camera" size={16}/>
              <span style={{ fontSize: 9.5 }}>촬영</span>
            </button>
          </div>
        </div>

        <div style={{ background: '#fff', borderRadius: 10, padding: 14, marginBottom: 10, border: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <span style={{ fontSize: 13, fontWeight: 600 }}>애프터 사진</span>
            <Badge tone="success">{afters.length}장</Badge>
            <div style={{ flex: 1 }}/>
            <button style={{
              height: 26, padding: '0 10px', border: 'none', borderRadius: 6,
              background: 'var(--success-bg)', color: 'var(--success-fg)',
              fontSize: 12, fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 4,
            }}>
              <Icon name="plus" size={12}/> 추가
            </button>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 6 }}>
            {afters.map((a, i) => (
              <div key={i} className="placeholder-img" style={{ aspectRatio: '1', fontSize: 9 }}>A-{a}</div>
            ))}
            {/* uploading state */}
            <div className="placeholder-img" style={{ aspectRatio: '1', fontSize: 9, position: 'relative', overflow: 'hidden' }}>
              A-{uploadingIdx + 2}
              <div style={{
                position: 'absolute', inset: 0, background: 'rgba(15, 23, 42, 0.5)',
                display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 3,
              }}>
                <span style={{ fontSize: 9, color: '#fff', fontWeight: 600 }}>62%</span>
                <div style={{ width: 36, height: 3, background: 'rgba(255,255,255,0.3)', borderRadius: 2, overflow: 'hidden' }}>
                  <div style={{ width: '62%', height: '100%', background: '#fff' }}/>
                </div>
              </div>
            </div>
            <button style={{
              aspectRatio: '1', border: '1.5px dashed var(--border-strong)', borderRadius: 6,
              background: 'var(--bg-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'center',
              cursor: 'pointer', flexDirection: 'column', gap: 2, color: 'var(--text-tertiary)',
            }}>
              <Icon name="camera" size={16}/>
              <span style={{ fontSize: 9.5 }}>촬영</span>
            </button>
          </div>
        </div>

        {/* Memo */}
        <div style={{ background: '#fff', borderRadius: 10, padding: 14, marginBottom: 10, border: '1px solid var(--border)' }}>
          <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 600, letterSpacing: '0.04em', marginBottom: 6 }}>작업 메모</div>
          <textarea
            defaultValue="스탠드 1대 필터 교체 권장 (별도 비용 안내드림)."
            style={{
              width: '100%', minHeight: 64, padding: 10,
              border: '1px solid var(--border)', borderRadius: 8,
              fontSize: 13, fontFamily: 'inherit', resize: 'none',
              background: 'var(--bg-subtle)',
            }}/>
        </div>
      </div>

      {/* Sticky bottom CTA */}
      <div style={{
        padding: '10px 14px 12px',
        background: '#fff',
        borderTop: '1px solid var(--border)',
        boxShadow: '0 -4px 12px rgba(15,23,42,0.04)',
      }}>
        <button style={{
          width: '100%', height: 46,
          background: 'var(--brand)', color: '#fff', border: 'none',
          borderRadius: 10, fontSize: 14.5, fontWeight: 700,
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
          cursor: 'pointer',
        }}>
          <Icon name="check" size={16}/> 작업 완료 처리
        </button>
        <div style={{ textAlign: 'center', fontSize: 10.5, color: 'var(--text-tertiary)', marginTop: 6 }}>
          완료 처리 시 관리자에게 사진 검수 요청이 자동 발송됩니다
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { PartnerJobDetail });

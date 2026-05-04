// Customer reservation page — premium, trustworthy, mobile-first

function CustomerReservation() {
  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: '#f7f6f3', overflow: 'hidden', fontFamily: 'var(--font)' }}>
      {/* Brand header */}
      <div style={{
        padding: '18px 20px 14px',
        background: 'linear-gradient(180deg, #ffffff 0%, #f7f6f3 100%)',
        borderBottom: '1px solid rgba(15,23,42,0.06)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{
            width: 28, height: 28, borderRadius: 7,
            background: '#0f172a', color: '#fff',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 13, fontWeight: 700, letterSpacing: '-0.04em',
          }}>C</div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, letterSpacing: '-0.01em' }}>클린오피스 코리아</div>
            <div style={{ fontSize: 10.5, color: '#64748b' }}>cleanops.kr · 1588-2480</div>
          </div>
        </div>
      </div>

      <div className="scroll" style={{ flex: 1, overflow: 'auto' }}>
        {/* Hero */}
        <div style={{ padding: '24px 20px 16px' }}>
          <div style={{ fontSize: 11.5, color: '#64748b', letterSpacing: '0.04em', fontWeight: 600, marginBottom: 6 }}>예약이 확정되었습니다</div>
          <h1 style={{ margin: 0, fontSize: 22, fontWeight: 700, letterSpacing: '-0.025em', lineHeight: 1.3 }}>
            이서연 님,<br/>
            <span style={{ color: '#475569', fontWeight: 500 }}>5월 2일 오후 방문 예정입니다.</span>
          </h1>

          <div style={{ display: 'flex', gap: 6, marginTop: 14 }}>
            <Badge tone="success" dot>일정 확정</Badge>
            <Badge tone="brand">에어컨 분해세척 4대</Badge>
          </div>
        </div>

        {/* Visit detail card */}
        <div style={{ padding: '0 16px' }}>
          <div style={{
            background: '#fff', borderRadius: 14,
            border: '1px solid rgba(15,23,42,0.06)',
            boxShadow: '0 1px 3px rgba(15,23,42,0.04), 0 4px 12px rgba(15,23,42,0.04)',
            overflow: 'hidden',
          }}>
            <div style={{ padding: '16px 18px', borderBottom: '1px solid #f1f5f4' }}>
              <div style={{ fontSize: 10.5, color: '#94a3b8', fontWeight: 600, letterSpacing: '0.06em', marginBottom: 4 }}>방문 일시</div>
              <div style={{ fontSize: 18, fontWeight: 700, letterSpacing: '-0.02em' }}>2026년 5월 2일 토요일</div>
              <div style={{ fontSize: 13, color: '#475569', marginTop: 2 }}>오후 2시 - 5시 (3시간 소요 예상)</div>
            </div>

            <CustRow icon="mapPin" label="방문지">
              서울 마포구 와우산로 88<br/>
              <span style={{ color: '#64748b', fontSize: 12 }}>합정스카이뷰 1102호</span>
            </CustRow>
            <CustRow icon="package" label="서비스">
              에어컨 분해세척<br/>
              <span style={{ color: '#64748b', fontSize: 12 }}>벽걸이 2대 + 스탠드 2대</span>
            </CustRow>
            <CustRow icon="user" label="담당">
              클린파트너스 박정훈 팀장<br/>
              <span style={{ color: '#64748b', fontSize: 12 }}>15년 경력 · 평점 4.9</span>
            </CustRow>
            <CustRow icon="creditCard" label="결제" last>
              <span style={{ fontWeight: 600 }}>320,000원</span>
              <span style={{ color: '#64748b', fontSize: 12 }}> · 계약금 100,000원 입금완료</span><br/>
              <span style={{ color: '#94a3b8', fontSize: 11.5 }}>잔금 220,000원은 작업 완료 후 안내드립니다</span>
            </CustRow>
          </div>
        </div>

        {/* Notice */}
        <div style={{ padding: '16px 16px 8px' }}>
          <div style={{
            background: '#fffaeb', border: '1px solid #fde68a',
            borderRadius: 12, padding: '12px 14px',
          }}>
            <div style={{ fontSize: 11, color: '#b45309', fontWeight: 700, letterSpacing: '0.04em', marginBottom: 6, display: 'flex', alignItems: 'center', gap: 4 }}>
              <Icon name="bell" size={11}/> 방문 전 안내
            </div>
            <ul style={{ margin: 0, padding: '0 0 0 16px', fontSize: 12.5, color: '#78350f', lineHeight: 1.6 }}>
              <li>에어컨 주변 가구는 사전에 이동 부탁드립니다</li>
              <li>작업 중 약 1-2시간 정도 소음이 발생합니다</li>
              <li>작업 완료 후 첫 가동 시 24시간 환기를 권장드립니다</li>
            </ul>
          </div>
        </div>

        {/* Photos placeholder */}
        <div style={{ padding: '12px 16px 24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
            <span style={{ fontSize: 13, fontWeight: 700 }}>작업 완료 사진</span>
            <Badge tone="neutral">대기중</Badge>
          </div>
          <div style={{
            background: '#fff', borderRadius: 12,
            border: '1px dashed #d4d9e1',
            padding: '32px 20px', textAlign: 'center',
          }}>
            <div style={{
              width: 40, height: 40, borderRadius: 10,
              background: '#f1f5f4', color: '#94a3b8',
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              marginBottom: 8,
            }}>
              <Icon name="camera" size={18}/>
            </div>
            <div style={{ fontSize: 13, color: '#475569', fontWeight: 500, marginBottom: 2 }}>
              작업 완료 후 비포 / 애프터 사진이 이곳에 표시됩니다
            </div>
            <div style={{ fontSize: 11.5, color: '#94a3b8' }}>
              담당자가 검수한 사진만 공개됩니다
            </div>
          </div>
        </div>

        {/* Trust footer */}
        <div style={{ padding: '0 16px 24px' }}>
          <div style={{
            display: 'grid', gridTemplateColumns: '1fr 1fr 1fr',
            gap: 8, padding: '14px 4px',
            borderTop: '1px solid rgba(15,23,42,0.06)',
            borderBottom: '1px solid rgba(15,23,42,0.06)',
          }}>
            {[
              { icon: 'shield', label: '책임보험', sub: '5억원' },
              { icon: 'star', label: '평균 평점', sub: '4.86 / 5' },
              { icon: 'sparkles', label: '재시공', sub: '7일 무상' },
            ].map((t, i) => (
              <div key={i} style={{ textAlign: 'center' }}>
                <div style={{ display: 'inline-flex', color: '#475569', marginBottom: 4 }}>
                  <Icon name={t.icon} size={14}/>
                </div>
                <div style={{ fontSize: 10.5, color: '#94a3b8', fontWeight: 500 }}>{t.label}</div>
                <div style={{ fontSize: 12, fontWeight: 600 }}>{t.sub}</div>
              </div>
            ))}
          </div>

          <div style={{ display: 'flex', gap: 6, marginTop: 14 }}>
            <button style={{
              flex: 1, height: 42, borderRadius: 10,
              background: '#0f172a', color: '#fff', border: 'none',
              fontSize: 13, fontWeight: 600,
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
            }}>
              <Icon name="phone" size={14}/> 1588-2480
            </button>
            <button style={{
              flex: 1, height: 42, borderRadius: 10,
              background: '#fff', color: '#0f172a',
              border: '1px solid #d4d9e1',
              fontSize: 13, fontWeight: 600,
            }}>
              일정 변경 문의
            </button>
          </div>

          <div style={{ textAlign: 'center', fontSize: 10.5, color: '#94a3b8', marginTop: 16, lineHeight: 1.5 }}>
            본 페이지는 예약 고객 전용 링크입니다.<br/>
            연락처 뒷자리 4자리 인증으로 보호됩니다.
          </div>
        </div>
      </div>
    </div>
  );
}

function CustRow({ icon, label, children, last }) {
  return (
    <div style={{
      display: 'flex', gap: 12, padding: '12px 18px',
      borderBottom: last ? 'none' : '1px solid #f1f5f4',
    }}>
      <span style={{
        width: 28, height: 28, borderRadius: 7, flexShrink: 0,
        background: '#f1f5f4', color: '#0f172a',
        display: 'flex', alignItems: 'center', justifyContent: 'center', marginTop: 2,
      }}>
        <Icon name={icon} size={13}/>
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 10.5, color: '#94a3b8', fontWeight: 600, letterSpacing: '0.04em', marginBottom: 3 }}>{label}</div>
        <div style={{ fontSize: 13.5, color: '#0f172a', lineHeight: 1.5 }}>{children}</div>
      </div>
    </div>
  );
}

Object.assign(window, { CustomerReservation });

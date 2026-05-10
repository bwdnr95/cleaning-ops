// Order detail — sectioned body + right action panel + timeline

function OrderDetailPage({ orderId, onBack }) {
  const order = ORDERS.find((o) => o.id === orderId) || ORDERS[1]; // CO-2450 default

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, background: 'var(--bg)' }}>
      {/* Sub-header */}
      <div style={{
        padding: '10px 20px',
        background: 'var(--surface)',
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: 10,
      }}>
        <button className="btn btn--ghost btn--sm" onClick={onBack} style={{ padding: '0 6px' }}>
          <Icon name="chevronLeft" size={13}/> 목록
        </button>
        <span style={{ width: 1, height: 16, background: 'var(--border)' }}/>
        <span className="mono" style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>{order.id}</span>
        <h2 style={{ margin: 0, fontSize: 14, fontWeight: 600, letterSpacing: '-0.015em' }}>{order.product}</h2>
        <StatusBadge status={order.status}/>
        <div style={{ flex: 1 }}/>
        <button className="btn btn--ghost btn--sm">
          <Icon name="history" size={12}/> 변경 이력
        </button>
        <button className="btn btn--secondary btn--sm">수정</button>
        <button className="btn btn--ghost btn--sm" style={{ padding: '0 6px' }}>
          <Icon name="moreHorizontal" size={14}/>
        </button>
      </div>

      {/* Body: 2 columns */}
      <div className="scroll" style={{ flex: 1, overflow: 'auto', padding: 20 }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 16, maxWidth: 1320, margin: '0 auto' }}>
          {/* Left main */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <Section title="고객 정보" icon="user">
              <KV col={2}>
                <KVItem label="고객명" value="이서연"/>
                <KVItem label="연락처" value="010-7***-1129" mono action="복사"/>
                <KVItem label="유입 경로" value="자연검색 · 네이버"/>
                <KVItem label="이전 거래" value="2건 · 마지막 2025-11-04"/>
                <KVItem label="요청사항" value="강아지 있음. 베란다 곰팡이 심함. 오후 2시 이후 방문 가능." span={2} multiline/>
              </KV>
            </Section>

            <Section title="상품 / 일정" icon="package">
              <KV col={2}>
                <KVItem label="상품명" value="에어컨 분해세척"/>
                <KVItem label="세부" value="벽걸이 2대 + 스탠드 2대"/>
                <KVItem label="방문예정일" value="2026-05-02 (토)"/>
                <KVItem label="요청시간" value="오후 2-5시"/>
                <KVItem label="주소" value="서울 마포구 와우산로 88 합정스카이뷰 1102호" span={2} action="지도"/>
              </KV>
            </Section>

            <Section title="금액 / 결제" icon="creditCard">
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 0, padding: '4px 0' }}>
                <Money label="총 계약금액" value="320,000" big/>
                <Money label="계약금" value="100,000" sub="04-29 입금"/>
                <Money label="잔금" value="220,000" sub="작업 후"/>
                <Money label="현장추가" value="-" muted/>
              </div>
              <div style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '10px 14px', background: 'var(--success-bg)',
                border: '1px solid var(--success-border)', borderRadius: 6,
                marginTop: 10,
              }}>
                <Icon name="check" size={14} color="var(--success-fg)"/>
                <div style={{ flex: 1, fontSize: 12 }}>
                  <span style={{ fontWeight: 600, color: 'var(--success-fg)' }}>계약금 입금 확인 완료</span>
                  <span style={{ marginLeft: 8, color: 'var(--text-secondary)' }}>국민 1234-** 이서연 · ₩100,000</span>
                </div>
                <button className="btn btn--ghost btn--sm" style={{ color: 'var(--success-fg)' }}>잔금 청구 발송</button>
              </div>
            </Section>

            <Section title="협력사 배정" icon="truck">
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: 4 }}>
                <Avatar name="클" size={36} tone="info"/>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 600 }}>클린파트너스 <span style={{ color: 'var(--text-tertiary)', fontWeight: 400, marginLeft: 4 }}>· 박정훈 팀장</span></div>
                  <div style={{ fontSize: 11.5, color: 'var(--text-tertiary)', marginTop: 2 }}>
                    이번 달 23건 · 평점 4.8 · 평균 응답 12분
                  </div>
                </div>
                <Badge tone="success" dot>확인 완료</Badge>
                <button className="btn btn--ghost btn--sm">
                  <Icon name="phone" size={12}/> 통화
                </button>
                <button className="btn btn--secondary btn--sm">변경</button>
              </div>
            </Section>

            <Section title="비포 / 애프터 사진" icon="image" badge={<Badge tone="warn" dot>검수 대기</Badge>} action={<button className="btn btn--primary btn--sm">검수 화면 열기</button>}>
              <PhotoGrid title="비포" count={8} tone="neutral"/>
              <PhotoGrid title="애프터" count={8} tone="success"/>
              <div style={{
                padding: 10, marginTop: 8,
                background: 'var(--bg-subtle)', borderRadius: 6,
                fontSize: 11.5, color: 'var(--text-secondary)',
              }}>
                <span style={{ fontWeight: 600, color: 'var(--text)' }}>협력사 메모</span>
                <span style={{ marginLeft: 8 }}>스탠드 1대 필터 교체 권장 (별도 비용 안내드림). 베란다 새시 곰팡이 따로 견적 필요.</span>
              </div>
            </Section>
          </div>

          {/* Right action panel */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, position: 'sticky', top: 0, alignSelf: 'flex-start' }}>
            {/* Quick actions */}
            <div className="card" style={{ padding: 14 }}>
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 600, letterSpacing: '0.04em', marginBottom: 8 }}>현재 단계</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                <StatusBadge status="사진검수대기"/>
                <button className="btn btn--ghost btn--sm" style={{ padding: '0 4px', fontSize: 11 }}>
                  변경 <Icon name="chevronDown" size={10}/>
                </button>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <button className="btn btn--primary btn--block">
                  <Icon name="check" size={13}/> 사진 승인 + 고객 전달
                </button>
                <button className="btn btn--secondary btn--block">
                  <Icon name="send" size={13}/> 잔금 청구 안내 발송
                </button>
                <button className="btn btn--secondary btn--block">
                  <Icon name="user" size={13}/> 고객에게 메시지
                </button>
              </div>
            </div>

            {/* Customer link */}
            <div className="card" style={{ padding: 14 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                <span style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 600, letterSpacing: '0.04em' }}>고객 페이지 링크</span>
                <Badge tone="success" dot>활성</Badge>
              </div>
              <div style={{
                padding: '6px 10px',
                background: 'var(--bg-subtle)',
                border: '1px solid var(--border)',
                borderRadius: 6,
                fontFamily: 'var(--font-mono)', fontSize: 11,
                color: 'var(--text-secondary)',
                display: 'flex', alignItems: 'center', gap: 6,
                marginBottom: 8,
              }}>
                <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>cleanops.kr/o/CO-2450-7Hb2</span>
                <button className="btn btn--ghost btn--sm" style={{ padding: '0 4px', height: 18 }}>복사</button>
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                마지막 접속 04-30 16:22 · 조회 3회
              </div>
            </div>

            {/* Timeline */}
            <div className="card" style={{ padding: 14 }}>
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 600, letterSpacing: '0.04em', marginBottom: 10 }}>타임라인</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 0, position: 'relative' }}>
                {TIMELINE_2450.map((t, i) => (
                  <div key={i} style={{ display: 'flex', gap: 10, paddingBottom: i === TIMELINE_2450.length - 1 ? 0 : 12, position: 'relative' }}>
                    <div style={{ position: 'relative', width: 8, flexShrink: 0 }}>
                      <span style={{
                        width: 8, height: 8, borderRadius: '50%',
                        background: i === TIMELINE_2450.length - 1 ? 'var(--brand)' : 'var(--border-strong)',
                        boxShadow: i === TIMELINE_2450.length - 1 ? '0 0 0 3px var(--brand-bg)' : 'none',
                        display: 'block', marginTop: 4,
                      }}/>
                      {i < TIMELINE_2450.length - 1 && <span style={{
                        position: 'absolute', left: 3.5, top: 14, bottom: -8,
                        width: 1, background: 'var(--border)',
                      }}/>}
                    </div>
                    <div style={{ flex: 1, fontSize: 11.5 }}>
                      <div style={{ color: 'var(--text-tertiary)', fontSize: 10.5, marginBottom: 1 }}>{t.time} · {t.who}</div>
                      <div style={{ color: 'var(--text)' }}>{t.text}</div>
                    </div>
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

function Section({ title, icon, badge, action, children }) {
  return (
    <div className="card" style={{ padding: 0 }}>
      <div style={{
        padding: '10px 14px',
        borderBottom: '1px solid var(--divider)',
        display: 'flex', alignItems: 'center', gap: 8,
      }}>
        <Icon name={icon} size={13} color="var(--text-tertiary)"/>
        <span style={{ fontSize: 12.5, fontWeight: 600 }}>{title}</span>
        {badge}
        <div style={{ flex: 1 }}/>
        {action}
      </div>
      <div style={{ padding: 14 }}>{children}</div>
    </div>
  );
}

function KV({ children, col = 2 }) {
  return <div style={{ display: 'grid', gridTemplateColumns: `repeat(${col}, 1fr)`, gap: '10px 16px' }}>{children}</div>;
}

function KVItem({ label, value, mono, span, action, multiline }) {
  return (
    <div style={{ gridColumn: span ? `span ${span}` : 'auto' }}>
      <div style={{ fontSize: 10.5, color: 'var(--text-tertiary)', fontWeight: 500, letterSpacing: '0.02em', marginBottom: 3 }}>{label}</div>
      <div style={{
        fontSize: 12.5, color: 'var(--text)',
        fontFamily: mono ? 'var(--font-mono)' : 'inherit',
        display: 'flex', alignItems: multiline ? 'flex-start' : 'center', gap: 6,
        lineHeight: multiline ? 1.5 : 1.4,
      }}>
        <span style={{ flex: 1 }}>{value}</span>
        {action && <button className="btn btn--ghost btn--sm" style={{ height: 20, padding: '0 6px', fontSize: 11 }}>{action}</button>}
      </div>
    </div>
  );
}

function Money({ label, value, sub, big, muted }) {
  return (
    <div style={{ padding: '0 14px', borderRight: '1px solid var(--divider)' }}>
      <div style={{ fontSize: 10.5, color: 'var(--text-tertiary)', fontWeight: 500, marginBottom: 3 }}>{label}</div>
      <div style={{ fontSize: big ? 18 : 14, fontWeight: 600, letterSpacing: '-0.02em', color: muted ? 'var(--text-quaternary)' : 'var(--text)', fontVariantNumeric: 'tabular-nums' }}>
        {value !== '-' && <span style={{ fontSize: big ? 12 : 10, color: 'var(--text-tertiary)', fontWeight: 400, marginRight: 2 }}>₩</span>}
        {value}
      </div>
      {sub && <div style={{ fontSize: 10.5, color: 'var(--text-tertiary)', marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

function PhotoGrid({ title, count, tone }) {
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
        <Badge tone={tone}>{title}</Badge>
        <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{count}장</span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(8, 1fr)', gap: 6 }}>
        {Array.from({ length: count }).map((_, i) => (
          <div key={i} className="placeholder-img" style={{ aspectRatio: '1', fontSize: 9 }}>
            {title === '비포' ? `B-${i + 1}` : `A-${i + 1}`}
          </div>
        ))}
      </div>
    </div>
  );
}

Object.assign(window, { OrderDetailPage });

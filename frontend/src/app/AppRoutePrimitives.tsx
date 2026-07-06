export function RouteState({ text }: { readonly text: string }) {
  return (
    <div style={{ minHeight: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-tertiary)', fontSize: 13 }}>
      {text}
    </div>
  );
}

export function ComingSoon({ page }: { readonly page: string }) {
  return (
    <div className="coming-soon">
      <div className="card">
        <div className="app-eyebrow">준비 중</div>
        <h2>{page}</h2>
        <p>운영 흐름에 맞춰 이어서 연결할 영역입니다.</p>
      </div>
    </div>
  );
}

export function isCustomerLinkRoute() {
  return /^\/(?:c|customer)(?:\/|$)/.test(window.location.pathname);
}

export function isPartnerLinkRoute() {
  return /^\/partner(?:\/|$)/.test(window.location.pathname);
}

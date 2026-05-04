export function PhoneFrame({ time = '14:08', children }) {
  return (
    <div className="phone-frame">
      <div className="phone-status">
        <span>{time}</span>
        <span>●●● ●● ▮▮</span>
      </div>
      <div className="phone-inner">{children}</div>
    </div>
  );
}

export function DesktopFrame({ children, title = 'app.cleanops.kr' }) {
  return (
    <div className="desktop-frame">
      <div className="desktop-chrome">
        <span style={{ background: '#ff5f57' }} />
        <span style={{ background: '#febc2e' }} />
        <span style={{ background: '#28c840' }} />
        <span className="desktop-title">{title}</span>
      </div>
      <div className="desktop-body">{children}</div>
    </div>
  );
}

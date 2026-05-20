import React from 'react';
import DaumPostcode from 'react-daum-postcode';

interface AddressInputProps {
  baseAddress: string;
  detailAddress: string;
  onChange: (next: { baseAddress: string; detailAddress: string }) => void;
  required?: boolean;
  testIdPrefix?: string;
}

interface DaumPostcodeData {
  roadAddress?: string;
  address: string;
  jibunAddress?: string;
  zonecode: string;
}

export function AddressInput({
  baseAddress,
  detailAddress,
  onChange,
  required = false,
  testIdPrefix = 'order-customer-address',
}: AddressInputProps) {
  const [isSearchOpen, setSearchOpen] = React.useState(false);

  const handleComplete = (data: DaumPostcodeData) => {
    const chosen = data.roadAddress || data.address || data.jibunAddress || '';
    const formatted = data.zonecode ? `(${data.zonecode}) ${chosen}` : chosen;
    onChange({ baseAddress: formatted, detailAddress });
    setSearchOpen(false);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-tertiary)' }}>
        주소{required ? ' *' : ''}
      </label>

      <div style={{ display: 'flex', gap: 6 }}>
        <input
          data-testid={testIdPrefix}
          className="input"
          style={{ flex: 1 }}
          value={baseAddress}
          placeholder="검색 버튼을 눌러 우편번호 / 도로명을 선택하세요"
          onChange={(event) => onChange({ baseAddress: event.target.value, detailAddress })}
        />
        <button
          type="button"
          data-testid={`${testIdPrefix}-search`}
          className="btn btn--secondary btn--sm"
          onClick={() => setSearchOpen(true)}
        >
          주소 검색
        </button>
      </div>

      <input
        data-testid={`${testIdPrefix}-detail`}
        className="input"
        value={detailAddress}
        placeholder="상세주소 (동/호수 등) - 권장"
        onChange={(event) => onChange({ baseAddress, detailAddress: event.target.value })}
      />

      {baseAddress && !detailAddress && (
        <div style={{ fontSize: 11, color: 'var(--warning-fg)' }}>
          상세주소 미입력 - 동/호수까지 입력하면 협력사가 헤매지 않습니다.
        </div>
      )}

      {isSearchOpen && (
        <div
          data-testid={`${testIdPrefix}-modal`}
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.4)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
          }}
          onClick={() => setSearchOpen(false)}
        >
          <div
            style={{
              background: 'var(--surface)',
              padding: 12,
              borderRadius: 8,
              width: 480,
              maxWidth: '90vw',
            }}
            onClick={(event) => event.stopPropagation()}
          >
            <DaumPostcode onComplete={handleComplete} autoClose={false} style={{ height: 480 }} />
            <div style={{ marginTop: 8, textAlign: 'right' }}>
              <button
                type="button"
                data-testid={`${testIdPrefix}-modal-close`}
                className="btn btn--ghost btn--sm"
                onClick={() => setSearchOpen(false)}
              >
                닫기
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

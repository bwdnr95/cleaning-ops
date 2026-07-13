import { SOURCE_CHANNEL_OPTIONS, sourceChannelLabel } from '../../../domain/sourceChannel';

interface Props {
  value: string;
  onChange: (value: string) => void;
}

export function SourceChannelSelect({ value, onChange }: Props) {
  const hasLegacyValue = Boolean(
    value && !SOURCE_CHANNEL_OPTIONS.some((option) => option.value === value),
  );

  return (
    <select
      data-testid="order-source-channel"
      className="input"
      value={value}
      onChange={(event) => onChange(event.target.value)}
    >
      <option value="">미선택</option>
      {hasLegacyValue && <option value={value}>{sourceChannelLabel(value)}</option>}
      {SOURCE_CHANNEL_OPTIONS.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  );
}

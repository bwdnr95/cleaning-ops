export function formatQuantity(value: string | null | undefined): string {
  if (value == null) {
    return '';
  }

  const text = String(value);
  if (text.trim() === '') {
    return text;
  }

  const decimalOnly = text.match(/^(\s*)(\d+)\.(\d+)(\s*)$/);
  if (decimalOnly) {
    return `${decimalOnly[1]}${formatDecimalQuantity(decimalOnly[2], decimalOnly[3])}${decimalOnly[4]}`;
  }

  const decimalWithUnit = text.match(/^(\s*)(\d+)\.(\d+)(\s*[^\d.\s].*)$/u);
  if (decimalWithUnit) {
    return `${decimalWithUnit[1]}${formatDecimalQuantity(decimalWithUnit[2], decimalWithUnit[3])}${decimalWithUnit[4]}`;
  }

  return text;
}

function formatDecimalQuantity(integerPart: string, decimalPart: string): string {
  const normalizedInteger = integerPart.replace(/^0+(?=\d)/, '');
  const trimmedDecimal = decimalPart.replace(/0+$/, '');

  if (!trimmedDecimal) {
    return normalizedInteger || '0';
  }
  return `${normalizedInteger || '0'}.${trimmedDecimal}`;
}

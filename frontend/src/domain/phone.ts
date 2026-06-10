export function formatPhone(phone) {
  if (!phone) {
    return '-';
  }

  const digits = digitsOnly(phone);
  if (!digits) {
    return phone;
  }

  // 0으로만 채워진 값은 일괄 등록 시 들어간 플레이스홀더이므로 미등록으로 표시한다.
  if (/^0+$/.test(digits)) {
    return '-';
  }

  if (digits.startsWith('02')) {
    if (digits.length === 9) {
      return `${digits.slice(0, 2)}-${digits.slice(2, 5)}-${digits.slice(5)}`;
    }
    if (digits.length === 10) {
      return `${digits.slice(0, 2)}-${digits.slice(2, 6)}-${digits.slice(6)}`;
    }
  }

  if (digits.length === 10) {
    return `${digits.slice(0, 3)}-${digits.slice(3, 6)}-${digits.slice(6)}`;
  }
  if (digits.length === 11) {
    return `${digits.slice(0, 3)}-${digits.slice(3, 7)}-${digits.slice(7)}`;
  }

  return phone;
}

export function digitsOnly(value) {
  return String(value || '').replace(/\D/g, '');
}

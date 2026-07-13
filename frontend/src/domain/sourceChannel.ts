export const SOURCE_CHANNEL_OPTIONS = [
  { value: '전화', label: '전화' },
  { value: '네이버톡톡', label: '네이버톡톡' },
  { value: '네이버검색', label: '네이버검색' },
  { value: '카카오채널', label: '카카오채널' },
  { value: '홈페이지', label: '홈페이지' },
  { value: '아파트게시판', label: '아파트게시판' },
  { value: '유튜브', label: '유튜브' },
  { value: '블로그', label: '블로그' },
  { value: '스마트스토어', label: '스마트스토어' },
  { value: '숨고', label: '숨고' },
  { value: '당근', label: '당근' },
  { value: '중개사', label: '중개사' },
  { value: '소개', label: '소개' },
  { value: '재주문', label: '재주문' },
  { value: '기타', label: '기타' },
] as const;

export function sourceChannelLabel(value: string | null | undefined) {
  const normalized = (value || '').trim();
  if (!normalized) {
    return '-';
  }
  if (normalized === '네이버') {
    return '네이버톡톡';
  }
  return normalized;
}

export const CATEGORY_LABEL: Record<string, string> = {
  productivity: '생산성',
  'dev-tools': '개발 도구',
  data: '데이터',
  design: '디자인',
  education: '교육',
  entertainment: '엔터테인먼트',
  game: '게임',
  business: '비즈니스',
  other: '기타',
}

export const categoryLabel = (c: string | null | undefined) => CATEGORY_LABEL[c ?? 'other'] ?? c ?? '기타'

export const errorDetail = (e: unknown, fallback: string) => (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? fallback

/** '최근 활동' 표시: 방금 / N분 / N시간 / N일 / 날짜 */
export function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const m = Math.floor(diff / 60000)
  if (m < 1) return '방금'
  if (m < 60) return `${m}분`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}시간`
  const d = Math.floor(h / 24)
  if (d < 30) return `${d}일`
  return new Date(iso).toLocaleDateString()
}

/** JSON 값을 들여쓰기해서 보여 준다 (길면 스크롤). 문자열 결과는 그대로 보인다 */
export default function JsonBlock({ value, label, empty = '(없음)' }: { value: unknown; label: string; empty?: string }) {
  const text = value === null || value === undefined ? '' : typeof value === 'string' ? value : JSON.stringify(value, null, 2)
  return (
    <div>
      <div className="mb-1 text-[11px] font-medium text-content-tertiary">{label}</div>
      <pre aria-label={label} className="m-0 p-3 max-h-64 overflow-auto rounded-lg border border-border bg-surface-secondary text-[12px] leading-relaxed text-content-primary font-mono whitespace-pre-wrap break-all">
        {text || <span className="text-content-muted">{empty}</span>}
      </pre>
    </div>
  )
}

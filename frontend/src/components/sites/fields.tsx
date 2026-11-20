import { inputCls } from '../skills/common'

export function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="block space-y-1">
      <span className="text-[13px] font-medium text-content-primary">{label}</span>
      {children}
      {hint && <span className="block text-xs text-content-tertiary">{hint}</span>}
    </label>
  )
}

export function TextArea({ value, onChange, rows = 8, mono = false, placeholder }: {
  value: string
  onChange: (v: string) => void
  rows?: number
  mono?: boolean
  placeholder?: string
}) {
  return (
    <textarea
      value={value}
      onChange={(e) => onChange(e.target.value)}
      rows={rows}
      placeholder={placeholder}
      spellCheck={false}
      className={`${inputCls} resize-y leading-relaxed ${mono ? 'font-mono text-[12.5px]' : ''}`}
    />
  )
}

export const secondaryBtn =
  'px-3.5 py-2 rounded-[var(--radius-md)] border border-border bg-transparent text-[13px] text-content-primary cursor-pointer hover:bg-surface-hover disabled:opacity-40 disabled:cursor-not-allowed'

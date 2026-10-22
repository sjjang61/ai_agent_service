import type { TableSpec } from '../../types/widget'

/** 비교 표 위젯. 색은 모두 테마 토큰이라 라이트/다크 어느 쪽에서도 글자와 구분선이 잘 보인다. */
export default function TableWidget({ spec }: { spec: TableSpec }) {
  return (
    <div>
      <div className="overflow-x-auto rounded-[var(--radius-md)] border border-border">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="bg-surface-tertiary">
              {spec.columns.map((c, i) => (
                <th
                  key={i}
                  scope="col"
                  className="text-left px-3.5 py-2.5 text-[13px] font-semibold text-content-primary border-b border-border whitespace-nowrap"
                >
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {spec.rows.map((row, r) => (
              <tr key={r} className="even:bg-surface-tertiary/40 hover:bg-surface-hover/60 transition-colors [&:last-child>td]:border-b-0">
                {row.map((cell, c) => (
                  <td
                    key={c}
                    className={`px-3.5 py-2.5 text-[13px] text-content-primary border-b border-border/60 ${
                      c === 0 ? 'font-medium' : ''
                    } ${typeof cell === 'number' ? 'text-right tabular-nums' : ''}`}
                  >
                    {typeof cell === 'number' ? cell.toLocaleString() : cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {spec.caption && <p className="mt-2 text-xs text-content-tertiary">{spec.caption}</p>}
    </div>
  )
}

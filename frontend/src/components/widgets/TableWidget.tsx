import type { TableSpec } from '../../types/widget'

export default function TableWidget({ spec }: { spec: TableSpec }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr>
            {spec.columns.map((c, i) => (
              <th
                key={i}
                className="text-left px-3 py-2 bg-slate-700/60 text-slate-200 font-medium border border-slate-600 whitespace-nowrap"
              >
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {spec.rows.map((row, r) => (
            <tr key={r} className="odd:bg-slate-800/40">
              {row.map((cell, c) => (
                <td
                  key={c}
                  className={`px-3 py-2 border border-slate-700 text-slate-200 ${
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
      {spec.caption && <p className="mt-2 text-xs text-slate-400">{spec.caption}</p>}
    </div>
  )
}

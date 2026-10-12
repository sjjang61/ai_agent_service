import { useEffect, useState } from 'react'
import type { FlowSpec } from '../../types/widget'

let counter = 0

export default function FlowWidget({ spec }: { spec: FlowSpec }) {
  const [svg, setSvg] = useState<string>('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const mermaid = (await import('mermaid')).default
        // strict: 스크립트/클릭 이벤트 등을 차단하고 SVG 를 sanitize 한다
        mermaid.initialize({ startOnLoad: false, securityLevel: 'strict', theme: 'dark', suppressErrorRendering: true })
        await mermaid.parse(spec.mermaid) // 문법 오류면 여기서 예외 (페이지에 오류 그래픽이 붙지 않게 먼저 검증)
        const { svg } = await mermaid.render(`widget-flow-${Date.now()}-${counter++}`, spec.mermaid)
        if (!cancelled) {
          setSvg(svg)
          setError(null)
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e))
      }
    })()
    return () => {
      cancelled = true
    }
  }, [spec.mermaid])

  if (error) {
    return (
      <div className="space-y-2">
        <p className="text-xs text-red-400">흐름도를 그리지 못했습니다. 원본 코드를 표시합니다.</p>
        <pre className="text-xs text-slate-300 bg-slate-900 rounded p-2 overflow-x-auto">{spec.mermaid}</pre>
      </div>
    )
  }
  if (!svg) return <p className="text-xs text-slate-500">흐름도를 그리는 중...</p>
  return <div className="overflow-x-auto [&_svg]:max-w-full [&_svg]:h-auto" dangerouslySetInnerHTML={{ __html: svg }} />
}

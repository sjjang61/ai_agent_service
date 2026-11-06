import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import ForceGraph2D from 'react-force-graph-2d'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Lightbulb, Loader2, Maximize2, RefreshCw, Search, X, ZoomIn, ZoomOut, ChevronDown, ChevronRight, Sparkles } from 'lucide-react'
import { wikiApi } from '../../api/wiki'
import WikiMarkdown from './WikiMarkdown'
import type { GraphNode, WikiNodeType } from '../../types/wiki'

const TYPE_INFO: Record<WikiNodeType, { label: string; color: string }> = {
  entity: { label: '개체', color: '#3b82f6' },
  concept: { label: '개념', color: '#a855f7' },
  source: { label: '원본', color: '#f97316' },
  overview: { label: '개요', color: '#eab308' },
  other: { label: '기타', color: '#94a3b8' },
}
const TYPE_ORDER: WikiNodeType[] = ['entity', 'concept', 'source', 'overview', 'other']
const COMMUNITY_COLORS = ['#3b82f6', '#a855f7', '#f97316', '#22c55e', '#ec4899', '#eab308', '#06b6d4', '#ef4444', '#84cc16', '#8b5cf6']

type ColorMode = 'type' | 'community'
const nodeColor = (n: GraphNode, mode: ColorMode) =>
  mode === 'type' ? TYPE_INFO[n.node_type]?.color ?? '#94a3b8' : COMMUNITY_COLORS[n.community % COMMUNITY_COLORS.length]

interface FNode extends GraphNode { x?: number; y?: number }

function DetailPanel({ id, nodes, onSelect, onClose }: { id: string; nodes: Map<string, GraphNode>; onSelect: (id: string) => void; onClose: () => void }) {
  const qc = useQueryClient()
  const { data: entry, isLoading } = useQuery({ queryKey: ['wiki-entry', id], queryFn: async () => (await wikiApi.get(id)).data })
  const promote = useMutation({
    mutationFn: async () => wikiApi.update(id, { auto_generated: false } as never),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['wiki-entry', id] }); qc.invalidateQueries({ queryKey: ['wiki-graph'] }); qc.invalidateQueries({ queryKey: ['wiki-entries'] }) },
  })
  const docs = [...(entry?.links ?? []), ...(entry?.backlinks ?? [])]
  const node = nodes.get(id)
  return (
    <aside className="w-[340px] flex-shrink-0 border-l border-border bg-surface-secondary overflow-y-auto">
      <div className="flex items-start gap-2 px-4 pt-4 pb-2">
        <div className="flex-1 min-w-0">
          <h3 className="text-[15px] font-semibold text-content-primary break-words">{node?.title ?? entry?.title}</h3>
          {node && (
            <div className="mt-1 flex items-center gap-1.5 text-[11px]">
              <span className="px-1.5 py-0.5 rounded border border-border" style={{ color: TYPE_INFO[node.node_type]?.color }}>{TYPE_INFO[node.node_type]?.label}</span>
              <span className="text-content-tertiary">연결 {node.degree}</span>
              {node.auto_generated && <span className="text-content-tertiary">· AI 생성</span>}
            </div>
          )}
        </div>
        <button onClick={onClose} aria-label="닫기" className="p-1 text-content-muted hover:text-content-primary"><X size={15} /></button>
      </div>
      {isLoading || !entry ? (
        <div className="p-6 text-center text-content-muted"><Loader2 size={14} className="animate-spin inline" /></div>
      ) : (
        <div className="px-4 pb-6 space-y-3">
          {entry.auto_generated && (
            <button onClick={() => promote.mutate()} disabled={promote.isPending} className="text-xs px-2.5 py-1 rounded-md bg-accent-primary/15 text-accent-primary hover:bg-accent-primary/25">
              정식 문서로 승격
            </button>
          )}
          {!!entry.aliases?.length && <p className="text-xs text-content-tertiary">별칭: {entry.aliases.join(', ')}</p>}
          <WikiMarkdown docs={docs} onOpen={onSelect}>{entry.content}</WikiMarkdown>
          {[['연결된 문서', entry.links], ['이 문서를 가리키는 문서', entry.backlinks]].map(([label, list]) =>
            (list as typeof entry.links)?.length ? (
              <div key={label as string}>
                <div className="text-xs font-medium text-content-muted mb-1">{label as string}</div>
                <div className="flex flex-wrap gap-1">
                  {(list as NonNullable<typeof entry.links>).map((l) => (
                    <button key={l.id} onClick={() => onSelect(l.id)} className="text-xs px-2 py-0.5 rounded-full bg-surface-tertiary text-content-secondary hover:text-content-primary">{l.title}</button>
                  ))}
                </div>
              </div>
            ) : null
          )}
        </div>
      )}
    </aside>
  )
}

export default function WikiGraphView() {
  const qc = useQueryClient()
  const [mode, setMode] = useState<ColorMode>('type')
  const [hidden, setHidden] = useState<Set<WikiNodeType>>(new Set())
  const [selected, setSelected] = useState<string | null>(null)
  const [hover, setHover] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [showInsights, setShowInsights] = useState(false)
  const [open, setOpen] = useState<Record<string, boolean>>({ entity: true, concept: true, source: true })
  const wrap = useRef<HTMLDivElement>(null)
  const fg = useRef<any>(null) // eslint-disable-line @typescript-eslint/no-explicit-any
  const [size, setSize] = useState({ w: 600, h: 520 })

  const { data, isLoading, isError } = useQuery({
    queryKey: ['wiki-graph'],
    queryFn: async () => (await wikiApi.graph()).data,
    refetchInterval: (q) => ((q.state.data?.pending ?? 0) > 0 ? 3000 : false), // 지식화가 진행 중이면 결과가 나올 때까지 갱신
  })
  const insights = useQuery({ queryKey: ['wiki-graph-insights'], queryFn: async () => (await wikiApi.graphInsights()).data.insights, enabled: showInsights })
  const rebuild = useMutation({
    mutationFn: async () => (await wikiApi.graphRebuild(false)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['wiki-graph'] }),
  })

  useEffect(() => {
    if (!wrap.current) return
    const ro = new ResizeObserver(([e]) => setSize({ w: Math.max(300, e.contentRect.width), h: Math.max(400, e.contentRect.height) }))
    ro.observe(wrap.current)
    return () => ro.disconnect()
  }, [])

  const nodesById = useMemo(() => new Map((data?.nodes ?? []).map((n) => [n.id, n])), [data])
  const graphData = useMemo(() => {
    const nodes: FNode[] = (data?.nodes ?? []).filter((n) => !hidden.has(n.node_type)).map((n) => ({ ...n }))
    const ids = new Set(nodes.map((n) => n.id))
    const links = (data?.edges ?? []).filter((e) => ids.has(e.source) && ids.has(e.target)).map((e) => ({ ...e }))
    return { nodes, links }
  }, [data, hidden])

  const neighbors = useMemo(() => {
    const m = new Map<string, Set<string>>()
    for (const e of data?.edges ?? []) {
      if (!m.has(e.source)) m.set(e.source, new Set())
      if (!m.has(e.target)) m.set(e.target, new Set())
      m.get(e.source)!.add(e.target); m.get(e.target)!.add(e.source)
    }
    return m
  }, [data])

  const q = search.trim().toLowerCase()
  const focus = hover ?? selected
  const lit = (id: string) => !focus || id === focus || neighbors.get(focus)?.has(id)

  const textColor = useMemo(() => getComputedStyle(document.documentElement).getPropertyValue('--text-primary').trim() || '#e5e7eb', [])
  const draw = useCallback((node: FNode, ctx: CanvasRenderingContext2D, scale: number) => {
    const r = 3 + Math.sqrt(node.degree + 1) * 2.2
    const dim = !lit(node.id) || (q && !node.title.toLowerCase().includes(q))
    ctx.globalAlpha = dim ? 0.18 : 1
    ctx.beginPath()
    ctx.arc(node.x ?? 0, node.y ?? 0, r, 0, 2 * Math.PI)
    ctx.fillStyle = nodeColor(node, mode)
    ctx.fill()
    if (node.id === selected) { ctx.lineWidth = 2 / scale; ctx.strokeStyle = '#fff'; ctx.stroke() }
    const showLabel = node.id === selected || node.id === hover || node.degree >= 4 || scale > 1.6 || (q && node.title.toLowerCase().includes(q))
    if (showLabel && !dim) {
      const fs = 11 / Math.max(scale, 0.8)
      ctx.font = `${fs}px sans-serif`
      ctx.textAlign = 'center'
      ctx.fillStyle = textColor
      ctx.fillText(node.title.length > 28 ? node.title.slice(0, 27) + '…' : node.title, node.x ?? 0, (node.y ?? 0) + r + fs + 1)
    }
    ctx.globalAlpha = 1
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, selected, hover, q, neighbors, textColor])

  const typeCounts = data?.type_counts ?? {}
  const byType = useMemo(() => {
    const m: Record<string, GraphNode[]> = {}
    for (const n of data?.nodes ?? []) (m[n.node_type] ??= []).push(n)
    for (const k in m) m[k].sort((a, b) => b.degree - a.degree || a.title.localeCompare(b.title))
    return m
  }, [data])

  const select = (id: string) => {
    setSelected(id)
    const n = graphData.nodes.find((x) => x.id === id)
    if (n?.x != null && fg.current) { fg.current.centerAt(n.x, n.y, 400); fg.current.zoom(2.2, 400) }
  }

  if (isLoading) return <div className="py-20 text-center text-sm text-content-muted"><Loader2 size={14} className="animate-spin inline mr-1" /> 그래프를 불러오는 중...</div>
  if (isError || !data) return <div className="py-20 text-center text-sm text-accent-red">그래프를 불러오지 못했습니다.</div>

  return (
    <div className="flex border border-border rounded-xl overflow-hidden bg-surface-primary" style={{ height: 'calc(100vh - 230px)', minHeight: 520 }}>
      {/* 좌: 유형별 트리 */}
      <aside className="w-[210px] flex-shrink-0 border-r border-border bg-surface-secondary flex flex-col">
        <div className="p-2 border-b border-border">
          <div className="relative">
            <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-content-muted" />
            <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="노드 검색"
              className="w-full pl-7 pr-2 py-1.5 text-xs bg-surface-primary border border-border rounded-md text-content-primary focus:outline-none focus:border-accent-primary" />
          </div>
        </div>
        <div className="flex-1 overflow-y-auto py-1">
          {TYPE_ORDER.filter((t) => byType[t]?.length).map((t) => {
            const list = byType[t].filter((n) => !q || n.title.toLowerCase().includes(q))
            return (
              <div key={t}>
                <button onClick={() => setOpen((o) => ({ ...o, [t]: !o[t] }))} className="w-full flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-content-secondary hover:bg-surface-hover">
                  {open[t] ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                  <span className="w-2 h-2 rounded-full" style={{ background: TYPE_INFO[t].color }} />
                  {TYPE_INFO[t].label}
                  <span className="ml-auto text-content-tertiary">{typeCounts[t] ?? 0}</span>
                </button>
                {open[t] && list.map((n) => (
                  <button key={n.id} onClick={() => select(n.id)} title={n.title}
                    className={`w-full text-left pl-8 pr-2 py-1 text-xs truncate hover:bg-surface-hover ${selected === n.id ? 'bg-surface-active text-content-primary' : 'text-content-muted'}`}>
                    {n.title}
                  </button>
                ))}
              </div>
            )
          })}
        </div>
      </aside>

      {/* 중: 그래프 */}
      <div className="flex-1 min-w-0 relative">
        <div className="absolute top-2 left-2 right-2 z-10 flex flex-wrap items-center gap-1.5 pointer-events-none">
          <span className="pointer-events-auto px-2 py-1 rounded-md bg-surface-secondary/90 border border-border text-xs text-content-secondary">
            {data.nodes.length} 노드 · {data.edges.length} 연결
          </span>
          {(['type', 'community'] as ColorMode[]).map((m) => (
            <button key={m} onClick={() => setMode(m)} className={`pointer-events-auto px-2.5 py-1 rounded-md border text-xs ${mode === m ? 'bg-accent-primary text-white border-accent-primary' : 'bg-surface-secondary/90 border-border text-content-secondary hover:text-content-primary'}`}>
              {m === 'type' ? '유형' : `커뮤니티 (${data.communities})`}
            </button>
          ))}
          <button onClick={() => setShowInsights((v) => !v)} className="pointer-events-auto flex items-center gap-1 px-2.5 py-1 rounded-md border border-border bg-surface-secondary/90 text-xs text-content-secondary hover:text-content-primary">
            <Lightbulb size={12} /> 인사이트
          </button>
          <button onClick={() => rebuild.mutate()} disabled={rebuild.isPending || data.pending > 0} title="아직 지식화되지 않은 문서에서 개체·관계를 추출합니다"
            className="pointer-events-auto flex items-center gap-1 px-2.5 py-1 rounded-md border border-border bg-surface-secondary/90 text-xs text-content-secondary hover:text-content-primary disabled:opacity-50">
            {rebuild.isPending || data.pending > 0 ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />}
            {data.pending > 0 ? `지식화 중 (${data.pending})` : '지식화'}
          </button>
          <button onClick={() => qc.invalidateQueries({ queryKey: ['wiki-graph'] })} aria-label="새로고침" className="pointer-events-auto p-1.5 rounded-md border border-border bg-surface-secondary/90 text-content-muted hover:text-content-primary"><RefreshCw size={12} /></button>
        </div>

        {showInsights && (
          <div className="absolute top-12 left-2 z-20 w-[320px] max-h-[60%] overflow-y-auto rounded-lg border border-border bg-surface-secondary shadow-lg p-3 space-y-2">
            <div className="flex items-center text-xs font-semibold text-content-primary">인사이트<button className="ml-auto" onClick={() => setShowInsights(false)}><X size={13} /></button></div>
            {insights.isLoading && <Loader2 size={13} className="animate-spin" />}
            {insights.data?.length === 0 && <p className="text-xs text-content-muted">아직 표시할 인사이트가 없습니다.</p>}
            {insights.data?.map((i, k) => (
              <div key={k} className="text-xs text-content-secondary">
                <p>{i.message}</p>
                <div className="mt-1 flex flex-wrap gap-1">
                  {i.entries.map((e) => <button key={e.id} onClick={() => select(e.id)} className="px-2 py-0.5 rounded-full bg-surface-tertiary hover:text-content-primary">{e.title}</button>)}
                </div>
              </div>
            ))}
          </div>
        )}

        <div ref={wrap} className="absolute inset-0">
          {graphData.nodes.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center text-content-muted text-sm px-6">
              <p>표시할 노드가 없습니다.</p>
              <p className="text-xs mt-1">위키에 문서를 저장하면 개체·개념이 자동으로 추출되어 그래프가 만들어집니다.</p>
            </div>
          ) : (
            <ForceGraph2D
              ref={fg}
              width={size.w}
              height={size.h}
              graphData={graphData}
              backgroundColor="rgba(0,0,0,0)"
              nodeRelSize={4}
              cooldownTicks={120}
              nodeCanvasObject={(n, ctx, s) => draw(n as FNode, ctx, s)}
              nodePointerAreaPaint={(n, color, ctx) => { const x = n as FNode; ctx.fillStyle = color; ctx.beginPath(); ctx.arc(x.x ?? 0, x.y ?? 0, 3 + Math.sqrt(x.degree + 1) * 2.2 + 2, 0, 2 * Math.PI); ctx.fill() }}
              linkColor={(l) => {
                const s = typeof l.source === 'object' ? (l.source as FNode).id : (l.source as string)
                const t = typeof l.target === 'object' ? (l.target as FNode).id : (l.target as string)
                return focus && (s === focus || t === focus) ? 'rgba(148,163,184,0.9)' : 'rgba(148,163,184,0.28)'
              }}
              linkWidth={(l) => ((l as { kind?: string }).kind === 'extracted' ? 1.4 : 0.8)}
              onNodeHover={(n) => setHover(n ? (n as FNode).id : null)}
              onNodeClick={(n) => setSelected((n as FNode).id)}
              onBackgroundClick={() => setSelected(null)}
            />
          )}
        </div>

        {/* 범례 + 줌 */}
        <div className="absolute bottom-2 left-2 z-10 rounded-lg border border-border bg-surface-secondary/90 px-3 py-2 text-xs">
          <div className="font-medium text-content-secondary mb-1">노드 유형</div>
          {TYPE_ORDER.filter((t) => typeCounts[t]).map((t) => (
            <button key={t} onClick={() => setHidden((h) => { const n = new Set(h); n.has(t) ? n.delete(t) : n.add(t); return n })}
              className={`flex items-center gap-1.5 w-full text-left py-0.5 ${hidden.has(t) ? 'opacity-40' : ''}`} title="클릭하여 표시/숨김">
              <span className="w-2.5 h-2.5 rounded-full" style={{ background: TYPE_INFO[t].color }} />
              <span className="text-content-secondary">{TYPE_INFO[t].label}</span>
              <span className="ml-auto pl-3 text-content-tertiary">{typeCounts[t]}</span>
            </button>
          ))}
        </div>
        <div className="absolute top-12 right-2 z-10 flex flex-col gap-1">
          {[[ZoomIn, () => fg.current?.zoom((fg.current.zoom() || 1) * 1.4, 200)], [ZoomOut, () => fg.current?.zoom((fg.current.zoom() || 1) / 1.4, 200)], [Maximize2, () => fg.current?.zoomToFit(400, 40)]].map(([Icon, fn], i) => {
            const I = Icon as typeof ZoomIn
            return <button key={i} onClick={fn as () => void} className="p-1.5 rounded-md border border-border bg-surface-secondary/90 text-content-muted hover:text-content-primary"><I size={14} /></button>
          })}
        </div>
      </div>

      {selected && <DetailPanel id={selected} nodes={nodesById} onSelect={select} onClose={() => setSelected(null)} />}
    </div>
  )
}

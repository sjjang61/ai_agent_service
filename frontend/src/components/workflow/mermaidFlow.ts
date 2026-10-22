/**
 * Mermaid 흐름도(flowchart / graph) 텍스트를 노드·엣지로 파싱한다.
 *
 * 에이전트가 create_widget(flow)로 만든 Mermaid 를 React Flow 다이어그램으로 그리기 위한 간이 파서다.
 * 흔히 쓰는 문법(노드 모양, 화살표 종류, 엣지 라벨, A --> B --> C 체인, & 묶음)만 처리하고,
 * subgraph 는 펼쳐서 노드만 남긴다. 해석할 수 없는 문서(sequenceDiagram 등)나 노드가 없는 경우 null 을 돌려주면
 * 호출한 쪽이 Mermaid 렌더러로 되돌아간다.
 */

export type NodeShape = 'rect' | 'round' | 'stadium' | 'circle' | 'decision' | 'subroutine' | 'database' | 'hexagon' | 'flag'

export interface FlowNode {
  id: string
  label: string
  shape: NodeShape
}

export interface FlowEdge {
  from: string
  to: string
  label: string
  dashed: boolean
  thick: boolean
  arrow: boolean
}

export interface ParsedFlow {
  direction: 'TB' | 'LR'
  nodes: FlowNode[]
  edges: FlowEdge[]
}

const SHAPES: { open: string; close: string; shape: NodeShape }[] = [
  { open: '(((', close: ')))', shape: 'circle' },
  { open: '[[', close: ']]', shape: 'subroutine' },
  { open: '[(', close: ')]', shape: 'database' },
  { open: '([', close: '])', shape: 'stadium' },
  { open: '((', close: '))', shape: 'circle' },
  { open: '{{', close: '}}', shape: 'hexagon' },
  { open: '[', close: ']', shape: 'rect' },
  { open: '(', close: ')', shape: 'round' },
  { open: '{', close: '}', shape: 'decision' },
  { open: '>', close: ']', shape: 'flag' },
]

const ID_RE = /^[A-Za-z0-9_À-￿][A-Za-z0-9_\-À-￿]*/
// 라벨이 줄 안에 들어가는 형태: A -- 라벨 --> B, A == 라벨 ==> B, A -. 라벨 .-> B
const LABELED_EDGE_RE = /^\s*(<?)(--|==|-\.)\s+(.+?)\s+(-{2,3}>?|={2,3}>?|\.-+>?|\.->?|-\.+-?>?)\s*/
// 일반 화살표 (뒤에 |라벨| 이 올 수 있다)
const EDGE_RE = /^\s*(<?)(-{2,}>?|={2,}>?|-\.+-?>?|--[xo])\s*(?:\|([^|]*)\|)?\s*/

function cleanLabel(raw: string): string {
  let t = raw.trim()
  if ((t.startsWith('"') && t.endsWith('"')) || (t.startsWith("'") && t.endsWith("'"))) t = t.slice(1, -1)
  return t
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<[^>]+>/g, '')
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&#(\d+);/g, (_, n) => String.fromCharCode(Number(n)))
    .trim()
}

interface Cursor {
  s: string
  i: number
}

/** `id` + 선택적 모양 `[라벨]` 을 읽는다. 읽을 수 없으면 null */
function readNode(c: Cursor): FlowNode | null {
  const rest = c.s.slice(c.i)
  const m = ID_RE.exec(rest)
  if (!m) return null
  const id = m[0].replace(/-+$/, '')
  let consumed = id.length
  const after = rest.slice(consumed)
  for (const sh of SHAPES) {
    if (!after.startsWith(sh.open)) continue
    // 따옴표 안의 닫는 기호는 무시한다
    let j = sh.open.length
    let quote = ''
    let end = -1
    while (j < after.length) {
      const ch = after[j]
      if (quote) {
        if (ch === quote) quote = ''
      } else if (ch === '"' || ch === "'") {
        quote = ch
      } else if (after.startsWith(sh.close, j)) {
        end = j
        break
      }
      j++
    }
    if (end < 0) continue
    const label = cleanLabel(after.slice(sh.open.length, end))
    c.i += consumed + end + sh.close.length
    return { id, label: label || id, shape: sh.shape }
  }
  c.i += consumed
  return { id, label: id, shape: 'rect' }
}

function skipSpaces(c: Cursor) {
  while (c.i < c.s.length && /\s/.test(c.s[c.i])) c.i++
}

/** 노드 또는 `A & B` 묶음 */
function readNodeGroup(c: Cursor): FlowNode[] | null {
  const group: FlowNode[] = []
  for (;;) {
    skipSpaces(c)
    const n = readNode(c)
    if (!n) return group.length ? group : null
    group.push(n)
    skipSpaces(c)
    if (c.s[c.i] === '&') {
      c.i++
      continue
    }
    return group
  }
}

function readEdge(c: Cursor): Omit<FlowEdge, 'from' | 'to'> | null {
  const rest = c.s.slice(c.i)
  let m = LABELED_EDGE_RE.exec(rest)
  if (m) {
    c.i += m[0].length
    const op = m[4]
    return { label: cleanLabel(m[3]), dashed: m[2] === '-.' || op.includes('.'), thick: m[2] === '==', arrow: op.endsWith('>') }
  }
  m = EDGE_RE.exec(rest)
  if (!m) return null
  c.i += m[0].length
  const op = m[2]
  return { label: cleanLabel(m[3] ?? ''), dashed: op.includes('.'), thick: op.startsWith('='), arrow: op.endsWith('>') || /[xo]$/.test(op) && op.startsWith('--') && op.length === 3 }
}

export function parseMermaidFlow(source: string): ParsedFlow | null {
  const lines = source
    .split('\n')
    .map((l) => l.replace(/%%.*$/, '').trim())
    .filter(Boolean)
  if (!lines.length) return null
  const head = /^(flowchart|graph)\b\s*(TB|TD|BT|LR|RL)?/i.exec(lines[0])
  if (!head) return null
  const dir = (head[2] ?? 'TD').toUpperCase()
  const direction: 'TB' | 'LR' = dir === 'LR' || dir === 'RL' ? 'LR' : 'TB'

  const nodes = new Map<string, FlowNode>()
  const edges: FlowEdge[] = []
  const remember = (n: FlowNode) => {
    const prev = nodes.get(n.id)
    // 처음엔 id 만 나오고 나중에 모양·라벨이 정의되는 경우를 위해 더 구체적인 정의로 덮어쓴다
    if (!prev || (prev.label === prev.id && n.label !== n.id)) nodes.set(n.id, n)
  }

  // 'flowchart LR; A-->B' 처럼 첫 줄에 문장이 이어 붙은 경우도 처리한다
  const tail = lines[0].slice(head[0].length).replace(/^\s*;/, '').trim()
  for (const line of [...(tail ? [tail] : []), ...lines.slice(1)]) {
    if (/^(subgraph|end|direction|classDef|class|style|linkStyle|click|accTitle|accDescr)\b/i.test(line)) continue
    for (const stmt of line.split(';')) {
      const c: Cursor = { s: stmt.trim(), i: 0 }
      if (!c.s) continue
      let prev = readNodeGroup(c)
      if (!prev) continue
      prev.forEach(remember)
      for (;;) {
        skipSpaces(c)
        if (c.i >= c.s.length) break
        const edge = readEdge(c)
        if (!edge) break
        const next = readNodeGroup(c)
        if (!next) break
        next.forEach(remember)
        for (const a of prev) for (const b of next) edges.push({ from: a.id, to: b.id, ...edge })
        prev = next
      }
    }
  }
  if (nodes.size === 0) return null
  return { direction, nodes: [...nodes.values()], edges }
}

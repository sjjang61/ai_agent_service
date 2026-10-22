/**
 * 위젯으로 이미 보여 준 표를 답변 글에서 다시 보여 주지 않도록 걸러낸다.
 * 답변 글에 위젯 표와 같은 헤더(열 이름)를 가진 마크다운 표가 있으면 그 표와, 바로 위의 같은 제목을 뺀다.
 * 헤더가 다른 표(요약 등)는 새 정보이므로 남긴다. 저장된 답변 원문은 바꾸지 않고 화면에 그릴 때만 쓴다.
 */
const norm = (s: string) => s.replace(/[*_`\s]/g, '').toLowerCase()

const cells = (line: string) =>
  line
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map(norm)
    .filter(Boolean)

const isTableLine = (line: string) => line.trim().startsWith('|')
const headingText = (line: string) => {
  const m = line.trim().match(/^(?:#{1,6}\s+(.+)|\*\*(.+)\*\*)$/)
  return m ? norm(m[1] ?? m[2]) : null
}

function sameColumns(a: string[], b: string[]): boolean {
  if (!a.length || !b.length) return false
  const sa = new Set(a)
  const sb = new Set(b)
  let common = 0
  sa.forEach((x) => sb.has(x) && common++)
  return common / (sa.size + sb.size - common) >= 0.8
}

interface TableWidgetLike {
  type: string
  title?: string
  spec: unknown
}

export function stripWidgetTables(content: string, widgets: TableWidgetLike[]): string {
  const tables = widgets
    .filter((w) => w.type === 'table' && Array.isArray((w.spec as { columns?: unknown })?.columns))
    .map((w) => ({
      cols: ((w.spec as { columns: unknown[] }).columns).map((c) => norm(String(c))),
      title: norm(w.title ?? ''),
    }))
  if (!tables.length || !content.includes('|')) return content

  const lines = content.split('\n')
  const out: string[] = []
  let fenced = false
  for (let i = 0; i < lines.length; ) {
    const line = lines[i]
    if (/^\s*(```|~~~)/.test(line)) fenced = !fenced
    if (!fenced && isTableLine(line)) {
      let j = i
      while (j < lines.length && isTableLine(lines[j])) j++
      const header = cells(line)
      // 스트리밍 중 아직 헤더가 다 안 온 표(내용 끝, 구분선 전)는 열이 위젯 열의 일부면 미리 숨겨 깜박임을 막는다
      const incomplete = j >= lines.length && j - i === 1
      const hit = tables.find(
        (t) => sameColumns(header, t.cols) || (incomplete && header.length > 0 && header.every((c) => t.cols.includes(c)))
      )
      if (hit) {
        // 표 바로 위에 위젯 제목과 같은 제목이 있으면 같이 뺀다
        let k = out.length - 1
        while (k >= 0 && !out[k].trim()) k--
        const h = k >= 0 ? headingText(out[k]) : null
        if (h && hit.title && (h.includes(hit.title) || hit.title.includes(h))) out.length = k
        i = j
        continue
      }
      out.push(...lines.slice(i, j))
      i = j
      continue
    }
    out.push(line)
    i++
  }
  return out.join('\n').replace(/\n{3,}/g, '\n\n').replace(/^\n+/, '')
}

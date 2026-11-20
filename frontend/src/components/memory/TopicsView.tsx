import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { BookOpen } from 'lucide-react'
import { wikiApi } from '../../api/wiki'
import { T } from '../skills/typography'

/** Topics: 전문 지식은 위키에 영구 보관된다 (지식 그래프·병합·검색). 여기서는 최근 문서를 훑어보고 위키로 이동한다. */
export default function TopicsView() {
  const { data, isLoading } = useQuery({ queryKey: ['memory-topics'], queryFn: async () => (await wikiApi.list({ limit: 12 })).data })
  const entries = data ?? []
  return (
    <div className="space-y-3 max-w-[760px]">
      <p className={T.itemDesc}>
        주제별 전문 지식(Topics)은 위키에 영구 보관됩니다. 답변을 위키로 저장하면 AI가 정리하고, 같은 주제는 기존 문서에 합쳐지며, 에이전트는 필요할 때 위키를 검색해 씁니다.
      </p>
      <Link to="/wiki" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-surface-secondary hover:bg-surface-hover text-content-primary border border-border text-[13px] no-underline"><BookOpen size={14} />위키 열기</Link>
      {isLoading && <p className={T.itemDesc}>불러오는 중…</p>}
      {!isLoading && entries.length === 0 && <p className={T.itemDesc}>아직 저장된 주제가 없습니다.</p>}
      <ul className="space-y-2">
        {entries.map((e) => (
          <li key={e.id} className="bg-surface-secondary border border-border rounded-xl px-4 py-3">
            <div className={T.itemTitle}>{e.title}</div>
            {(e.summary || e.tags?.length) && <div className="text-[13px] text-content-secondary mt-0.5 truncate">{e.summary || e.tags.join(', ')}</div>}
          </li>
        ))}
      </ul>
    </div>
  )
}

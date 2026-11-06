import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeSanitize from 'rehype-sanitize'
import { File, FileText, Loader2, X } from 'lucide-react'
import { skillsApi } from '../../api/skills'
import { formatFullDateTime } from '../../utils/time'
import type { Skill, SkillDetail, SkillFileContent, SkillTranslation } from '../../types/skill'

/** SKILL.md 맨 앞의 --- frontmatter 를 본문과 분리한다 */
function splitFrontmatter(text: string): { meta: string; body: string } {
  const m = text.match(/^---\s*\n([\s\S]*?)\n---\s*(\n|$)/)
  return m ? { meta: m[1], body: text.slice(m[0].length) } : { meta: '', body: text }
}

/** 한글이 거의 없는 문서인지 (번역 버튼을 보여 줄지 판단) */
function needsTranslation(text: string): boolean {
  const hangul = (text.match(/[가-힣]/g) ?? []).length
  const latin = (text.match(/[A-Za-z]/g) ?? []).length
  return latin > 80 && hangul / (hangul + latin) < 0.2
}

const kb = (n: number) => (n < 1024 ? `${n}B` : `${(n / 1024).toFixed(n < 10240 ? 1 : 0)}KB`)

/** 스킬 상세: 메타 정보, 파일 목록, 선택한 파일의 내용(SKILL.md 는 마크다운으로 렌더링) */
export default function SkillDetailDialog({ skill, onClose }: { skill: Skill; onClose: () => void }) {
  const [path, setPath] = useState('SKILL.md')
  const [mode, setMode] = useState<'preview' | 'raw' | 'ko'>('preview')

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const { data: detail } = useQuery<SkillDetail>({
    queryKey: ['skill-detail', skill.id],
    queryFn: async () => (await skillsApi.detail(skill.id)).data,
  })
  const files = detail?.files ?? []
  useEffect(() => {
    if (files.length && !files.some((f) => f.path === path)) setPath(files[0].path)
  }, [files, path])

  const { data: file, isLoading, isError } = useQuery<SkillFileContent>({
    queryKey: ['skill-file', skill.id, path],
    queryFn: async () => (await skillsApi.file(skill.id, path)).data,
    enabled: files.some((f) => f.path === path),
  })

  const isMd = /\.(md|markdown)$/i.test(path)
  const canTranslate = !!file && !file.binary && /\.(md|markdown|txt)$/i.test(path) && needsTranslation(file.content)
  const qc = useQueryClient()
  const koKey = ['skill-translate', skill.id, path, file?.content.length ?? 0]
  const ko = useQuery<SkillTranslation>({
    queryKey: koKey,
    queryFn: async () => (await skillsApi.translate(skill.id, path)).data,
    enabled: mode === 'ko' && canTranslate,
    staleTime: Infinity,
    retry: false,
  })
  const retranslate = async () => {
    // 저장된 기록을 무시하고 AI 로 다시 번역해 새 기록으로 바꾼다
    qc.setQueryData(koKey, undefined)
    try {
      const res = await qc.fetchQuery({ queryKey: koKey, queryFn: async () => (await skillsApi.translate(skill.id, path, true)).data, staleTime: 0 })
      qc.setQueryData(koKey, res)
    } catch {
      // 실패 상태는 쿼리에 남아 '다시 시도' 로 표시된다
    }
  }
  const translating = mode === 'ko' && canTranslate
  const shown = translating ? ko.data?.content : file?.content
  const parsed = shown != null && (isMd || translating) && mode !== 'raw' ? splitFrontmatter(shown) : null
  const source = skill.source_url.startsWith('upload:')
    ? `ZIP 업로드 (${skill.source_url.slice(7)})`
    : skill.source_url.startsWith('manual:')
      ? '직접 작성'
      : skill.source_url

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onMouseDown={onClose}>
      <div
        className="w-full max-w-[980px] h-[min(760px,92vh)] flex flex-col bg-surface-primary border border-border rounded-[var(--radius-xl)] shadow-xl overflow-hidden"
        onMouseDown={(e) => e.stopPropagation()}
        role="dialog"
        aria-label={`${skill.name} 상세`}
      >
        <div className="flex items-start gap-3 px-6 pt-5 pb-4 border-b border-border">
          <div className="min-w-0 flex-1">
            <h2 className="text-[17px] font-semibold text-content-primary truncate">{skill.name}</h2>
            {skill.description && <p className="mt-1 text-[13px] text-content-secondary">{skill.description}</p>}
            <p className="mt-2 text-xs text-content-muted break-all">
              {skill.is_active ? '사용 중' : '비활성'}
              {skill.plugin_name ? ` · 플러그인 ${skill.plugin_name}` : ''}
              {' · 출처 '}
              {source.startsWith('http') ? <a href={source} target="_blank" rel="noopener noreferrer" className="text-accent-primary">{source}</a> : source}
              {' · 설치 '}{formatFullDateTime(skill.created_at)}
            </p>
          </div>
          <button onClick={onClose} aria-label="닫기" className="text-content-tertiary hover:text-content-primary border-none bg-transparent cursor-pointer">
            <X size={18} />
          </button>
        </div>

        <div className="flex flex-1 min-h-0">
          <div className="w-[240px] flex-shrink-0 border-r border-border overflow-y-auto py-2">
            {!detail ? (
              <div className="px-4 py-3 text-xs text-content-muted flex items-center gap-2"><Loader2 size={13} className="animate-spin" />불러오는 중...</div>
            ) : files.length === 0 ? (
              <div className="px-4 py-3 text-xs text-content-muted">파일을 찾을 수 없습니다. 스킬을 다시 설치해 보세요.</div>
            ) : (
              <>
                <div className="px-4 pb-1 text-[11px] text-content-muted">파일 {files.length}개{detail.truncated ? '+' : ''}</div>
                {files.map((f) => (
                  <button
                    key={f.path}
                    onClick={() => { setPath(f.path); setMode('preview') }}
                    title={f.path}
                    className={`w-full flex items-center gap-2 px-4 py-1.5 text-left text-xs border-none cursor-pointer ${f.path === path ? 'bg-surface-active text-content-primary' : 'bg-transparent text-content-secondary hover:bg-surface-hover'}`}
                  >
                    {f.path === 'SKILL.md' ? <FileText size={13} className="flex-shrink-0 text-accent-primary" /> : <File size={13} className="flex-shrink-0 text-content-muted" />}
                    <span className="truncate flex-1">{f.path}</span>
                    <span className="text-[10px] text-content-muted flex-shrink-0">{kb(f.size)}</span>
                  </button>
                ))}
              </>
            )}
          </div>

          <div className="flex-1 min-w-0 flex flex-col">
            <div className="flex items-center gap-2 px-5 py-2 border-b border-border text-xs text-content-muted">
              <span className="font-mono truncate flex-1">{path}</span>
              {(isMd || canTranslate) && (
                <div className="flex rounded-md border border-border overflow-hidden">
                  {([
                    ...(isMd ? [['preview', '미리보기'], ['raw', '원문']] : [['preview', '원문']]),
                    ...(canTranslate ? [['ko', '한글 번역']] : []),
                  ] as [typeof mode, string][]).map(([m, label]) => (
                    <button
                      key={m}
                      onClick={() => setMode(m)}
                      className={`px-2.5 py-1 border-none cursor-pointer text-xs ${mode === m ? 'bg-surface-active text-content-primary' : 'bg-transparent text-content-secondary hover:text-content-primary'}`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              )}
            </div>
            <div className="flex-1 overflow-auto px-5 py-4">
              {isLoading ? (
                <div className="text-xs text-content-muted flex items-center gap-2"><Loader2 size={13} className="animate-spin" />불러오는 중...</div>
              ) : isError ? (
                <div className="text-xs text-accent-red">파일을 불러오지 못했습니다.</div>
              ) : file?.binary ? (
                <div className="text-xs text-content-muted">바이너리 파일이라 내용을 표시하지 않습니다 ({kb(file.size)}).</div>
              ) : translating && ko.isFetching ? (
                <div className="text-xs text-content-muted flex items-center gap-2"><Loader2 size={13} className="animate-spin" />한국어로 번역하는 중... (문서가 길면 30초 이상 걸릴 수 있습니다)</div>
              ) : translating && ko.isError ? (
                <div className="text-xs text-accent-red">
                  번역하지 못했습니다.{' '}
                  <button onClick={() => ko.refetch()} className="text-accent-primary border-none bg-transparent cursor-pointer underline">다시 시도</button>
                </div>
              ) : file ? (
                <>
                  {translating && (
                    <div className="mb-3 text-xs text-content-muted flex items-center gap-2 flex-wrap">
                      <span>
                        {ko.data?.cached ? `저장된 번역입니다${ko.data.translated_at ? ` (${formatFullDateTime(ko.data.translated_at)})` : ''}.` : 'AI 가 번역한 내용입니다.'} 정확한 내용은 원문을 확인하세요.
                        {ko.data?.truncated ? ' 문서가 길어 앞부분만 번역했습니다.' : ''}
                      </span>
                      <button onClick={retranslate} className="text-accent-primary border-none bg-transparent cursor-pointer underline text-xs">다시 번역</button>
                    </div>
                  )}
                  {file.truncated && <div className="mb-3 text-xs text-accent-amber">파일이 커서 앞부분(200KB)만 표시합니다. 전체 {kb(file.size)}</div>}
                  {parsed ? (
                    <>
                      {parsed.meta && (
                        <pre className="mb-4 p-3 rounded-lg bg-surface-secondary border border-border text-xs font-mono text-content-secondary whitespace-pre-wrap break-words">{parsed.meta}</pre>
                      )}
                      <div className="skill-md text-sm text-content-primary leading-relaxed [&_h1]:text-lg [&_h1]:font-semibold [&_h1]:mt-4 [&_h2]:text-base [&_h2]:font-semibold [&_h2]:mt-4 [&_h3]:font-semibold [&_h3]:mt-3 [&_p]:my-2 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5 [&_code]:font-mono [&_code]:text-[12px] [&_code]:bg-surface-secondary [&_code]:px-1 [&_code]:rounded [&_pre]:bg-surface-secondary [&_pre]:border [&_pre]:border-border [&_pre]:rounded-lg [&_pre]:p-3 [&_pre]:overflow-auto [&_pre_code]:bg-transparent [&_pre_code]:p-0 [&_a]:text-accent-primary [&_table]:border-collapse [&_td]:border [&_td]:border-border [&_td]:px-2 [&_td]:py-1 [&_th]:border [&_th]:border-border [&_th]:px-2 [&_th]:py-1 [&_blockquote]:border-l-2 [&_blockquote]:border-border [&_blockquote]:pl-3 [&_blockquote]:text-content-secondary">
                        <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>{parsed.body}</ReactMarkdown>
                      </div>
                    </>
                  ) : (
                    <pre className="text-xs font-mono text-content-secondary whitespace-pre-wrap break-words">{shown ?? file.content}</pre>
                  )}
                </>
              ) : null}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

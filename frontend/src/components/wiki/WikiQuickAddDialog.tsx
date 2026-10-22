import { useEffect, useState } from 'react'
import { Loader2, Sparkles, X } from 'lucide-react'
import { useCreateWikiEntry, useMergeWikiEntry } from '../../hooks/useWiki'
import { wikiApi } from '../../api/wiki'
import WikiMarkdown from './WikiMarkdown'
import type { WikiCategory, WikiDraft, WikiLinkRef } from '../../types/wiki'

interface WikiQuickAddDialogProps {
  selectedText: string
  messageId?: string
  conversationId?: string
  onClose: () => void
}

export default function WikiQuickAddDialog({
  selectedText,
  messageId,
  conversationId,
  onClose,
}: WikiQuickAddDialogProps) {
  const createMutation = useCreateWikiEntry()
  const mergeMutation = useMergeWikiEntry()

  const [title, setTitle] = useState('')
  const [category, setCategory] = useState<WikiCategory>('general')
  const [tagsInput, setTagsInput] = useState('')
  const [error, setError] = useState('')
  const [summary, setSummary] = useState('')
  const [content, setContent] = useState('')
  const [preview, setPreview] = useState(true)
  // AI 가 선택한 텍스트를 위키 문서로 정리하는 동안 loading, 실패하면 failed (원문 그대로 저장 가능)
  const [draft, setDraft] = useState<'loading' | 'done' | 'failed'>('loading')

  // 같은 주제의 기존 문서가 있어 그 문서에 합친 결과일 때 그 문서, 그리고 연결할 관련 문서
  const [mergeInto, setMergeInto] = useState<WikiLinkRef | null>(null)
  const [related, setRelated] = useState<WikiLinkRef[]>([])

  const applyDraft = (d: WikiDraft) => {
    setTitle(d.title)
    setSummary(d.summary)
    setContent(d.content)
    setCategory(d.category)
    setTagsInput(d.tags.join(', '))
    setMergeInto(d.merge_into ?? null)
    setRelated(d.related ?? [])
    setDraft('done')
  }

  const runDraft = (allowMerge: boolean) => {
    setDraft('loading')
    wikiApi
      .draft(selectedText, allowMerge)
      .then((res) => applyDraft(res.data))
      .catch(() => {
        setContent(selectedText)
        setMergeInto(null)
        setRelated([])
        setDraft('failed')
      })
  }

  useEffect(() => {
    runDraft(true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedText])

  const useOriginal = () => {
    setMergeInto(null)
    setRelated([])
    setContent(selectedText)
    setSummary('')
    setDraft('failed')
    setPreview(false)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (!title.trim()) {
      setError('제목은 필수 입력입니다')
      return
    }

    if (!content.trim()) {
      setError('내용이 비어있습니다.')
      return
    }

    const tags = tagsInput
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean)

    try {
      const payload = {
        title: title.trim(),
        content: content.trim(),
        summary: summary.trim() || undefined,
        // 정리한 문서가 원문과 다를 때만 원문을 함께 보관한다
        source_text: content.trim() !== selectedText.trim() ? selectedText.trim() : undefined,
        category,
        tags,
        source_message_id: messageId,
        source_conversation_id: conversationId,
      }
      if (mergeInto) {
        // 같은 주제의 기존 문서에 합친다 (태그·연결은 합집합, 원문은 이어 붙임)
        await mergeMutation.mutateAsync({
          id: mergeInto.id,
          data: {
            content: payload.content,
            summary: payload.summary,
            tags,
            new_source_text: payload.source_text ?? selectedText.trim(),
            add_links: related.map((r) => r.id),
          },
        })
      } else {
        await createMutation.mutateAsync({ ...payload, links: related.map((r) => r.id) })
      }
      onClose()
    } catch (err: unknown) {
      const apiError = err as {
        response?: {
          data?: {
            detail?: string | Array<{ loc: string[]; msg: string; type: string }>
          }
        }
      }

      // Handle Pydantic validation errors
      const detail = apiError.response?.data?.detail
      if (Array.isArray(detail)) {
        const errorMessages = detail.map(e => `${e.loc.join('.')}: ${e.msg}`).join(', ')
        setError(`Validation Error: ${errorMessages}`)
      } else {
        setError(typeof detail === 'string' ? detail : '저장에 실패했습니다')
      }
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto rounded-xl p-5 bg-surface-primary border border-border shadow-xl">
        <div className="flex justify-between items-center mb-4">
          <h3 className="font-semibold text-content-primary">Wiki에 저장</h3>
          <button
            onClick={onClose}
            className="text-content-secondary hover:text-content-primary transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="text-xs text-content-secondary block mb-1.5">
              제목 *
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Wiki 항목 제목"
              autoFocus
              className="w-full px-3 py-2 bg-surface-secondary border border-border rounded-[var(--radius-md)] text-content-primary text-sm focus:outline-none focus:border-accent-primary transition-colors"
            />
          </div>

          <div className="flex items-center gap-2 text-xs">
            {draft === 'loading' ? (
              <span className="flex items-center gap-1.5 text-accent-primary"><Loader2 size={13} className="animate-spin" /> AI 가 선택한 내용을 위키 문서로 정리하는 중…</span>
            ) : draft === 'done' ? (
              <>
                <span className="flex items-center gap-1.5 text-accent-primary"><Sparkles size={13} /> AI 가 정리한 문서입니다. 저장 전에 고칠 수 있습니다.</span>
                <button type="button" onClick={useOriginal} className="ml-auto text-content-tertiary hover:text-content-primary underline bg-transparent border-none cursor-pointer">원문 그대로 사용</button>
              </>
            ) : (
              <span className="text-content-tertiary">정리 없이 선택한 원문 그대로 저장합니다.</span>
            )}
          </div>

          {draft === 'done' && mergeInto && (
            <div className="px-3 py-2 rounded-[var(--radius-md)] bg-accent-primary/10 border border-accent-primary/30 text-xs text-content-primary flex items-center gap-2">
              <span className="flex-1">
                <b>‘{mergeInto.title}’</b> 문서와 같은 주제여서, 새 문서를 만드는 대신 그 문서에 합쳐 정리했습니다. 저장하면 그 문서가 갱신됩니다.
              </span>
              <button type="button" onClick={() => runDraft(false)} className="flex-shrink-0 underline text-accent-primary bg-transparent border-none cursor-pointer">
                새 문서로 저장
              </button>
            </div>
          )}
          {draft === 'done' && !mergeInto && related.length > 0 && (
            <div className="text-xs text-content-secondary">
              관련 문서와 연결됩니다: {related.map((r) => `[[${r.title}]]`).join(', ')}
            </div>
          )}

          {summary && (
            <div>
              <label className="text-xs text-content-secondary block mb-1.5">요약</label>
              <textarea
                value={summary}
                onChange={(e) => setSummary(e.target.value)}
                rows={2}
                className="w-full px-3 py-2 bg-surface-secondary border border-border rounded-[var(--radius-md)] text-content-primary text-sm focus:outline-none focus:border-accent-primary resize-none"
              />
            </div>
          )}

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs text-content-secondary">본문</label>
              {draft === 'done' && (
                <button type="button" onClick={() => setPreview((v) => !v)} className="text-xs text-accent-primary bg-transparent border-none cursor-pointer">
                  {preview ? '마크다운 편집' : '미리보기'}
                </button>
              )}
            </div>
            {draft === 'loading' ? (
              <div className="h-40 rounded-[var(--radius-md)] border border-border bg-surface-tertiary animate-pulse" />
            ) : preview && draft === 'done' ? (
              <div className="px-4 py-2 max-h-72 overflow-y-auto bg-surface-secondary border border-border rounded-[var(--radius-md)]">
                <WikiMarkdown>{content}</WikiMarkdown>
              </div>
            ) : (
              <textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                rows={10}
                className="w-full px-3 py-2 bg-surface-secondary border border-border rounded-[var(--radius-md)] text-content-primary text-sm font-mono focus:outline-none focus:border-accent-primary resize-y"
              />
            )}
          </div>

          {draft === 'done' && (
            <details className="text-xs">
              <summary className="cursor-pointer text-content-tertiary hover:text-content-primary">선택한 원문 보기</summary>
              <div className="mt-2 px-3 py-2 bg-surface-tertiary border border-border rounded-[var(--radius-md)] text-content-secondary max-h-32 overflow-y-auto whitespace-pre-wrap">
                {selectedText}
              </div>
            </details>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-content-secondary block mb-1.5">
                카테고리
              </label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value as WikiCategory)}
                className="w-full px-3 py-2 bg-surface-secondary border border-border rounded-[var(--radius-md)] text-content-primary text-sm focus:outline-none focus:border-accent-primary transition-colors"
              >
                <option value="general">일반</option>
                <option value="work">업무</option>
                <option value="learning">학습</option>
                <option value="reference">참고</option>
              </select>
            </div>

            <div>
              <label className="text-xs text-content-secondary block mb-1.5">
                태그 (쉼표로 구분)
              </label>
              <input
                type="text"
                value={tagsInput}
                onChange={(e) => setTagsInput(e.target.value)}
                placeholder="python, api, ..."
                className="w-full px-3 py-2 bg-surface-secondary border border-border rounded-[var(--radius-md)] text-content-primary text-sm focus:outline-none focus:border-accent-primary transition-colors"
              />
            </div>
          </div>

          {error && (
            <p className="text-accent-red text-xs">{error}</p>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-content-secondary hover:text-content-primary text-sm transition-colors"
            >
              취소
            </button>
            <button
              type="submit"
              disabled={createMutation.isPending || mergeMutation.isPending || draft === 'loading'}
              className="px-4 py-2 bg-accent-primary hover:bg-accent-primary/90 text-white rounded-[var(--radius-md)] text-sm transition-colors disabled:opacity-50"
            >
              저장
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

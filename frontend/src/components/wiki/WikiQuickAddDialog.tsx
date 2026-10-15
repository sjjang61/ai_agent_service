import { useState } from 'react'
import { X } from 'lucide-react'
import { useCreateWikiEntry } from '../../hooks/useWiki'
import type { WikiCategory } from '../../types/wiki'

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

  const [title, setTitle] = useState('')
  const [category, setCategory] = useState<WikiCategory>('general')
  const [tagsInput, setTagsInput] = useState('')
  const [error, setError] = useState('')

  console.log('[WikiQuickAddDialog] Rendered with selectedText:', {
    length: selectedText?.length,
    preview: selectedText?.substring(0, 50),
    messageId,
    conversationId,
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (!title.trim()) {
      setError('제목은 필수 입력입니다')
      return
    }

    if (!selectedText.trim()) {
      setError('내용이 비어있습니다. 텍스트를 다시 선택해주세요.')
      return
    }

    const tags = tagsInput
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean)

    try {
      const payload = {
        title: title.trim(),
        content: selectedText.trim(),
        category,
        tags,
        source_message_id: messageId,
        source_conversation_id: conversationId,
      }
      console.log('[WikiQuickAddDialog] Submitting:', payload)

      await createMutation.mutateAsync(payload)
      console.log('[WikiQuickAddDialog] Success!')
      onClose()
    } catch (err: unknown) {
      console.error('[WikiQuickAddDialog] Error:', err)
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
      <div className="w-full max-w-lg mx-4 rounded-xl p-5 bg-surface-primary border border-border shadow-xl">
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

          <div>
            <label className="text-xs text-content-secondary block mb-1.5">
              선택된 내용
            </label>
            <div className="w-full px-3 py-2 bg-surface-tertiary border border-border rounded-[var(--radius-md)] text-content-secondary text-sm max-h-32 overflow-y-auto">
              {selectedText}
            </div>
          </div>

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
              disabled={createMutation.isPending}
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

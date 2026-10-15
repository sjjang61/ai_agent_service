import { useState } from 'react'
import { X } from 'lucide-react'
import { useCreateWikiEntry, useUpdateWikiEntry } from '../../hooks/useWiki'
import type { WikiEntry, WikiCategory } from '../../types/wiki'

interface WikiFormProps {
  entry: WikiEntry | null
  onClose: () => void
}

export default function WikiForm({ entry, onClose }: WikiFormProps) {
  const createMutation = useCreateWikiEntry()
  const updateMutation = useUpdateWikiEntry()

  const [title, setTitle] = useState(entry?.title || '')
  const [content, setContent] = useState(entry?.content || '')
  const [category, setCategory] = useState<WikiCategory>(entry?.category || 'general')
  const [tagsInput, setTagsInput] = useState(entry?.tags.join(', ') || '')
  const [error, setError] = useState('')

  const isEditing = !!entry

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (!title.trim() || !content.trim()) {
      setError('제목과 내용은 필수 입력입니다')
      return
    }

    const tags = tagsInput
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean)

    try {
      if (isEditing) {
        await updateMutation.mutateAsync({
          id: entry.id,
          data: { title, content, category, tags },
        })
      } else {
        await createMutation.mutateAsync({
          title: title.trim(),
          content: content.trim(),
          category,
          tags,
        })
      }
      onClose()
    } catch (err: unknown) {
      const apiError = err as { response?: { data?: { detail?: string } } }
      setError(apiError.response?.data?.detail || '저장에 실패했습니다')
    }
  }

  return (
    <div className="rounded-xl p-4 bg-surface-primary border border-border">
      <div className="flex justify-between items-center mb-4">
        <h3 className="font-medium text-content-primary">
          {isEditing ? 'Wiki 수정' : '새 Wiki 항목'}
        </h3>
        <button onClick={onClose} className="text-content-secondary hover:text-content-primary">
          <X size={18} />
        </button>
      </div>

      <form onSubmit={handleSubmit} className="space-y-3">
        <div>
          <label className="text-xs text-content-secondary block mb-1">제목 *</label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Wiki 항목 제목"
            className="w-full px-3 py-2 bg-surface-secondary border border-border rounded-[var(--radius-md)] text-content-primary text-sm focus:outline-none focus:border-accent-primary"
          />
        </div>

        <div>
          <label className="text-xs text-content-secondary block mb-1">내용 *</label>
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="Wiki 내용을 입력하세요"
            rows={8}
            className="w-full px-3 py-2 bg-surface-secondary border border-border rounded-[var(--radius-md)] text-content-primary text-sm focus:outline-none focus:border-accent-primary resize-none"
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-content-secondary block mb-1">카테고리</label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value as WikiCategory)}
              className="w-full px-3 py-2 bg-surface-secondary border border-border rounded-[var(--radius-md)] text-content-primary text-sm focus:outline-none focus:border-accent-primary"
            >
              <option value="general">일반</option>
              <option value="work">업무</option>
              <option value="learning">학습</option>
              <option value="reference">참고</option>
            </select>
          </div>

          <div>
            <label className="text-xs text-content-secondary block mb-1">
              태그 (쉼표로 구분)
            </label>
            <input
              type="text"
              value={tagsInput}
              onChange={(e) => setTagsInput(e.target.value)}
              placeholder="python, api, ..."
              className="w-full px-3 py-2 bg-surface-secondary border border-border rounded-[var(--radius-md)] text-content-primary text-sm focus:outline-none focus:border-accent-primary"
            />
          </div>
        </div>

        {error && <p className="text-accent-red text-xs">{error}</p>}

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
            disabled={createMutation.isPending || updateMutation.isPending}
            className="px-4 py-2 bg-accent-primary hover:bg-accent-primary/90 text-white rounded-[var(--radius-md)] text-sm transition-colors disabled:opacity-50"
          >
            {isEditing ? '수정' : '저장'}
          </button>
        </div>
      </form>
    </div>
  )
}

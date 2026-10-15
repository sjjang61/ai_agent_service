import { useState } from 'react'
import { X } from 'lucide-react'
import { useCreateMemory, useUpdateMemory } from '../../hooks/useMemories'
import type { Memory, MemoryCategory } from '../../types/memory'

interface MemoryFormProps {
  memory: Memory | null
  onClose: () => void
}

export default function MemoryForm({ memory, onClose }: MemoryFormProps) {
  const createMutation = useCreateMemory()
  const updateMutation = useUpdateMemory()

  const [key, setKey] = useState(memory?.key || '')
  const [value, setValue] = useState(memory?.value || '')
  const [category, setCategory] = useState<MemoryCategory>(
    memory?.category || 'general'
  )
  const [importance, setImportance] = useState(memory?.importance || 5)
  const [tagsInput, setTagsInput] = useState(memory?.tags.join(', ') || '')
  const [error, setError] = useState('')

  const isEditing = !!memory

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (!key.trim() || !value.trim()) {
      setError('키와 값은 필수 입력입니다')
      return
    }

    const tags = tagsInput
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean)

    try {
      if (isEditing) {
        await updateMutation.mutateAsync({
          id: memory.id,
          data: { category, value, importance, tags },
        })
      } else {
        await createMutation.mutateAsync({
          key: key.trim(),
          value: value.trim(),
          category,
          importance,
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
    <div className="rounded-xl p-4 bg-surface-secondary/80 border border-border">
      <div className="flex justify-between items-center mb-4">
        <h3 className="font-medium text-content-primary">
          {isEditing ? '메모리 수정' : '새 메모리 추가'}
        </h3>
        <button onClick={onClose} className="text-content-muted hover:text-content-primary">
          <X size={18} />
        </button>
      </div>

      <form onSubmit={handleSubmit} className="space-y-3">
        {!isEditing && (
          <div>
            <label className="text-xs text-content-muted block mb-1">
              키 (식별자)
            </label>
            <input
              type="text"
              value={key}
              onChange={(e) => setKey(e.target.value)}
              placeholder="예: preferred_language"
              className="w-full px-3 py-2 bg-surface-primary border border-border rounded-lg text-content-primary text-sm focus:outline-none focus:border-accent-primary"
            />
          </div>
        )}

        <div>
          <label className="text-xs text-content-muted block mb-1">값</label>
          <textarea
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="에이전트가 기억해야 할 내용"
            rows={3}
            className="w-full px-3 py-2 bg-surface-primary border border-border rounded-lg text-content-primary text-sm focus:outline-none focus:border-accent-primary resize-none"
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-content-muted block mb-1">
              카테고리
            </label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value as MemoryCategory)}
              className="w-full px-3 py-2 bg-surface-primary border border-border rounded-lg text-content-primary text-sm focus:outline-none focus:border-accent-primary"
            >
              <option value="general">일반</option>
              <option value="preference">선호도</option>
              <option value="fact">사실</option>
              <option value="instruction">지시사항</option>
            </select>
          </div>

          <div>
            <label className="text-xs text-content-muted block mb-1">
              중요도 ({importance})
            </label>
            <input
              type="range"
              min={1}
              max={10}
              value={importance}
              onChange={(e) => setImportance(Number(e.target.value))}
              className="w-full accent-accent-primary"
            />
          </div>
        </div>

        <div>
          <label className="text-xs text-content-muted block mb-1">
            태그 (쉼표로 구분)
          </label>
          <input
            type="text"
            value={tagsInput}
            onChange={(e) => setTagsInput(e.target.value)}
            placeholder="python, 코딩, 업무"
            className="w-full px-3 py-2 bg-surface-primary border border-border rounded-lg text-content-primary text-sm focus:outline-none focus:border-accent-primary"
          />
        </div>

        {error && <p className="text-accent-red text-xs">{error}</p>}

        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-content-muted hover:text-content-primary text-sm transition-colors"
          >
            취소
          </button>
          <button
            type="submit"
            disabled={createMutation.isPending || updateMutation.isPending}
            className="px-4 py-2 bg-accent-primary hover:bg-accent-hover text-white rounded-lg text-sm transition-colors disabled:opacity-50"
          >
            {isEditing ? '수정' : '저장'}
          </button>
        </div>
      </form>
    </div>
  )
}

import { useState } from 'react'
import { X } from 'lucide-react'
import { useCreateMemory, useUpdateMemory } from '../../hooks/useMemories'
import type { EpisodeDetail, Memory, MemoryCategory, MemoryType } from '../../types/memory'

interface MemoryFormProps {
  memory: Memory | null
  onClose: () => void
}

export default function MemoryForm({ memory, onClose }: MemoryFormProps) {
  const createMutation = useCreateMemory()
  const updateMutation = useUpdateMemory()

  const [key, setKey] = useState(memory?.key || '')
  const [value, setValue] = useState(memory?.value || '')
  const [memoryType, setMemoryType] = useState<MemoryType>(memory?.memory_type || 'semantic')
  const [detail, setDetail] = useState<EpisodeDetail>(
    memory?.detail || { situation: '', resolution: '', outcome: '' }
  )
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

    if (memoryType === 'episodic' && (!detail.situation.trim() || !detail.resolution.trim())) {
      setError('사례는 상황과 해결을 모두 입력해야 합니다')
      return
    }
    // 작업 방식은 항상 지시사항, 사례는 일반 카테고리로 저장한다
    const effCategory: MemoryCategory =
      memoryType === 'procedural' ? 'instruction' : memoryType === 'episodic' ? 'general' : category
    const epi = memoryType === 'episodic' ? { detail } : {}

    const tags = tagsInput
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean)

    try {
      if (isEditing) {
        await updateMutation.mutateAsync({
          id: memory.id,
          data: { category: effCategory, memory_type: memoryType, value, importance, tags, ...epi },
        })
      } else {
        await createMutation.mutateAsync({
          key: key.trim(),
          value: value.trim(),
          category: effCategory,
          memory_type: memoryType,
          importance,
          tags,
          ...epi,
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
        <div>
          <label className="text-xs text-content-muted block mb-1">종류</label>
          <div className="flex gap-1">
            {([['semantic', '사실'], ['procedural', '작업 방식'], ['episodic', '사례']] as const).map(([k, label]) => (
              <button
                key={k}
                type="button"
                onClick={() => setMemoryType(k)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  memoryType === k ? 'bg-accent-primary text-white' : 'bg-surface-primary text-content-muted hover:text-content-primary border border-border'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          <p className="text-[11px] text-content-tertiary mt-1">
            {memoryType === 'semantic' && '사용자에 대한 안정된 사실. 예: "백엔드 개발자, 서울 거주"'}
            {memoryType === 'procedural' && '에이전트가 따를 실행 방법으로 쓰세요. 예: "설명할 때 예제 코드를 먼저 보여 준 뒤 원리를 풀어 쓴다"'}
            {memoryType === 'episodic' && '특정 시점에 있었던 사건·해결 사례. 값에는 사례 제목을 쓰고 아래에 상황·해결·결과를 적습니다.'}
          </p>
        </div>

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

        {memoryType === 'episodic' && (
          <div className="space-y-2">
            {([['situation', '상황 (필수)'], ['resolution', '해결 (필수)'], ['outcome', '결과']] as const).map(([k, label]) => (
              <div key={k}>
                <label className="text-xs text-content-muted block mb-1">{label}</label>
                <textarea
                  value={detail[k]}
                  onChange={(e) => setDetail({ ...detail, [k]: e.target.value })}
                  rows={2}
                  maxLength={1000}
                  className="w-full px-3 py-2 bg-surface-primary border border-border rounded-lg text-content-primary text-sm focus:outline-none focus:border-accent-primary resize-none"
                />
              </div>
            ))}
          </div>
        )}

        <div className="grid grid-cols-2 gap-3">
          {memoryType === 'semantic' ? (
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
          ) : <div />}

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

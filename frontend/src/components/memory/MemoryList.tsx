import { useState, useMemo, useEffect } from 'react'
import { Search, Trash2, Edit2, Brain, Star, Tag } from 'lucide-react'
import { useMemories, useDeleteMemory } from '../../hooks/useMemories'
import { useMemoryStore } from '../../store/memoryStore'
import MemoryForm from './MemoryForm'
import type { Memory, MemoryCategory, MemoryType } from '../../types/memory'

const CATEGORY_LABELS: Record<
  MemoryCategory,
  { label: string; color: string }
> = {
  preference: {
    label: '선호도',
    color: 'bg-accent-purple/20 text-accent-purple border-accent-purple/30',
  },
  fact: {
    label: '사실',
    color: 'bg-accent-blue/20 text-accent-blue border-accent-blue/30',
  },
  instruction: {
    label: '지시사항',
    color: 'bg-accent-orange/20 text-accent-orange border-accent-orange/30',
  },
  general: {
    label: '일반',
    color: 'bg-surface-tertiary/50 text-content-muted border-border',
  },
}

const TYPE_TABS: { key: MemoryType | null; label: string; hint: string }[] = [
  { key: null, label: '전체', hint: '' },
  { key: 'semantic', label: '사실', hint: '사용자에 대한 비교적 안정된 사실 (직업, 거주지, 기술 스택 등). 참고 정보로 반영됩니다.' },
  { key: 'procedural', label: '작업 방식', hint: '에이전트가 앞으로 따를 실행 지침 (예: 예제를 먼저 보여 준 뒤 원리를 설명한다). 모든 응답에 적용됩니다.' },
  { key: 'episodic', label: '사례', hint: '특정 시점의 사건·해결 사례. 현재 요청과 비슷할 때만 참고되며, 오래될수록 중요도가 낮아져 자동 정리됩니다.' },
]

const TYPE_BADGE: Record<MemoryType, { label: string; color: string }> = {
  semantic: { label: '사실', color: 'bg-accent-blue/20 text-accent-blue border-accent-blue/30' },
  procedural: { label: '작업 방식', color: 'bg-accent-orange/20 text-accent-orange border-accent-orange/30' },
  episodic: { label: '사례', color: 'bg-accent-green/20 text-accent-green border-accent-green/30' },
}

const SOURCE_LABELS: Record<string, string> = {
  manual: '수동',
  auto_extracted: '자동',
  agent: '에이전트',
}

/** addTick: 페이지 제목 줄의 '메모리 추가' 버튼을 누를 때마다 바뀌는 값. 바뀌면 새 메모리 입력 폼을 연다. */
export default function MemoryList({ addTick = 0 }: { addTick?: number }) {
  const {
    memories,
    selectedCategory,
    selectedType,
    searchQuery,
    setSelectedCategory,
    setSelectedType,
    setSearchQuery,
  } = useMemoryStore()

  const queryParams = useMemo(
    () => ({
      category: selectedCategory || undefined,
      memory_type: selectedType || undefined,
      query: searchQuery || undefined,
    }),
    [selectedCategory, selectedType, searchQuery]
  )

  const { isLoading, refetch } = useMemories(queryParams)
  const deleteMutation = useDeleteMemory()

  const [showForm, setShowForm] = useState(false)
  const [editMemory, setEditMemory] = useState<Memory | null>(null)

  useEffect(() => {
    if (addTick > 0) {
      setEditMemory(null)
      setShowForm(true)
    }
  }, [addTick])

  const handleDelete = async (id: string) => {
    if (!confirm('이 메모리를 삭제하시겠습니까?')) return
    await deleteMutation.mutateAsync(id)
  }

  const categories: (MemoryCategory | null)[] = [
    null,
    'preference',
    'fact',
    'instruction',
    'general',
  ]

  return (
    <div className="space-y-4">
      {/* 종류 탭 */}
      <div>
        <div className="flex gap-1 border-b border-border">
          {TYPE_TABS.map((t) => (
            <button
              key={t.key ?? 'all'}
              onClick={() => setSelectedType(t.key)}
              className={`px-4 py-2 text-sm border-b-2 -mb-px transition-colors ${
                selectedType === t.key
                  ? 'border-accent-primary text-content-primary'
                  : 'border-transparent text-content-muted hover:text-content-primary'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
        {TYPE_TABS.find((t) => t.key === selectedType)?.hint && (
          <p className="text-xs text-content-tertiary mt-2">
            {TYPE_TABS.find((t) => t.key === selectedType)?.hint}
          </p>
        )}
      </div>

      {/* Search & Filter */}
      <div className="flex gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search
            size={14}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-content-muted"
          />
          <input
            type="text"
            placeholder="메모리 검색..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-2 bg-surface-secondary border border-border rounded-lg text-content-primary text-sm focus:outline-none focus:border-accent-primary"
          />
        </div>
        <div className={`flex gap-1 ${selectedType === 'episodic' || selectedType === 'procedural' ? 'hidden' : ''}`}>
          {categories.map((cat) => (
            <button
              key={cat || 'all'}
              onClick={() => setSelectedCategory(cat)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                selectedCategory === cat
                  ? 'bg-accent-primary text-white'
                  : 'bg-surface-secondary text-content-muted hover:text-content-primary'
              }`}
            >
              {cat ? CATEGORY_LABELS[cat].label : '전체'}
            </button>
          ))}
        </div>
      </div>

      {/* Form Modal */}
      {(showForm || editMemory) && (
        <MemoryForm
          memory={editMemory}
          onClose={() => {
            setShowForm(false)
            setEditMemory(null)
            refetch()
          }}
        />
      )}

      {/* Memory List */}
      {isLoading ? (
        <div className="text-content-muted text-sm py-8 text-center">
          로딩 중...
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 items-start">
          {memories.map((memory) => {
            const catStyle = CATEGORY_LABELS[memory.category]
            return (
              <div
                key={memory.id}
                className="rounded-xl p-4 bg-surface-secondary border border-border hover:border-border-light transition-colors"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <span className="text-[14px] font-medium text-content-primary">
                        {memory.key}
                      </span>
                      <span
                        className={`text-[10px] px-1.5 py-0.5 rounded border ${TYPE_BADGE[memory.memory_type ?? 'semantic'].color}`}
                      >
                        {TYPE_BADGE[memory.memory_type ?? 'semantic'].label}
                      </span>
                      {memory.memory_type !== 'episodic' && (
                        <span
                          className={`text-[10px] px-1.5 py-0.5 rounded border ${catStyle.color}`}
                        >
                          {catStyle.label}
                        </span>
                      )}
                      {memory.memory_type === 'episodic' && memory.occurred_at && (
                        <span className="text-[10px] text-content-tertiary">
                          {new Date(memory.occurred_at).toLocaleDateString()}
                        </span>
                      )}
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-tertiary text-content-muted">
                        {SOURCE_LABELS[memory.source]}
                      </span>
                      <div className="flex items-center gap-0.5">
                        {[...Array(Math.min(memory.importance, 5))].map(
                          (_, i) => (
                            <Star
                              key={i}
                              size={10}
                              className="text-accent-yellow fill-accent-yellow"
                            />
                          )
                        )}
                      </div>
                    </div>
                    <p className="text-[13px] text-content-secondary whitespace-pre-wrap break-words">
                      {memory.value}
                    </p>
                    {memory.memory_type === 'episodic' && memory.detail && (
                      <dl className="mt-2 space-y-0.5 text-xs text-content-secondary">
                        {([['situation', '상황'], ['resolution', '해결'], ['outcome', '결과']] as const).map(
                          ([k, label]) =>
                            memory.detail?.[k] ? (
                              <div key={k} className="flex gap-2">
                                <dt className="text-content-tertiary w-8 flex-shrink-0">{label}</dt>
                                <dd className="break-words">{memory.detail[k]}</dd>
                              </div>
                            ) : null
                        )}
                      </dl>
                    )}
                    {memory.tags.length > 0 && (
                      <div className="flex items-center gap-1 mt-2">
                        <Tag size={12} className="text-content-muted" />
                        {memory.tags.map((tag) => (
                          <span
                            key={tag}
                            className="text-xs bg-surface-tertiary px-1.5 py-0.5 rounded text-content-muted"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-1 flex-shrink-0">
                    <button
                      onClick={() => setEditMemory(memory)}
                      className="p-1.5 text-content-muted hover:text-content-primary transition-colors"
                      title="수정"
                    >
                      <Edit2 size={14} />
                    </button>
                    <button
                      onClick={() => handleDelete(memory.id)}
                      className="p-1.5 text-content-muted hover:text-accent-red transition-colors"
                      title="삭제"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              </div>
            )
          })}
          {memories.length === 0 && (
            <div className="col-span-full text-center text-content-muted py-12 border border-dashed border-border rounded-xl">
              <Brain size={32} className="mx-auto mb-2 opacity-50" />
              <p className="text-sm">저장된 메모리가 없습니다.</p>
              <p className="text-xs mt-1">
                에이전트가 사용자의 선호도를 기억하도록 메모리를 추가하세요.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

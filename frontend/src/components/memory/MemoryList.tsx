import { useState, useMemo } from 'react'
import { Plus, Search, Trash2, Edit2, Brain, Star, Tag } from 'lucide-react'
import { useMemories, useDeleteMemory } from '../../hooks/useMemories'
import { useMemoryStore } from '../../store/memoryStore'
import MemoryForm from './MemoryForm'
import type { Memory, MemoryCategory } from '../../types/memory'

const CATEGORY_LABELS: Record<
  MemoryCategory,
  { label: string; color: string }
> = {
  preference: {
    label: '선호도',
    color: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  },
  fact: {
    label: '사실',
    color: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  },
  instruction: {
    label: '지시사항',
    color: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  },
  general: {
    label: '일반',
    color: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
  },
}

const SOURCE_LABELS: Record<string, string> = {
  manual: '수동',
  auto_extracted: '자동',
  agent: '에이전트',
}

export default function MemoryList() {
  const {
    memories,
    selectedCategory,
    searchQuery,
    setSelectedCategory,
    setSearchQuery,
  } = useMemoryStore()

  const queryParams = useMemo(
    () => ({
      category: selectedCategory || undefined,
      query: searchQuery || undefined,
    }),
    [selectedCategory, searchQuery]
  )

  const { isLoading, refetch } = useMemories(queryParams)
  const deleteMutation = useDeleteMemory()

  const [showForm, setShowForm] = useState(false)
  const [editMemory, setEditMemory] = useState<Memory | null>(null)

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
      {/* Header */}
      <div className="flex justify-between items-center">
        <h2 className="text-lg font-semibold text-white flex items-center gap-2">
          <Brain size={20} />
          메모리 관리
        </h2>
        <button
          onClick={() => {
            setEditMemory(null)
            setShowForm(true)
          }}
          className="flex items-center gap-2 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm transition-colors"
        >
          <Plus size={14} />
          메모리 추가
        </button>
      </div>

      {/* Search & Filter */}
      <div className="flex gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search
            size={14}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
          />
          <input
            type="text"
            placeholder="메모리 검색..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500"
          />
        </div>
        <div className="flex gap-1">
          {categories.map((cat) => (
            <button
              key={cat || 'all'}
              onClick={() => setSelectedCategory(cat)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                selectedCategory === cat
                  ? 'bg-blue-600 text-white'
                  : 'bg-slate-800 text-slate-400 hover:text-white'
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
        <div className="text-slate-400 text-sm py-8 text-center">
          로딩 중...
        </div>
      ) : (
        <div className="space-y-2">
          {memories.map((memory) => {
            const catStyle = CATEGORY_LABELS[memory.category]
            return (
              <div
                key={memory.id}
                className="rounded-xl p-4 bg-slate-800 border border-slate-700 hover:border-slate-600 transition-colors"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <span className="font-medium text-white">
                        {memory.key}
                      </span>
                      <span
                        className={`text-[10px] px-1.5 py-0.5 rounded border ${catStyle.color}`}
                      >
                        {catStyle.label}
                      </span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-700 text-slate-400">
                        {SOURCE_LABELS[memory.source]}
                      </span>
                      <div className="flex items-center gap-0.5">
                        {[...Array(Math.min(memory.importance, 5))].map(
                          (_, i) => (
                            <Star
                              key={i}
                              size={10}
                              className="text-yellow-500 fill-yellow-500"
                            />
                          )
                        )}
                      </div>
                    </div>
                    <p className="text-sm text-slate-300 whitespace-pre-wrap break-words">
                      {memory.value}
                    </p>
                    {memory.tags.length > 0 && (
                      <div className="flex items-center gap-1 mt-2">
                        <Tag size={12} className="text-slate-500" />
                        {memory.tags.map((tag) => (
                          <span
                            key={tag}
                            className="text-xs bg-slate-700 px-1.5 py-0.5 rounded text-slate-400"
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
                      className="p-1.5 text-slate-400 hover:text-white transition-colors"
                      title="수정"
                    >
                      <Edit2 size={14} />
                    </button>
                    <button
                      onClick={() => handleDelete(memory.id)}
                      className="p-1.5 text-slate-400 hover:text-red-400 transition-colors"
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
            <div className="text-center text-slate-500 py-12 border border-dashed border-slate-700 rounded-xl">
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

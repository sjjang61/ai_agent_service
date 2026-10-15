import { useState, useMemo } from 'react'
import { Plus, Search, Trash2, Edit2, BookOpen, ChevronDown, ChevronRight } from 'lucide-react'
import { useWikiEntries, useDeleteWikiEntry } from '../../hooks/useWiki'
import { useWikiStore } from '../../store/wikiStore'
import WikiForm from './WikiForm'
import type { WikiEntry, WikiCategory } from '../../types/wiki'

const CATEGORY_LABELS: Record<WikiCategory, { label: string; color: string }> = {
  general: {
    label: '일반',
    color: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
  },
  work: {
    label: '업무',
    color: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  },
  learning: {
    label: '학습',
    color: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  },
  reference: {
    label: '참고',
    color: 'bg-green-500/20 text-green-400 border-green-500/30',
  },
}

function formatDate(dateString: string): string {
  const date = new Date(dateString)
  if (isNaN(date.getTime())) return ''
  const month = date.getMonth() + 1
  const day = date.getDate()
  return `${month}월 ${day}일`
}

export default function WikiList() {
  const {
    entries,
    selectedCategory,
    searchQuery,
    setSelectedCategory,
    setSearchQuery,
  } = useWikiStore()

  const queryParams = useMemo(
    () => ({
      category: selectedCategory || undefined,
      query: searchQuery || undefined,
    }),
    [selectedCategory, searchQuery]
  )

  const { isLoading, refetch } = useWikiEntries(queryParams)
  const deleteMutation = useDeleteWikiEntry()

  const [showForm, setShowForm] = useState(false)
  const [editEntry, setEditEntry] = useState<WikiEntry | null>(null)
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const handleDelete = async (id: string) => {
    if (!confirm('이 Wiki 항목을 삭제하시겠습니까?')) return
    await deleteMutation.mutateAsync(id)
  }

  const categories: (WikiCategory | null)[] = [null, 'general', 'work', 'learning', 'reference']

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex justify-between items-center">
        <h2 className="text-lg font-semibold text-content-primary flex items-center gap-2">
          <BookOpen size={20} />
          Personal Wiki
        </h2>
        <button
          onClick={() => {
            setEditEntry(null)
            setShowForm(true)
          }}
          className="flex items-center gap-2 px-3 py-1.5 bg-accent-primary hover:bg-accent-primary/90 text-white rounded-[var(--radius-md)] text-sm transition-colors"
        >
          <Plus size={14} />
          새 항목
        </button>
      </div>

      {/* Search & Filter */}
      <div className="flex gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search
            size={14}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-content-secondary"
          />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="검색..."
            className="w-full pl-9 pr-3 py-2 bg-surface-secondary border border-border rounded-[var(--radius-md)] text-content-primary text-sm focus:outline-none focus:border-accent-primary"
          />
        </div>

        <div className="flex gap-2">
          {categories.map((cat) => (
            <button
              key={cat || 'all'}
              onClick={() => setSelectedCategory(cat)}
              className={`px-3 py-2 rounded-[var(--radius-md)] text-sm transition-colors border ${
                selectedCategory === cat
                  ? 'bg-accent-primary text-white border-accent-primary'
                  : 'bg-surface-secondary text-content-secondary border-border hover:bg-surface-tertiary'
              }`}
            >
              {cat ? CATEGORY_LABELS[cat].label : '전체'}
            </button>
          ))}
        </div>
      </div>

      {/* Form */}
      {showForm && (
        <WikiForm
          entry={editEntry}
          onClose={() => {
            setShowForm(false)
            setEditEntry(null)
          }}
        />
      )}

      {/* List */}
      <div className="space-y-2">
        {isLoading ? (
          <p className="text-center text-content-secondary py-8">로딩중...</p>
        ) : entries.length === 0 ? (
          <div className="text-center py-12 text-content-secondary">
            <BookOpen size={48} className="mx-auto mb-3 opacity-30" />
            <p>저장된 Wiki 항목이 없습니다</p>
            <p className="text-sm mt-1">채팅 응답에서 텍스트를 선택하여 저장하세요</p>
          </div>
        ) : (
          entries.map((entry) => {
            const isExpanded = expandedId === entry.id
            return (
              <div
                key={entry.id}
                className="p-4 bg-surface-secondary border border-border rounded-[var(--radius-md)] hover:bg-surface-tertiary transition-colors"
              >
                <div
                  className="flex items-start justify-between cursor-pointer"
                  onClick={() => setExpandedId(isExpanded ? null : entry.id)}
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      {isExpanded ? (
                        <ChevronDown size={16} className="text-content-secondary" />
                      ) : (
                        <ChevronRight size={16} className="text-content-secondary" />
                      )}
                      <h3 className="font-medium text-content-primary">{entry.title}</h3>
                      <span
                        className={`px-2 py-0.5 rounded-full text-xs border ${
                          CATEGORY_LABELS[entry.category].color
                        }`}
                      >
                        {CATEGORY_LABELS[entry.category].label}
                      </span>
                    </div>
                    <div className="ml-6 flex items-center gap-3 text-xs text-content-secondary">
                      <span>{formatDate(entry.created_at)}</span>
                      {entry.tags.length > 0 && (
                        <div className="flex gap-1">
                          {entry.tags.map((tag) => (
                            <span key={tag} className="text-accent-primary">
                              #{tag}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
                    <button
                      onClick={() => {
                        setEditEntry(entry)
                        setShowForm(true)
                      }}
                      className="p-1.5 text-content-secondary hover:text-accent-primary transition-colors"
                    >
                      <Edit2 size={14} />
                    </button>
                    <button
                      onClick={() => handleDelete(entry.id)}
                      className="p-1.5 text-content-secondary hover:text-accent-red transition-colors"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>

                {isExpanded && (
                  <div className="ml-6 mt-3 pt-3 border-t border-border">
                    <p className="text-sm text-content-primary whitespace-pre-wrap">
                      {entry.content}
                    </p>
                  </div>
                )}
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}

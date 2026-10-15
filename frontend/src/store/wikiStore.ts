import { create } from 'zustand'
import type { WikiEntry, WikiCategory } from '../types/wiki'

interface WikiState {
  entries: WikiEntry[]
  selectedCategory: WikiCategory | null
  searchQuery: string
  isLoading: boolean

  setEntries: (entries: WikiEntry[]) => void
  addEntry: (entry: WikiEntry) => void
  updateEntry: (id: string, data: Partial<WikiEntry>) => void
  removeEntry: (id: string) => void
  setSelectedCategory: (category: WikiCategory | null) => void
  setSearchQuery: (query: string) => void
  setLoading: (loading: boolean) => void
}

export const useWikiStore = create<WikiState>((set) => ({
  entries: [],
  selectedCategory: null,
  searchQuery: '',
  isLoading: false,

  setEntries: (entries) => set({ entries }),

  addEntry: (entry) =>
    set((state) => ({
      entries: [entry, ...state.entries],
    })),

  updateEntry: (id, data) =>
    set((state) => ({
      entries: state.entries.map((e) => (e.id === id ? { ...e, ...data } : e)),
    })),

  removeEntry: (id) =>
    set((state) => ({
      entries: state.entries.filter((e) => e.id !== id),
    })),

  setSelectedCategory: (category) => set({ selectedCategory: category }),
  setSearchQuery: (query) => set({ searchQuery: query }),
  setLoading: (loading) => set({ isLoading: loading }),
}))

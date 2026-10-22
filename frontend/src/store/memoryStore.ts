import { create } from 'zustand'
import type { Memory, MemoryCategory, MemoryType } from '../types/memory'

interface MemoryState {
  memories: Memory[]
  selectedCategory: MemoryCategory | null
  selectedType: MemoryType | null
  searchQuery: string
  isLoading: boolean

  setMemories: (memories: Memory[]) => void
  addMemory: (memory: Memory) => void
  updateMemory: (id: string, data: Partial<Memory>) => void
  removeMemory: (id: string) => void
  setSelectedCategory: (category: MemoryCategory | null) => void
  setSelectedType: (type: MemoryType | null) => void
  setSearchQuery: (query: string) => void
  setLoading: (loading: boolean) => void
}

export const useMemoryStore = create<MemoryState>((set) => ({
  memories: [],
  selectedCategory: null,
  selectedType: null,
  searchQuery: '',
  isLoading: false,

  setMemories: (memories) => set({ memories }),

  addMemory: (memory) =>
    set((state) => ({
      memories: [memory, ...state.memories],
    })),

  updateMemory: (id, data) =>
    set((state) => ({
      memories: state.memories.map((m) => (m.id === id ? { ...m, ...data } : m)),
    })),

  removeMemory: (id) =>
    set((state) => ({
      memories: state.memories.filter((m) => m.id !== id),
    })),

  setSelectedCategory: (category) => set({ selectedCategory: category }),
  setSelectedType: (type) => set({ selectedType: type }),
  setSearchQuery: (query) => set({ searchQuery: query }),
  setLoading: (loading) => set({ isLoading: loading }),
}))

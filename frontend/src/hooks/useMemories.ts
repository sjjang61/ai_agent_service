import { useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { memoryApi } from '../api/memory'
import { useMemoryStore } from '../store/memoryStore'
import type {
  Memory,
  MemoryCreate,
  MemoryUpdate,
  MemorySearchParams,
} from '../types/memory'

export function useMemories(params?: MemorySearchParams) {
  const { setMemories, setLoading } = useMemoryStore()

  const query = useQuery({
    queryKey: ['memories', params],
    queryFn: () => memoryApi.list(params).then((r) => r.data),
  })

  useEffect(() => {
    if (query.data) setMemories(query.data)
  }, [query.data, setMemories])

  useEffect(() => {
    setLoading(query.isLoading)
  }, [query.isLoading, setLoading])

  return query
}

export function useCreateMemory() {
  const queryClient = useQueryClient()
  const { addMemory } = useMemoryStore()

  return useMutation({
    mutationFn: (data: MemoryCreate) =>
      memoryApi.create(data).then((r) => r.data),
    onSuccess: (memory: Memory) => {
      addMemory(memory)
      queryClient.invalidateQueries({ queryKey: ['memories'] })
    },
  })
}

export function useUpdateMemory() {
  const queryClient = useQueryClient()
  const { updateMemory } = useMemoryStore()

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: MemoryUpdate }) =>
      memoryApi.update(id, data).then((r) => r.data),
    onSuccess: (memory: Memory) => {
      updateMemory(memory.id, memory)
      queryClient.invalidateQueries({ queryKey: ['memories'] })
    },
  })
}

export function useDeleteMemory() {
  const queryClient = useQueryClient()
  const { removeMemory } = useMemoryStore()

  return useMutation({
    mutationFn: (id: string) => memoryApi.delete(id),
    onSuccess: (_, id) => {
      removeMemory(id)
      queryClient.invalidateQueries({ queryKey: ['memories'] })
    },
  })
}

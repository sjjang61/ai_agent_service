import { useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { wikiApi } from '../api/wiki'
import { useWikiStore } from '../store/wikiStore'
import type {
  WikiEntry,
  WikiEntryCreate,
  WikiEntryUpdate,
  WikiSearchParams,
} from '../types/wiki'

export function useWikiEntries(params?: WikiSearchParams) {
  const { setEntries, setLoading } = useWikiStore()

  const query = useQuery({
    queryKey: ['wiki-entries', params],
    queryFn: () => wikiApi.list(params).then((r) => r.data),
  })

  useEffect(() => {
    if (query.data) setEntries(query.data)
  }, [query.data, setEntries])

  useEffect(() => {
    setLoading(query.isLoading)
  }, [query.isLoading, setLoading])

  return query
}

export function useCreateWikiEntry() {
  const queryClient = useQueryClient()
  const { addEntry } = useWikiStore()

  return useMutation({
    mutationFn: (data: WikiEntryCreate) =>
      wikiApi.create(data).then((r) => r.data),
    onSuccess: (entry: WikiEntry) => {
      addEntry(entry)
      queryClient.invalidateQueries({ queryKey: ['wiki-entries'] })
    },
  })
}

export function useUpdateWikiEntry() {
  const queryClient = useQueryClient()
  const { updateEntry } = useWikiStore()

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: WikiEntryUpdate }) =>
      wikiApi.update(id, data).then((r) => r.data),
    onSuccess: (entry: WikiEntry) => {
      updateEntry(entry.id, entry)
      queryClient.invalidateQueries({ queryKey: ['wiki-entries'] })
    },
  })
}

export function useDeleteWikiEntry() {
  const queryClient = useQueryClient()
  const { removeEntry } = useWikiStore()

  return useMutation({
    mutationFn: (id: string) => wikiApi.delete(id),
    onSuccess: (_, id) => {
      removeEntry(id)
      queryClient.invalidateQueries({ queryKey: ['wiki-entries'] })
    },
  })
}

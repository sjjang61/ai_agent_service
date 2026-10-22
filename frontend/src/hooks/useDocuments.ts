import { useQuery } from '@tanstack/react-query'
import { documentsApi, type RagDocument } from '../api/documents'

/** 대화의 RAG 문서 목록. 처리 중인 문서가 있는 동안만 2초마다 다시 불러온다. */
export function useDocuments(conversationId: string | null) {
  return useQuery<RagDocument[]>({
    queryKey: ['documents', conversationId],
    queryFn: async () => (await documentsApi.list(conversationId as string)).data,
    enabled: !!conversationId,
    refetchInterval: (query) => (query.state.data?.some((d) => d.status === 'processing') ? 2000 : false),
  })
}

import apiClient from './client'

export interface RagDocument {
  id: string
  filename: string
  file_type: string
  file_size: number
  status: string // processing | completed | failed
  total_chunks: number
  created_at: string
  error_message?: string | null
}

export const documentsApi = {
  list: (conversationId: string) => apiClient.get<RagDocument[]>(`/conversations/${conversationId}/documents`),
  upload: (conversationId: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return apiClient.post<RagDocument>(`/conversations/${conversationId}/documents`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  remove: (documentId: string) => apiClient.delete(`/documents/${documentId}`),
}

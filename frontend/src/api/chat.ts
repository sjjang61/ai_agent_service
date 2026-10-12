import apiClient from './client'

export const chatApi = {
  getConversations: () => apiClient.get('/chat/conversations'),
  createConversation: (data: {
    title?: string
    llm_provider?: string
    model_name?: string
  }) => apiClient.post('/chat/conversations', data),
  deleteConversation: (id: string) => apiClient.delete(`/chat/conversations/${id}`),
  getMessages: (id: string) => apiClient.get(`/chat/conversations/${id}/messages`),
}

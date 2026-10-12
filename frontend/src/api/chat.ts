import apiClient from './client'

export const chatApi = {
  getConversations: () => apiClient.get('/chat/conversations'),
  createConversation: (data: {
    title?: string
    llm_provider?: string
    model_name?: string
  }) => apiClient.post('/chat/conversations', data),
  deleteConversation: (id: string) => apiClient.delete(`/chat/conversations/${id}`),
  answerForm: (id: string, data: { answers?: Record<string, string | string[]>; cancelled?: boolean }) =>
    apiClient.post(`/chat/conversations/${id}/form-answer`, data),
  /** 이 대화에서 실행 중인 에이전트를 취소한다 (실행 중이 아니면 404) */
  cancelRun: (id: string) => apiClient.post(`/chat/conversations/${id}/cancel`),
  getMessages: (id: string) => apiClient.get(`/chat/conversations/${id}/messages`),
}

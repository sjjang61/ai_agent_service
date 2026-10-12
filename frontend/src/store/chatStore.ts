import { create } from 'zustand'
import type { Conversation, Message } from '../types/chat'

interface ChatState {
  conversations: Conversation[]
  currentConversationId: string | null
  messages: Record<string, Message[]>
  setConversations: (c: Conversation[]) => void
  addConversation: (c: Conversation) => void
  removeConversation: (id: string) => void
  setCurrentConversation: (id: string | null) => void
  setMessages: (convId: string, msgs: Message[]) => void
  addMessage: (convId: string, msg: Message) => void
  updateLastAssistantMessage: (convId: string, content: string) => void
}

export const useChatStore = create<ChatState>((set) => ({
  conversations: [],
  currentConversationId: null,
  messages: {},
  setConversations: (conversations) => set({ conversations }),
  addConversation: (c) => set((s) => ({ conversations: [c, ...s.conversations] })),
  removeConversation: (id) =>
    set((s) => ({ conversations: s.conversations.filter((c) => c.id !== id) })),
  setCurrentConversation: (id) => set({ currentConversationId: id }),
  setMessages: (convId, msgs) =>
    set((s) => ({ messages: { ...s.messages, [convId]: msgs } })),
  addMessage: (convId, msg) =>
    set((s) => ({
      messages: { ...s.messages, [convId]: [...(s.messages[convId] || []), msg] },
    })),
  updateLastAssistantMessage: (convId, content) =>
    set((s) => {
      const msgs = [...(s.messages[convId] || [])]
      const last = msgs[msgs.length - 1]
      if (last && last.role === 'assistant') {
        msgs[msgs.length - 1] = { ...last, content }
      }
      return { messages: { ...s.messages, [convId]: msgs } }
    }),
}))

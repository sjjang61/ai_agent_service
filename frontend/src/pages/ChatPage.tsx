import { useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useChatStore } from '../store/chatStore'
import { chatApi } from '../api/chat'
import ChatLayout from '../components/chat/ChatLayout'
import type { Conversation, Message } from '../types/chat'
import { isStreaming } from '../hooks/useAgentStream'

export default function ChatPage() {
  const { conversationId } = useParams()
  const { setConversations, setMessages, setCurrentConversation } = useChatStore()
  const navigate = useNavigate()

  useEffect(() => {
    chatApi.getConversations().then((r) => {
      const convs = r.data as Conversation[]
      setConversations(convs)
      if (!conversationId && convs.length > 0) {
        navigate(`/chat/${convs[0].id}`)
      }
    })
  }, [])

  useEffect(() => {
    if (conversationId) {
      setCurrentConversation(conversationId)
      chatApi.getMessages(conversationId).then((r) => {
        const saved = r.data as Message[]
        // 다른 화면에 갔다 돌아왔을 때 이 대화의 응답이 아직 스트리밍 중이면, 서버에는 이번 답변이 저장돼 있지 않다.
        // 그대로 덮어쓰면 진행 중인 답변이 사라지고 이후 토큰도 붙을 곳이 없어지므로, 화면의 진행 중 메시지를 이어 붙인다.
        if (isStreaming(conversationId)) {
          const local = useChatStore.getState().messages[conversationId] ?? []
          let start = -1
          for (let i = local.length - 1; i >= 0; i--) {
            if (local[i].role === 'user' && local[i].id.startsWith('user-')) { start = i; break }
          }
          if (start >= 0) {
            const tail = local.slice(start)
            let base = saved
            for (let i = saved.length - 1; i >= 0; i--) {
              if (saved[i].role === 'user' && saved[i].content === tail[0].content) { base = saved.slice(0, i); break }
            }
            setMessages(conversationId, [...base, ...tail])
            return
          }
        }
        setMessages(conversationId, saved)
      })
    }
  }, [conversationId])

  return <ChatLayout />
}

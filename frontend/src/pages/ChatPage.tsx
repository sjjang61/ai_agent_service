import { useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useChatStore } from '../store/chatStore'
import { chatApi } from '../api/chat'
import ChatLayout from '../components/chat/ChatLayout'
import type { Conversation, Message } from '../types/chat'

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
        setMessages(conversationId, r.data as Message[])
      })
    }
  }, [conversationId])

  return <ChatLayout />
}

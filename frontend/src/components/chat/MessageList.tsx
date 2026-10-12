import { useEffect, useRef } from 'react'
import { useChatStore } from '../../store/chatStore'
import MessageBubble from './MessageBubble'

export default function MessageList({ conversationId }: { conversationId: string }) {
  const { messages } = useChatStore()
  const msgs = messages[conversationId] || []
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [msgs])

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      {msgs.length === 0 && (
        <div className="flex items-center justify-center h-full">
          <p className="text-slate-500 text-sm">Send a message to start the conversation</p>
        </div>
      )}
      {msgs.map((msg) => (
        <MessageBubble key={msg.id} message={msg} />
      ))}
      <div ref={bottomRef} />
    </div>
  )
}

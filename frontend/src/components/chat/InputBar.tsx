import { useState, useRef } from 'react'
import { Send, Loader2 } from 'lucide-react'
import { useAgentStore } from '../../store/agentStore'
import { useAgentStream } from '../../hooks/useAgentStream'

export default function InputBar({ conversationId }: { conversationId: string }) {
  const [value, setValue] = useState('')
  const { isRunning } = useAgentStore()
  const { sendMessage } = useAgentStream(conversationId)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const handleSend = async () => {
    if (!value.trim() || isRunning) return
    const content = value.trim()
    setValue('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
    await sendMessage(content)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleInput = () => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`
    }
  }

  return (
    <div className="p-4 border-t border-slate-700 bg-slate-900">
      <div className="flex gap-3 items-end bg-slate-800 rounded-xl border border-slate-600 px-4 py-3 focus-within:border-blue-500 transition-colors">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onInput={handleInput}
          rows={1}
          placeholder="메시지를 입력하세요... (Shift+Enter: 줄바꿈)"
          disabled={isRunning}
          className="flex-1 bg-transparent text-white resize-none outline-none text-sm placeholder-slate-500 max-h-40 leading-6"
          style={{ minHeight: '24px' }}
        />
        <button
          onClick={handleSend}
          disabled={!value.trim() || isRunning}
          className="flex-shrink-0 p-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
        >
          {isRunning ? (
            <Loader2 size={16} className="animate-spin" />
          ) : (
            <Send size={16} />
          )}
        </button>
      </div>
      <p className="text-xs text-slate-600 text-center mt-2">
        AI can make mistakes. Verify important information.
      </p>
    </div>
  )
}

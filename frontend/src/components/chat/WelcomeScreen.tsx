import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Cloud, Folder, Monitor, Plus, ThumbsUp, Settings, Send, Mic, Loader2 } from 'lucide-react'
import { useChatStore } from '../../store/chatStore'
import { chatApi } from '../../api/chat'
import type { Conversation } from '../../types/chat'

export default function WelcomeScreen() {
  const [input, setInput] = useState('')
  const [activeTab, setActiveTab] = useState<'project' | 'computer'>('project')
  const [isCreating, setIsCreating] = useState(false)
  const { addConversation, setCurrentConversation } = useChatStore()
  const navigate = useNavigate()

  const handleSubmit = async () => {
    if (!input.trim() || isCreating) return

    setIsCreating(true)
    try {
      // Create a new conversation with the input as title
      const title = input.slice(0, 50) + (input.length > 50 ? '...' : '')
      const res = await chatApi.createConversation({ title })
      const conversation = res.data as Conversation
      addConversation(conversation)
      setCurrentConversation(conversation.id)
      navigate(`/chat/${conversation.id}`)
      // The message will be sent via InputBar after navigation
    } catch (error) {
      console.error('Failed to create conversation:', error)
    } finally {
      setIsCreating(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <div className="flex-1 flex flex-col">
      {/* Main Content */}
      <div className="flex-1 flex flex-col items-center justify-center px-6">
        {/* Welcome Icon */}
        <div className="w-20 h-20 mb-6 text-content-tertiary">
          <Cloud size={80} strokeWidth={1.5} />
        </div>

        {/* Welcome Title */}
        <h1 className="text-[28px] font-semibold text-content-primary mb-2">
          What would you like to create?
        </h1>
        <p className="text-[15px] text-content-secondary">
          Ask me to write code, analyze, debug, or anything else
        </p>
      </div>

      {/* Input Area */}
      <div className="px-6 pb-6 max-w-[800px] w-full mx-auto">
        {/* Tabs */}
        <div className="flex gap-1 mb-2">
          <button
            onClick={() => setActiveTab('project')}
            className={`flex items-center gap-1.5 px-3.5 py-2 text-[13px] rounded-[var(--radius-md)] transition-colors ${
              activeTab === 'project'
                ? 'bg-surface-tertiary text-content-primary'
                : 'text-content-secondary hover:bg-surface-hover hover:text-content-primary'
            }`}
          >
            <Folder size={16} />
            Select Project
          </button>
          <button
            onClick={() => setActiveTab('computer')}
            className={`flex items-center gap-1.5 px-3.5 py-2 text-[13px] rounded-[var(--radius-md)] transition-colors ${
              activeTab === 'computer'
                ? 'bg-surface-tertiary text-content-primary'
                : 'text-content-secondary hover:bg-surface-hover hover:text-content-primary'
            }`}
          >
            <Monitor size={16} />
            This Computer
          </button>
        </div>

        {/* Input Container */}
        <div className="bg-surface-secondary border border-border rounded-[var(--radius-lg)] overflow-hidden">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask anything..."
            rows={1}
            disabled={isCreating}
            className="w-full px-[18px] py-4 text-[15px] text-content-primary bg-transparent
              border-none outline-none resize-none placeholder:text-content-muted
              min-h-[52px] max-h-[200px] disabled:opacity-50"
          />

          {/* Toolbar */}
          <div className="flex items-center justify-between px-3.5 py-2.5 border-t border-border">
            <div className="flex items-center gap-1">
              <button
                className="flex items-center gap-1.5 px-3 py-2 text-[13px] text-content-secondary
                  hover:bg-surface-hover hover:text-content-primary rounded-[var(--radius-sm)] transition-colors"
              >
                <Plus size={16} />
              </button>
              <button
                className="flex items-center gap-1.5 px-3 py-2 text-[13px] text-content-secondary
                  hover:bg-surface-hover hover:text-content-primary rounded-[var(--radius-sm)] transition-colors"
              >
                <ThumbsUp size={16} />
                Approval Request
              </button>
              <button
                className="flex items-center gap-1.5 px-3 py-2 text-[13px] text-content-secondary
                  hover:bg-surface-hover hover:text-content-primary rounded-[var(--radius-sm)] transition-colors"
              >
                <Settings size={16} />
              </button>
            </div>

            <div className="flex items-center gap-2">
              <button
                className="px-2.5 py-1.5 text-xs text-content-secondary hover:text-content-primary transition-colors"
              >
                Claude 3.5 Sonnet
              </button>
              <button
                className="w-9 h-9 rounded-full flex items-center justify-center
                  text-content-secondary hover:bg-surface-hover hover:text-content-primary transition-colors"
              >
                <Mic size={18} />
              </button>
              <button
                onClick={handleSubmit}
                disabled={!input.trim() || isCreating}
                className="w-9 h-9 rounded-full flex items-center justify-center
                  bg-accent-primary hover:bg-accent-hover text-white transition-colors
                  disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {isCreating ? (
                  <Loader2 size={18} className="animate-spin" />
                ) : (
                  <Send size={18} />
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

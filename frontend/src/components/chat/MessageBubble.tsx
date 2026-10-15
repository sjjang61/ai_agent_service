import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import type { Message } from '../../types/chat'
import StepProgressItem from './StepProgressItem'
import StreamingCursor from './StreamingCursor'
import WidgetRenderer, { extractWidgets } from '../widgets/WidgetRenderer'
import TodoCard, { extractLatestTodos } from './TodoCard'
import FormCard, { extractLatestForm } from './FormCard'
import { useAgentStore } from '../../store/agentStore'
import { useChatStore } from '../../store/chatStore'
import { Paperclip, Bot, User } from 'lucide-react'
import { formatSize } from '../sandbox/ArtifactsPanel'
import { useAuthStore } from '../../store/authStore'
import { useTextSelection } from '../../hooks/useTextSelection'
import SelectionTooltip from '../wiki/SelectionTooltip'
import WikiQuickAddDialog from '../wiki/WikiQuickAddDialog'

function formatKoreanDateTime(dateString: string): string {
  const date = new Date(dateString)
  if (isNaN(date.getTime())) return ''

  const month = date.getMonth() + 1
  const day = date.getDate()
  const hours = date.getHours()
  const minutes = date.getMinutes()

  const period = hours < 12 ? '오전' : '오후'
  const displayHours = hours === 0 ? 12 : hours > 12 ? hours - 12 : hours
  const displayMinutes = minutes.toString().padStart(2, '0')

  return `${month}월 ${day}일 ${period} ${displayHours}:${displayMinutes}`
}

export default function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user'
  const { isRunning } = useAgentStore()
  const { messages, currentConversationId } = useChatStore()
  const { user } = useAuthStore()
  const { selectedText, position, clearSelection } = useTextSelection()
  const [showWikiDialog, setShowWikiDialog] = useState(false)
  const [savedSelectedText, setSavedSelectedText] = useState('')

  const msgs = currentConversationId ? messages[currentConversationId] || [] : []
  const isLastAssistant = !isUser && msgs[msgs.length - 1]?.id === message.id
  const widgets = isUser ? [] : extractWidgets(message.agent_steps)
  const todos = isUser ? null : extractLatestTodos(message.agent_steps)
  const form = isUser ? null : extractLatestForm(message.agent_steps)
  const showCursor = isLastAssistant && isRunning && !message.content

  const handleSaveToWiki = () => {
    console.log('[MessageBubble] Opening Wiki dialog with selectedText:', {
      length: selectedText?.length,
      preview: selectedText?.substring(0, 50),
    })
    // Save the selected text before opening dialog
    setSavedSelectedText(selectedText)
    setShowWikiDialog(true)
  }

  const handleCloseWikiDialog = () => {
    console.log('[MessageBubble] Closing Wiki dialog')
    setShowWikiDialog(false)
    setSavedSelectedText('')
    clearSelection()
  }

  return (
    <div className="message">
      {/* Header */}
      <div className="flex items-center gap-2.5 mb-3">
        <div
          className={`w-7 h-7 rounded-full flex items-center justify-center text-sm flex-shrink-0 ${
            isUser
              ? 'bg-gradient-to-br from-accent-primary to-purple-500'
              : 'bg-surface-tertiary border border-border'
          }`}
        >
          {isUser ? (
            <span className="text-white text-xs font-semibold">
              {user?.display_name?.slice(0, 2).toUpperCase() || 'U'}
            </span>
          ) : (
            <Bot size={14} className="text-content-secondary" />
          )}
        </div>
        <span className="text-sm font-semibold text-content-primary">
          {isUser ? 'You' : 'Agent'}
        </span>
      </div>

      {/* Content */}
      <div className="pl-[38px]">
        {/* Agent steps */}
        {message.agent_steps && message.agent_steps.length > 0 && (
          <div className="mb-3 space-y-1">
            {message.agent_steps.map((step, i) => (
              <StepProgressItem
                key={i}
                step={{
                  id: `msg-${message.id}-step-${i}`,
                  type: step.type as 'thought' | 'tool_call' | 'tool_result',
                  tool: step.tool,
                  content: step.content,
                  input: step.input,
                  output: step.output,
                }}
              />
            ))}
          </div>
        )}

        {todos && <TodoCard todos={todos} />}

        {form && (
          <FormCard
            form={form}
            conversationId={message.conversation_id}
            interactive={isLastAssistant && isRunning}
          />
        )}

        <WidgetRenderer widgets={widgets} />

        {/* Attachments */}
        {message.attachments && message.attachments.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-2">
            {message.attachments.map((a) => (
              <span
                key={a.path}
                title={a.path}
                className="inline-flex items-center gap-1 max-w-[220px] px-2 py-1 rounded-[var(--radius-md)] text-xs border bg-surface-tertiary border-border text-content-secondary"
              >
                <Paperclip size={11} className="flex-shrink-0" />
                <span className="truncate">{a.name}</span>
                <span className="opacity-60 flex-shrink-0">{formatSize(a.size)}</span>
              </span>
            ))}
          </div>
        )}

        {/* Message content */}
        <div className="prose prose-sm max-w-none text-content-primary">
          {message.content === '__error__' ? (
            <span className="text-accent-red not-prose">
              An error occurred. Please try again later.
            </span>
          ) : message.content ? (
            <ReactMarkdown>{message.content}</ReactMarkdown>
          ) : showCursor ? (
            <StreamingCursor />
          ) : (
            <span className="text-content-muted italic">...</span>
          )}
        </div>
        {!isUser && message.created_at && (
          <div className="mt-2 text-xs text-slate-500 text-right">
            {formatKoreanDateTime(message.created_at)}
          </div>
        )}
      </div>

      {/* Text Selection Tooltip (only for assistant messages) */}
      {!isUser && selectedText && position && (
        <SelectionTooltip
          selectedText={selectedText}
          position={position}
          onSaveToWiki={handleSaveToWiki}
          onClose={clearSelection}
        />
      )}

      {/* Wiki Quick Add Dialog */}
      {showWikiDialog && (
        <WikiQuickAddDialog
          selectedText={savedSelectedText}
          messageId={message.id}
          conversationId={message.conversation_id}
          onClose={handleCloseWikiDialog}
        />
      )}
    </div>
  )
}

import ReactMarkdown from 'react-markdown'
import type { Message } from '../../types/chat'
import StepProgressItem from './StepProgressItem'
import StreamingCursor from './StreamingCursor'
import WidgetRenderer, { extractWidgets } from '../widgets/WidgetRenderer'
import TodoCard, { extractLatestTodos } from './TodoCard'
import FormCard, { extractLatestForm } from './FormCard'
import { useAgentStore } from '../../store/agentStore'
import { useChatStore } from '../../store/chatStore'
import { Paperclip } from 'lucide-react'
import { formatSize } from '../sandbox/ArtifactsPanel'

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

  const msgs = currentConversationId ? messages[currentConversationId] || [] : []
  const isLastAssistant = !isUser && msgs[msgs.length - 1]?.id === message.id
  const widgets = isUser ? [] : extractWidgets(message.agent_steps)
  const todos = isUser ? null : extractLatestTodos(message.agent_steps)
  const form = isUser ? null : extractLatestForm(message.agent_steps)
  const showCursor = isLastAssistant && isRunning && !message.content

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      {!isUser && (
        <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0 mr-3 mt-1">
          <span className="text-white text-xs font-bold">AI</span>
        </div>
      )}
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 ${
          isUser
            ? 'bg-blue-600 text-white rounded-tr-sm'
            : 'bg-slate-800 text-slate-100 rounded-tl-sm border border-slate-700'
        }`}
      >
        {/* 저장된 에이전트 스텝 — 컴팩트 클릭 가능 항목으로 표시 */}
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
        {message.attachments && message.attachments.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-2">
            {message.attachments.map((a) => (
              <span
                key={a.path}
                title={a.path}
                className={`inline-flex items-center gap-1 max-w-[220px] px-2 py-1 rounded-lg text-xs border ${
                  isUser ? 'bg-blue-700/60 border-blue-400/40 text-blue-50' : 'bg-slate-700/60 border-slate-600 text-slate-200'
                }`}
              >
                <Paperclip size={11} className="flex-shrink-0" />
                <span className="truncate">{a.name}</span>
                <span className="opacity-60 flex-shrink-0">{formatSize(a.size)}</span>
              </span>
            ))}
          </div>
        )}
        <div className="prose prose-invert prose-sm max-w-none">
          {message.content === '__error__' ? (
            <span className="text-red-400 not-prose">
              비정상적인 에러 발생으로 잠시후에 다시 시도해주세요.
            </span>
          ) : message.content ? (
            <ReactMarkdown>{message.content}</ReactMarkdown>
          ) : showCursor ? (
            <StreamingCursor />
          ) : (
            <span className="text-slate-500 italic">...</span>
          )}
        </div>
        {!isUser && message.created_at && (
          <div className="mt-2 text-xs text-slate-500 text-right">
            {formatKoreanDateTime(message.created_at)}
          </div>
        )}
      </div>
    </div>
  )
}

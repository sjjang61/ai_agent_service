import ReactMarkdown from 'react-markdown'
import type { Message } from '../../types/chat'
import StepProgressItem from './StepProgressItem'
import StreamingCursor from './StreamingCursor'
import { useAgentStore } from '../../store/agentStore'
import { useChatStore } from '../../store/chatStore'

export default function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user'
  const { isRunning } = useAgentStore()
  const { messages, currentConversationId } = useChatStore()

  const msgs = currentConversationId ? messages[currentConversationId] || [] : []
  const isLastAssistant = !isUser && msgs[msgs.length - 1]?.id === message.id
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
      </div>
    </div>
  )
}

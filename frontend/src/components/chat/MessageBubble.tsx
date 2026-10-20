import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'
import rehypeSanitize from 'rehype-sanitize'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark, oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism'
import type { Message } from '../../types/chat'
import StepProgressItem from './StepProgressItem'
import StreamingCursor from './StreamingCursor'
import WidgetRenderer, { extractWidgets } from '../widgets/WidgetRenderer'
import TodoCard, { extractLatestTodos } from './TodoCard'
import FormCard, { extractLatestForm } from './FormCard'
import ScheduleCard, { extractScheduleResults } from './ScheduleCard'
import { useAgentStore } from '../../store/agentStore'
import { useChatStore } from '../../store/chatStore'
import { Paperclip, Bot, User, Copy, Check } from 'lucide-react'
import { formatSize } from '../sandbox/ArtifactsPanel'
import { useAuthStore } from '../../store/authStore'
import WorkflowDiagram from '../workflow/WorkflowDiagram'
import { shouldShowWorkflow } from '../workflow/WorkflowDetector'
import { useState } from 'react'
import { useTypingAnimation } from '../../hooks/useTypingAnimation'
import { getTypingSpeed } from '../../config/animation'
import { useTextSelection } from '../../hooks/useTextSelection'
import SelectionTooltip from '../wiki/SelectionTooltip'
import WikiQuickAddDialog from '../wiki/WikiQuickAddDialog'

// 코드 블록 컴포넌트
function CodeBlock({ inline, className, children, ...props }: any) {
  const [copied, setCopied] = useState(false)
  const match = /language-(\w+)/.exec(className || '')
  const language = match ? match[1] : ''
  const code = String(children).replace(/\n$/, '')

  // 다크모드 감지 (간단한 방법)
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark'

  const handleCopy = async () => {
    await navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (inline) {
    return (
      <code className="px-1.5 py-0.5 rounded bg-surface-tertiary text-accent-primary font-mono text-sm" {...props}>
        {children}
      </code>
    )
  }

  return (
    <div className="relative group my-3">
      <div className="flex items-center justify-between px-4 py-2 bg-surface-tertiary border-b border-border rounded-t-lg">
        <span className="text-xs font-semibold text-content-secondary uppercase">{language || 'code'}</span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 px-2 py-1 text-xs rounded hover:bg-surface-hover transition-colors text-content-secondary"
        >
          {copied ? (
            <>
              <Check size={12} />
              Copied!
            </>
          ) : (
            <>
              <Copy size={12} />
              Copy
            </>
          )}
        </button>
      </div>
      <SyntaxHighlighter
        style={isDark ? oneDark : oneLight}
        language={language}
        PreTag="div"
        className="!mt-0 !rounded-t-none !rounded-b-lg"
        customStyle={{
          margin: 0,
          borderTopLeftRadius: 0,
          borderTopRightRadius: 0,
        }}
        {...props}
      >
        {code}
      </SyntaxHighlighter>
    </div>
  )
}

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

// URL을 마크다운 링크로 변환하는 함수
function convertUrlsToMarkdown(text: string): string {
  // HTTP/HTTPS URL 패턴 감지 (이미 마크다운 링크 형식이 아닌 경우만)
  const urlRegex = /(?<!\]\()https?:\/\/[^\s<>)\]]+/g
  return text.replace(urlRegex, (url) => {
    // URL 끝의 구두점 제거
    const cleanUrl = url.replace(/[.,;:!?]$/, '')
    return `[${cleanUrl}](${cleanUrl})`
  })
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
  const scheduleResults = isUser ? [] : extractScheduleResults(message.agent_steps)
  const showCursor = isLastAssistant && isRunning && !message.content

  // 워크플로우 다이어그램 표시 여부 (자동)
  const showWorkflowDiagram = !isUser && shouldShowWorkflow(message.agent_steps || [])

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

  // 타이핑 애니메이션 적용 (마지막 assistant 메시지이고 실행 중일 때만)
  const shouldAnimate = isLastAssistant && isRunning && message.content
  const displayContent = useTypingAnimation(message.content, {
    speed: getTypingSpeed(), // 설정된 타이핑 속도 사용 (기본 20ms)
    instant: !shouldAnimate, // 실행 중이 아니면 즉시 표시
  })

  // URL을 마크다운 링크로 변환
  const contentWithLinks = displayContent ? convertUrlsToMarkdown(displayContent) : ''

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
        {/* Workflow Diagram (자동 표시) */}
        {showWorkflowDiagram && (
          <div className="mb-4">
            <div className="text-xs font-semibold text-content-secondary mb-2 flex items-center gap-2">
              <span>🔄 Workflow Diagram</span>
            </div>
            <WorkflowDiagram steps={message.agent_steps || []} height={450} />
          </div>
        )}

        {/* Agent steps (리스트 형태) */}
        {message.agent_steps && message.agent_steps.length > 0 && !showWorkflowDiagram && (
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

        {scheduleResults.map((r, i) => (
          <ScheduleCard key={i} result={r} />
        ))}

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
          ) : contentWithLinks ? (
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeRaw, rehypeSanitize]}
              components={{
                code: CodeBlock,
                // 링크 스타일링
                a: ({ node, ...props }) => {
                  const href = props.href || ''
                  // 다운로드 링크 감지 (/api/files/로 시작하거나 포함)
                  const isDownloadLink = href.includes('/api/files/')

                  if (isDownloadLink) {
                    // URL을 상대 경로로 변환 (Vite 프록시를 통하도록)
                    const relativePath = href.includes('://')
                      ? href.substring(href.indexOf('/api/files/'))
                      : href

                    return (
                      <a
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-accent-primary/10 border border-accent-primary/30 text-accent-primary hover:bg-accent-primary/20 transition-colors no-underline font-medium"
                        href={relativePath}
                        download
                        {...props}
                      >
                        <Paperclip size={14} />
                        {props.children || '다운로드'}
                      </a>
                    )
                  }

                  return (
                    <a
                      className="text-accent-primary hover:text-accent-primary/80 underline break-all"
                      target="_blank"
                      rel="noopener noreferrer"
                      {...props}
                    />
                  )
                },
                // 테이블 스타일링
                table: ({ node, ...props }) => (
                  <div className="overflow-x-auto my-4">
                    <table className="min-w-full border border-border rounded-lg" {...props} />
                  </div>
                ),
                thead: ({ node, ...props }) => (
                  <thead className="bg-surface-tertiary" {...props} />
                ),
                th: ({ node, ...props }) => (
                  <th className="px-4 py-2 text-left border-b border-border font-semibold" {...props} />
                ),
                td: ({ node, ...props }) => (
                  <td className="px-4 py-2 border-b border-border" {...props} />
                ),
                // 리스트 스타일링
                ul: ({ node, ...props }) => (
                  <ul className="list-disc list-inside space-y-1 my-2" {...props} />
                ),
                ol: ({ node, ...props }) => (
                  <ol className="list-decimal list-inside space-y-1 my-2" {...props} />
                ),
                // 인용구 스타일링
                blockquote: ({ node, ...props }) => (
                  <blockquote
                    className="border-l-4 border-accent-primary pl-4 py-2 my-3 bg-surface-tertiary/50 italic"
                    {...props}
                  />
                ),
                // 제목 스타일링
                h1: ({ node, ...props }) => (
                  <h1 className="text-2xl font-bold mt-4 mb-2" {...props} />
                ),
                h2: ({ node, ...props }) => (
                  <h2 className="text-xl font-bold mt-3 mb-2" {...props} />
                ),
                h3: ({ node, ...props }) => (
                  <h3 className="text-lg font-bold mt-2 mb-1" {...props} />
                ),
                // 수평선
                hr: ({ node, ...props }) => (
                  <hr className="my-4 border-border" {...props} />
                ),
              }}
            >
              {contentWithLinks}
            </ReactMarkdown>
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

      {/* Text Selection Tooltip */}
      {selectedText && position && (
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
          isOpen={showWikiDialog}
          onClose={handleCloseWikiDialog}
          initialContent={savedSelectedText}
        />
      )}
    </div>
  )
}

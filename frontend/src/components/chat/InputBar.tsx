import { useState, useRef, useEffect } from 'react'
import axios from 'axios'
import { Send, Loader2, Paperclip, X, FileText, AlertCircle, Square } from 'lucide-react'
import { useAgentStore } from '../../store/agentStore'
import { useAgentStream } from '../../hooks/useAgentStream'
import { sandboxApi } from '../../api/sandbox'
import { formatSize } from '../sandbox/ArtifactsPanel'
import type { Attachment } from '../../types/chat'

const MAX_FILES = 10
const MAX_MB = 50

interface Pending {
  id: string
  name: string
  size: number
  status: 'uploading' | 'done' | 'error'
  progress: number
  error?: string
  attachment?: Attachment
}

let seq = 0

export default function InputBar({ conversationId }: { conversationId: string }) {
  const [value, setValue] = useState('')
  const [files, setFiles] = useState<Pending[]>([])
  const [dragging, setDragging] = useState(false)
  const { isRunning, triggerWorkspaceRefresh } = useAgentStore()
  const { sendMessage, cancelRun } = useAgentStream(conversationId)
  const [cancelling, setCancelling] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleCancel = async () => {
    if (cancelling) return
    setCancelling(true)
    await cancelRun()
  }

  // 실행이 끝나면 '중단 중' 표시를 해제하고, 실행 중에는 Esc 로도 중단할 수 있게 한다
  useEffect(() => {
    if (!isRunning) {
      setCancelling(false)
      return
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') handleCancel()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  const uploading = files.some((f) => f.status === 'uploading')
  const ready = files.filter((f) => f.status === 'done' && f.attachment)
  const canSend = (value.trim().length > 0 || ready.length > 0) && !isRunning && !uploading

  const patch = (id: string, p: Partial<Pending>) =>
    setFiles((list) => list.map((f) => (f.id === id ? { ...f, ...p } : f)))

  const addFiles = (list: FileList | File[]) => {
    const incoming = Array.from(list)
    const room = MAX_FILES - files.length
    incoming.slice(room).forEach((f) =>
      setFiles((l) => [...l, { id: `f${++seq}`, name: f.name, size: f.size, status: 'error', progress: 0, error: `최대 ${MAX_FILES}개까지 첨부할 수 있습니다` }])
    )
    for (const file of incoming.slice(0, Math.max(room, 0))) {
      const id = `f${++seq}`
      if (file.size > MAX_MB * 1024 * 1024) {
        setFiles((l) => [...l, { id, name: file.name, size: file.size, status: 'error', progress: 0, error: `${MAX_MB}MB 를 넘습니다` }])
        continue
      }
      setFiles((l) => [...l, { id, name: file.name, size: file.size, status: 'uploading', progress: 0 }])
      sandboxApi
        .uploadFile(file, (percent) => patch(id, { progress: percent }))
        .then((res) => {
          patch(id, { status: 'done', progress: 100, attachment: res.data.files[0] })
          triggerWorkspaceRefresh() // 산출물 패널 갱신
        })
        .catch((e) => {
          const detail = axios.isAxiosError(e) ? e.response?.data?.detail : null
          patch(id, { status: 'error', error: typeof detail === 'string' ? detail : '업로드하지 못했습니다' })
        })
    }
  }

  const handleSend = async () => {
    if (!canSend) return
    const attachments = ready.map((f) => f.attachment!)
    const content = value.trim() || '첨부한 파일을 확인해 주세요.'
    setValue('')
    setFiles([])
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
    await sendMessage(content, attachments)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
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

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    if (!isRunning && e.dataTransfer.files.length) addFiles(e.dataTransfer.files)
  }

  const onPaste = (e: React.ClipboardEvent) => {
    const pasted = Array.from(e.clipboardData.files)
    if (pasted.length && !isRunning) {
      e.preventDefault()
      addFiles(pasted)
    }
  }

  return (
    <div className="p-4 border-t border-slate-700 bg-slate-900">
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`bg-slate-800 rounded-xl border px-4 py-3 transition-colors ${
          dragging ? 'border-blue-400 bg-blue-500/10' : 'border-slate-600 focus-within:border-blue-500'
        }`}
      >
        {files.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-2">
            {files.map((f) => (
              <div
                key={f.id}
                title={f.error ?? f.name}
                className={`flex items-center gap-1.5 max-w-[240px] pl-2 pr-1 py-1 rounded-lg text-xs border ${
                  f.status === 'error'
                    ? 'bg-red-500/10 border-red-500/40 text-red-300'
                    : 'bg-slate-700/60 border-slate-600 text-slate-200'
                }`}
              >
                {f.status === 'uploading' ? (
                  <Loader2 size={12} className="animate-spin flex-shrink-0 text-blue-400" />
                ) : f.status === 'error' ? (
                  <AlertCircle size={12} className="flex-shrink-0" />
                ) : (
                  <FileText size={12} className="flex-shrink-0 text-cyan-400" />
                )}
                <span className="truncate">{f.attachment?.name ?? f.name}</span>
                <span className="text-slate-500 flex-shrink-0">
                  {f.status === 'uploading' ? `${f.progress}%` : f.status === 'error' ? f.error : formatSize(f.size)}
                </span>
                <button
                  onClick={() => setFiles((l) => l.filter((x) => x.id !== f.id))}
                  title="첨부 취소"
                  className="p-0.5 text-slate-500 hover:text-slate-200 flex-shrink-0"
                >
                  <X size={12} />
                </button>
              </div>
            ))}
          </div>
        )}
        <div className="flex gap-3 items-end">
          <input
            ref={fileInputRef}
            type="file"
            multiple
            hidden
            onChange={(e) => {
              if (e.target.files) addFiles(e.target.files)
              e.target.value = '' // 같은 파일을 다시 선택할 수 있게
            }}
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={isRunning || files.length >= MAX_FILES}
            title={`파일 첨부 (sandbox 에 업로드, 파일당 최대 ${MAX_MB}MB)`}
            className="flex-shrink-0 p-1.5 text-slate-400 hover:text-white disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            <Paperclip size={18} />
          </button>
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            onInput={handleInput}
            onPaste={onPaste}
            rows={1}
            placeholder="메시지를 입력하세요... (Shift+Enter: 줄바꿈, 파일은 끌어다 놓거나 붙여넣기)"
            disabled={isRunning}
            className="flex-1 bg-transparent text-white resize-none outline-none text-sm placeholder-slate-500 max-h-40 leading-6"
            style={{ minHeight: '24px' }}
          />
          {isRunning ? (
            <button
              onClick={handleCancel}
              disabled={cancelling}
              title="실행 중단 (Esc)"
              className="flex-shrink-0 p-1.5 bg-red-600 hover:bg-red-700 disabled:opacity-60 text-white rounded-lg transition-colors"
            >
              {cancelling ? <Loader2 size={16} className="animate-spin" /> : <Square size={16} fill="currentColor" />}
            </button>
          ) : (
            <button
              onClick={handleSend}
              disabled={!canSend}
              title={uploading ? '업로드가 끝나면 보낼 수 있습니다' : undefined}
              className="flex-shrink-0 p-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
            >
              {uploading ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
            </button>
          )}
        </div>
      </div>
      <p className="text-xs text-slate-600 text-center mt-2">
        AI can make mistakes. Verify important information.
      </p>
    </div>
  )
}

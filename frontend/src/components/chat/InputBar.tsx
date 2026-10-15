import { useState, useRef, useEffect } from 'react'
import axios from 'axios'
import { Send, Loader2, Paperclip, X, FileText, AlertCircle, Square, Plus, ThumbsUp, Settings, Mic } from 'lucide-react'
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
      setFiles((l) => [...l, { id: `f${++seq}`, name: f.name, size: f.size, status: 'error', progress: 0, error: `Max ${MAX_FILES} files` }])
    )
    for (const file of incoming.slice(0, Math.max(room, 0))) {
      const id = `f${++seq}`
      if (file.size > MAX_MB * 1024 * 1024) {
        setFiles((l) => [...l, { id, name: file.name, size: file.size, status: 'error', progress: 0, error: `Exceeds ${MAX_MB}MB` }])
        continue
      }
      setFiles((l) => [...l, { id, name: file.name, size: file.size, status: 'uploading', progress: 0 }])
      sandboxApi
        .uploadFile(file, (percent) => patch(id, { progress: percent }))
        .then((res) => {
          patch(id, { status: 'done', progress: 100, attachment: res.data.files[0] })
          triggerWorkspaceRefresh()
        })
        .catch((e) => {
          const detail = axios.isAxiosError(e) ? e.response?.data?.detail : null
          patch(id, { status: 'error', error: typeof detail === 'string' ? detail : 'Upload failed' })
        })
    }
  }

  const handleSend = async () => {
    if (!canSend) return
    const attachments = ready.map((f) => f.attachment!)
    const content = value.trim() || 'Please check the attached files.'
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
    <div className="p-4 border-t border-border bg-surface-primary">
      <div className="max-w-[800px] mx-auto">
        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={`bg-surface-secondary rounded-[var(--radius-lg)] border transition-colors ${
            dragging ? 'border-accent-primary bg-accent-primary/10' : 'border-border'
          }`}
        >
          {/* Attached Files */}
          {files.length > 0 && (
            <div className="flex flex-wrap gap-2 px-4 pt-3">
              {files.map((f) => (
                <div
                  key={f.id}
                  title={f.error ?? f.name}
                  className={`flex items-center gap-1.5 max-w-[240px] pl-2 pr-1 py-1 rounded-[var(--radius-md)] text-xs border ${
                    f.status === 'error'
                      ? 'bg-accent-red/10 border-accent-red/40 text-red-300'
                      : 'bg-surface-tertiary border-border text-content-secondary'
                  }`}
                >
                  {f.status === 'uploading' ? (
                    <Loader2 size={12} className="animate-spin flex-shrink-0 text-accent-primary" />
                  ) : f.status === 'error' ? (
                    <AlertCircle size={12} className="flex-shrink-0" />
                  ) : (
                    <FileText size={12} className="flex-shrink-0 text-cyan-400" />
                  )}
                  <span className="truncate">{f.attachment?.name ?? f.name}</span>
                  <span className="text-content-muted flex-shrink-0">
                    {f.status === 'uploading' ? `${f.progress}%` : f.status === 'error' ? f.error : formatSize(f.size)}
                  </span>
                  <button
                    onClick={() => setFiles((l) => l.filter((x) => x.id !== f.id))}
                    title="Remove"
                    className="p-0.5 text-content-muted hover:text-content-primary flex-shrink-0"
                  >
                    <X size={12} />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Input Field */}
          <div className="px-4 py-3">
            <input
              ref={fileInputRef}
              type="file"
              multiple
              hidden
              onChange={(e) => {
                if (e.target.files) addFiles(e.target.files)
                e.target.value = ''
              }}
            />
            <textarea
              ref={textareaRef}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              onKeyDown={handleKeyDown}
              onInput={handleInput}
              onPaste={onPaste}
              rows={1}
              placeholder="Type your message... (Shift+Enter: new line, drag & drop files)"
              disabled={isRunning}
              className="w-full bg-transparent text-content-primary resize-none outline-none text-[15px] placeholder:text-content-muted max-h-40 leading-6 disabled:opacity-50"
              style={{ minHeight: '24px' }}
            />
          </div>

          {/* Toolbar */}
          <div className="flex items-center justify-between px-3.5 py-2.5 border-t border-border">
            <div className="flex items-center gap-1">
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={isRunning || files.length >= MAX_FILES}
                title={`Attach files (max ${MAX_MB}MB each)`}
                className="flex items-center gap-1.5 px-3 py-2 text-[13px] text-content-secondary
                  hover:bg-surface-hover hover:text-content-primary rounded-[var(--radius-sm)] transition-colors
                  disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <Plus size={16} />
              </button>
              <button
                className="flex items-center gap-1.5 px-3 py-2 text-[13px] text-content-secondary
                  hover:bg-surface-hover hover:text-content-primary rounded-[var(--radius-sm)] transition-colors"
              >
                <ThumbsUp size={16} />
                <span className="hidden sm:inline">Approval</span>
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
              {isRunning ? (
                <button
                  onClick={handleCancel}
                  disabled={cancelling}
                  title="Stop (Esc)"
                  className="w-9 h-9 rounded-full flex items-center justify-center
                    bg-accent-red hover:bg-red-600 text-white transition-colors disabled:opacity-60"
                >
                  {cancelling ? <Loader2 size={16} className="animate-spin" /> : <Square size={16} fill="currentColor" />}
                </button>
              ) : (
                <button
                  onClick={handleSend}
                  disabled={!canSend}
                  title={uploading ? 'Wait for upload to complete' : 'Send'}
                  className="w-9 h-9 rounded-full flex items-center justify-center
                    bg-accent-primary hover:bg-accent-hover text-white transition-colors
                    disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {uploading ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
                </button>
              )}
            </div>
          </div>
        </div>

        <p className="text-xs text-content-muted text-center mt-2">
          AI can make mistakes. Verify important information.
        </p>
      </div>
    </div>
  )
}

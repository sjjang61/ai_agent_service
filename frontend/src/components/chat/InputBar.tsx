import { useState, useRef, useEffect } from 'react'
import axios from 'axios'
import { Send, Loader2, X, FileText, AlertCircle, Square, Plus, ThumbsUp, Settings, Mic, Folder, FolderUp, Paperclip, MessageSquare, BookMarked } from 'lucide-react'
import { useAgentStore } from '../../store/agentStore'
import { useAgentStream } from '../../hooks/useAgentStream'
import { sandboxApi } from '../../api/sandbox'
import { formatSize } from '../sandbox/ArtifactsPanel'
import ReferencePicker, { MAX_REFERENCES } from './ReferencePicker'
import type { Attachment, Reference } from '../../types/chat'

const MAX_FILES = 10
const MAX_MB = 50
// 폴더 업로드에서 올리지 않을 항목 (용량만 크고 의미 없는 것들)
const SKIP_DIRS = new Set(['.git', 'node_modules', '__pycache__', '.venv', '.idea', '.vscode'])
const SKIP_FILES = new Set(['.DS_Store', 'Thumbs.db'])
const FOLDER_MAX_FILES = 300
const FOLDER_MAX_MB = 100

interface Pending {
  id: string
  name: string
  size: number
  status: 'uploading' | 'done' | 'error'
  progress: number
  error?: string
  attachment?: Attachment
  folder?: boolean
}

let seq = 0

function MenuItem({ icon, label, hint, disabled, onClick }: { icon: React.ReactNode; label: string; hint?: string; disabled?: boolean; onClick: () => void }) {
  return (
    <button
      role="menuitem"
      onClick={onClick}
      disabled={disabled}
      className="w-full flex items-center gap-3 px-3 py-2 text-left border-none bg-transparent cursor-pointer text-content-primary hover:bg-surface-hover disabled:opacity-40 disabled:cursor-not-allowed"
    >
      <span className="text-content-secondary">{icon}</span>
      <span className="flex-1 min-w-0">
        <span className="block text-[13px]">{label}</span>
        {hint && <span className="block text-[11px] text-content-muted">{hint}</span>}
      </span>
    </button>
  )
}

export default function InputBar({ conversationId }: { conversationId: string }) {
  const [value, setValue] = useState('')
  const [files, setFiles] = useState<Pending[]>([])
  const [dragging, setDragging] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const [pickerOpen, setPickerOpen] = useState(false)
  const [refs, setRefs] = useState<Reference[]>([])
  const menuRef = useRef<HTMLDivElement>(null)
  const folderInputRef = useRef<HTMLInputElement>(null)
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

  useEffect(() => {
    if (!menuOpen) return
    const onDown = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false)
    }
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setMenuOpen(false)
    document.addEventListener('mousedown', onDown)
    window.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      window.removeEventListener('keydown', onKey)
    }
  }, [menuOpen])

  const uploading = files.some((f) => f.status === 'uploading')
  const ready = files.filter((f) => f.status === 'done' && f.attachment)
  const canSend = (value.trim().length > 0 || ready.length > 0 || refs.length > 0) && !isRunning && !uploading

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

  const addFolder = (list: FileList) => {
    const all = Array.from(list)
    const rel = (f: File) => (f as File & { webkitRelativePath?: string }).webkitRelativePath || f.name
    const kept = all.filter((f) => {
      const parts = rel(f).split('/')
      return !SKIP_FILES.has(parts[parts.length - 1]) && !parts.slice(0, -1).some((d) => SKIP_DIRS.has(d))
    })
    if (kept.length === 0) return
    const folderName = rel(kept[0]).split('/')[0]
    const id = `f${++seq}`
    const total = kept.reduce((n, f) => n + f.size, 0)
    const fail = (error: string) =>
      setFiles((l) => [...l, { id, name: folderName, size: total, status: 'error', progress: 0, error, folder: true }])
    if (files.length >= MAX_FILES) return fail(`Max ${MAX_FILES} files`)
    if (kept.length > FOLDER_MAX_FILES) return fail(`파일 ${FOLDER_MAX_FILES}개 초과`)
    if (total > FOLDER_MAX_MB * 1024 * 1024) return fail(`${FOLDER_MAX_MB}MB 초과`)
    setFiles((l) => [...l, { id, name: folderName, size: total, status: 'uploading', progress: 0, folder: true }])
    sandboxApi
      .uploadFolder(kept, kept.map(rel), (percent) => patch(id, { progress: percent }))
      .then((res) => {
        patch(id, { status: 'done', progress: 100, attachment: res.data.files[0] })
        triggerWorkspaceRefresh()
      })
      .catch((e) => {
        const detail = axios.isAxiosError(e) ? e.response?.data?.detail : null
        patch(id, { status: 'error', error: typeof detail === 'string' ? detail : 'Upload failed' })
      })
  }

  const handleSend = async () => {
    if (!canSend) return
    const attachments = ready.map((f) => f.attachment!)
    const content = value.trim() || (attachments.length ? 'Please check the attached files.' : '참조한 자료를 확인해 주세요.')
    const references = refs
    setValue('')
    setFiles([])
    setRefs([])
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
    await sendMessage(content, attachments, references)
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
          {/* References */}
          {refs.length > 0 && (
            <div className="flex flex-wrap gap-2 px-4 pt-3">
              {refs.map((r) => (
                <div key={`${r.type}:${r.id}`} title={r.title} className="flex items-center gap-1.5 max-w-[240px] pl-2 pr-1 py-1 rounded-[var(--radius-md)] text-xs border bg-surface-tertiary border-border text-content-secondary">
                  {r.type === 'page' ? <BookMarked size={12} className="flex-shrink-0 text-cyan-400" /> : <MessageSquare size={12} className="flex-shrink-0 text-accent-primary" />}
                  <span className="truncate">{r.title}</span>
                  <button
                    onClick={() => setRefs((l) => l.filter((x) => !(x.type === r.type && x.id === r.id)))}
                    title="Remove"
                    className="p-0.5 text-content-muted hover:text-content-primary flex-shrink-0"
                  >
                    <X size={12} />
                  </button>
                </div>
              ))}
            </div>
          )}

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
                    f.folder ? <Folder size={12} className="flex-shrink-0 text-cyan-400" /> : <FileText size={12} className="flex-shrink-0 text-cyan-400" />
                  )}
                  <span className="truncate">{f.attachment?.name ?? f.name}</span>
                  <span className="text-content-muted flex-shrink-0">
                    {f.status === 'uploading' ? `${f.progress}%` : f.status === 'error' ? f.error : f.folder ? `${f.attachment?.file_count ?? 0}개 · ${formatSize(f.attachment?.size ?? f.size)}` : formatSize(f.size)}
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
            <input
              ref={folderInputRef}
              type="file"
              hidden
              {...({ webkitdirectory: '', directory: '' } as Record<string, string>)}
              onChange={(e) => {
                if (e.target.files) addFolder(e.target.files)
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
              <div ref={menuRef} className="relative">
                <button
                  onClick={() => setMenuOpen((o) => !o)}
                  disabled={isRunning}
                  aria-haspopup="menu"
                  aria-expanded={menuOpen}
                  aria-label="첨부 및 참조 메뉴"
                  title="파일·폴더 첨부, 참조 추가"
                  className="flex items-center gap-1.5 px-3 py-2 text-[13px] text-content-secondary
                    hover:bg-surface-hover hover:text-content-primary rounded-[var(--radius-sm)] transition-colors
                    disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  <Plus size={16} className={`transition-transform ${menuOpen ? 'rotate-45' : ''}`} />
                </button>
                {menuOpen && (
                  <div role="menu" className="absolute bottom-full left-0 mb-2 w-[260px] py-1.5 z-30 bg-surface-tertiary border border-border rounded-[var(--radius-md)] shadow-lg">
                    <MenuItem
                      icon={<Paperclip size={15} />}
                      label="파일 첨부"
                      hint={`파일당 최대 ${MAX_MB}MB`}
                      disabled={files.length >= MAX_FILES}
                      onClick={() => { setMenuOpen(false); fileInputRef.current?.click() }}
                    />
                    <MenuItem
                      icon={<FolderUp size={15} />}
                      label="폴더 첨부"
                      hint={`파일 ${FOLDER_MAX_FILES}개 · ${FOLDER_MAX_MB}MB 이하`}
                      disabled={files.length >= MAX_FILES}
                      onClick={() => { setMenuOpen(false); folderInputRef.current?.click() }}
                    />
                    <div className="my-1 border-t border-border" />
                    <MenuItem
                      icon={<BookMarked size={15} />}
                      label="참조 추가"
                      hint="스페이스 페이지·이전 대화"
                      onClick={() => { setMenuOpen(false); setPickerOpen(true) }}
                    />
                  </div>
                )}
              </div>
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

        {pickerOpen && (
          <ReferencePicker
            selected={refs}
            currentConversationId={conversationId}
            onChange={setRefs}
            onClose={() => setPickerOpen(false)}
          />
        )}

        <p className="text-xs text-content-muted text-center mt-2">
          AI can make mistakes. Verify important information.
        </p>
      </div>
    </div>
  )
}

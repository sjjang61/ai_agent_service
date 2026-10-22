import { useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { AlertCircle, CheckCircle2, FileText, Loader2, Trash2, Upload, X } from 'lucide-react'
import axios from 'axios'
import { documentsApi, type RagDocument } from '../../api/documents'
import { useDocuments } from '../../hooks/useDocuments'
import { relativeTime } from '../spaces/utils'

const ACCEPT = ['txt', 'md', 'pdf']

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`
}

/** '12분' → '12분 전', '방금' 은 그대로, 오래된 문서는 날짜 */
function ago(iso: string) {
  const r = relativeTime(iso)
  return /^\d+(분|시간|일)$/.test(r) ? `${r} 전` : r
}

function StatusChip({ doc }: { doc: RagDocument }) {
  if (doc.status === 'processing')
    return <span className="flex items-center gap-1 text-[11px] text-accent-primary"><Loader2 size={12} className="animate-spin" /> 처리 중</span>
  if (doc.status === 'failed')
    return <span className="flex items-center gap-1 text-[11px] text-accent-red"><AlertCircle size={12} /> 실패</span>
  return <span className="flex items-center gap-1 text-[11px] text-accent-green"><CheckCircle2 size={12} /> 완료</span>
}

/** 이 대화의 RAG 문서: 업로드(드래그 앤 드롭 포함), 상태, 삭제 */
export default function DocumentsPanel({ conversationId }: { conversationId: string }) {
  const queryClient = useQueryClient()
  const { data: documents = [], isLoading } = useDocuments(conversationId)
  const fileRef = useRef<HTMLInputElement>(null)
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null)
  const [dragging, setDragging] = useState(false)
  const [errors, setErrors] = useState<string[]>([])
  const [confirmId, setConfirmId] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['documents', conversationId] })

  const upload = async (files: File[]) => {
    if (!files.length || progress) return
    const problems: string[] = []
    const valid = files.filter((f) => {
      const ext = f.name.split('.').pop()?.toLowerCase() ?? ''
      if (!ACCEPT.includes(ext)) problems.push(`${f.name}: 지원하지 않는 형식입니다 (txt, md, pdf)`)
      return ACCEPT.includes(ext)
    })
    setProgress({ done: 0, total: valid.length })
    for (const [i, f] of valid.entries()) {
      try {
        await documentsApi.upload(conversationId, f)
      } catch (e) {
        const detail = axios.isAxiosError(e) ? e.response?.data?.detail : null
        problems.push(`${f.name}: ${typeof detail === 'string' ? detail : '업로드하지 못했습니다'}`)
      }
      setProgress({ done: i + 1, total: valid.length })
    }
    setProgress(null)
    setErrors(problems)
    refresh()
  }

  const remove = async (id: string) => {
    setDeletingId(id)
    try {
      await documentsApi.remove(id)
      setConfirmId(null)
      refresh()
    } catch {
      setErrors(['문서를 삭제하지 못했습니다'])
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div className="p-4 space-y-4">
      <p className="text-xs text-content-tertiary leading-relaxed">
        이 대화에서만 쓰는 문서입니다. 업로드하면 내용을 나눠 저장해 두고, 에이전트가 질문에 필요할 때 검색해서 참고합니다.
      </p>

      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); void upload(Array.from(e.dataTransfer.files)) }}
        className={`rounded-[var(--radius-lg)] border-2 border-dashed px-4 py-6 text-center transition-colors ${
          dragging ? 'border-accent-primary bg-accent-primary/10' : 'border-border bg-surface-secondary'
        }`}
      >
        {progress ? (
          <div role="status" className="flex items-center justify-center gap-2 text-[13px] text-content-secondary">
            <Loader2 size={15} className="animate-spin" /> 업로드 중 ({progress.done}/{progress.total})
          </div>
        ) : (
          <>
            <Upload size={20} className="mx-auto text-content-tertiary mb-2" />
            <div className="text-[13px] text-content-primary">파일을 여기로 끌어다 놓거나</div>
            <button
              onClick={() => fileRef.current?.click()}
              className="mt-2 px-3.5 py-1.5 rounded-full text-[13px] bg-accent-primary hover:bg-accent-hover text-white border-none cursor-pointer"
            >
              파일 선택
            </button>
            <div className="mt-2 text-[11px] text-content-tertiary">TXT · MD · PDF</div>
          </>
        )}
        <input ref={fileRef} type="file" accept=".txt,.md,.pdf" multiple hidden onChange={(e) => { void upload(Array.from(e.target.files ?? [])); e.target.value = '' }} />
      </div>

      {errors.length > 0 && (
        <div role="alert" className="rounded-[var(--radius-md)] border border-accent-red/30 px-3 py-2 text-xs text-accent-red space-y-1">
          <div className="flex items-start justify-between gap-2">
            <div className="space-y-0.5">{errors.map((m, i) => <div key={i}>{m}</div>)}</div>
            <button onClick={() => setErrors([])} aria-label="알림 닫기" className="flex-shrink-0 border-none bg-transparent cursor-pointer text-inherit"><X size={13} /></button>
          </div>
        </div>
      )}

      <div>
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-[13px] font-semibold text-content-primary">문서 <span className="font-normal text-content-tertiary">{documents.length}</span></h3>
        </div>
        {isLoading ? (
          <div className="flex justify-center py-8 text-content-muted"><Loader2 size={16} className="animate-spin" /></div>
        ) : documents.length === 0 ? (
          <div className="text-center text-[13px] text-content-muted py-8 border border-dashed border-border rounded-[var(--radius-lg)]">
            아직 문서가 없습니다.
            <div className="text-xs mt-1">PDF나 텍스트를 올리면 답변에 근거로 활용됩니다.</div>
          </div>
        ) : (
          <ul className="space-y-2">
            {documents.map((doc) => (
              <li key={doc.id} className="group rounded-[var(--radius-lg)] border border-border bg-surface-secondary px-3.5 py-3">
                <div className="flex items-start gap-3">
                  <span className="w-9 h-9 rounded-[var(--radius-md)] bg-surface-tertiary flex items-center justify-center text-accent-primary flex-shrink-0"><FileText size={17} /></span>
                  <div className="min-w-0 flex-1">
                    <div className="text-[13px] font-medium text-content-primary truncate" title={doc.filename}>{doc.filename}</div>
                    <div className="mt-0.5 flex flex-wrap items-center gap-x-2 text-[11px] text-content-tertiary">
                      <span className="uppercase">{doc.file_type}</span>
                      <span>·</span>
                      <span>{formatSize(doc.file_size)}</span>
                      {doc.status === 'completed' && doc.total_chunks > 0 && (<><span>·</span><span>{doc.total_chunks}개 조각</span></>)}
                      <span>·</span>
                      <span>{ago(doc.created_at)}</span>
                    </div>
                    <div className="mt-1"><StatusChip doc={doc} /></div>
                    {doc.error_message && <div className="mt-1 text-[11px] text-accent-red break-words">{doc.error_message}</div>}
                  </div>
                  <button
                    onClick={() => setConfirmId(doc.id)}
                    aria-label={`${doc.filename} 삭제`}
                    title="삭제"
                    className="opacity-0 group-hover:opacity-100 focus-visible:opacity-100 text-content-muted hover:text-accent-red transition-all border-none bg-transparent cursor-pointer"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
                {confirmId === doc.id && (
                  <div className="mt-2.5 flex items-center justify-between gap-2 rounded-[var(--radius-md)] bg-surface-tertiary px-3 py-2 text-xs text-content-secondary">
                    <span>이 문서를 삭제할까요?</span>
                    <span className="flex gap-2">
                      <button onClick={() => setConfirmId(null)} className="px-2.5 py-1 rounded-full border border-border bg-transparent text-content-secondary cursor-pointer">취소</button>
                      <button onClick={() => remove(doc.id)} disabled={deletingId === doc.id} className="px-2.5 py-1 rounded-full border-none bg-accent-red text-white cursor-pointer disabled:opacity-50">
                        {deletingId === doc.id ? '삭제 중…' : '삭제'}
                      </button>
                    </span>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

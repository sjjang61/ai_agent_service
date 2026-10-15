import { useState, useEffect, useRef } from 'react'
import { FileText, Upload, Trash2, Loader2, AlertCircle, CheckCircle, X } from 'lucide-react'
import apiClient from '../../api/client'

interface Document {
  id: string
  filename: string
  file_type: string
  file_size: number
  status: string
  total_chunks: number
  created_at: string
  error_message?: string
}

export default function DocumentPanel({ conversationId }: { conversationId: string }) {
  const [documents, setDocuments] = useState<Document[]>([])
  const [uploading, setUploading] = useState(false)
  const [loading, setLoading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const loadDocuments = async () => {
    if (!conversationId) return
    setLoading(true)
    try {
      const res = await apiClient.get(`/conversations/${conversationId}/documents`)
      setDocuments(res.data)
    } catch (error) {
      console.error('Failed to load documents:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadDocuments()
  }, [conversationId])

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || files.length === 0) return

    setUploading(true)

    for (const file of files) {
      const formData = new FormData()
      formData.append('file', file)

      try {
        await apiClient.post(`/conversations/${conversationId}/documents`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        })
      } catch (error) {
        console.error(`Failed to upload ${file.name}:`, error)
        alert(`Failed to upload ${file.name}`)
      }
    }

    setUploading(false)
    loadDocuments()
    e.target.value = ''
  }

  const handleDelete = async (docId: string) => {
    if (!confirm('Delete this document?')) return

    try {
      await apiClient.delete(`/documents/${docId}`)
      loadDocuments()
    } catch (error) {
      console.error('Failed to delete document:', error)
      alert('Failed to delete document')
    }
  }

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes}B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)}MB`
  }

  return (
    <div className="border-t border-border p-3">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-content-primary flex items-center gap-2">
          <FileText size={14} />
          RAG Documents
        </h3>
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs bg-accent-primary hover:bg-accent-hover
            text-white rounded-[var(--radius-sm)] transition-colors disabled:opacity-50"
        >
          {uploading ? (
            <>
              <Loader2 size={12} className="animate-spin" />
              Uploading...
            </>
          ) : (
            <>
              <Upload size={12} />
              Upload
            </>
          )}
        </button>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept=".txt,.md,.pdf"
        multiple
        hidden
        onChange={handleFileChange}
      />

      {loading ? (
        <div className="flex items-center justify-center py-8 text-content-muted">
          <Loader2 size={16} className="animate-spin" />
        </div>
      ) : documents.length === 0 ? (
        <div className="text-xs text-content-muted text-center py-6 px-2">
          No documents uploaded.
          <br />
          Upload PDF, TXT, or MD files to use RAG.
        </div>
      ) : (
        <div className="space-y-1.5 max-h-[300px] overflow-y-auto">
          {documents.map((doc) => (
            <div
              key={doc.id}
              className="flex items-start gap-2 p-2 rounded-[var(--radius-sm)] bg-surface-tertiary
                border border-border hover:border-accent-primary/30 transition-colors group"
            >
              <div className="flex-shrink-0 mt-0.5">
                {doc.status === 'processing' ? (
                  <Loader2 size={14} className="animate-spin text-accent-primary" />
                ) : doc.status === 'failed' ? (
                  <AlertCircle size={14} className="text-accent-red" />
                ) : (
                  <CheckCircle size={14} className="text-green-500" />
                )}
              </div>

              <div className="flex-1 min-w-0">
                <div className="text-xs font-medium text-content-primary truncate" title={doc.filename}>
                  {doc.filename}
                </div>
                <div className="flex items-center gap-2 mt-0.5 text-[10px] text-content-muted">
                  <span className="uppercase">{doc.file_type}</span>
                  <span>•</span>
                  <span>{formatSize(doc.file_size)}</span>
                  {doc.status === 'completed' && doc.total_chunks > 0 && (
                    <>
                      <span>•</span>
                      <span>{doc.total_chunks} chunks</span>
                    </>
                  )}
                </div>
                {doc.error_message && (
                  <div className="text-[10px] text-accent-red mt-1">
                    {doc.error_message}
                  </div>
                )}
              </div>

              <button
                onClick={() => handleDelete(doc.id)}
                className="opacity-0 group-hover:opacity-100 flex-shrink-0 p-1 text-content-muted
                  hover:text-accent-red transition-all"
                title="Delete document"
              >
                <Trash2 size={12} />
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="mt-2 text-[10px] text-content-muted">
        💡 Tip: Upload documents to enable semantic search with RAG
      </div>
    </div>
  )
}

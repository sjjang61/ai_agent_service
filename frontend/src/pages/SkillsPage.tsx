import { useState } from 'react'
import { Download, Loader2, Trash2 } from 'lucide-react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import IconBar from '../components/layout/IconBar'
import { skillsApi } from '../api/skills'
import type { Skill } from '../types/skill'

export default function SkillsPage() {
  const queryClient = useQueryClient()
  const { data: skills = [], isLoading } = useQuery<Skill[]>({
    queryKey: ['skills'],
    queryFn: async () => (await skillsApi.list()).data,
  })
  const [url, setUrl] = useState('')
  const [installing, setInstalling] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const handleInstall = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!url.trim()) return
    setInstalling(true)
    setError(null)
    setMessage(null)
    try {
      const res = await skillsApi.install(url.trim())
      const names = (res.data.installed as Skill[]).map((s) => s.name).join(', ')
      if (res.data.sandbox_synced) {
        setMessage(`Installed: ${names} (copied to sandbox: /workspace/skills/)`)
      } else {
        setMessage(`Installed: ${names}`)
        setError(`Sandbox copy failed: ${res.data.sandbox_error ?? 'unknown error'}`)
      }
      setUrl('')
      queryClient.invalidateQueries({ queryKey: ['skills'] })
    } catch (err) {
      const detail = axios.isAxiosError(err) ? err.response?.data?.detail : null
      setError(typeof detail === 'string' ? detail : 'Failed to install skill')
    } finally {
      setInstalling(false)
    }
  }

  const handleSync = async () => {
    setError(null)
    setMessage(null)
    try {
      const res = await skillsApi.sync()
      if (res.data.sandbox_error) setError(`Sandbox sync failed: ${res.data.sandbox_error}`)
      else setMessage(`Synced ${res.data.synced} skill(s) to sandbox`)
    } catch {
      setError('Sandbox sync failed')
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this skill?')) return
    await skillsApi.remove(id)
    queryClient.invalidateQueries({ queryKey: ['skills'] })
  }

  return (
    <div className="flex h-screen bg-surface-primary overflow-hidden">
      {/* Left Icon Bar */}
      <IconBar />

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0 bg-surface-primary overflow-hidden">
        {/* Header */}
        <header className="h-[52px] border-b border-border flex items-center px-6 flex-shrink-0 bg-surface-primary">
          <h1 className="text-[15px] font-semibold text-content-primary">Skills</h1>
        </header>

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto">
          <div className="max-w-[1000px] mx-auto p-6 space-y-6">
            {/* Install Form */}
            <div className="bg-surface-secondary border border-border rounded-[var(--radius-lg)] p-5">
              <h2 className="text-sm font-medium text-content-primary mb-3">
                Install from GitHub URL
              </h2>
              <form onSubmit={handleInstall} className="space-y-3">
                <div className="flex gap-2">
                  <input
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    placeholder="https://github.com/owner/repo/tree/main/skills/my-skill"
                    className="flex-1 px-3.5 py-2.5 bg-surface-primary border border-border rounded-[var(--radius-md)]
                      text-[13px] text-content-primary placeholder:text-content-muted
                      focus:outline-none focus:border-accent-primary transition-colors"
                  />
                  <button
                    type="submit"
                    disabled={installing || !url.trim()}
                    className="flex items-center gap-2 px-4 py-2.5 bg-accent-primary hover:bg-accent-hover
                      disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-[var(--radius-md)]
                      text-[13px] font-medium transition-colors"
                  >
                    {installing ? (
                      <Loader2 size={14} className="animate-spin" />
                    ) : (
                      <Download size={14} />
                    )}
                    Install
                  </button>
                </div>
                {error && (
                  <p className="text-[13px] text-accent-red">{error}</p>
                )}
                {message && (
                  <p className="text-[13px] text-accent-green">{message}</p>
                )}
              </form>
            </div>

            {/* Installed Skills */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-[15px] font-semibold text-content-primary">
                  Installed Skills
                </h2>
                {skills.length > 0 && (
                  <button
                    onClick={handleSync}
                    className="text-xs text-content-tertiary hover:text-content-primary transition-colors"
                    title="Copy installed skills to the sandbox again"
                  >
                    Re-sync to sandbox
                  </button>
                )}
              </div>

              {isLoading ? (
                <div className="text-content-tertiary text-sm py-8 text-center">
                  Loading...
                </div>
              ) : skills.length === 0 ? (
                <div className="text-content-muted text-sm py-8 text-center">
                  No skills installed.
                </div>
              ) : (
                <div className="space-y-2">
                  {skills.map((s) => (
                    <div
                      key={s.id}
                      className="flex items-start justify-between gap-3 p-4 bg-surface-secondary
                        border border-border rounded-[var(--radius-md)] hover:bg-surface-hover
                        transition-colors"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="text-[14px] font-medium text-content-primary">
                          {s.name}
                        </div>
                        {s.description && (
                          <div className="text-[13px] text-content-secondary mt-1 line-clamp-2">
                            {s.description}
                          </div>
                        )}
                        {s.source_url.startsWith('https://') ? (
                          <a
                            href={s.source_url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-xs text-accent-primary hover:underline break-all mt-1 inline-block"
                          >
                            {s.source_url}
                          </a>
                        ) : (
                          <span className="text-xs text-content-tertiary break-all mt-1 inline-block">
                            {s.source_url.startsWith('sandbox:')
                              ? `Created in sandbox (${s.source_url.slice(8)})`
                              : s.source_url}
                          </span>
                        )}
                      </div>
                      <button
                        onClick={() => handleDelete(s.id)}
                        className="text-content-muted hover:text-accent-red transition-colors flex-shrink-0"
                        title="Delete"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}

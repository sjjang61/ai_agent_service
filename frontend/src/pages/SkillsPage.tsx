import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, Download, Loader2, Trash2 } from 'lucide-react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
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
    <div className="min-h-screen bg-slate-900 p-6">
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="flex items-center gap-3">
          <Link to="/" className="text-slate-400 hover:text-white transition-colors">
            <ArrowLeft size={20} />
          </Link>
          <h1 className="text-xl font-bold text-white">Skills</h1>
        </div>

        <form onSubmit={handleInstall} className="space-y-2">
          <label className="text-sm text-slate-300">Install from GitHub URL</label>
          <div className="flex gap-2">
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://github.com/owner/repo/tree/main/skills/my-skill"
              className="flex-1 px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
            />
            <button
              type="submit"
              disabled={installing || !url.trim()}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg text-sm transition-colors"
            >
              {installing ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
              Install
            </button>
          </div>
          {error && <p className="text-sm text-red-400">{error}</p>}
          {message && <p className="text-sm text-green-400">{message}</p>}
        </form>

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white">Installed Skills</h2>
            {skills.length > 0 && (
              <button
                onClick={handleSync}
                className="text-xs text-slate-400 hover:text-white transition-colors"
                title="Copy installed skills to the sandbox again"
              >
                Re-sync to sandbox
              </button>
            )}
          </div>
          {isLoading ? (
            <div className="text-slate-400 text-sm">Loading...</div>
          ) : skills.length === 0 ? (
            <div className="text-slate-500 text-sm">No skills installed.</div>
          ) : (
            skills.map((s) => (
              <div
                key={s.id}
                className="flex items-start justify-between gap-3 p-3 bg-slate-800 border border-slate-700 rounded-lg"
              >
                <div className="min-w-0">
                  <div className="text-sm font-medium text-white">{s.name}</div>
                  {s.description && (
                    <div className="text-xs text-slate-400 mt-0.5 line-clamp-2">{s.description}</div>
                  )}
                  {s.source_url.startsWith('https://') ? (
                    <a
                      href={s.source_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs text-blue-400 hover:underline break-all"
                    >
                      {s.source_url}
                    </a>
                  ) : (
                    <span className="text-xs text-slate-500 break-all">
                      {s.source_url.startsWith('sandbox:') ? `Created in sandbox (${s.source_url.slice(8)})` : s.source_url}
                    </span>
                  )}
                </div>
                <button
                  onClick={() => handleDelete(s.id)}
                  className="text-slate-500 hover:text-red-400 transition-colors flex-shrink-0"
                  title="Delete"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}

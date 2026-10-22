import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { useAuthStore } from '../../store/authStore'
import { Play, Square, Terminal, RefreshCw } from 'lucide-react'
import { T } from '../skills/typography'

export default function SandboxStatus() {
  const { token } = useAuthStore()
  const qc = useQueryClient()
  const headers = { Authorization: `Bearer ${token}` }

  const { data: status, isLoading } = useQuery({
    queryKey: ['sandbox-status'],
    queryFn: () => axios.get('/api/sandbox/status', { headers }).then((r) => r.data),
    refetchInterval: 10000,
  })

  const startMutation = useMutation({
    mutationFn: () => axios.post('/api/sandbox/start', {}, { headers }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sandbox-status'] }),
  })

  const stopMutation = useMutation({
    mutationFn: () => axios.post('/api/sandbox/stop', {}, { headers }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sandbox-status'] }),
  })

  const isRunning = status?.status === 'running'

  return (
    <div className="bg-surface-secondary rounded-xl p-6 border border-border">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-surface-tertiary rounded-xl flex items-center justify-center">
            <Terminal size={20} className="text-accent-blue" />
          </div>
          <div>
            <h3 className={T.itemTitle}>Sandbox Container</h3>
            <p className={T.itemDesc}>Isolated execution environment</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div
            className={`w-2.5 h-2.5 rounded-full ${
              isLoading ? 'bg-surface-tertiary' : isRunning ? 'bg-accent-green animate-pulse' : 'bg-accent-red'
            }`}
          />
          <span className="text-sm text-content-muted capitalize">
            {isLoading ? 'checking...' : status?.status || 'unknown'}
          </span>
        </div>
      </div>

      {status?.container_id && (
        <p className="text-xs text-content-muted font-mono mb-4 bg-surface-primary px-3 py-1.5 rounded border border-border">
          Container: {status.container_id.slice(0, 12)}...
        </p>
      )}

      <div className="flex gap-2">
        <button
          onClick={() => startMutation.mutate()}
          disabled={isRunning || startMutation.isPending}
          className="flex items-center gap-2 px-4 py-2 bg-accent-green hover:bg-accent-green/80 disabled:opacity-50 text-white rounded-lg text-sm transition-colors"
        >
          {startMutation.isPending ? <RefreshCw size={14} className="animate-spin" /> : <Play size={14} />}
          Start
        </button>
        <button
          onClick={() => stopMutation.mutate()}
          disabled={!isRunning || stopMutation.isPending}
          className="flex items-center gap-2 px-4 py-2 bg-accent-red hover:bg-accent-red/80 disabled:opacity-50 text-white rounded-lg text-sm transition-colors"
        >
          {stopMutation.isPending ? <RefreshCw size={14} className="animate-spin" /> : <Square size={14} />}
          Stop
        </button>
      </div>
    </div>
  )
}

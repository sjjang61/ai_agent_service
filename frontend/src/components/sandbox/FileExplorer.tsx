import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import { useAuthStore } from '../../store/authStore'
import { Folder, RefreshCw } from 'lucide-react'

export default function FileExplorer({ path = '' }: { path?: string }) {
  const { token } = useAuthStore()
  const headers = { Authorization: `Bearer ${token}` }

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['sandbox-files', path],
    queryFn: () =>
      axios
        .get(`/api/sandbox/files?path=/workspace/${path}`, { headers })
        .then((r) => r.data),
    retry: false,
  })

  return (
    <div className="bg-slate-800 rounded-xl p-4 border border-slate-700">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Folder size={16} className="text-blue-400" />
          <span className="text-sm font-medium text-white">/workspace/{path}</span>
        </div>
        <button
          onClick={() => refetch()}
          className="text-slate-400 hover:text-white transition-colors"
        >
          <RefreshCw size={14} className={isLoading ? 'animate-spin' : ''} />
        </button>
      </div>
      {data?.listing ? (
        <pre className="text-xs text-slate-300 font-mono whitespace-pre-wrap bg-slate-900 p-3 rounded-lg overflow-x-auto">
          {data.listing}
        </pre>
      ) : (
        <p className="text-xs text-slate-500 text-center py-4">
          {isLoading ? 'Loading...' : 'No files or sandbox not running'}
        </p>
      )}
    </div>
  )
}

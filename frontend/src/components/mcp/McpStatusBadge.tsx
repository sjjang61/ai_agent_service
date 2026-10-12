export default function McpStatusBadge({
  status,
}: {
  status: 'connected' | 'error' | 'unknown'
}) {
  const colors = {
    connected: 'bg-green-500',
    error: 'bg-red-500',
    unknown: 'bg-slate-500',
  }
  return <span className={`inline-block w-2 h-2 rounded-full ${colors[status]}`} />
}

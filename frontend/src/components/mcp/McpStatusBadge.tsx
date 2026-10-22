export default function McpStatusBadge({
  status,
}: {
  status: 'connected' | 'error' | 'unknown'
}) {
  const colors = {
    connected: 'bg-accent-green',
    error: 'bg-accent-red',
    unknown: 'bg-content-muted',
  }
  return <span className={`inline-block w-2 h-2 rounded-full ${colors[status]}`} />
}

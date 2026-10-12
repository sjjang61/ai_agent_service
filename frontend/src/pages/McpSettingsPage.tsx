import { Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import McpServerList from '../components/mcp/McpServerList'

export default function McpSettingsPage() {
  return (
    <div className="min-h-screen bg-slate-900 p-6">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center gap-3 mb-6">
          <Link to="/" className="text-slate-400 hover:text-white transition-colors">
            <ArrowLeft size={20} />
          </Link>
          <h1 className="text-xl font-bold text-white">MCP Server Settings</h1>
        </div>
        <McpServerList />
      </div>
    </div>
  )
}

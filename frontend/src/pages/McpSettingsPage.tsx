import IconBar from '../components/layout/IconBar'
import McpServerList from '../components/mcp/McpServerList'

export default function McpSettingsPage() {
  return (
    <div className="flex h-screen bg-surface-primary overflow-hidden">
      {/* Left Icon Bar */}
      <IconBar />

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0 bg-surface-primary overflow-hidden">
        {/* Header */}
        <header className="h-[52px] border-b border-border flex items-center px-6 flex-shrink-0 bg-surface-primary">
          <h1 className="text-[15px] font-semibold text-content-primary">MCP Server Settings</h1>
        </header>

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto">
          <div className="max-w-[1000px] mx-auto p-6">
            <McpServerList />
          </div>
        </div>
      </main>
    </div>
  )
}

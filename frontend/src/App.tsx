import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './store/authStore'
import AdminUsagePage from './pages/AdminUsagePage'
import AuthPage from './pages/AuthPage'
import ChatPage from './pages/ChatPage'
import McpSettingsPage from './pages/McpSettingsPage'
import MemoryPage from './pages/MemoryPage'
import SandboxPage from './pages/SandboxPage'
import SchedulesPage from './pages/SchedulesPage'
import SkillsPage from './pages/SkillsPage'
import PluginsPage from './pages/PluginsPage'
import SpacesPage from './pages/SpacesPage'
import PageEditorPage from './pages/PageEditorPage'
import ToolsPage from './pages/ToolsPage'
import WikiPage from './pages/WikiPage'

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { token } = useAuthStore()
  return token ? <>{children}</> : <Navigate to="/auth" replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/auth" element={<AuthPage />} />
      <Route path="/" element={<PrivateRoute><ChatPage /></PrivateRoute>} />
      <Route path="/chat/:conversationId" element={<PrivateRoute><ChatPage /></PrivateRoute>} />
      <Route path="/mcp" element={<PrivateRoute><McpSettingsPage /></PrivateRoute>} />
      <Route path="/memory" element={<PrivateRoute><MemoryPage /></PrivateRoute>} />
      <Route path="/wiki" element={<PrivateRoute><WikiPage /></PrivateRoute>} />
      <Route path="/spaces" element={<PrivateRoute><SpacesPage /></PrivateRoute>} />
      <Route path="/spaces/pages/:pageId" element={<PrivateRoute><PageEditorPage /></PrivateRoute>} />
      <Route path="/schedules" element={<PrivateRoute><SchedulesPage /></PrivateRoute>} />
      <Route path="/sandbox" element={<PrivateRoute><SandboxPage /></PrivateRoute>} />
      <Route path="/skills" element={<PrivateRoute><SkillsPage /></PrivateRoute>} />
      <Route path="/plugins" element={<PrivateRoute><PluginsPage /></PrivateRoute>} />
      <Route path="/admin/usage" element={<PrivateRoute><AdminUsagePage /></PrivateRoute>} />
      <Route path="/tools" element={<PrivateRoute><ToolsPage /></PrivateRoute>} />
    </Routes>
  )
}

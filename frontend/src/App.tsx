import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './store/authStore'
import AuthPage from './pages/AuthPage'
import ChatPage from './pages/ChatPage'
import McpSettingsPage from './pages/McpSettingsPage'
import SandboxPage from './pages/SandboxPage'
import SkillsPage from './pages/SkillsPage'
import ToolsPage from './pages/ToolsPage'

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
      <Route path="/sandbox" element={<PrivateRoute><SandboxPage /></PrivateRoute>} />
      <Route path="/skills" element={<PrivateRoute><SkillsPage /></PrivateRoute>} />
      <Route path="/tools" element={<PrivateRoute><ToolsPage /></PrivateRoute>} />
    </Routes>
  )
}

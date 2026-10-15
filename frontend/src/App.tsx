import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './store/authStore'
import AuthPage from './pages/AuthPage'
import ChatPage from './pages/ChatPage'
import McpSettingsPage from './pages/McpSettingsPage'
import MemoryPage from './pages/MemoryPage'
import SandboxPage from './pages/SandboxPage'
import SkillsPage from './pages/SkillsPage'

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
      <Route path="/sandbox" element={<PrivateRoute><SandboxPage /></PrivateRoute>} />
      <Route path="/skills" element={<PrivateRoute><SkillsPage /></PrivateRoute>} />
    </Routes>
  )
}

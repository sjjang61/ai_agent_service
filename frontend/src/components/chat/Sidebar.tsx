import { useNavigate } from 'react-router-dom'
import { Plus, MessageSquare, Settings, Box, Sparkles, Brain, LogOut, Trash2 } from 'lucide-react'
import { useChatStore } from '../../store/chatStore'
import { useAuthStore } from '../../store/authStore'
import { chatApi } from '../../api/chat'
import type { Conversation } from '../../types/chat'

export default function Sidebar() {
  const {
    conversations,
    currentConversationId,
    addConversation,
    removeConversation,
    setCurrentConversation,
  } = useChatStore()
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()

  const handleNewChat = async () => {
    const res = await chatApi.createConversation({ title: 'New Conversation' })
    addConversation(res.data as Conversation)
    navigate(`/chat/${res.data.id}`)
  }

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation()
    await chatApi.deleteConversation(id)
    removeConversation(id)
    if (currentConversationId === id) navigate('/')
  }

  return (
    <div className="w-64 bg-slate-800 flex flex-col border-r border-slate-700 flex-shrink-0">
      <div className="p-4 border-b border-slate-700">
        <div className="flex items-center gap-2 mb-3">
          <div className="w-6 h-6 bg-blue-600 rounded flex items-center justify-center">
            <span className="text-white text-xs font-bold">AI</span>
          </div>
          <span className="text-white font-semibold text-sm">Agent Platform</span>
        </div>
        <button
          onClick={handleNewChat}
          className="w-full flex items-center gap-2 px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors text-sm font-medium"
        >
          <Plus size={16} />
          New Chat
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-2">
        {conversations.length === 0 ? (
          <p className="text-slate-500 text-xs text-center mt-6 px-3">
            No conversations yet. Start one!
          </p>
        ) : (
          conversations.map((conv) => (
            <div
              key={conv.id}
              onClick={() => {
                setCurrentConversation(conv.id)
                navigate(`/chat/${conv.id}`)
              }}
              className={`group flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer mb-0.5 transition-colors ${
                currentConversationId === conv.id
                  ? 'bg-slate-700 text-white'
                  : 'text-slate-400 hover:bg-slate-700/50 hover:text-white'
              }`}
            >
              <MessageSquare size={14} className="flex-shrink-0" />
              <span className="text-sm truncate flex-1">{conv.title}</span>
              <button
                onClick={(e) => handleDelete(e, conv.id)}
                className="opacity-0 group-hover:opacity-100 text-slate-500 hover:text-red-400 transition-all flex-shrink-0"
              >
                <Trash2 size={12} />
              </button>
            </div>
          ))
        )}
      </div>

      <div className="p-3 border-t border-slate-700 space-y-0.5">
        <button
          onClick={() => navigate('/mcp')}
          className="w-full flex items-center gap-2 px-3 py-2 text-slate-400 hover:text-white hover:bg-slate-700 rounded-lg transition-colors text-sm"
        >
          <Settings size={15} />
          MCP Settings
        </button>
        <button
          onClick={() => navigate('/skills')}
          className="w-full flex items-center gap-2 px-3 py-2 text-slate-400 hover:text-white hover:bg-slate-700 rounded-lg transition-colors text-sm"
        >
          <Sparkles size={15} />
          Skills
        </button>
        <button
          onClick={() => navigate('/memory')}
          className="w-full flex items-center gap-2 px-3 py-2 text-slate-400 hover:text-white hover:bg-slate-700 rounded-lg transition-colors text-sm"
        >
          <Brain size={15} />
          Memory
        </button>
        <button
          onClick={() => navigate('/sandbox')}
          className="w-full flex items-center gap-2 px-3 py-2 text-slate-400 hover:text-white hover:bg-slate-700 rounded-lg transition-colors text-sm"
        >
          <Box size={15} />
          Sandbox
        </button>
        <div className="flex items-center justify-between px-3 py-2 mt-1">
          <span className="text-xs text-slate-500 truncate">{user?.display_name}</span>
          <button
            onClick={() => {
              logout()
              navigate('/auth')
            }}
            className="text-slate-500 hover:text-red-400 transition-colors"
            title="Logout"
          >
            <LogOut size={14} />
          </button>
        </div>
      </div>
    </div>
  )
}

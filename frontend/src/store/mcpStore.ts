import { create } from 'zustand'
import type { MCPServer } from '../types/mcp'

interface MCPState {
  servers: MCPServer[]
  setServers: (s: MCPServer[]) => void
  addServer: (s: MCPServer) => void
  removeServer: (id: string) => void
  updateServer: (id: string, s: Partial<MCPServer>) => void
}

export const useMcpStore = create<MCPState>((set) => ({
  servers: [],
  setServers: (servers) => set({ servers }),
  addServer: (s) => set((st) => ({ servers: [...st.servers, s] })),
  removeServer: (id) => set((st) => ({ servers: st.servers.filter((s) => s.id !== id) })),
  updateServer: (id, data) =>
    set((st) => ({
      servers: st.servers.map((s) => (s.id === id ? { ...s, ...data } : s)),
    })),
}))

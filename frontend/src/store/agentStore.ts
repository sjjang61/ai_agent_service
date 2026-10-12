import { create } from 'zustand'
import type { AgentStep, SelectedStepDetail } from '../types/agent'

interface AgentState {
  isRunning: boolean
  currentSteps: AgentStep[]
  streamingContent: string
  selectedStep: SelectedStepDetail | null
  workspaceRefreshTick: number
  artifactsOpen: boolean
  setRunning: (v: boolean) => void
  addStep: (step: AgentStep) => void
  appendToken: (token: string) => void
  clearSteps: () => void
  setSelectedStep: (step: SelectedStepDetail | null) => void
  triggerWorkspaceRefresh: () => void
  toggleArtifacts: (open?: boolean) => void
}

export const useAgentStore = create<AgentState>((set) => ({
  isRunning: false,
  currentSteps: [],
  streamingContent: '',
  selectedStep: null,
  workspaceRefreshTick: 0,
  artifactsOpen: false,
  setRunning: (isRunning) => set({ isRunning }),
  addStep: (step) => set((s) => ({ currentSteps: [...s.currentSteps, step] })),
  appendToken: (token) => set((s) => ({ streamingContent: s.streamingContent + token })),
  clearSteps: () => set({ currentSteps: [], streamingContent: '' }),
  setSelectedStep: (selectedStep) => set({ selectedStep }),
  triggerWorkspaceRefresh: () => set((s) => ({ workspaceRefreshTick: s.workspaceRefreshTick + 1 })),
  toggleArtifacts: (open) => set((s) => ({ artifactsOpen: open ?? !s.artifactsOpen })),
}))

import { create } from 'zustand'
import type { AgentStep, SelectedStepDetail } from '../types/agent'

export type RightPanelKind = 'steps' | 'artifacts' | 'documents' | null

interface AgentState {
  isRunning: boolean
  currentSteps: AgentStep[]
  /** currentSteps 가 어느 대화의 실행인지 (다른 대화로 옮겨 가도 남의 단계가 보이지 않게 한다) */
  stepsOwner: string | null
  streamingContent: string
  selectedStep: SelectedStepDetail | null
  workspaceRefreshTick: number
  /** 채팅 우측에 열려 있는 패널 (한 번에 하나). 단계 상세(selectedStep)가 열려 있으면 그쪽이 우선한다 */
  rightPanel: RightPanelKind
  setRunning: (v: boolean) => void
  addStep: (step: AgentStep) => void
  appendToken: (token: string) => void
  clearSteps: (owner?: string) => void
  setSelectedStep: (step: SelectedStepDetail | null) => void
  triggerWorkspaceRefresh: () => void
  togglePanel: (panel: Exclude<RightPanelKind, null>) => void
  closePanel: () => void
}

export const useAgentStore = create<AgentState>((set) => ({
  isRunning: false,
  currentSteps: [],
  stepsOwner: null,
  streamingContent: '',
  selectedStep: null,
  workspaceRefreshTick: 0,
  rightPanel: null,
  setRunning: (isRunning) => set({ isRunning }),
  addStep: (step) => set((s) => ({ currentSteps: [...s.currentSteps, step] })),
  appendToken: (token) => set((s) => ({ streamingContent: s.streamingContent + token })),
  clearSteps: (owner) => set({ currentSteps: [], streamingContent: '', stepsOwner: owner ?? null }),
  setSelectedStep: (selectedStep) => set({ selectedStep }),
  triggerWorkspaceRefresh: () => set((s) => ({ workspaceRefreshTick: s.workspaceRefreshTick + 1 })),
  togglePanel: (panel) => set((s) => ({ rightPanel: s.rightPanel === panel ? null : panel })),
  closePanel: () => set({ rightPanel: null }),
}))

import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface LayoutState {
  /** 좌측 LNB(대화·메뉴 목록) 접힘 여부. 모든 화면에서 공유하고 새로고침해도 유지한다 */
  sidebarCollapsed: boolean
  toggleSidebar: () => void
}

export const useLayoutStore = create<LayoutState>()(
  persist(
    (set) => ({
      sidebarCollapsed: false,
      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
    }),
    { name: 'layout-storage' },
  ),
)

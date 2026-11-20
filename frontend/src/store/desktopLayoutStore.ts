import { useEffect } from 'react'
import { create } from 'zustand'

/** 데스크톱 앱에서 작업 진행창(우측 패널)이 브라우저의 왼쪽/오른쪽 어디에 있는지 (기본: 왼쪽). 웹 브라우저에서는 쓰지 않는다. */
export type PanelSide = 'left' | 'right'
// 기본 위치를 왼쪽으로 정하면서 키를 바꿔, 이전에 저장된 값(오른쪽)이 남아 기본값을 가리지 않게 한다
const KEY = 'steps-panel-side-v2'

/** 기본은 왼쪽 ([채팅][작업 진행][브라우저]). 사용자가 오른쪽을 고른 경우에만 오른쪽이다. */
const readSide = (): PanelSide => {
  try {
    return localStorage.getItem(KEY) === 'right' ? 'right' : 'left'
  } catch {
    return 'left'
  }
}

/** 데스크톱 앱 안에서 실행 중인지 (브라우저 영역 제어 API 가 있을 때) */
export const isDesktopShell = () => typeof window !== 'undefined' && typeof window.desktop?.browser?.setPanelSide === 'function'

interface DesktopLayoutState {
  side: PanelSide
  /** 앱의 브라우저 영역이 펼쳐져 있는지 */
  browserShown: boolean
  /** 브라우저 영역의 너비(px). 오른쪽 배치일 때 이만큼 자리를 비워 둔다 */
  paneW: number
  setSide: (side: PanelSide) => void
  applyLayout: (s: { shown: boolean; paneW: number }) => void
}

export const useDesktopLayoutStore = create<DesktopLayoutState>((set) => ({
  side: readSide(),
  browserShown: false,
  paneW: 0,
  setSide: (side) => {
    try {
      localStorage.setItem(KEY, side)
    } catch {
      // 저장하지 못해도 이번 실행에서는 동작한다
    }
    set({ side })
    window.desktop?.browser?.setPanelSide?.(side).catch(() => {})
  },
  applyLayout: (s) => set((cur) => (cur.browserShown === s.shown && cur.paneW === s.paneW ? cur : { browserShown: s.shown, paneW: s.paneW })),
}))

/** 앱과 상태를 맞춘다: 저장된 위치를 앱에 알리고, 앱이 알려 주는 브라우저 영역 상태를 받는다. 데스크톱이 아니면 아무 일도 하지 않는다. */
export function useDesktopLayoutSync() {
  useEffect(() => {
    const api = window.desktop?.browser
    if (!api?.setPanelSide || !api.onLayout) return
    const off = api.onLayout((s) => useDesktopLayoutStore.getState().applyLayout(s))
    api.setPanelSide(useDesktopLayoutStore.getState().side).catch(() => {})
    return off
  }, [])
}

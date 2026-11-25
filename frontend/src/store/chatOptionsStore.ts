import { create } from 'zustand'

interface ChatOptionsState {
  /** 이 브라우저 작업을 sandbox·앱 브라우저가 아니라 내 PC 의 Chrome(확장)으로 한다. 기본은 끔이고, 새로고침하면 다시 꺼진다 */
  useLocalChrome: boolean
  setUseLocalChrome: (on: boolean) => void
}

export const useChatOptionsStore = create<ChatOptionsState>((set) => ({
  useLocalChrome: false,
  setUseLocalChrome: (on) => set({ useLocalChrome: on }),
}))

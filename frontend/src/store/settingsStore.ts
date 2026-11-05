import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export const DEFAULT_TIMEZONE = 'Asia/Seoul' // KST

interface SettingsState {
  /** 화면에 표시하는 시간대 (IANA). 서버 시각은 UTC 로 오고 이 시간대로 바꿔 보여 준다. */
  timezone: string
  setTimezone: (timezone: string) => void
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      timezone: DEFAULT_TIMEZONE,
      setTimezone: (timezone) => set({ timezone }),
    }),
    { name: 'app-settings' }
  )
)

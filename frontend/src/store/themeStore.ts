import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type Theme = 'dark' | 'light'

interface ThemeState {
  theme: Theme
  setTheme: (theme: Theme) => void
  toggleTheme: () => void
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set, get) => ({
      theme: 'dark',
      setTheme: (theme) => {
        document.body.setAttribute('data-theme', theme)
        set({ theme })
      },
      toggleTheme: () => {
        const newTheme = get().theme === 'dark' ? 'light' : 'dark'
        document.body.setAttribute('data-theme', newTheme)
        set({ theme: newTheme })
      },
    }),
    {
      name: 'theme-storage',
      onRehydrateStorage: () => (state) => {
        // Apply theme on page load
        if (state) {
          document.body.setAttribute('data-theme', state.theme)
        }
      },
    }
  )
)

// Initialize theme on module load
const initTheme = () => {
  const stored = localStorage.getItem('theme-storage')
  if (stored) {
    try {
      const { state } = JSON.parse(stored)
      document.body.setAttribute('data-theme', state.theme || 'dark')
    } catch {
      document.body.setAttribute('data-theme', 'dark')
    }
  } else {
    document.body.setAttribute('data-theme', 'dark')
  }
}

initTheme()

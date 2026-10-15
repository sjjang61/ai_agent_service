import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: ['class', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        // Accent colors
        accent: {
          primary: 'var(--accent-primary)',
          hover: 'var(--accent-hover)',
          blue: 'var(--accent-blue)',
          green: 'var(--accent-green)',
          yellow: 'var(--accent-yellow)',
          orange: 'var(--accent-orange)',
          red: 'var(--accent-red)',
          purple: 'var(--accent-purple)',
          amber: 'var(--accent-amber)',
          cyan: 'var(--accent-cyan)',
        },
        // Theme-aware colors
        surface: {
          primary: 'var(--bg-primary)',
          secondary: 'var(--bg-secondary)',
          tertiary: 'var(--bg-tertiary)',
          hover: 'var(--bg-hover)',
          active: 'var(--bg-active)',
        },
        content: {
          primary: 'var(--text-primary)',
          secondary: 'var(--text-secondary)',
          tertiary: 'var(--text-tertiary)',
          muted: 'var(--text-muted)',
        },
        border: {
          DEFAULT: 'var(--border-color)',
          light: 'var(--border-light)',
        },
      },
      borderRadius: {
        sm: 'var(--radius-sm)',
        md: 'var(--radius-md)',
        lg: 'var(--radius-lg)',
        xl: 'var(--radius-xl)',
      },
      width: {
        'icon-bar': 'var(--icon-bar-width)',
        'sidebar': 'var(--sidebar-width)',
      },
      boxShadow: {
        sm: 'var(--shadow-sm)',
        md: 'var(--shadow-md)',
      },
    },
  },
  plugins: [],
} satisfies Config

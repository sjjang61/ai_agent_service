import type { Config } from 'tailwindcss'

/**
 * 테마 변수(CSS 변수) 색에 `/40` 같은 투명도 접미사가 동작하도록 color-mix 로 감싼다.
 * 그냥 'var(--x)' 로 두면 Tailwind 가 투명도 클래스(bg-accent-primary/15 등)를 아예 만들지 않아 배경·테두리가 사라진다.
 * 투명도를 쓰지 않으면 <alpha-value> 가 1 로 치환되어 원래 색 그대로다.
 */
const token = (name: string) => `color-mix(in srgb, var(${name}) calc(<alpha-value> * 100%), transparent)`

export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: ['class', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        // Accent colors
        accent: {
          primary: token('--accent-primary'),
          hover: token('--accent-hover'),
          blue: token('--accent-blue'),
          green: token('--accent-green'),
          yellow: token('--accent-yellow'),
          orange: token('--accent-orange'),
          red: token('--accent-red'),
          purple: token('--accent-purple'),
          amber: token('--accent-amber'),
          cyan: token('--accent-cyan'),
        },
        // Theme-aware colors
        surface: {
          primary: token('--bg-primary'),
          secondary: token('--bg-secondary'),
          tertiary: token('--bg-tertiary'),
          hover: token('--bg-hover'),
          active: token('--bg-active'),
        },
        content: {
          primary: token('--text-primary'),
          secondary: token('--text-secondary'),
          tertiary: token('--text-tertiary'),
          muted: token('--text-muted'),
        },
        border: {
          DEFAULT: token('--border-color'),
          light: token('--border-light'),
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

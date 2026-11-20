/**
 * 백엔드 서버 주소 설정.
 *
 * 웹(nginx/Vite 프록시)에서는 같은 출처의 상대 경로(`/api`, `/ws`)를 쓰고,
 * 데스크톱 앱처럼 화면과 서버의 출처가 다를 때만 절대 주소를 쓴다.
 *
 * 우선순위: ① 데스크톱 셸이 주입한 값(window.__AGENT_SERVER_URL__)
 *          ② 사용자가 저장한 값(localStorage 'agent_server_url')
 *          ③ 빌드 시 값(VITE_SERVER_URL)
 *          ④ 없음 → 같은 출처(상대 경로)
 */

declare global {
  interface Window {
    __AGENT_SERVER_URL__?: string
  }
}

const STORAGE_KEY = 'agent_server_url'

function normalize(url: string | undefined | null): string {
  return (url ?? '').trim().replace(/\/+$/, '')
}

export function getServerUrl(): string {
  if (typeof window !== 'undefined' && window.__AGENT_SERVER_URL__) {
    return normalize(window.__AGENT_SERVER_URL__)
  }
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) return normalize(saved)
  } catch { /* 저장소를 쓸 수 없는 환경 */ }
  return normalize(import.meta.env.VITE_SERVER_URL as string | undefined)
}

export function setServerUrl(url: string) {
  try {
    const v = normalize(url)
    if (v) localStorage.setItem(STORAGE_KEY, v)
    else localStorage.removeItem(STORAGE_KEY)
  } catch { /* 무시 */ }
}

/** `/api/...` 같은 경로를 서버 주소 기준 URL 로 만든다(서버 주소가 없으면 상대 경로 그대로). */
export function apiUrl(path: string): string {
  return `${getServerUrl()}${path}`
}

/** API 기본 경로 (axios baseURL) */
export function apiBase(): string {
  return apiUrl('/api')
}

/** WebSocket URL. 서버 주소가 없으면 현재 출처를 쓰되, Vite 개발 서버(5173)에서는 백엔드(8500)에 직접 연결한다. */
export function wsUrl(path: string): string {
  const server = getServerUrl()
  if (server) return `${server.replace(/^http/, 'ws')}${path}`
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
  // 개발 서버(vite)의 WebSocket 프록시가 불안정해 개발 중에는 백엔드(8500)에 직접 연결한다
  const host = location.port === '5173' ? `${location.hostname}:8500` : location.host
  return `${proto}//${host}${path}`
}

/** 데스크톱 앱(Electron preload)이 노출하는 API. 웹 브라우저에서는 없다. */
export interface DesktopChromeCheck {
  site?: string
  profile?: string
  count?: number
  error?: 'unsupported' | 'no-site' | 'chrome-not-found'
}
export interface DesktopChromeImport {
  site?: string
  imported?: number
  skipped?: number
  failed?: number
  error?: 'unsupported' | 'no-site' | 'no-cookies' | 'cancelled' | 'keychain-denied'
}
declare global {
  interface Window {
    desktop?: {
      browser?: {
        /** 앱 브라우저를 보이게 하고 화면을 나누는 비율(0.2~0.8)을 정한다 */
        setSplit?: (ratio: number) => Promise<void>
        /** 앱 브라우저에서 http(s) 주소를 연다 */
        navigate?: (url: string) => Promise<void>
        /** 데스크톱 앱 브라우저의 '스크린샷 첨부' 버튼: 현재 화면 PNG(base64). 해제 함수를 돌려준다 */
        onScreenshot?: (cb: (shot: { name: string; data: string }) => void) => () => void
        /** 작업 진행창 위치: right 면 [채팅][브라우저][작업 진행]. 웹 UI 가 브라우저 자리를 비워 두고 그 위치를 알려 준다 */
        setPanelSide?: (side: 'left' | 'right') => Promise<void>
        setSlot?: (rect: { x: number; width: number }) => void
        /** 브라우저 영역 상태(보이는지, 너비)가 바뀔 때마다 받는다. 해제 함수를 돌려준다 */
        onLayout?: (cb: (s: { shown: boolean; paneW: number; side: 'left' | 'right' }) => void) => () => void
      }
      chrome?: {
        check: () => Promise<DesktopChromeCheck>
        importCookies: () => Promise<DesktopChromeImport>
      }
    }
  }
}

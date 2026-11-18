import { useCallback, useRef } from 'react'

const KEY = 'chat-input-history'
const MAX = 50

function load(): string[] {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) || '[]')
    return Array.isArray(v) ? v.filter((s) => typeof s === 'string').slice(-MAX) : []
  } catch {
    return []
  }
}

/** 채팅 입력 기록(스택). 보낸 입력을 쌓고, ↑/↓ 로 이전·다음 입력을 불러온다 (셸 히스토리와 같다). 브라우저에 저장돼 새로고침 후에도 남는다. */
export function useInputHistory() {
  const items = useRef<string[]>(load())
  const cursor = useRef(-1)  // -1: 기록을 보고 있지 않음(작성 중), 0 이상: items 의 위치
  const draft = useRef('')   // 기록으로 이동하기 전에 쓰던 글 (↓ 로 끝까지 내려오면 복원)

  const push = useCallback((text: string) => {
    const t = text.trim()
    cursor.current = -1
    draft.current = ''
    if (!t || items.current[items.current.length - 1] === t) return
    items.current = [...items.current, t].slice(-MAX)
    try { localStorage.setItem(KEY, JSON.stringify(items.current)) } catch { /* 저장 불가는 무시 */ }
  }, [])

  /** 한 칸 이전 입력. 더 없으면 null */
  const prev = useCallback((current: string): string | null => {
    if (items.current.length === 0) return null
    if (cursor.current === -1) {
      draft.current = current
      cursor.current = items.current.length - 1
    } else if (cursor.current > 0) {
      cursor.current -= 1
    } else {
      return null
    }
    return items.current[cursor.current]
  }, [])

  /** 한 칸 다음 입력. 맨 끝을 지나면 쓰던 글을 돌려준다. 기록을 보고 있지 않으면 null */
  const next = useCallback((): string | null => {
    if (cursor.current === -1) return null
    if (cursor.current < items.current.length - 1) {
      cursor.current += 1
      return items.current[cursor.current]
    }
    cursor.current = -1
    return draft.current
  }, [])

  /** 직접 고쳐 쓰기 시작하면 기록 탐색을 끝낸다 */
  const reset = useCallback(() => { cursor.current = -1 }, [])
  const browsing = useCallback(() => cursor.current !== -1, [])

  return { push, prev, next, reset, browsing }
}

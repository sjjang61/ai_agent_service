import { useCallback, useEffect, useLayoutEffect, useRef } from 'react'

/**
 * 데스크톱 앱에서 작업 진행창을 브라우저 오른쪽에 둘 때, 브라우저가 들어갈 자리를 비워 두는 빈 칸.
 * 앱의 브라우저 화면은 이 칸 위에 겹쳐서 그려지므로, 칸의 위치(창 기준 x, 너비)가 바뀔 때마다 앱에 알려 준다.
 */
export default function BrowserSlot({ width }: { width: number }) {
  const ref = useRef<HTMLDivElement>(null)
  const last = useRef('')
  const report = useCallback(() => {
    const el = ref.current
    if (!el) return
    const r = el.getBoundingClientRect()
    const key = `${Math.round(r.x)}:${Math.round(r.width)}`
    if (key === last.current) return
    last.current = key
    window.desktop?.browser?.setSlot?.({ x: r.x, width: r.width })
  }, [])

  useLayoutEffect(report) // 렌더마다 확인한다: 다른 패널이 열리고 닫히면 위치가 바뀐다
  useEffect(() => {
    // 창 크기, 앞 칸(채팅 영역)의 크기(사이드바 접힘 등)가 바뀌어도 위치가 달라진다
    const ro = new ResizeObserver(report)
    ro.observe(document.documentElement)
    if (ref.current?.previousElementSibling) ro.observe(ref.current.previousElementSibling)
    window.addEventListener('resize', report)
    return () => {
      ro.disconnect()
      window.removeEventListener('resize', report)
    }
  }, [report])

  return <div ref={ref} aria-hidden data-browser-slot className="flex-shrink-0" style={{ width }} />
}

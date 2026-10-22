import { useEffect, useRef, useState } from 'react'
import { ANIMATION_CONFIG } from '../config/animation'

interface UseTypingAnimationOptions {
  /**
   * 문자당 타이핑 속도 (밀리초)
   * 기본값: 20ms (자연스러운 속도)
   */
  speed?: number
  /**
   * 즉시 표시할지 여부
   * true면 애니메이션 없이 즉시 표시
   */
  instant?: boolean
}

/**
 * 자연스러운 타이핑 애니메이션 효과를 제공하는 훅
 *
 * @param targetText - 최종적으로 표시할 전체 텍스트
 * @param options - 타이핑 속도 등 옵션
 * @returns 현재 표시 중인 텍스트
 */
export function useTypingAnimation(
  targetText: string,
  options: UseTypingAnimationOptions = {}
): string {
  const { speed = 30, instant = false } = options
  const [displayedText, setDisplayedText] = useState('')
  const targetRef = useRef(targetText)
  const indexRef = useRef(0)
  const timerRef = useRef<number | undefined>(undefined)

  useEffect(() => {
    targetRef.current = targetText

    // 즉시 표시 모드
    if (instant) {
      setDisplayedText(targetText)
      indexRef.current = targetText.length
      return
    }

    // 타겟 텍스트가 줄어든 경우 (새 메시지)
    if (targetText.length < displayedText.length) {
      setDisplayedText('')
      indexRef.current = 0
    }

    // 이미 모두 표시된 경우
    if (indexRef.current >= targetText.length) {
      return
    }

    // 타이핑 애니메이션
    const typeNextChar = () => {
      const currentTarget = targetRef.current
      const currentIndex = indexRef.current

      if (currentIndex < currentTarget.length) {
        // 한 번에 여러 문자를 추가할 수 있도록 (버퍼에 쌓인 경우)
        const batchSize = Math.min(
          ANIMATION_CONFIG.TYPING_BATCH_SIZE,
          currentTarget.length - currentIndex
        )
        const nextText = currentTarget.slice(0, currentIndex + batchSize)

        setDisplayedText(nextText)
        indexRef.current += batchSize

        // 다음 문자 타이핑 예약
        timerRef.current = window.setTimeout(typeNextChar, speed)
      }
    }

    // 타이핑 시작
    timerRef.current = window.setTimeout(typeNextChar, speed)

    // 클린업
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current)
      }
    }
  }, [targetText, speed, instant, displayedText.length])

  return displayedText
}

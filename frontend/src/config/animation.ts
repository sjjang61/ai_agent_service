/**
 * 애니메이션 관련 설정
 */

export const ANIMATION_CONFIG = {
  /**
   * 타이핑 애니메이션 속도 (밀리초 per character)
   *
   * 추천 값:
   * - 10ms: 매우 빠름 (개발/디버깅용)
   * - 20ms: 자연스러움 (기본값) ⭐
   * - 30ms: 천천히
   * - 50ms: 매우 천천히
   */
  TYPING_SPEED: 20,

  /**
   * 한 번에 타이핑할 문자 수
   * 높을수록 부드럽게 보이지만 CPU 사용량 증가
   */
  TYPING_BATCH_SIZE: 3,

  /**
   * 코드 블록 등 특수 구문을 더 빠르게 표시할지 여부
   */
  FAST_SPECIAL_SYNTAX: true,
} as const

/**
 * 개발 모드에서 애니메이션 속도를 변경하려면 브라우저 콘솔에서:
 *
 * ```js
 * localStorage.setItem('typingSpeed', '10') // 10ms로 설정
 * ```
 *
 * 그 후 새로고침하면 적용됩니다.
 */
export function getTypingSpeed(): number {
  if (typeof window === 'undefined') return ANIMATION_CONFIG.TYPING_SPEED

  const customSpeed = localStorage.getItem('typingSpeed')
  if (customSpeed) {
    const speed = parseInt(customSpeed, 10)
    if (!isNaN(speed) && speed > 0 && speed <= 1000) {
      return speed
    }
  }

  return ANIMATION_CONFIG.TYPING_SPEED
}

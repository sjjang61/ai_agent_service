import { useState, useEffect, useCallback, useRef } from 'react'

interface SelectionPosition {
  top: number
  left: number
  width: number
}

export function useTextSelection() {
  const [selectedText, setSelectedText] = useState('')
  const [position, setPosition] = useState<SelectionPosition | null>(null)
  const timeoutRef = useRef<NodeJS.Timeout>()

  const handleSelection = useCallback(() => {
    // Clear any pending timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
    }

    // Small delay to ensure selection is finalized
    timeoutRef.current = setTimeout(() => {
      const selection = window.getSelection()
      const text = selection?.toString().trim() || ''

      if (text.length > 0) {
        const range = selection?.getRangeAt(0)
        const rect = range?.getBoundingClientRect()

        if (rect) {
          setSelectedText(text)
          setPosition({
            top: rect.top + window.scrollY - 40, // 40px above selection
            left: rect.left + window.scrollX + rect.width / 2,
            width: rect.width,
          })
        }
      } else {
        setSelectedText('')
        setPosition(null)
      }
    }, 100)
  }, [])

  const clearSelection = useCallback(() => {
    setSelectedText('')
    setPosition(null)
    window.getSelection()?.removeAllRanges()
  }, [])

  useEffect(() => {
    document.addEventListener('mouseup', handleSelection)
    document.addEventListener('selectionchange', handleSelection)

    return () => {
      document.removeEventListener('mouseup', handleSelection)
      document.removeEventListener('selectionchange', handleSelection)
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }
    }
  }, [handleSelection])

  return { selectedText, position, clearSelection }
}

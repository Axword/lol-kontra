'use client'
import { useEffect, useRef, type RefObject } from 'react'

const dialogs: HTMLElement[] = []
let originalOverflow = ''

/** Share scroll locking and keyboard focus between every modal in the app. */
export function useDialog<T extends HTMLElement>(open: boolean, onClose: () => void, returnFocusRef?: RefObject<HTMLElement>) {
  const ref = useRef<T>(null)
  const closeRef = useRef(onClose)
  closeRef.current = onClose

  useEffect(() => {
    const dialog = ref.current
    if (!open || !dialog) return
    const previousFocus = document.activeElement as HTMLElement | null
    const returnTarget = returnFocusRef ? returnFocusRef.current : previousFocus
    if (dialogs.length === 0) {
      originalOverflow = document.body.style.overflow
      document.body.style.overflow = 'hidden'
    }
    dialogs.push(dialog)
    const focusable = () => Array.from(dialog.querySelectorAll<HTMLElement>(
      'button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex="0"]'
    )).filter((element) => element.tabIndex >= 0 && !element.closest('[inert]') && !element.hidden)

    const initial = dialog.querySelector<HTMLElement>('[data-dialog-focus]') || focusable()[0] || dialog
    initial.focus()

    const onKey = (event: KeyboardEvent) => {
      if (dialogs[dialogs.length - 1] !== dialog) return
      if (event.key === 'Escape') {
        event.preventDefault()
        event.stopPropagation()
        closeRef.current()
      }
      if (event.key === 'Tab') {
        const elements = focusable()
        const first = elements[0] || dialog
        const last = elements[elements.length - 1] || dialog
        if (event.shiftKey && (document.activeElement === first || !dialog.contains(document.activeElement))) {
          event.preventDefault()
          last.focus()
        } else if (!event.shiftKey && (document.activeElement === last || !dialog.contains(document.activeElement))) {
          event.preventDefault()
          first.focus()
        }
      }
    }
    const onFocus = (event: FocusEvent) => {
      if (dialogs[dialogs.length - 1] === dialog && !dialog.contains(event.target as Node)) {
        (focusable()[0] || dialog).focus()
      }
    }
    document.addEventListener('keydown', onKey, true)
    document.addEventListener('focusin', onFocus)
    return () => {
      document.removeEventListener('keydown', onKey, true)
      document.removeEventListener('focusin', onFocus)
      const index = dialogs.indexOf(dialog)
      if (index >= 0) dialogs.splice(index, 1)
      if (dialogs.length === 0) document.body.style.overflow = originalOverflow
      if (returnTarget?.isConnected && !returnTarget.hasAttribute('disabled')) returnTarget.focus()
    }
  }, [open, returnFocusRef])
  return ref
}

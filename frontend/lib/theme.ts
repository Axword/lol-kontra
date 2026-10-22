'use client'
import { useSyncExternalStore } from 'react'

export type Theme = 'light' | 'dark'
const key = 'axword-theme'
const event = 'axword-theme-change'

function preferredTheme(): Theme {
  try {
    const saved = localStorage.getItem(key)
    if (saved === 'dark' || saved === 'light') return saved
  } catch { /* Use system preference when storage is blocked. */ }
  return typeof matchMedia === 'function' && matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}
function snapshot(): Theme { return document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light' }
function subscribe(notify: () => void) {
  const sync = () => { document.documentElement.dataset.theme = preferredTheme(); notify() }
  const storage = (e: StorageEvent) => { if (e.key === key || e.key === null) sync() }
  const media = window.matchMedia?.('(prefers-color-scheme: dark)')
  window.addEventListener(event, notify)
  window.addEventListener('storage', storage)
  media?.addEventListener('change', sync)
  sync()
  return () => { window.removeEventListener(event, notify); window.removeEventListener('storage', storage); media?.removeEventListener('change', sync) }
}
export function setTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme
  try { localStorage.setItem(key, theme) } catch { /* A session-only choice is still usable. */ }
  window.dispatchEvent(new Event(event))
}
export function useTheme() { return useSyncExternalStore(subscribe, snapshot, () => 'light' as Theme) }
